import subprocess, sys
sys.path.insert(0, ".harness")
from runner import worktree
assert ".opencode/.gitignore" in worktree.OPENCODE_PKG, worktree.OPENCODE_PKG
assert ".opencode/package.json" in worktree.OPENCODE_PKG
assert subprocess.run([sys.executable, ".harness/selftest.py"], capture_output=True).returncode == 0
