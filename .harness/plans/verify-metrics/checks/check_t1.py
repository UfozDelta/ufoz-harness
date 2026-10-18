"""Acceptance T1: cache_write is a token key and pi/opencode/planner record it; selftest still passes."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".harness")
from runner.procs import TOKEN_KEYS  # noqa: E402

assert "cache_write" in TOKEN_KEYS, TOKEN_KEYS
ex = Path(".harness/runner/executors")
assert "cacheWrite" in (ex / "pi.py").read_text(encoding="utf-8")
assert '"write"' in (ex / "opencode.py").read_text(encoding="utf-8")
assert "cache_write" in Path(".harness/runner/planner.py").read_text(encoding="utf-8")
assert "cacheWrite" not in (ex / "claude.py").read_text(encoding="utf-8")
code = subprocess.run([sys.executable, ".harness/selftest.py"], capture_output=True, text=True).returncode
assert code == 0, "selftest failed"
print("T1 OK")
