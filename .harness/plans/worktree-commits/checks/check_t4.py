import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(".harness").resolve()))
from runner import land, worktree  # noqa: E402

ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t")


def git(*a, cwd=None):
    r = subprocess.run(["git", *a], capture_output=True, text=True, env=ENV,
                       cwd=str(cwd) if cwd else None)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout


repo = Path(tempfile.mkdtemp()) / "repo"
repo.mkdir()
os.chdir(repo)
git("init", "-q")
Path(".gitignore").write_text("node_modules/\n", encoding="utf-8")
Path("a.txt").write_text("one\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "init")
Path("node_modules/pkg").mkdir(parents=True)
Path("node_modules/pkg/i.js").write_text("keep", encoding="utf-8")
Path(".harness/plans/demo").mkdir(parents=True)
Path(".harness/plans/demo/plan.md").write_text("p\n", encoding="utf-8")


def work(wt, name, text):
    (wt / name).write_text(text, encoding="utf-8")
    git("-C", str(wt), "add", "-A", "--", name)
    git("-C", str(wt), "commit", "-qm", f"harness(demo): T1 {name}")


# fast-forward: the branch is just commits ahead of HEAD
wt = worktree.ensure("demo")
work(wt, "a.txt", "one\nTWO\n")
(wt / "new.py").write_text("x = 1\n", encoding="utf-8")
git("-C", str(wt), "add", "-A", "--", "new.py")
git("-C", str(wt), "commit", "-qm", "harness(demo): T1 new.py")
tip = git("-C", str(wt), "rev-parse", "HEAD").strip()
(wt / ".harness/plans/demo/items").mkdir(parents=True, exist_ok=True)
(wt / ".harness/plans/demo/items/T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
(wt / ".harness/plans/demo/SUMMARY.md").write_text("sum\n", encoding="utf-8")

assert land.land("demo") == 0
assert git("rev-parse", "HEAD").strip() == tip, "land did not fast-forward HEAD to the branch tip"
assert Path("a.txt").read_text(encoding="utf-8") == "one\nTWO\n"
assert Path("new.py").read_text(encoding="utf-8") == "x = 1\n", "new file not landed"
assert Path(".harness/plans/demo/items/T1.report.md").exists(), "report not copied"
assert Path(".harness/plans/demo/SUMMARY.md").exists(), "SUMMARY.md not copied"
assert not Path(".harness/plans/demo/land.patch").exists(), "land.patch is gone for good"
assert Path("node_modules/pkg/i.js").read_text(encoding="utf-8") == "keep", "junction target deleted!"
assert not wt.exists(), "worktree dir still there"
assert "harness/demo" not in git("branch", "--list")

# main moved on: --ff-only refuses, and everything is left for a human
wt2 = worktree.ensure("c")
work(wt2, "b.txt", "from-plan\n")
Path("b.txt").write_text("from-main\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "main moved on")
before = git("rev-parse", "HEAD").strip()
assert land.land("c") == 1, "land must refuse when HEAD moved"
assert git("rev-parse", "HEAD").strip() == before, "nothing changed here"
assert Path("b.txt").read_text(encoding="utf-8") == "from-main\n", "plan's file leaked into main"
assert wt2.exists() and "harness/c" in git("branch", "--list"), "worktree/branch must survive"

# a run in progress is still refused
Path(".harness/plans/r").mkdir(parents=True, exist_ok=True)
wt3 = worktree.ensure("r")
(wt3 / ".harness/plans/r").mkdir(parents=True, exist_ok=True)
(wt3 / ".harness/plans/r/run.lock").write_text("1", encoding="utf-8")
assert land.land("r") == 1 and wt3.exists()

assert land.land("nope") == 1
print("OK")