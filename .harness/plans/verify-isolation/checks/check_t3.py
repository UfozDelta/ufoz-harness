import subprocess, sys
from pathlib import Path
s = Path(".harness/plans/verify-isolation/SUMMARY.md").read_text(encoding="utf-8")
assert len(s) <= 700 and "BUILD: pass" in s
assert subprocess.run([sys.executable, "bench/verify/verify.py", "--dry"], capture_output=True).returncode == 0
