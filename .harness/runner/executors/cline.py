"""The cline executor: one headless `cline --json` run per task, behind the Executor interface.

Two differences from the pi and claude executors shape this file:

- **No warm session.** `cline --id <session-id>` (resume) is rejected in headless `--json`
  mode by the CLI itself -- every input channel returns `JSON output mode requires a prompt
  argument or piped stdin` (cline/cline#13239, open). So `ExecResult.session` is always None
  and every task starts fresh, which is exactly what `--fresh` does for pi.
- **No appended system prompt.** `-s/--system` *replaces* Cline's own system prompt, so the
  executor rules travel in `AGENTS.md` (Cline reads it as workspace rules) and a `rules=`
  path -- what the planner role passes -- is inlined into the prompt instead.

The stream is NDJSON: `hook_event`, `agent_event`, `error` and a final `run_result`.
`agent_event.usage` carries per-iteration *deltas* next to the running `total*` fields, so the
deltas are summed and `run_result.aggregateUsage` has the last word.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from ..procs import ANSI, EXIT_RATE_LIMIT, EXIT_TIMEOUT, stop_process_tree, zero_usage
from .base import ExecResult, Executor

DEFAULT_MODEL = "cline-free/deepseek-v4.1-flash"
# The free cline models share a daily quota, so the documented default is regularly capped
# ("Daily free limit reached", HTTP 429) and that used to kill a whole plan on its first call.
# Probe these in order and use the first that answers. When every candidate is capped the run
# loop still waits the quota out on its own (Executor.wait_for_quota).
FALLBACK_MODELS = ("stealth/space-bunny-alpha", "stealth/pixel-canary")
HEALTH_PROMPT = "Health check, not a task. Reply OK."
RATE_LIMIT_TEXT = "rate limit"
THINKING = ("none", "low", "medium", "high", "xhigh")
# Cline's own -t should fire first so its log stays complete; the runner's deadline (and
# taskkill) is the backstop that reports EXIT_TIMEOUT.
TIMEOUT_GRACE = 30


def _model(model=None):
    return model or os.environ.get("HARNESS_MODEL", DEFAULT_MODEL)


def _resolve_model(model=None):
    """The first candidate that answers right now, so a capped default does not end the run.

    An explicit model (--executor-model or HARNESS_MODEL) is honoured as given: the operator
    chose it, so it is never silently swapped for a different one.
    """
    explicit = model or os.environ.get("HARNESS_MODEL")
    if explicit:
        return explicit
    for candidate in (DEFAULT_MODEL, *FALLBACK_MODELS):
        if quota_ok(model=candidate):
            if candidate != DEFAULT_MODEL:
                print(f"[cline] {DEFAULT_MODEL} is capped; using {candidate}")
            return candidate
    return DEFAULT_MODEL  # all capped: the run loop waits the quota out


def _thinking():
    """Cline's effort enum is none|low|medium|high|xhigh, not pi/opencode's --thinking set."""
    variant = os.environ.get("HARNESS_VARIANT", "medium").lower()
    return variant if variant in THINKING else "medium"


def _platform_tag():
    plat = {"win32": "windows", "darwin": "darwin", "linux": "linux"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    return plat, arch


def _cline_binary():
    """The cline executable: HARNESS_CLINE, else PATH. The npm shim is a .cmd wrapper that
    re-parses the prompt through cmd.exe quoting rules, so the compiled binary next to it wins."""
    override = os.environ.get("HARNESS_CLINE")
    found = override or shutil.which("cline")
    shim = Path(found) if found else None
    if shim is None or not shim.exists():
        sys.exit(f"cline not found: {found or 'not on PATH'} (npm i -g cline, or set HARNESS_CLINE)")
    plat, arch = _platform_tag()
    exe = "cline.exe" if plat == "windows" else "cline"
    package = shim.parent / "node_modules" / "cline"
    for candidate in (package / "bin" / ".cline",
                      package / "node_modules" / "@cline" / f"cli-{plat}-{arch}" / "bin" / exe,
                      shim.parent / "node_modules" / "@cline" / f"cli-{plat}-{arch}" / "bin" / exe):
        if candidate.exists():
            return str(candidate)
    return str(shim)


def _deny_permissions():
    """`CLINE_COMMAND_PERMISSIONS`: the git commands .pi/deny.json bans, as deny globs.
    `allowRedirects` is deliberately left at Cline's own default (false)."""
    deny = json.loads(Path(".pi/deny.json").read_text(encoding="utf-8")).get("bash", [])
    return json.dumps({"deny": [f"{cmd}*" for cmd in deny]})


CLINE_SETTINGS = Path.home() / ".cline" / "data" / "settings" / "global-settings.json"


def _settings_path(data_dir=None):
    return Path(data_dir) / "settings" / "global-settings.json" if data_dir else CLINE_SETTINGS


def _force_act_mode(data_dir=None):
    """Cline's plan/act mode is *global persisted state* (`planActMode` in
    global-settings.json) and the agent itself can flip it. A run that starts in plan mode
    cannot write a single file -- measured: the same prompt writes the file under "act" and
    only prints a plan under "plan". So act is forced before every task and the old value is
    put back by stop(). Returns the value to restore, or None when nothing had to change."""
    path = _settings_path(data_dir)
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if settings.get("planActMode") == "act":
        return None
    previous = settings.get("planActMode")
    settings["planActMode"] = "act"
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return previous or None


def _restore_mode(previous, data_dir=None):
    """Best effort: leave the mode the user had before the run."""
    if not previous:
        return
    path = _settings_path(data_dir)
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    settings["planActMode"] = previous
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _prompt(brief, feedback, rules):
    """The one prompt argument. `rules` (the planner role) is inlined: Cline has no
    append-to-system-prompt flag, and -s would replace its whole tool-use prompt."""
    text = f"Do the task described in {brief}"
    if feedback:  # a path, not the text: multi-line args break through Windows .cmd shims
        text += f". Your previous attempt failed its acceptance check; read {feedback} first, then fix the work"
    if rules:
        return f"{Path(rules).read_text(encoding='utf-8')}\n\n{text}"
    return text


def _add_delta(event, usage):
    """One `agent_event.usage`: those fields are per-iteration deltas, so they add up."""
    usage["input"] += event.get("inputTokens", 0) or 0
    usage["output"] += event.get("outputTokens", 0) or 0
    usage["cache_read"] += event.get("cacheReadTokens", 0) or 0
    usage["cost"] += event.get("cost", 0) or 0


def _set_totals(aggregate, usage):
    """`run_result.aggregateUsage` is the run's own total: the last word, never added."""
    if not aggregate:
        return
    for key, field in (("input", "inputTokens"), ("output", "outputTokens"),
                       ("cache_read", "cacheReadTokens"), ("cost", "totalCost")):
        if aggregate.get(field) is not None:
            usage[key] = aggregate[field]


def _handle_content(event, f, state, seen):
    """Cline streams each block in fragments but closes it with the block's *whole* text, so
    only `content_end` is logged (measured: the closed text equals the fragments joined).
    Reasoning blocks are dropped: chatty, and the verdict is in the text anyway."""
    content = event.get("contentType")
    if content == "reasoning":
        return
    if content == "tool":
        call = event.get("toolName") or seen.get("tool_name")
        call_id = event.get("toolCallId") or seen.get("tool_call")
        if call_id and call_id in seen.setdefault("tools", set()):
            return  # the block was already reported when it closed
        seen["tools"].add(call_id)
        # `input` arrives on the streamed fragments, not on the closing record
        payload = event.get("input") or seen.get("tool_input") or {}
        seen["tool_input"] = None
        f.write(f"[toolCall {call}] {json.dumps(payload)[:200]}\n".encode("utf-8"))
    elif content == "text":
        text = event.get("text") or ""
        if text:
            state["text_out"] += len(text)
            f.write((text.rstrip("\n") + "\n").encode("utf-8"))
    else:  # a content type this runner does not know yet: keep the trace, lose nothing
        f.write(f"[{content}] {json.dumps(event)[:200]}\n".encode("utf-8"))


def _handle_event(event, f, usage, state, seen):
    """One NDJSON record -> log lines and usage.

    Only `done.reason` and `run_result.finishReason` decide the verdict (the process exit code
    is the third signal): Cline also emits *warning-shaped* `error` records -- "hook dispatch
    failed" arrives on every startup here -- and those must not fail a completed run.
    """
    kind = event.get("type")
    if kind == "error":
        message = str(event.get("message", ""))
        state["limited"] = state["limited"] or RATE_LIMIT_TEXT in message.lower()
        f.write(f"[error] {message}\n".encode("utf-8"))
    elif kind == "agent_event":
        inner = event.get("event", {})
        inner_kind = inner.get("type")
        if inner_kind == "error":
            message = str((inner.get("error") or {}).get("message") or inner.get("message") or inner)
            state["limited"] = state["limited"] or RATE_LIMIT_TEXT in message.lower()
            f.write(f"[error] {message}\n".encode("utf-8"))
        elif inner_kind == "content_end":
            _handle_content(inner, f, state, seen)
        elif inner_kind in ("content_start", "content_update"):
            seen["tool_name"] = inner.get("toolName") or seen.get("tool_name")
            seen["tool_call"] = inner.get("toolCallId") or seen.get("tool_call")
            seen["tool_input"] = inner.get("input") or seen.get("tool_input")
        elif inner_kind == "usage":
            _add_delta(inner, usage)
        elif inner_kind == "iteration_end":
            f.write(f"[iteration {inner.get('iteration')}] "
                    f"toolCalls={inner.get('toolCallCount')}\n".encode("utf-8"))
        elif inner_kind == "done":
            if inner.get("reason") != "completed":
                state["error"] = True
            f.write(f"[done] reason={inner.get('reason')} "
                    f"iterations={inner.get('iterations')}\n".encode("utf-8"))
            if not state["text_out"] and inner.get("text"):
                f.write((inner["text"].rstrip("\n") + "\n").encode("utf-8"))
    elif kind == "run_result":
        _set_totals(event.get("aggregateUsage"), usage)
        if event.get("finishReason") != "completed":
            state["error"] = True
        model = (event.get("model") or {}).get("id")
        f.write(f"[run] finish={event.get('finishReason')} model={model} "
                f"{int(event.get('durationMs') or 0)}ms\n".encode("utf-8"))


def run_cline(brief, log, timeout, feedback=None, rules=None, model=None, data_dir=None):
    """Returns (exit code, token usage, session id). The session is always None: Cline's CLI
    cannot resume a headless session (cline/cline#13239), so every task runs fresh."""
    binary = _cline_binary()
    usage = zero_usage()
    env = dict(os.environ, PWD=os.getcwd(), CLINE_COMMAND_PERMISSIONS=_deny_permissions())
    cmd = [binary, "--json", "-c", os.getcwd(), "-m", _model(model), "-t", str(timeout),
           "--thinking", _thinking(), "--auto-approve", "true"]
    if data_dir:  # never by default: Cline keeps its credentials inside the data dir
        cmd += ["--data-dir", data_dir]
    if provider := os.environ.get("HARNESS_CLINE_PROVIDER"):
        cmd += ["-P", provider]
    cmd.append(_prompt(brief, feedback, rules))
    state = {"error": False, "limited": False, "text_out": 0}
    seen = {}
    with open(log, "wb") as f:
        p = subprocess.Popen(cmd, cwd=os.getcwd(), env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

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
                        text = clean.decode("utf-8", "replace").lower()
                        state["limited"] = state["limited"] or RATE_LIMIT_TEXT in text
                    f.flush()
                    continue
                _handle_event(event, f, usage, state, seen)
                f.flush()

        t = threading.Thread(target=pump, daemon=True)
        t.start()
        deadline = time.time() + timeout + TIMEOUT_GRACE
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
    if state["error"]:
        code = 1
    if state["limited"] and code != EXIT_TIMEOUT:
        return EXIT_RATE_LIMIT, usage, None
    return code, usage, None


def quota_ok(timeout=90, model=None):
    """One tiny cline call on a throwaway data dir: True if the model answers. Output goes to
    a temp file and the whole process tree is killed on timeout (capture_output + timeout
    hangs on Windows: the child's descendants keep the pipe open after the parent is killed)."""
    cmd = [_cline_binary(), "--json", "-c", os.getcwd(), "-m", _model(model), "-t", str(timeout),
           HEALTH_PROMPT]
    if data_dir := os.environ.get("HARNESS_CLINE_DATA"):
        cmd += ["--data-dir", data_dir]
    env = dict(os.environ, PWD=os.getcwd())
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
    answered, limited = False, False
    for line in data.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            limited = limited or RATE_LIMIT_TEXT in line.decode("utf-8", "replace").lower()
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "run_result":
            answered = event.get("finishReason") == "completed"
        elif event.get("type") == "error":
            limited = limited or RATE_LIMIT_TEXT in str(event.get("message", "")).lower()
    return answered and not limited


class ClineExecutor(Executor):
    name = "cline"
    has_sessions = False  # `--id` resume is rejected headless (see the module docstring)
    # One process and one data dir per task, and no resumable session: concurrent runs would
    # fight over the same mode flag, so this backend cannot be driven with --parallel > 1.
    thread_safe = False

    def __init__(self, model=None):
        self.model = _resolve_model(model)
        # Cline stores its credentials inside its data dir, so the run uses Cline's own by
        # default (~/.cline/data): outside the repo, which is all the stray-file guard needs.
        # HARNESS_CLINE_DATA isolates state instead, for an account authenticated there.
        self.data_dir = os.environ.get("HARNESS_CLINE_DATA")
        self._mode_before = None

    def start(self):
        self._mode_before = _force_act_mode(self.data_dir)

    def stop(self):
        _restore_mode(self._mode_before, self.data_dir)

    def run(self, brief, log, timeout, feedback=None, session=None, rules=None) -> ExecResult:
        if session:
            # A failure of THIS task, not of the whole run: report it like any other failed
            # task (the run loop decides what to do next) instead of killing the process, and
            # say why in the log rather than swallowing the reason.
            with open(log, "ab") as f:
                f.write(b"[error] cline cannot resume a session in headless mode: --id is "
                        b"rejected upstream (cline/cline#13239); use --fresh, not --session\n")
            return ExecResult(code=1, usage=zero_usage(), session=None)
        _force_act_mode(self.data_dir)  # the agent can flip itself to plan mode mid-plan
        code, usage, sid = run_cline(brief, log, timeout, feedback, rules, self.model, self.data_dir)
        return ExecResult(code=code, usage=usage, session=sid)

    def probe(self) -> bool:
        return quota_ok(model=self.model)
