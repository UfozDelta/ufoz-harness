import os, sys, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, ".harness")
from runner import lint as L

main = os.getcwd()
seen = []
def fake(cmd, expect=None, timeout=300):
    seen.append(os.getcwd())
    return (False, "")
L.run_acceptance = fake
d = Path(tempfile.mkdtemp())
(d / "plan.md").write_text("## T1\n", encoding="utf-8")
t = [{"id": "T1", "deps": [], "files": ["a.py"], "red_first": True, "acceptance": "python -c pass"}]
L.lint(d, t, set())
assert len(seen) == 1, seen
assert Path(seen[0]).resolve() != Path(main).resolve(), "ran in main tree"
assert os.getcwd() == main
out = subprocess.run(["git", "worktree", "list"], capture_output=True, text=True).stdout
assert seen[0] not in out and Path(seen[0]).as_posix() not in out, "worktree left behind"
