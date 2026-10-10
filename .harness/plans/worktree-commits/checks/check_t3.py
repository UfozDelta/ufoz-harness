import subprocess
import sys
from pathlib import Path

test = Path("tests") / "test_worktree_commits.py"
assert test.is_file(), f"{test} was not written"

r = subprocess.run([sys.executable, "-m", "pytest", str(test), "-q"],
                   capture_output=True, text=True)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
assert r.returncode == 0, "the guard regression test fails"
print("OK")