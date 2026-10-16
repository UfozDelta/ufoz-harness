import io
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.executors import pi  # noqa: E402


class _NeverExitingProc:
    """Popen stand-in whose wait() always times out and whose stdout closes empty."""

    def __init__(self, *args, **kwargs):
        self.pid = 999999
        self.stdout = io.BytesIO(b"")
        self.returncode = None
        self.killed = False

    def wait(self, timeout=None):
        time.sleep(min(timeout or 0, 0.2))
        raise subprocess.TimeoutExpired(cmd="pi", timeout=timeout)

    def kill(self):
        self.killed = True

    def poll(self):
        return None


def test_run_pi_returns_exit_timeout_when_the_command_never_exits(tmp_path, monkeypatch):
    launcher = tmp_path / "pi-launcher.js"
    launcher.write_text("// stub\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_PI", str(launcher))
    monkeypatch.setattr(pi.subprocess, "Popen", _NeverExitingProc)

    start = time.time()
    code, usage, session = pi.run_pi("brief", str(tmp_path / "run.log"), timeout=2)
    elapsed = time.time() - start

    assert code == pi.EXIT_TIMEOUT
    assert usage == pi.zero_usage()
    assert session
    assert elapsed < 7
