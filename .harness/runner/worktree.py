"""Per-plan git worktrees under .worktrees/, so several plans can run at once.

The worktree is a snapshot of the current tree (uncommitted edits and untracked,
non-ignored files included) built with a temporary index, so the user's index, HEAD
and branches are never touched. Nobody commits here: the user reviews and merges by
hand. Every git call goes through subprocess.run(..., check=False).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

time_sleep = time.sleep

WORKTREES_DIR = ".worktrees"
SHARED_DIRS = ("node_modules", ".venv", ".opencode/node_modules")
ENV_FILE = ".harness/.env"
IDENTITY = {"GIT_AUTHOR_NAME": "harness", "GIT_AUTHOR_EMAIL": "harness@localhost",
            "GIT_COMMITTER_NAME": "harness", "GIT_COMMITTER_EMAIL": "harness@localhost"}


def _git(*args, env=None):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          env=dict(os.environ, **IDENTITY, **(env or {})))


def in_git_repo():
    """True when the current tree is inside a git work tree."""
    return _git("rev-parse", "--is-inside-work-tree").stdout.strip() == "true"


def sync_plan(slug, target, source_root):
    """Copy the plan files (plan.md, tasks.json, checks/) of `slug` from `source_root`
    into the worktree's plan dir, overwriting what is there. Reports, logs, the lock
    and SUMMARY.md of the worktree are left alone."""
    src = Path(source_root) / ".harness" / "plans" / slug
    dst = Path(target) / ".harness" / "plans" / slug
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("plan.md", "tasks.json"):
        if (src / name).is_file():
            shutil.copyfile(src / name, dst / name)
    if (src / "checks").is_dir():
        shutil.copytree(src / "checks", dst / "checks", dirs_exist_ok=True)


def path_for(slug):
    """Worktree location for a plan, relative to the current tree."""
    return Path(WORKTREES_DIR) / slug


def _exclude_worktrees():
    """.worktrees/ in .git/info/exclude: local only, so no tracked file changes and
    neither the main tree's status nor the guard snapshot ever sees it."""
    exclude = Path(".git/info/exclude")
    try:
        current = exclude.read_text(encoding="utf-8")
    except OSError:
        current = ""
    if f"{WORKTREES_DIR}/" in current:
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as fh:
        if current and not current.endswith("\n"):
            fh.write("\n")
        fh.write(f"{WORKTREES_DIR}/\n")


def _known_worktrees():
    out = _git("worktree", "list", "--porcelain").stdout
    return [Path(line[len("worktree "):]).resolve()
            for line in out.splitlines() if line.startswith("worktree ")]


def _snapshot(slug):
    """Commit sha of the current tree, incl. uncommitted + untracked non-ignored files,
    built on a throwaway index. The user's index and HEAD stay as they are."""
    fd, index = tempfile.mkstemp(prefix="harness-index-")
    os.close(fd)
    os.unlink(index)
    env = {"GIT_INDEX_FILE": index}
    try:
        for args in (("read-tree", "HEAD"), ("add", "-A"), ("write-tree",)):
            r = _git(*args, env=env)
            if r.returncode != 0:
                sys.exit(f"worktree: {args[0]} failed: {r.stderr.strip() or r.stdout.strip()}")
        tree = r.stdout.strip()
        head = _git("rev-parse", "HEAD").stdout.strip()
        c = _git("commit-tree", tree, "-p", head, "-m", f"harness snapshot for {slug}", env=env)
        if c.returncode != 0:
            sys.exit(f"worktree: commit-tree failed: {c.stderr.strip()}")
        return c.stdout.strip()
    finally:
        if os.path.exists(index):
            os.unlink(index)


def _link(name, target):
    """Share a big, gitignored dir with the worktree instead of copying it."""
    src = Path(name)
    if not src.is_dir() or _git("check-ignore", "-q", name).returncode != 0:
        return
    dst = target / name
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src.resolve())],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"worktree: could not link {name}: {r.stderr.strip() or r.stdout.strip()}")
    else:
        shutil.copytree(src, dst, dirs_exist_ok=True)


def ensure(slug):
    """Create (or reuse) the worktree for `slug` and return its absolute path."""
    _exclude_worktrees()
    target = (Path.cwd() / path_for(slug)).resolve()
    if target in _known_worktrees():
        return target
    if target.exists():
        sys.exit(f"worktree: {path_for(slug)} exists but git does not know it as a worktree; "
                 f"remove or rename it, or run: git worktree prune")
    if _git("rev-parse", "--verify", "--quiet", f"refs/heads/harness/{slug}").returncode == 0:
        sys.exit(f"worktree: branch harness/{slug} already exists but {path_for(slug)} does not; "
                 f"delete the branch or use another slug")
    sha = _snapshot(slug)
    r = None
    for attempt in range(3):
        r = _git("worktree", "add", "-b", f"harness/{slug}", str(path_for(slug)), sha)
        if r.returncode == 0 or ".lock" not in (r.stderr or ""):
            break
        # several plans starting at once contend on git's lock files
        if attempt < 2 and time_sleep:
            time_sleep(1)
    if r.returncode != 0:
        sys.exit(f"worktree: git worktree add failed: {r.stderr.strip() or r.stdout.strip()}")
    for name in SHARED_DIRS:
        _link(name, target)
    if Path(ENV_FILE).is_file():
        (target / ENV_FILE).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ENV_FILE, target / ENV_FILE)
    return target
