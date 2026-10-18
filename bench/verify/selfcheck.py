"""End-to-end self-check: run exactly one verify cell through the public CLI.

`verify-pi-pi-pi-r1` via the deterministic runner planner, forced so a prior row is
replaced. Returns verify.py's exit code so the harness can gate on it.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "bench" / "verify" / "verify.py"


def main(argv=None):
    cmd = [sys.executable, str(VERIFY), "--only", "verify-pi-pi-pi-r1",
           "--plan-via", "runner", "--force"]
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
