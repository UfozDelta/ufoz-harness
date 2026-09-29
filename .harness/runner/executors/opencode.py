"""The opencode executor: the same brief, guards and guards-only overhead, but the code is
written by `opencode serve` over its HTTP+SSE API instead of a CLI per task.

Ported from harness-speed-test/latency.py (which drives the same server for latency
measurements): one warm server per run, opencode's own agent with the .pi/executor.md
rules appended, and a task streamed to completion by watching the event bus for that
session's idle.
"""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..procs import EXIT_RATE_LIMIT, EXIT_TIMEOUT, TOKEN_KEYS, stop_process_tree
from .base import ExecResult, Executor

DEFAULT_MODEL = "opencode/space-bunny-free"
HEALTH_PROMPT = "Health check, not a task. Reply OK."
RATE_LIMIT_TEXT = "rate limit"
CONNECT_TIMEOUT = 10     # seconds for the event stream to connect
STARTUP_TIMEOUT = 120    # seconds for the server to answer HTTP
VARIANT = os.environ.get("HARNESS_VARIANT", "medium")
SESSION_BODY = {"permission": [{"permission": name, "action": "deny", "pattern": "*"}
                                for name in ("question", "plan_enter", "plan_exit")]}


def opencode_command(*args):
    """Native binary only: the .cmd wrapper cannot be exec'd with a piped stdio setup."""
    discovered = shutil.which("opencode")
    if discovered is None:
        raise FileNotFoundError("opencode was not found on PATH")
    discovered_path = Path(discovered)
    native = discovered_path.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    if native.exists():
        return [str(native), *args]
    if discovered_path.suffix.lower() == ".cmd":
        raise FileNotFoundError("opencode was found only as a .cmd wrapper")
    return [discovered, *args]


def opencode_config(deny_bash):
    """The config the executor runs under: no snapshot/lsp/formatter/autoupdate, no share,
    no title/summary generation, and no custom agent (the rules travel with each prompt as
    the system prompt). Questions and plan mode are denied so the run cannot block on them.
    The git commands .pi/deny.json bans are denied by pattern; everything else the agent
    runs is allowed."""
    return {
        "snapshot": False,
        "lsp": False,
        "formatter": False,
        "autoupdate": False,
        "share": "disabled",
        "agent": {
            "title": {"disable": True},
            "summary": {"disable": True},
        },
        "permission": {
            "edit": "allow",
            "question": "deny",
            "plan_enter": "deny",
            "plan_exit": "deny",
            "webfetch": "deny",
            "external_directory": "deny",
            "bash": {"*": "allow", **{f"{cmd} *": "deny" for cmd in deny_bash}},
        },
    }


def _executor_prompt(rules=None):
    return Path(rules or ".pi/executor.md").read_text(encoding="utf-8")


def _deny_bash():
    return json.loads(Path(".pi/deny.json").read_text(encoding="utf-8")).get("bash", [])


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _model_parts(model):
    provider, _, api_model = model.partition("/")
    return provider, api_model


def _http(url, path, body=None, timeout=600):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(f"{url}{path}", data=data, headers=headers,
                                     method="GET" if body is None else "POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _prompt_body(model, prompt, system):
    provider, api_model = _model_parts(model)
    return {
        "model": {"providerID": provider, "modelID": api_model},
        "system": system,
        "variant": VARIANT,
        "parts": [{"type": "text", "text": prompt}],
    }


def _read_events(url, events, connected, responses):
    """Follow the SSE bus, collecting every event until the response is closed."""
    try:
        with urllib.request.urlopen(f"{url}/event", timeout=1800) as response:
            responses.append(response)
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                events.append(payload)
                if payload.get("type") == "server.connected":
                    connected.set()
    except Exception:
        pass


def _part_text(part, state):
    if part.get("type") == "text":
        return part.get("text", "")
    return state.get("error") or state.get("output") or ""


class OpenCodeExecutor(Executor):
    name = "opencode"

    def __init__(self, model=None):
        self.model = model or os.environ.get("HARNESS_MODEL", DEFAULT_MODEL)
        self.url = None
        self.process = None
        self._config = None

    def start(self):
        """Write the executor config into a throwaway XDG_CONFIG_HOME, then serve it."""
        self._config = tempfile.TemporaryDirectory(prefix="harness-oc-")
        config_dir = Path(self._config.name)
        path = config_dir / "opencode" / "opencode.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(opencode_config(_deny_bash()), indent=2) + "\n",
                        encoding="utf-8")
        port = _free_port()
        self.url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, XDG_CONFIG_HOME=str(config_dir), PWD=os.getcwd())
        self.process = subprocess.Popen(opencode_command("serve", "--port", str(port)),
                                        cwd=os.getcwd(), env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started = time.monotonic()
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"opencode serve exited with status {self.process.returncode}")
            try:
                with urllib.request.urlopen(self.url, timeout=1):
                    return
            except urllib.error.HTTPError:  # it answers, it just has nothing at "/"
                return
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() - started > STARTUP_TIMEOUT:
                    self.stop()
                    raise TimeoutError(f"opencode serve did not answer HTTP within {STARTUP_TIMEOUT} seconds")
                time.sleep(0.1)

    def stop(self):
        if self.process is not None:
            stop_process_tree(self.process)
            self.process = None
        if self._config is not None:
            self._config.cleanup()
            self._config = None

    def run(self, brief, log, timeout, feedback=None, session=None, rules=None) -> ExecResult:
        prompt = f"Do the task described in {brief}"
        if session:
            prompt = (f"Next task in the same plan: {brief}. The earlier tasks are done and verified; same rules, "
                      f"touch only this task's FILES. Finish with DONE: or BLOCKED:")
        if feedback:  # a path, not the text: the prompt travels over JSON, but keep it one line
            prompt += f". Your previous attempt failed its acceptance check; read {feedback} first, then fix the work"
        code, usage, session, _ = self._stream(prompt, log, timeout, session,
                                              _executor_prompt(rules) if rules else None)
        return ExecResult(code=code, usage=usage, session=session)

    def probe(self) -> bool:
        """One tiny prompt on a fresh session: True if the model answers."""
        import tempfile as _tempfile
        with _tempfile.TemporaryFile(mode="w+", encoding="utf-8") as out:
            _, _, _, answered = self._stream(HEALTH_PROMPT, out, 90, None)
        return answered

    def _stream(self, prompt, log, timeout, session, system_text=None):
        """Send one prompt and follow its session to idle. Returns (code, usage, session id,
        whether any assistant text came back)."""
        url = self.url or self._started_url()
        events, responses, connected = [], [], threading.Event()
        reader = threading.Thread(target=_read_events, args=(url, events, connected, responses), daemon=True)
        reader.start()
        if not connected.wait(CONNECT_TIMEOUT):
            return 1, self._usage(), session, False
        try:
            session_id = session or _http(url, "/session", SESSION_BODY)["id"]
            _http(url, f"/session/{session_id}/prompt_async",
                  _prompt_body(self.model, prompt, _executor_prompt() if system_text is None else system_text))
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
            self._close(responses)
            return 1, self._usage(), session, False
        usage, answered, seen = self._usage(), False, {"non_assistant": set(), "logged": set()}
        deadline = time.monotonic() + timeout
        code = EXIT_TIMEOUT
        while time.monotonic() < deadline:
            state = self._drain(events, session_id, log, usage, seen)
            answered = answered or state["text"]
            if state["idle"]:
                code = 0
                break
            if state["error"]:
                code = EXIT_RATE_LIMIT if RATE_LIMIT_TEXT in state["error"].lower() else 1
                break
            time.sleep(0.05)
        else:
            try:
                _http(url, f"/session/{session_id}/abort", {})
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
        self._close(responses)
        reader.join(5)
        return code, usage, session_id, answered

    def _started_url(self):
        self.start()
        return self.url

    @staticmethod
    def _usage():
        return {**dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}

    @staticmethod
    def _close(responses):
        for response in responses:
            try:
                response.close()
            except OSError:
                pass

    def _drain(self, events, session_id, log, usage, seen):
        """Consume every event seen so far for this session: log it, sum its tokens."""
        state = {"idle": False, "error": None, "text": False}
        while events:
            event = events.pop(0)
            if not isinstance(event, dict) or event.get("properties", {}).get("sessionID") != session_id:
                continue
            kind, props = event.get("type", ""), event.get("properties", {})
            if kind.startswith("question.asked") or kind.startswith("permission.asked"):
                state["error"] = "blocked on question/permission"
                self._write(log, state["error"])
            elif kind == "session.idle":
                state["idle"] = True
            elif kind == "session.error":
                error = props.get("error") or {}
                state["error"] = str(error.get("data", {}).get("message") or error.get("name") or error)
            elif kind == "message.updated":
                info = props.get("info", {})
                if info.get("role") and info["role"] != "assistant" and info.get("id"):
                    seen["non_assistant"].add(info["id"])
            elif kind == "message.part.updated":
                part = props.get("part", {})
                if part.get("type") == "step-finish":
                    tokens = part.get("tokens", {})
                    usage["input"] += tokens.get("input", 0) or 0
                    usage["output"] += tokens.get("output", 0) or 0
                    usage["reasoning"] += tokens.get("reasoning", 0) or 0
                    usage["cache_read"] += (tokens.get("cache") or {}).get("read", 0) or 0
                    usage["cost"] += part.get("cost", 0) or 0
                elif part.get("type") == "text":
                    if part.get("messageID") in seen["non_assistant"]:
                        continue  # the prompt/tool output echoed back, not the executor talking
                    text = part.get("text", "")
                    state["text"] = state["text"] or bool(text)
                    logged = seen.setdefault("logged", set())
                    if text and part.get("time", {}).get("end") and part.get("id") not in logged:
                        self._write(log, text)
                        logged.add(part["id"])
                elif part.get("type") == "tool":
                    part_state = part.get("state", {})
                    logged = seen.setdefault("logged", set())
                    pid = part.get("id")
                    if pid is not None and pid in logged:
                        continue  # already logged in an earlier status
                    if part_state.get("status") == "error":
                        self._write(log, f"[tool error] {_part_text(part, part_state)[:200]}")
                        if pid is not None:
                            logged.add(pid)
                    elif part_state.get("status") == "completed":
                        args = json.dumps(part_state.get("input", {}))[:200]
                        self._write(log, f"[toolCall {part.get('tool')}] {args}")
                        if pid is not None:
                            logged.add(pid)
        return state

    @staticmethod
    def _write(log, text):
        if not text:
            return
        writer = getattr(log, "write", None)
        if callable(writer):  # an open binary/text handle (probe's temp file)
            log.write(text if text.endswith("\n") else text + "\n")
            log.flush()
        else:
            with open(log, "a", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
