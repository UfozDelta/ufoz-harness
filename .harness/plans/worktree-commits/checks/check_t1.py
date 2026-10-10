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
Path(".gitignore").write_text("node_modules/\n", encoding="utf-8")
Path("a.txt").write_text("one\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "init")
head = git("rev-parse", "HEAD").strip()

# 1. dirty tree: untracked file -> hard refuse
Path("dirty.txt").write_text("x\n", encoding="utf-8")
try:
    worktree.ensure("demo")
    raise AssertionError("expected SystemExit on an untracked file")
except SystemExit as exc:
    assert "dirty.txt" in str(exc), exc

# 2. dirty tree: modified tracked file -> hard refuse
Path("dirty.txt").unlink()
Path("a.txt").write_text("one\ntwo\n", encoding="utf-8")
try:
    worktree.ensure("demo")
    raise AssertionError("expected SystemExit on a modified tracked file")
except SystemExit as exc:
    assert "a.txt" in str(exc), exc
git("checkout", "--", "a.txt")
assert not git("status", "--porcelain").strip(), "worktree dir leaked into git status"

# 3. clean tree: worktree branches from real HEAD, not a synthetic snapshot
wt = worktree.ensure("demo")
branch_tip = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True,
                            text=True, env=ENV).stdout.strip()
assert branch_tip == head, f"branch base is not HEAD: {branch_tip} != {head}"
subjects = subprocess.run(["git", "-C", str(wt), "log", "--oneline"], capture_output=True,
                          text=True, env=ENV).stdout
assert "harness snapshot" not in subjects, f"synthetic snapshot commit still used:\n{subjects}"

# 4. a directory git does not know is pruned, not a dead end
stale = Path(".worktrees/stale")
stale.mkdir(parents=True, exist_ok=True)
(stale / "junk.txt").write_text("j\n", encoding="utf-8")
wt2 = worktree.ensure("stale")
assert (wt2 / "a.txt").exists(), "stale dir not pruned"
assert not (stale / "junk.txt").exists(), "stale contents survived"

# 5. the bench path (exclude/orphan) is untouched: still runs on a dirty tree
Path("bench.txt").write_text("untracked\n", encoding="utf-8")
wt3 = worktree.ensure("bench", exclude=["bench.txt"], orphan=True)
assert (wt3 / "a.txt").exists(), "bench worktree not created on a dirty tree"

print("OK")