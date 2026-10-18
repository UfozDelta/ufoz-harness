"""Per-plan git worktrees under .worktrees/, so several plans can run at once.

A plan's worktree starts at real HEAD, so the tree must be clean when it is created:
the runner refuses to start on uncommitted edits, and everything the runner does inside
the worktree is ordinary git that can be reviewed with git log/git diff and landed with
git merge --ff-only. The synthetic snapshot path (_snapshot) stays only for throwaway
worktrees made with `exclude`/`orphan`, which are never landed. Every git call goes
through subprocess.run(..., check=False).
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
OPENCODE_PKG = (".opencode/package.json", ".opencode/package-lock.json")
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
    exclude = Path(_git("rev-parse", "--git-path", "info/exclude").stdout.strip() or ".git/info/exclude")
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


def _snapshot(slug, exclude=(), orphan=False):
    """Commit sha of the current tree, incl. uncommitted + untracked non-ignored files,
    built on a throwaway index. The user's index and HEAD stay as they are.
    `exclude`: paths left out of the snapshot entirely (not even as git objects in it).
    `orphan`: no parent commit, so `git show HEAD~1:<path>` reaches nothing of the main
    history (for throwaway worktrees that are never landed)."""
    fd, index = tempfile.mkstemp(prefix="harness-index-")
    os.close(fd)
    os.unlink(index)
    env = {"GIT_INDEX_FILE": index}
    steps = [("read-tree", "HEAD"), ("add", "-A")]
    if exclude:
        steps.append(("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *exclude))
    steps.append(("write-tree",))
    try:
        for args in steps:
            r = _git(*args, env=env)
            if r.returncode != 0:
                sys.exit(f"worktree: {args[0]} failed: {r.stderr.strip() or r.stdout.strip()}")
        tree = r.stdout.strip()
        parent = [] if orphan else ["-p", _git("rev-parse", "HEAD").stdout.strip()]
        c = _git("commit-tree", tree, *parent, "-m", f"harness snapshot for {slug}", env=env)
        if c.returncode != 0:
            sys.exit(f"worktree: commit-tree failed: {c.stderr.strip()}")
        return c.stdout.strip()
    finally:
        if os.path.exists(index):
            os.unlink(index)


def _link(name, target):
    """Share a big, gitignored dir with the worktree instead of copying it.

    Inside a linked worktree the shared dir only exists in the main tree (the parent
    of the common git dir), so the source is looked up there; falls back to the
    current tree when that copy is absent."""
    src = Path(name)
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    root = Path(common).parent if common else None
    main = root / name if root is not None and (root / name).is_dir() else None
    if main is not None:
        src = main
        ignored = _git("-C", str(root), "check-ignore", "-q", str(src)).returncode == 0
    else:
        ignored = _git("check-ignore", "-q", name).returncode == 0
    if not src.is_dir() or not ignored:
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


def _lf_agents(target):
    """git on Windows (core.autocrlf) checks the worktree out with CRLF, and Claude Code then
    cannot find agent files that have a hooks block (`--agent claude-executor` fails). Agent
    files are LF in the repo, so rewrite them LF here. Under autocrlf git still flags the LF
    rewrite as modified and `--land` refuses, so mark the files skip-worktree."""
    files = list((target / ".claude" / "agents").glob("*.md"))
    for f in files:
        raw = f.read_bytes()
        if b"\r\n" in raw:
            f.write_bytes(raw.replace(b"\r\n", b"\n"))
    if files:
        _git("-C", str(target), "update-index", "--skip-worktree", *(str(f) for f in files))


def _dirty_paths(slug=None):
    """Porcelain paths of uncommitted edits and untracked non-ignored files.
    `slug`: the plan dir `.harness/plans/<slug>/` of the plan being run is left out
    (matched on a path-component boundary, so `x` does not hide `xy`). With a `slug`,
    untracked files are listed one by one: git's default collapses them into a single
    directory entry, which would hide sibling plan dirs as well."""
    out = _git("status", "--porcelain", *(["--untracked-files=all"] if slug else [])).stdout
    skip = f".harness/plans/{slug}/" if slug else None
    paths = []
    for line in out.splitlines():
        entry = line[3:].strip() if len(line) > 3 else ""
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        entry = entry.replace("\\", "/").rstrip("/")
        if skip and (entry == skip[:-1] or entry.startswith(skip)):
            continue
        if entry:
            paths.append(entry)
    return paths


def _require_clean_tree(slug=None):
    """Hard refuse: a plan worktree starts at HEAD, so uncommitted edits cannot be part
    of it. Commit or stash them, then rerun. `slug`: see _dirty_paths."""
    dirty = _dirty_paths(slug)
    if dirty:
        sys.exit("worktree: the tree has uncommitted changes and a plan worktree starts at "
                 f"HEAD:\n  {chr(10).join('  ' + p for p in dirty)}\n"
                 "commit or stash them, then rerun")


def _prune_stale(target, slug):
    """A directory at `target` git does not know: let git prune it, then drop what is
    left over when it is not a worktree. A dir git knows is never touched."""
    _git("worktree", "prune")
    if not target.exists():
        return
    if not (target / ".git").exists():
        shutil.rmtree(target, ignore_errors=True)
        return
    sys.exit(f"worktree: {path_for(slug)} exists but git does not know it as a worktree; "
             f"remove or rename it, or run: git worktree prune")


def ensure(slug, exclude=(), orphan=False):
    """Create (or reuse) the worktree for `slug` and return its absolute path.
    `exclude`/`orphan`: see _snapshot (used by harness-suite; plans that land use neither)."""
    _exclude_worktrees()
    target = (Path.cwd() / path_for(slug)).resolve()
    if target in _known_worktrees():
        return target
    if target.exists():
        _prune_stale(target, slug)
    if _git("rev-parse", "--verify", "--quiet", f"refs/heads/harness/{slug}").returncode == 0:
        sys.exit(f"worktree: branch harness/{slug} already exists but {path_for(slug)} does not; "
                 f"delete the branch or use another slug")
    if exclude or orphan:
        base = _snapshot(slug, exclude, orphan)
    else:
        _require_clean_tree(slug)
        base = "HEAD"
    r = None
    for attempt in range(3):
        r = _git("worktree", "add", "-b", f"harness/{slug}", str(path_for(slug)), base)
        if r.returncode == 0 or ".lock" not in (r.stderr or ""):
            break
        # several plans starting at once contend on git's lock files
        if attempt < 2 and time_sleep:
            time_sleep(1)
    if r.returncode != 0:
        sys.exit(f"worktree: git worktree add failed: {r.stderr.strip() or r.stdout.strip()}")
    _lf_agents(target)
    for name in SHARED_DIRS:
        _link(name, target)
    for name in (ENV_FILE, *OPENCODE_PKG):  # gitignored, so the checkout lacks them
        if Path(name).is_file() and not (target / name).exists():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, target / name)
    return target
