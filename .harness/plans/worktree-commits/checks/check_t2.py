import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(".harness").resolve()))
from runner.task_runner import commit_task  # noqa: E402

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
git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", "--allow-empty")

# a passing task commits its own files, with the harness identity
Path("src").mkdir()
Path("src/app.py").write_text("x = 1\n", encoding="utf-8")
sha = commit_task("demo", "T1", "add the thing", ["src/app.py"])
assert sha, "commit_task returned no sha"
assert git("rev-parse", "HEAD").strip() == sha, "HEAD is not the new commit"
assert git("log", "-1", "--pretty=%s").strip() == "harness(demo): T1 add the thing"
assert git("log", "-1", "--name-only", "--pretty=").split() == ["src/app.py"], "wrong files committed"
assert git("log", "-1", "--pretty=%an").strip() == "harness", git("log", "-1", "--pretty=%an")

# nothing to commit -> no empty commit, no sha
assert commit_task("demo", "T2", "nothing", ["src/app.py"]) is None
assert git("rev-list", "--count", "HEAD").strip() == "2", "an empty commit was created"

# files outside the task's list are never swept in
Path("src/other.py").write_text("y = 2\n", encoding="utf-8")
Path("stray.py").write_text("z = 3\n", encoding="utf-8")
commit_task("demo", "T3", "second", ["src/other.py"])
committed = git("show", "--name-only", "--pretty=", "HEAD").split()
assert committed == ["src/other.py"], f"out-of-scope file committed: {committed}"
assert git("status", "--porcelain").strip().endswith("stray.py"), "stray.py was committed"

# HARNESS_COMMIT_STYLE: short drops the slug, an unknown value falls back to full
os.environ["HARNESS_COMMIT_STYLE"] = "short"
Path("src/other.py").write_text("y = 2 modified\n", encoding="utf-8")
commit_task("demo", "T4", "third", ["src/other.py"])
assert git("log", "-1", "--pretty=%s").strip() == "T4: third", git("log", "-1", "--pretty=%s")
os.environ["HARNESS_COMMIT_STYLE"] = "nonsense"
Path("src/other.py").write_text("y = 2 modified again\n", encoding="utf-8")
commit_task("demo", "T5", "fourth", ["src/other.py"])
assert git("log", "-1", "--pretty=%s").strip() == "harness(demo): T5 fourth", \
    f"unknown style did not fall back to full: {git('log', '-1', '--pretty=%s')!r}"

print("OK")