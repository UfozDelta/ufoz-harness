"""The pi executor: today's run_pi/quota_ok, unchanged, behind the Executor interface."""
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from ..procs import ANSI, EXIT_RATE_LIMIT, EXIT_TIMEOUT, stop_process_tree, zero_usage
from .base import ExecResult, Executor

RATE_LIMIT = b"Rate limit exceeded"
RATE_LIMIT_GIVEUP = 120
DEFAULT_MODEL = "opencode/space-bunny-free"


def _model(model=None):
    return model or os.environ.get("HARNESS_MODEL", DEFAULT_MODEL)


def _pi_launcher():
    launcher = os.environ.get("HARNESS_PI") or str(Path.home() / ".pi" / "agent" / "bin" / "pi-launcher.js")
    if not Path(launcher).exists():
        sys.exit(f"pi not found: {launcher}")
    return launcher


def run_pi(brief, log, timeout, feedback=None, session=None, raw_prompt=None, rules=None, model=None,
           env=None):
    """Returns (exit code, token usage, session id). With `session`, the task is sent into
    that existing pi session (warm context) instead of a fresh one."""
    launcher = _pi_launcher()
    prompt = f"Do the task described in {brief}"
    if session:
        prompt = (f"Next task in the same plan: {brief}. The earlier tasks are done and verified; same rules, "
                  f"touch only this task's FILES. Finish with DONE: or BLOCKED:")
    if feedback:  # a path, not the text: multi-line args break through Windows .cmd shims
        prompt += f". Your previous attempt failed its acceptance check; read {feedback} first, then fix the work"
    prompt = raw_prompt or prompt
    session = session or uuid.uuid4().hex
    usage = zero_usage()
    env = dict(os.environ, PWD=os.getcwd(), **(env or {}))
    cmd = ["node", launcher, "-p", "--mode", "json", "--no-extensions", "--no-skills",
           "--no-prompt-templates", "-e", ".pi/extensions/deny-list.ts",
           "--append-system-prompt", rules or ".pi/executor.md",
           "--model", _model(model),
           "--thinking", os.environ.get("HARNESS_VARIANT", "medium"),
           "--session-id", session, prompt]
    with open(log, "wb") as f:
        p = subprocess.Popen(cmd, cwd=os.getcwd(), env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        seen = {"rl_since": None}

        def pump():
            for line in p.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if isinstance(event, dict):
                    seen["rl_since"] = None
                elif RATE_LIMIT in line and seen["rl_since"] is None:
                    seen["rl_since"] = time.time()
                if not isinstance(event, dict):
                    clean = ANSI.sub(b"", line)
                    if clean.strip():
                        f.write(clean)
                    f.flush()
                    continue
                if event.get("type") == "message_end" and event.get("message", {}).get("role") == "assistant":
                    message = event["message"]
                    u = message.get("usage", {})
                    usage["input"] += u.get("input", 0) or 0
                    usage["output"] += u.get("output", 0) or 0
                    usage["reasoning"] += u.get("reasoning", 0) or 0
                    usage["cache_read"] += u.get("cacheRead", 0) or 0
                    usage["cost"] += (u.get("cost") or {}).get("total", 0) or 0
                    for part in message.get("content", []):
                        if part.get("type") == "text" and part.get("text"):
                            f.write((part["text"] + "\n").encode("utf-8"))
                        elif part.get("type") == "toolCall":
                            args_text = json.dumps(part.get("arguments", {}))[:200]
                            f.write(f"[toolCall {part.get('name')}] {args_text}\n".encode("utf-8"))
                elif event.get("type") == "tool_execution_end" and event.get("isError"):
                    result = event.get("result", {})
                    if isinstance(result, dict):
                        text = result.get("text", "") or "".join(
                            part.get("text", "") for part in result.get("content", [])
                            if isinstance(part, dict) and part.get("type") == "text")
                    else:
                        text = str(result)
                    f.write(f"[tool error] {text[:200]}\n".encode("utf-8"))
                f.flush()

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        deadline = time.time() + timeout
        while True:
            try:
                code = p.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                limited = seen["rl_since"] and time.time() - seen["rl_since"] > RATE_LIMIT_GIVEUP
                if limited or time.time() > deadline:
                    stop_process_tree(p)
                    code = EXIT_RATE_LIMIT if limited else EXIT_TIMEOUT
                    break
        t.join(5)
        return code, usage, session


def quota_ok(timeout=90, model=None, env=None):
    """One tiny pi executor call: True if the model answers. Output goes to a temp file and the whole
    process tree is killed on timeout (capture_output + timeout hangs on Windows: the child's
    descendants keep the pipe open after the parent is killed)."""
    import tempfile
    launcher = _pi_launcher()
    cmd = ["node", launcher, "-p", "--mode", "json", "--no-extensions", "--no-skills",
           "--no-prompt-templates", "-e", ".pi/extensions/deny-list.ts",
           "--append-system-prompt", ".pi/executor.md",
           "--model", _model(model),
           "--thinking", os.environ.get("HARNESS_VARIANT", "medium"),
           "--session-id", uuid.uuid4().hex, "Health check, not a task. Reply OK."]
    env = dict(os.environ, PWD=os.getcwd(), **(env or {}))
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(cmd, cwd=os.getcwd(), env=env, stdin=subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.STDOUT)
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_process_tree(p)
            return False  # stuck retrying: still limited
        out.seek(0)
        data = out.read()
    def has_assistant_text():
        for line in data.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            message = event.get("message", {})
            if (event.get("type") == "message_end" and message.get("role") == "assistant"
                    and any(p.get("type") == "text" and p.get("text") for p in message.get("content", []))):
                return True
        return False
    return RATE_LIMIT not in data and has_assistant_text()


class PiExecutor(Executor):
    name = "pi"

    def __init__(self, model=None):
        self.model = _model(model)
        self.env = None

    def run(self, brief, log, timeout, feedback=None, session=None, raw_prompt=None, rules=None) -> ExecResult:
        code, usage, sid = run_pi(brief, log, timeout, feedback, session, raw_prompt, rules, self.model,
                                  env=self.env)
        return ExecResult(code=code, usage=usage, session=sid)

    def probe(self) -> bool:
        return quota_ok(model=self.model, env=self.env)
