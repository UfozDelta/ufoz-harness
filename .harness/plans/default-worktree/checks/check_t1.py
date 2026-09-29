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


plain = Path(tempfile.mkdtemp())
os.chdir(plain)
assert worktree.in_git_repo() is False

repo = Path(tempfile.mkdtemp()) / "repo"
repo.mkdir()
os.chdir(repo)
git("init", "-q")
Path("a.txt").write_text("a\n", encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "init")
assert worktree.in_git_repo() is True
p = Path(".harness/plans/demo")
(p / "checks").mkdir(parents=True)
(p / "plan.md").write_text("v1\n", encoding="utf-8")
(p / "tasks.json").write_text('{"v": 1}\n', encoding="utf-8")
(p / "checks/check_t1.py").write_text("print(1)\n", encoding="utf-8")
wt = worktree.ensure("demo")
wp = wt / ".harness/plans/demo"
(wp / "items").mkdir(parents=True, exist_ok=True)
(wp / "items/T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
(wp / "plan.lock.json").write_text("{}\n", encoding="utf-8")
(p / "plan.md").write_text("v2\n", encoding="utf-8")
(p / "tasks.json").write_text('{"v": 2}\n', encoding="utf-8")
(p / "checks/check_t1.py").write_text("print(2)\n", encoding="utf-8")
(p / "checks/check_t2.py").write_text("print(3)\n", encoding="utf-8")
(p / "items").mkdir()
(p / "items/T1.report.md").write_text("MAIN\n", encoding="utf-8")
worktree.sync_plan("demo", wt, repo)
assert (wp / "plan.md").read_text(encoding="utf-8") == "v2\n"
assert (wp / "tasks.json").read_text(encoding="utf-8") == '{"v": 2}\n'
assert (wp / "checks/check_t1.py").read_text(encoding="utf-8") == "print(2)\n"
assert (wp / "checks/check_t2.py").exists()
assert (wp / "items/T1.report.md").read_text(encoding="utf-8") == "RESULT: pass\n", "items must not sync"
assert (wp / "plan.lock.json").read_text(encoding="utf-8") == "{}\n", "lock must not sync"
calls = []
real = worktree._git
def flaky(*a, **k):
    if a[:2] == ("worktree", "add"):
        calls.append(a)
        if len(calls) < 3:
            return subprocess.CompletedProcess(a, 128, "", "fatal: Unable to create '.git/config.lock': File exists")
    return real(*a, **k)
worktree._git = flaky
worktree.time_sleep = None
import time as _t
_orig_sleep = _t.sleep
_t.sleep = lambda s: None
wt2 = worktree.ensure("demo2")
_t.sleep = _orig_sleep
worktree._git = real
assert wt2.exists() and len(calls) == 3, calls
print("OK")
