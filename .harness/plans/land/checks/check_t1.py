import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(".harness").resolve()))
from runner import land, worktree  # noqa: E402

ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t")


def git(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout


repo = Path(tempfile.mkdtemp()) / "repo"
repo.mkdir()
os.chdir(repo)
git("init", "-q")
Path(".gitignore").write_text("node_modules/\n", encoding="utf-8")
Path("a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
Path("b.txt").write_text("b\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "init")
Path("node_modules/pkg").mkdir(parents=True)
Path("node_modules/pkg/i.js").write_text("keep", encoding="utf-8")
Path(".harness/plans/demo").mkdir(parents=True)
Path(".harness/plans/demo/plan.md").write_text("p\n", encoding="utf-8")

# happy path
wt = worktree.ensure("demo")
assert (wt / "node_modules/pkg/i.js").exists()
(wt / "a.txt").write_text("one\nTWO\nthree\n", encoding="utf-8")
(wt / "new.py").write_text("x = 1\n", encoding="utf-8")
(wt / ".harness/plans/demo/items").mkdir(parents=True)
(wt / ".harness/plans/demo/items/T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
(wt / ".harness/plans/demo/SUMMARY.md").write_text("sum\n", encoding="utf-8")
assert land.land("demo") == 0
assert Path("a.txt").read_text(encoding="utf-8") == "one\nTWO\nthree\n"
assert Path("new.py").read_text(encoding="utf-8") == "x = 1\n", "new file not landed"
assert Path(".harness/plans/demo/items/T1.report.md").exists()
assert Path(".harness/plans/demo/SUMMARY.md").exists()
assert Path(".harness/plans/demo/land.patch").exists()
assert Path("node_modules/pkg/i.js").read_text(encoding="utf-8") == "keep", "junction target deleted!"
assert not wt.exists(), "worktree dir still there"
assert "harness/demo" not in git("branch", "--list")
assert str(wt).replace("\\", "/").lower() not in git("worktree", "list").replace("\\", "/").lower()

# conflict: main changed the same line differently -> nothing changes, worktree kept
Path(".harness/plans/c").mkdir(parents=True)
wt2 = worktree.ensure("c")
(wt2 / "b.txt").write_text("from-plan\n", encoding="utf-8")
Path("b.txt").write_text("from-main\n", encoding="utf-8")
assert land.land("c") == 1
assert Path("b.txt").read_text(encoding="utf-8") == "from-main\n"
assert wt2.exists() and Path(".harness/plans/c/land.patch").exists()

# running plan -> refuse
Path(".harness/plans/r").mkdir(parents=True)
wt3 = worktree.ensure("r")
(wt3 / ".harness/plans/r").mkdir(parents=True, exist_ok=True)
(wt3 / ".harness/plans/r/run.lock").write_text("1", encoding="utf-8")
assert land.land("r") == 1 and wt3.exists()

# no worktree
assert land.land("nope") == 1
print("OK")
