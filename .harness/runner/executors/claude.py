"""The claude executor: `claude -p` per task, behind the Executor interface.

Same contract as the pi executor, but Claude writes the code. For fair A/B benchmarks:
same plan, same guards, only the executor differs. `.pi/executor.md` plus AGENTS.md are
appended as the system prompt so it acts as executor, not as the CLAUDE.md orchestrator.
Sessions are warm: the first task gets a fresh `--session-id`, every later task in the same
plan `--resume`s it.
"""
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from ..procs import ANSI, EXIT_RATE_LIMIT, EXIT_TIMEOUT, TOKEN_KEYS, stop_process_tree
from .base import ExecResult, Executor

HEALTH_PROMPT = "Health check, not a task. Reply OK."
AGENT = "claude-executor"
ALLOWED_TOOLS = "Read,Edit,Write,Glob,Grep,Bash"
USAGE_LIMIT = ("usage limit", "rate limit")
# $ per million tokens (input, output, cache_read): the claude CLI's total_cost_usd misprices these
# keyed by a substring of the model name: arms pass the alias ("haiku") as often as the full id
RATES = {"haiku": (0.10, 0.50, 0.01)}


def _deny_bash():
    """The bash commands .pi/deny.json bans, as claude --disallowedTools patterns."""
    deny = json.loads(Path(".pi/deny.json").read_text(encoding="utf-8")).get("bash", [])
    # `--land` is the main session's command: an executor never lands its own work
    return ",".join([*(f"Bash({cmd}:*)" for cmd in deny), "Bash(*run_plan.py*--land*)"])


def _executor_prompt(rules=None):
    """The rules the executor must follow: `rules` alone when given, else .pi/executor.md
    plus AGENTS.md, both as text."""
    if rules:
        return Path(rules).read_text(encoding="utf-8")
    text = Path(".pi/executor.md").read_text(encoding="utf-8")
    agents = Path("AGENTS.md")
    return f"{text}\n\n{agents.read_text(encoding='utf-8')}" if agents.exists() else text


def use_agent(model):
    """Agent mode: claude runs the `.claude/agents/claude-executor.md` definition (tools,
    hooks, system prompt) instead of ad-hoc `claude -p` flags. Haiku always; any other model
    keeps the plain command. HARNESS_CLAUDE_AGENT=0 opts out, =1 forces it on."""
    flag = os.environ.get("HARNESS_CLAUDE_AGENT", "").strip()
    if flag == "0":
        return False
    if flag == "1":
        return True
    return "haiku" in model


def rated_cost(model, usage):
    """Dollar cost from the token counts at RATES (output already includes thinking), or
    None when the model has no entry and the CLI's own cost stands."""
    rate = next((r for name, r in RATES.items() if name in model), None)
    if rate is None:
        return None
    price_in, price_out, price_cache = rate
    return (usage["input"] * price_in + usage["output"] * price_out + usage["cache_read"] * price_cache) / 1e6


def _claude_cmd(prompt, model, session, resume, rules=None):
    """The headless claude invocation: streaming JSON out, edits accepted, state kept in a
    session (fresh id, or resumed) so later tasks in a plan keep their context."""
    return ["claude", "-p", prompt,
            "--model", model,
            "--effort", os.environ.get("HARNESS_VARIANT", "medium"),
            "--output-format", "stream-json", "--verbose",
            "--setting-sources", "project,local", "--strict-mcp-config",
            "--permission-mode", "acceptEdits",
            # the agent file defines tools and rules: no --allowedTools/--append-system-prompt
            # agent mode: Bash is allowed like plain mode (acceptEdits alone prompts for every
            # python/pytest/&& command and the agent burns turns on the denials). --disallowedTools
            # below still wins over this allow, and the git guard hook still runs.
            *(["--agent", AGENT, "--allowedTools", "Bash"] if use_agent(model) else ["--allowedTools", ALLOWED_TOOLS]),
            "--disallowedTools", _deny_bash(),
            *([] if use_agent(model) else ["--append-system-prompt", _executor_prompt(rules)]),
            *(["--resume", session] if resume else ["--session-id", session])]


def rotate_limit():
    """Context size above which a session is rotated: HARNESS_CLAUDE_ROTATE tokens
    (default 100000, 0 disables rotation)."""
    try:
        return int(os.environ.get("HARNESS_CLAUDE_ROTATE", 100000))
    except ValueError:
        return 100000


def rotated(ctx, limit):
    """True when the session's context (tokens) is past the rotation limit. 0 disables."""
    return 0 < limit < ctx


def _handle_event(event, f, usage, state):
    """Turn one stream-json event into log lines and usage; record error/limit in `state`."""
    kind = event.get("type")
    if kind == "assistant":
        u = event.get("message", {}).get("usage", {}) or {}
        # context the session now carries: input + what it just wrote to + read from cache
        state["ctx"] = ((u.get("input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0)
                        + (u.get("cache_read_input_tokens", 0) or 0))
        # one line per turn so a kept log shows how context grows (turns = [usage] lines)
        f.write(f"[usage] ctx={state['ctx']} out={u.get('output_tokens', 0) or 0}\n".encode("utf-8"))
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text"):
                f.write((block["text"] + "\n").encode("utf-8"))
            elif block.get("type") == "tool_use":
                args_text = json.dumps(block.get("input", {}))[:200]
                f.write(f"[toolCall {block.get('name')}] {args_text}\n".encode("utf-8"))
    elif kind == "user":
        for block in event.get("message", {}).get("content", []):
            result = block.get("content") if block.get("type") == "tool_result" else None
            if block.get("type") == "tool_result" and block.get("is_error") and result:
                text = result if isinstance(result, str) else json.dumps(result)
                f.write(f"[tool error] {text[:200]}\n".encode("utf-8"))
    elif kind == "rate_limit_event":
        status = str(event.get("rate_limit_info", {}).get("status", ""))
        if not status.startswith("allowed"):
            state["limited"] = True
    elif kind == "result":
        u = event.get("usage", {}) or {}
        usage["input"] += u.get("input_tokens", 0) or 0
        usage["input"] += u.get("cache_creation_input_tokens", 0) or 0
        usage["output"] += u.get("output_tokens", 0) or 0
        usage["reasoning"] += (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0
        usage["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        usage["cost"] += event.get("total_cost_usd", 0) or 0
        state["error"] = bool(event.get("is_error"))
        if state["error"] and any(text in str(event.get("result", "")).lower() for text in USAGE_LIMIT):
            state["limited"] = True


def run_claude_exec(brief, log, timeout, feedback=None, session=None, model="sonnet", rules=None):
    """Same contract as run_pi, but Claude writes the code (`claude -p`). Returns
    (exit code, token usage, session id). With `session`, the task is sent into that
    existing claude session (warm context) instead of a fresh one."""
    prompt = f"Do the task described in {brief}"
    if session:
        prompt = (f"Next task in the same plan: {brief}. The earlier tasks are done and verified; same rules, "
                  f"touch only this task's FILES. Finish with DONE: or BLOCKED:")
    if feedback:  # a path, not the text: multi-line args break through Windows .cmd shims
        prompt += f". Your previous attempt failed its acceptance check; read {feedback} first, then fix the work"
    resume = bool(session)
    session = session or str(uuid.uuid4())
    if use_agent(model):  # the agent file asks for the worktree's absolute path
        prompt += (f" Worktree (absolute): {os.getcwd()}. Do ONLY this one task, then stop: do not start later "
                   f"tasks or write SUMMARY.md unless this task says so.")
    usage = {**dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}
    cmd = _claude_cmd(prompt, model, session, resume, rules)
    with open(log, "wb") as f:
        p = subprocess.Popen(cmd, cwd=os.getcwd(), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        state = {"limited": False, "error": False, "ctx": 0}

        def pump():
            for line in p.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if not isinstance(event, dict):
                    clean = ANSI.sub(b"", line)
                    if clean.strip():
                        f.write(clean)
                    f.flush()
                    continue
                _handle_event(event, f, usage, state)
                f.flush()

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        deadline = time.time() + timeout
        while True:
            try:
                code = p.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if time.time() > deadline:
                    stop_process_tree(p)
                    code = EXIT_TIMEOUT
                    break
        t.join(5)
    rated = rated_cost(model, usage)
    if rated is not None:
        usage["cost"] = rated
    if state["limited"]:
        stop_process_tree(p)
        return EXIT_RATE_LIMIT, usage, session
    # past the context limit: return "" (not None) so the runner starts fresh next task
    session = "" if rotated(state["ctx"], rotate_limit()) else session
    return (1 if state["error"] else code), usage, session


def quota_ok(timeout=90, model="haiku"):
    """One tiny claude call on a fresh session: True if the model answers. Output goes to a
    temp file and the whole process tree is killed on timeout (capture_output + timeout hangs
    on Windows: the child's descendants keep the pipe open after the parent is killed)."""
    cmd = ["claude", "-p", HEALTH_PROMPT, "--model", model,
           "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project,local", "--strict-mcp-config"]
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(cmd, cwd=os.getcwd(), stdin=subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.STDOUT)
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_process_tree(p)
            return False  # stuck retrying: still limited
        out.seek(0)
        data = out.read()
    answered, limited = False, False
    for line in data.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result" and not event.get("is_error"):
            answered = True
        elif event.get("type") == "rate_limit_event":
            status = str(event.get("rate_limit_info", {}).get("status", ""))
            limited = limited or not status.startswith("allowed")
    return answered and not limited


class ClaudeExecutor(Executor):
    name = "claude"

    def __init__(self, model="sonnet"):
        self.model = model

    def run(self, brief, log, timeout, feedback=None, session=None, rules=None) -> ExecResult:
        code, usage, sid = run_claude_exec(brief, log, timeout, feedback, session, self.model, rules)
        return ExecResult(code=code, usage=usage, session=sid)

    def probe(self) -> bool:
        return quota_ok(model=self.model)
