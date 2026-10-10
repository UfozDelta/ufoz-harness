import os, subprocess, sys, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / ".harness"))
from runner import worktree as w

d = tempfile.mkdtemp()
def g(*a): subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)
g("init", "-q"); g("config", "user.email", "a@b"); g("config", "user.name", "a")
Path(d, "f.txt").write_text("x"); g("add", "."); g("commit", "-qm", "i")
os.chdir(d)
p = Path(d, ".harness/plans/x"); p.mkdir(parents=True)
(p / "plan.md").write_text("p")
q = Path(d, ".harness/plans/xy"); q.mkdir(parents=True)
(q / "plan.md").write_text("p")
r = w._dirty_paths("x")
assert not any(s.replace("\\", "/").startswith(".harness/plans/x/") for s in r), r
assert any("plans/xy" in s for s in r), r
assert w._dirty_paths(), "no-slug must still list plan dirs"
(q / "plan.md").unlink(); q.rmdir()
w._require_clean_tree("x")  # plan dir alone passes
Path(d, "f.txt").write_text("changed")
try:
    w._require_clean_tree("x")
except SystemExit as e:
    assert "f.txt" in str(e)
else:
    raise AssertionError("other dirty file must refuse")
print("ok")
