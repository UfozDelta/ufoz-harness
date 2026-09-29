"""The Executor interface every backend implements.

The run loop (task_runner/scheduler) only ever sees this: run a brief, find out the exit
code, what it cost, and which session to continue next time. Which model actually wrote
the code — pi, claude, an HTTP server — is the subclass's business.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecResult:
    code: int
    usage: dict  # TOKEN_KEYS + "cost"
    session: str | None


class Executor(ABC):
    name: str
    has_sessions = True  # False for backends that cannot continue a session (cline today)
    # False for backends that cannot be driven from several threads at once (one shared
    # session/process per plan), so the run loop can refuse --parallel > 1.
    thread_safe = True

    @abstractmethod
    def run(self, brief, log, timeout, feedback=None, session=None, rules=None,
            raw_prompt=None) -> ExecResult:
        """Run one task. `brief` and `feedback` are paths (multi-line text breaks through
        Windows .cmd shims). `rules`: optional path, overrides the backend's default executor
        prompt. `raw_prompt`: optional path, pi-only, bypasses the standard brief template.
        Returns the exit code, the token/cost usage, and the session
        to continue on the next task (None when the backend has no sessions)."""

    @abstractmethod
    def probe(self) -> bool:
        """One tiny call: True if the model answers right now (False when rate-limited)."""

    def wait_for_quota(self, log, max_wait=6 * 3600) -> None:
        """Block until the model answers again (probe every 60 s). Appends to `log`."""
        t0 = time.time()
        while time.time() - t0 < max_wait:
            time.sleep(60)
            ok = self.probe()
            with open(log, "ab") as f:
                f.write(f"[runner] quota probe after {int(time.time() - t0)}s: "
                        f"{'ok' if ok else 'still rate-limited'}\n".encode())
            if ok:
                return

    def start(self) -> None:
        """Bring up anything the backend needs before the first run (default: nothing)."""

    def stop(self) -> None:
        """Tear down what start() brought up (default: nothing)."""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.stop()
