import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(".harness").resolve()))
from runner import worktree  # noqa: E402

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
Path(".gitignore").write_text("node_modules/\n.harness/.env\n", encoding="utf-8")
Path("a.txt").write_text("one\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "init")
Path("a.txt").write_text("two\n", encoding="utf-8")        # uncommitted edit
Path("new.txt").write_text("untracked\n", encoding="utf-8")  # untracked
Path("staged.txt").write_text("s\n", encoding="utf-8")
git("add", "staged.txt")                                     # user's own staged change
Path("node_modules/pkg").mkdir(parents=True)
Path("node_modules/pkg/i.js").write_text("x", encoding="utf-8")
Path(".harness").mkdir()
Path(".harness/.env").write_text("K=V\n", encoding="utf-8")
head = git("rev-parse", "HEAD")
index_before = git("diff", "--cached", "--name-only")
status_before = git("status", "--porcelain")

wt = worktree.ensure("demo")
assert wt.is_absolute() and wt == (repo / ".worktrees" / "demo").resolve(), wt
assert worktree.path_for("demo") == Path(".worktrees") / "demo"
assert (wt / "a.txt").read_text(encoding="utf-8") == "two\n"
assert (wt / "new.txt").exists() and (wt / "staged.txt").exists()
assert (wt / "node_modules/pkg/i.js").exists(), "node_modules not linked"
assert (wt / ".harness/.env").read_text(encoding="utf-8") == "K=V\n"
assert git("rev-parse", "HEAD") == head, "HEAD moved"
assert git("diff", "--cached", "--name-only") == index_before, "user index changed"
assert git("status", "--porcelain") == status_before, "main status changed (.worktrees not excluded?)"
assert "harness/demo" in git("branch", "--list", "harness/demo")
r = subprocess.run(["git", "-C", str(wt), "status", "--porcelain"], capture_output=True, text=True)
assert r.stdout.strip() == "", f"worktree not clean vs snapshot: {r.stdout}"
assert worktree.ensure("demo") == wt  # reuse
Path(".worktrees/bogus").mkdir()
r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                    "from runner import worktree; worktree.ensure('bogus')", str(Path(worktree.__file__).parents[1])],
                   capture_output=True, text=True)
assert r.returncode != 0, "non-worktree dir must fail"
print("OK")
