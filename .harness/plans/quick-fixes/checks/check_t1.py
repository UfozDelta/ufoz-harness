"""Acceptance check for quick-fixes T1. Hash-locked: the executor cannot edit this.

Proves run_plan.py reconfigures stdout to UTF-8 at import time, so printing a
non-ASCII character (e.g. the summary's "->" arrow) never crashes on Windows'
cp1252 console.
"""
import subprocess
import sys

CODE = (
    "import sys; sys.path.insert(0, '.harness'); import run_plan; "
    "print(sys.stdout.encoding)"
)

r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True)
if r.returncode != 0:
    print("FAIL: import crashed")
    print(r.stderr)
    sys.exit(1)

encoding = r.stdout.strip().lower()
if not encoding.startswith("utf"):
    print(f"FAIL: sys.stdout.encoding is {encoding!r}, expected utf-8")
    sys.exit(1)

# The actual failure mode: printing the arrow used in run_plan.py's own summaries.
r2 = subprocess.run(
    [sys.executable, "-c", CODE.replace("print(sys.stdout.encoding)", "print('\\u2192')")],
    capture_output=True,
    text=True,
)
if r2.returncode != 0:
    print("FAIL: printing U+2192 still crashes")
    print(r2.stderr)
    sys.exit(1)

print("PASS: stdout is utf-8, non-ASCII print does not crash")
