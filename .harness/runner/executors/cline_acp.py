"""The cline ACP executor: one `cline --acp` process for a whole plan, warm across tasks.

`cline --json --id <session-id>` is rejected headless (cline/cline#13239, open), so the
`--json` executor is forced to start a fresh process per task. ACP sidesteps that: one
long-lived process, `session/new` once, then one `session/prompt` per task, exactly like
pi (`--session-id`) and opencode (HTTP server). `session/load` additionally restores a
session in a NEW process, so a crash mid-plan is recoverable.

What the protocol measured, before any of this was written (see cline-test/README.md for the
raw runs; `python -m pytest cline-test --run-live` reproduces them):

- The model is NOT set by `-m`; it is silently ignored. `CLINE_MODEL` is the documented
  lever and is the only thing that works. The account default is a PAID model
  (anthropic/claude-sonnet-5, ~$0.01 for a one-word reply), so this is a money leak, not a
  style choice. `_resolve_model` reads the `model` config option back to prove it took.
- `session/resume` and `session/list` are bundled in cline's binary but NOT implemented
  (-32601). Only `session/load` works. Strings in a binary prove nothing.
- Config options are advertised at session setup, not in `initialize`. Two of them share
  `category: "model"` ("provider" and "model"), so they must be matched by `id`.
- There is NO reasoning/effort selector, so `--thinking` cannot be honoured here.
- ACP carries NO token usage: it is read back from cline's own session file.
- The agent calls BACK into the client for `fs/*`, `terminal/*` and
  `session/request_permission`. An unanswered request hangs the agent forever. Permissions
  are the client's job, so the deny-list is enforced here, not by a CLI flag.
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..procs import EXIT_RATE_LIMIT, EXIT_TIMEOUT, zero_usage
from .base import ExecResult, Executor

EXIT_TIMEOUT = 124
NO_REPLY = object()

DEFAULT_MODEL = "stealth/space-bunny-alpha"
# `-m` is ignored in ACP mode, so the free model is also offered as a fallback. The account
# default is a paid model, which is why CLINE_MODEL is pinned and then verified.
FALLBACK_MODELS = ("stealth/space-bunny-alpha", "stealth/pixel-canary")
HEALTH_PROMPT = "Health check, not a task. Reply OK."
RATE_LIMIT_TEXT = "rate limit"
TIMEOUT_GRACE = 30


def _thinking():
    """Kept for interface parity only: ACP exposes no reasoning/effort selector, so --thinking
    cannot be honoured on this transport. The run log says so rather than pretending."""
    return os.environ.get("HARNESS_VARIANT", "medium").lower()


def _deny_bash():
    try:
        return json.loads(Path(".pi/deny.json").read_text(encoding="utf-8")).get("bash", [])
    except (OSError, ValueError):
        return []


def _permission_policy(denied):
    """Answer `session/request_permission` from .pi/deny.json, fail closed.

    ACP has no `CLINE_COMMAND_PERMISSIONS` equivalent and `--auto-approve` would delete this
    guardrail entirely (measured: it suppresses the requests, so nothing is ever checked).
    So permissions are answered HERE: the denied commands are refused, everything else runs,
    and anything we do not recognise is refused rather than allowed.
    """
    def decide(params):
        options = params.get("options") or []
        blob = json.dumps(params).lower()
        blocked = [cmd for cmd in denied if cmd and cmd.lower() in blob]
        wanted = "reject_once" if blocked else "allow_once"
        for option in options:
            if option.get("kind") == wanted:
                return option.get("optionId")
        for option in options:
            if option.get("kind") in ("reject_once", "reject_always"):
                return option.get("optionId")
        return options[0].get("optionId") if options else "reject"
    return decide



def _resolve_model(model=None):
    """The model to pin, honoured as given: an explicit --executor-model or HARNESS_MODEL is
    never silently swapped for a different one."""
    return model or os.environ.get("HARNESS_MODEL", DEFAULT_MODEL)


CLIENT_CAPABILITIES = {
    "fs": {"readTextFile": True, "writeTextFile": True},
    # Terminals are how the agent gets a shell. With this false, cline cannot run pytest,
    # git or pip at all, and a coding task flails: measured 40 tool calls and 47.7s versus
    # 7 calls and 17.1s on the --json path. See bench/speed results-acp.csv.
    "terminal": True,
}

DEFAULT_OUTPUT_BYTE_LIMIT = 1024 * 1024
POLL_SLICE = 0.5   # how often a blocked read re-checks whether the agent is still alive


class _Terminal:
    """One running command, buffered for `terminal/output`.

    Output is truncated FROM THE BEGINNING once the limit is hit, as the spec requires, so the
    agent always sees the end of a long build rather than the start.
    """

    def __init__(self, terminal_id, proc, limit):
        self.id = terminal_id
        self.proc = proc
        self.limit = limit
        self.chunks = []
        self.size = 0
        self.truncated = False
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self):
        try:
            for raw in self.proc.stdout:
                text = raw.decode("utf-8", "replace")
                self._append(text)
        except Exception:  # noqa: BLE001 - a dead pipe just ends the output
            pass

    def _append(self, text):
        """Keep the most recent `limit` characters, dropping from the FRONT.

        A single read can exceed the whole limit (one long line, a minified bundle), so the
        text is trimmed in place as well as across chunks - otherwise a one-chunk burst sails
        past outputByteLimit entirely.
        """
        self.chunks.append(text)
        self.size += len(text)
        while self.size > self.limit:
            overflow = self.size - self.limit
            head = self.chunks[0]
            if len(self.chunks) == 1:
                # one chunk holds everything: cut from its front, keeping the limit
                keep = head[overflow:] if overflow < len(head) else ""
                self.chunks[0] = keep
                self.size = len(keep)
            else:
                dropped = self.chunks.pop(0)
                self.size -= len(dropped)
            self.truncated = True

    def output(self):
        return "".join(self.chunks)

    def exit_status(self):
        code = self.proc.poll()
        if code is None:
            return None
        return {"exitCode": code, "signal": None}

    def wait(self):
        """Wait for the command AND for its output to be fully read.

        Returning when the process exits is not enough: the pump thread may not have drained
        the pipe yet, so a caller that waits and then reads output can get nothing. Measured
        as a flaky `truncated` assertion, which passed only when the read happened to win the
        race.
        """
        code = self.proc.wait()
        self._thread.join(timeout=5)
        return code

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()

    def dispose(self):
        self.kill()
        try:
            if self.proc.stdout is not None:
                self.proc.stdout.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass


def _allow_all(params):
    """Allow whatever is offered, preferring a 'yes' option. The counterpart to the
    fail-closed default; the executor will use a deny-list policy instead of either."""
    for option in params.get("options") or []:
        if str(option.get("kind", "")).startswith("allow"):
            return option.get("optionId")
    options = params.get("options") or []
    return options[0].get("optionId") if options else "reject"


class AcpError(RuntimeError):
    """The agent answered a request with a JSON-RPC error."""


class AcpDead(RuntimeError):
    """The process died while a request was outstanding."""


def cline_binary():
    """The compiled binary next to the npm shim, same rule as the runner's _cline_binary:
    the .cmd wrapper cannot be exec'd with a piped stdio setup."""
    found = os.environ.get("HARNESS_CLINE") or shutil.which("cline")
    if not found:
        raise FileNotFoundError("cline was not found on PATH (npm i -g cline)")
    shim = Path(found)
    machine = os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE") or ""
    machine = {"AMD64": "x64", "x64": "x64", "ARM64": "arm64", "arm64": "arm64"}.get(machine.upper(), machine.lower())
    plat = "windows" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
    exe = "cline.exe" if plat == "windows" else "cline"
    roots = [shim.parent / "node_modules" / "cline",
             shim.parent / "node_modules" / "cline" / "node_modules" / "@cline",
             shim.parent / "node_modules" / "@cline"]
    for root in roots:
        for candidate in (root / "bin" / ".cline",
                          root / f"cli-{plat}-{machine}" / "bin" / exe,
                          root / "bin" / exe):
            if candidate.exists():
                return str(candidate)
    return str(shim)


def session_usage(data_dir, session_id):
    """Cumulative usage for a session, read out of band from cline's own session file.

    ACP itself carries no usage: the protocol has no usage method or notification, and
    cline's only `session/update` kinds are the eight standard ones (agent_message_chunk,
    agent_thought_chunk, tool_call, tool_call_update, plan, user_message_chunk,
    available_commands_update, current_mode_update) - none of them usage-related.
    The numbers are therefore read from `<sessionId>.json`, which is cumulative for the
    whole session, so per-turn cost needs the previous reading subtracted.
    """
    base = Path(data_dir) if data_dir else Path.home() / ".cline" / "data"
    path = base / "sessions" / session_id / f"{session_id}.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    usage = (doc.get("metadata") or {}).get("usage") or {}
    if not usage:
        return None
    return {"input": usage.get("inputTokens", 0) or 0,
            "output": usage.get("outputTokens", 0) or 0,
            "cache_read": usage.get("cacheReadTokens", 0) or 0,
            "cost": usage.get("totalCost", 0.0) or 0.0}


def usage_delta(after, before):
    """Per-turn usage: cumulative snapshot minus the previous one."""
    if after is None:
        return None
    before = before or {"input": 0, "output": 0, "cache_read": 0, "cost": 0.0}
    return {key: round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in before}


class AcpClient:
    """One `cline --acp` process, many prompts. This is the warm-session transport the
    current executor cannot do: `cline --json --id` is rejected headless (cline#13239)."""

    def __init__(self, cwd, model=None, data_dir=None, provider=None, auto_approve=False,
                 extra_args=(), env=None, binary=None, raw=False, permission_policy=None):
        """`raw=True` omits `--acp -c <cwd>`, for driving a fake agent that is not cline
        (a plain python process, which would reject `--acp` outright). Real use never sets it.
        `permission_policy` is called with the `session/request_permission` params and returns
        the optionId to answer; the default fails closed.
        """
        self.permission_policy = permission_policy
        self.cwd = Path(cwd).resolve()
        self.model = model
        self.data_dir = data_dir
        self.inbox = queue.Queue()
        self.session_id = None
        self.last_session_result = {}
        self.notifications = []   # every session/update seen, for assertions
        self.client_calls = []     # methods the agent asked US to handle
        self._next_id = 0
        self._pending = {}
        self._proc = None
        self._read_error = None
        self._stderr = []
        self._terminals = {}
        self.terminal_log = []   # every command the agent asked us to run, for assertions
        cmd = [binary or cline_binary()] if raw else [binary or cline_binary(), "--acp",
                                                       "-c", str(self.cwd)]
        if model:
            cmd += ["-m", model]
        if data_dir:
            cmd += ["--data-dir", str(data_dir)]
        if provider:
            cmd += ["-P", provider]
        if auto_approve:
            cmd += ["--auto-approve", "true"]
        cmd += list(extra_args)
        self.cmd = cmd
        run_env = dict(os.environ, PWD=str(self.cwd), **(env or {}))
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, cwd=str(self.cwd), bufsize=0,
                                      env=run_env)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self._stderr = []
        self._err_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._err_thread.start()

    # --- plumbing ---------------------------------------------------------------------

    def _drain_stderr(self):
        for raw in self._proc.stderr:
            self._stderr.append(raw.decode("utf-8", "replace").rstrip())

    def _read(self):
        try:
            for raw in self._proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    self.inbox.put(json.loads(line))
                except ValueError:
                    self.inbox.put({"__unparsed__": line})
        except Exception as exc:  # noqa: BLE001 - a dead reader must not hang the client
            self._read_error = f"{type(exc).__name__}: {exc}"

    def _send(self, message):
        self._proc.stdin.write((json.dumps(message) + "\n").encode())
        self._proc.stdin.flush()

    def _handle_inbound(self, message):
        """The agent is calling US. Answering is mandatory: an unanswered request hangs it."""
        method = message.get("method")
        mid = message.get("id")
        params = message.get("params") or {}
        self.client_calls.append(method)
        if method == "fs/write_text_file":
            path = Path(params.get("path", ""))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params.get("content", ""), encoding="utf-8")
            result = {}
        elif method == "fs/read_text_file":
            path = Path(params.get("path", ""))
            result = {"content": path.read_text(encoding="utf-8") if path.is_file() else ""}
        elif method == "session/request_permission":
            result = {"outcome": {"outcome": "selected",
                                  "optionId": self._decide_permission(params)}}
        elif method and method.startswith("terminal/"):
            result = self._terminal(method, params)
        else:
            result = {}
        self._send({"jsonrpc": "2.0", "id": mid, "result": result})

    # --- terminals: the agent's shell -------------------------------------------------------

    def _terminal(self, method, params):
        """terminal/create | output | wait_for_exit | kill | release (agentclientprotocol.com).

        `create` returns immediately with a terminalId so the agent can keep working while the
        command runs, which is the whole point of the method being asynchronous.
        """
        tid = params.get("terminalId")
        if method == "terminal/create":
            env = dict(os.environ)
            for item in params.get("env") or []:
                if item.get("name"):
                    env[item["name"]] = str(item.get("value", ""))
            cwd = params.get("cwd") or str(self.cwd)
            argv = [params.get("command") or ""] + list(params.get("args") or [])
            try:
                proc = subprocess.Popen(
                    argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
            except OSError as exc:
                # The spec has no error channel here, so a command that cannot start is
                # reported as a finished terminal with a non-zero code, which the agent reads.
                return {"output": f"failed to start {argv!r}: {exc}\n", "truncated": False,
                        "exitStatus": {"exitCode": 127, "signal": None}}
            new_id = f"term_{len(self._terminals) + 1}"
            terminal = _Terminal(new_id, proc,
                                 params.get("outputByteLimit") or DEFAULT_OUTPUT_BYTE_LIMIT)
            self._terminals[new_id] = terminal
            self.terminal_log.append({"command": argv, "cwd": cwd})
            return {"terminalId": new_id}
        terminal = self._terminals.get(tid)
        if terminal is None:
            return {"output": f"unknown terminal {tid}", "truncated": False,
                    "exitStatus": {"exitCode": 1, "signal": None}}
        if method == "terminal/output":
            result = {"output": terminal.output(), "truncated": terminal.truncated}
            status = terminal.exit_status()
            if status is not None:
                result["exitStatus"] = status
            return result
        if method == "terminal/wait_for_exit":
            code = terminal.wait()
            return {"exitCode": code, "signal": None}
        if method == "terminal/kill":
            terminal.kill()
            return {}
        if method == "terminal/release":
            terminal.dispose()
            self._terminals.pop(tid, None)
            return {}
        return {}

    # --- the public surface ------------------------------------------------------------

    def _dead(self):
        """True once the agent process has exited and its output pipe is drained.

        Detection has to be independent of the inbox: a crashed agent can leave messages
        queued, and a loop that only checks the process when the queue is empty will sit on
        `get()` until the full request timeout instead of failing. Measured: the agent died
        after writing its files and the run sat for 30 minutes before giving up.
        """
        return self._proc is not None and self._proc.poll() is not None and self.inbox.empty()

    def _wait_message(self, deadline):
        """Next message, or None if the agent is gone. Polls in slices so a dead process is
        noticed within POLL seconds rather than at the deadline."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                return self.inbox.get(timeout=min(POLL_SLICE, remaining))
            except queue.Empty:
                if self._dead():
                    return None

    def call(self, method, params=None, timeout=120):
        """One request, waiting for its response while servicing notifications and the
        agent's own requests. Raises AcpError on a JSON-RPC error, AcpDead if the process
        dies first."""
        self._next_id += 1
        rid = self._next_id
        message = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + timeout
        while True:
            got = self._wait_message(deadline)
            if got is None:
                if self._dead():
                    raise AcpDead(f"{method}: agent exited {self._proc.returncode} "
                                  f"({'; '.join(self._stderr[-3:])})")
                raise AcpError(f"{method}: timed out after {timeout}s")
            if "method" in got and "id" in got:
                self._handle_inbound(got)
                continue
            if "method" in got:
                self.notifications.append(got)
                continue
            if got.get("id") == rid:
                if "error" in got:
                    raise AcpError(f"{method}: {got['error'].get('code')} "
                                   f"{got['error'].get('message')}")
                return got.get("result", {})
        raise AcpError(f"{method}: timed out after {timeout}s")

    def _decide_permission(self, params):
        """Default policy: FAIL CLOSED. An unrecognised request gets the reject option, so a
        permission the client does not understand can never be silently allowed. A caller can
        pass `permission_policy` to answer differently (the executor uses a deny-list)."""
        if self.permission_policy is not None:
            return self.permission_policy(params)
        options = params.get("options") or []
        for option in options:
            if option.get("kind") in ("reject_once", "reject_always"):
                return option.get("optionId")
        return options[0].get("optionId") if options else "reject"

    def initialize(self, timeout=120):
        return self.call("initialize", {"protocolVersion": 1,
                                        "clientCapabilities": CLIENT_CAPABILITIES}, timeout)

    def new_session(self, timeout=120):
        result = self.call("session/new", {"cwd": str(self.cwd), "mcpServers": []}, timeout)
        self.last_session_result = result
        if isinstance(result, dict):
            self.session_id = result.get("sessionId")
        return result

    def load_session(self, session_id, timeout=120):
        result = self.call("session/load", {"sessionId": session_id, "cwd": str(self.cwd),
                                           "mcpServers": []}, timeout)
        self.session_id = session_id
        self.last_session_result = result
        return result

    def prompt(self, text, timeout=240):
        """One turn. Returns (assistant_text, seconds, stop_reason, update_kinds)."""
        texts, kinds = [], []
        started = time.monotonic()
        self._next_id += 1
        rid = self._next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                    "params": {"sessionId": self.session_id,
                               "prompt": [{"type": "text", "text": text}]}})
        deadline = started + timeout
        while True:
            got = self._wait_message(deadline)
            if got is None:
                if self._dead():
                    raise AcpDead(f"prompt: agent exited {self._proc.returncode} "
                                  f"after {round(time.monotonic() - started, 1)}s "
                                  f"({'; '.join(self._stderr[-3:])})")
                raise AcpError(f"prompt: timed out after {timeout}s")
            if "method" in got and "id" in got:
                self._handle_inbound(got)
                continue
            if "method" in got:
                self.notifications.append(got)
                update = (got.get("params") or {}).get("update") or {}
                kind = update.get("sessionUpdate")
                if kind:
                    kinds.append(kind)
                for node in (update.get("content"), update.get("text")):
                    if isinstance(node, dict) and node.get("type") == "text":
                        texts.append(node.get("text", ""))
                continue
            if got.get("id") == rid:
                result = got.get("result") or {}
                return (" ".join(t for t in texts if t), time.monotonic() - started,
                        result.get("stopReason"), kinds)

    def set_config_option(self, config_id, value, timeout=60, type_=None):
        """`type: "boolean"` is REQUIRED for boolean options (cline's `auto_approve`): the
        spec says a boolean configId without it is invalid params (-32602)."""
        params = {"sessionId": self.session_id, "configId": config_id, "value": value}
        if type_:
            params["type"] = type_
        return self.call("session/set_config_option", params, timeout)

    def set_mode(self, mode_id, timeout=60):
        return self.call("session/set_mode",
                         {"sessionId": self.session_id, "modeId": mode_id}, timeout)

    def usage(self):
        return session_usage(self.data_dir, self.session_id) if self.session_id else None

    @staticmethod
    def config_options(result):
        return result.get("configOptions") or [] if isinstance(result, dict) else []

    @staticmethod
    def option(result, category=None, config_id=None):
        """Look up a config option. `config_id` is checked FIRST and on its own: cline has two
        options with category "model" ("provider" and "model"), so a category-only lookup
        returns the provider and the model check silently passes against the wrong field."""
        options = AcpClient.config_options(result)
        if config_id:
            for option in options:
                if option.get("id") == config_id:
                    return option
        if category:
            for option in options:
                if option.get("category") == category:
                    return option
        return None

    def observed_model(self, wait=0.0):
        """The model cline is on, from its own session file once it exists, else from the
        `model` config option. `-m` is NOT honoured in ACP mode, and CLINE_MODEL is the
        documented lever, so the executor needs to be able to read back what it got."""
        base = Path(self.data_dir) if self.data_dir else Path.home() / ".cline" / "data"
        if self.session_id:
            path = base / "sessions" / self.session_id / f"{self.session_id}.json"
            deadline = time.monotonic() + max(0.0, wait)
            while True:
                if path.is_file():
                    try:
                        model = json.loads(path.read_text(encoding="utf-8")).get("model")
                    except (OSError, ValueError):
                        model = None
                    if model:
                        return model
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.2)
        option = self.option(self.last_session_result, config_id="model")
        if option is None:
            option = self.option(self.last_session_result, category="model")
        return (option or {}).get("currentValue")

    def close(self):
        for terminal in list(getattr(self, "_terminals", {}).values()):
            terminal.dispose()
        self._terminals = {}
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
        except Exception:  # noqa: BLE001 - may already be gone
            pass
        time.sleep(0.5)
        if self._proc.poll() is None:
            self._proc.kill()

    def kill(self):
        """Hard kill on purpose, for the durability test."""
        for terminal in list(getattr(self, "_terminals", {}).values()):
            terminal.dispose()
        self._terminals = {}
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# --- the executor ---------------------------------------------------------------------------


class ClineAcpExecutor(Executor):
    """One `cline --acp` process per plan, one `session/prompt` per task.

    Unlike the `--json` executor this has `has_sessions = True`: the session id is real, so the
    run loop keeps the agent's context between tasks the way pi and opencode already do.
    """

    name = "cline-acp"
    has_sessions = True
    # One ACP process and one session for the whole plan: concurrent turns would interleave
    # in the same session, so this backend cannot be driven with --parallel > 1.
    thread_safe = False

    def __init__(self, model=None):
        self.model = _resolve_model(model)
        self.data_dir = os.environ.get("HARNESS_CLINE_DATA")
        self.client = None
        self._usage_before = None
        self._pid = None

    # -- lifecycle: the process belongs to the whole plan, not to a task ----------------------

    def start(self):
        self.client = AcpClient(os.getcwd(), binary=cline_binary(), model=self.model,
                                data_dir=self.data_dir,
                                permission_policy=_permission_policy(_deny_bash()),
                                env={"CLINE_MODEL": self.model})
        self.client.initialize()
        created = self.client.new_session()
        self._pid = self.client._proc.pid
        seen = self.client.observed_model()
        if seen != self.model:
            # Never run a plan on a model we did not ask for: the default is a PAID one.
            self.stop()
            raise RuntimeError(
                f"cline-acp: asked for {self.model!r} but the agent reports {seen!r}. "
                f"ACP ignores -m, so CLINE_MODEL is the only lever; refusing to continue.")
        option = self.client.option(created, category="mode")
        if option and option.get("currentValue") != "act":
            # Plan mode cannot write a single file, and a run that starts in it does nothing.
            self.client.set_config_option("mode", "act")
        self._usage_before = self.client.usage()

    def stop(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    # -- one task ----------------------------------------------------------------------------

    def run(self, brief, log, timeout, feedback=None, session=None, rules=None) -> ExecResult:
        if self.client is None:
            # The plan was not started (or the process died): fall back to a cold run rather
            # than silently skipping the task.
            self.start()
        prompt = f"Do the task described in {brief}"
        if session:
            prompt = (f"Next task in the same plan: {brief}. The earlier tasks are done and "
                      f"verified; same rules, touch only this task's FILES. "
                      f"Finish with DONE: or BLOCKED:")
        if feedback:
            prompt += (f". Your previous attempt failed its acceptance check; read {feedback} "
                       f"first, then fix the work")
        if rules:
            prompt = f"{Path(rules).read_text(encoding='utf-8')}\n\n{prompt}"

        started = time.monotonic()
        with open(log, "ab") as f:
            f.write(f"[run] acp session={self.client.session_id} pid={self._pid} "
                    f"model={self.model} thinking={_thinking()} (ACP has no effort selector)\n"
                    .encode("utf-8"))
            try:
                # Only this turn's notifications can say anything about THIS turn being rate
                # limited; a fixed tail of an ever-growing list would find the previous turn's
                # text (or miss this one) as the list grows.
                start = len(getattr(self.client, "notifications", []))
                text, seconds, stop, kinds = self.client.prompt(prompt, timeout=timeout)
            except (AcpDead, AcpError) as exc:
                f.write(f"[error] {type(exc).__name__}: {exc}\n".encode("utf-8"))
                # Every failure here leaves the transport unusable for the next task (a dead
                # agent, or a request that timed out mid-flight), so the session is always
                # dropped: the run loop's next attempt starts fresh instead of writing into a
                # corpse or into a half-answered turn. A timeout is reported as such.
                self.stop()
                code = EXIT_TIMEOUT if (isinstance(exc, AcpDead)
                                        or "timed out" in str(exc)) else 1
                return ExecResult(code=code, usage=zero_usage(), session=None)
            after = self.client.usage()
            delta = usage_delta(after, self._usage_before) or {}
            self._usage_before = after
            for line in (text or "").splitlines():
                f.write((line + "\n").encode("utf-8"))
            f.write(f"[acp] {seconds:.1f}s updates={len(kinds)} stop={stop} "
                    f"tools={kinds.count('tool_call')} "
                    f"permissions={len(self.client.client_calls)}\n".encode("utf-8"))
        seen = getattr(self.client, "notifications", [])[start:]
        limited = RATE_LIMIT_TEXT in json.dumps(seen).lower()
        code = EXIT_RATE_LIMIT if limited else (0 if stop == "end_turn" else 1)
        usage = zero_usage()
        for key, value in (delta or {}).items():
            usage[key] = value
        return ExecResult(code=code, usage=usage, session=self.client.session_id)

    def probe(self) -> bool:
        """One throwaway session: True if the pinned model answers. The account default is a
        paid model, so this also proves the pin held."""
        client = AcpClient(os.getcwd(), binary=cline_binary(), model=self.model,
                           data_dir=self.data_dir, env={"CLINE_MODEL": self.model})
        try:
            client.initialize()
            client.new_session()
            text, _, stop, _ = client.prompt(HEALTH_PROMPT, timeout=90)
            return stop == "end_turn" and bool(text)
        except (AcpDead, AcpError, OSError):
            return False
        finally:
            client.close()


