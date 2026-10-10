"""`run_plan.py <slug> --land`: the user's one command to bring a finished worktree
plan into the main tree.

Order: copy the worktree's plan records into .harness/plans/<slug>, then perform
a git merge --ff-only to bring in the code changes. On success, drop the junctions,
the worktree and the branch. On failure, print git's message and leave everything
in place for manual recovery.
"""
import os
import shutil
import subprocess
from pathlib import Path

from . import worktree
from .plan import Plan


def _git(*args, **kwargs):
    return subprocess.run(["git", *args], capture_output=True, check=False, **kwargs)


def _known_worktrees():
    out = _git("worktree", "list", "--porcelain").stdout.decode("utf-8", "replace")
    return [Path(line[len("worktree "):]).resolve()
            for line in out.splitlines() if line.startswith("worktree ")]


def land(slug):
    """Apply the worktree changes of `slug` to the current (main) tree using a fast-forward
    merge, then remove the worktree. Returns 0 on success, 1 when there is nothing to land
    into or the merge fails."""
    wt = (Path.cwd() / worktree.path_for(slug)).resolve()
    if wt not in _known_worktrees():
        print(f"no worktree for {slug}")
        return 1
    if (wt / ".harness" / "plans" / slug / "run.lock").exists():
        print("run in progress")
        return 1

    # Copy plan records first (they are git-ignored)
    src = wt / ".harness" / "plans" / slug
    if src.is_dir():
        plan_dir = Path(".harness") / "plans" / slug
        plan_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, plan_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("run.lock"))

    # Count the files that will change (for the report message)
    _git("-C", str(wt), "add", "-N", "--", ".")
    numstat = _git("-C", str(wt), "diff", "--numstat", "HEAD", "--", ".",
                    f":(exclude).harness/plans/{slug}").stdout.decode("utf-8", "replace")
    changed = len([line for line in numstat.splitlines() if line.strip()])

    # Attempt the fast-forward merge
    merge = _git("merge", "--ff-only", f"harness/{slug}")
    if merge.returncode != 0:
        print(merge.stderr.decode("utf-8", "replace").strip())
        return 1

    # Success: clean up the worktree and branch
    for name in worktree.SHARED_DIRS:
        link = wt / name
        if os.path.isjunction(link):
            os.rmdir(link)  # the link only, never the shared target
    _git("worktree", "remove", "--force", str(wt))
    if wt.is_dir() and not any(wt.iterdir()):
        try:
            wt.rmdir()  # git left an empty dir behind; Windows may still hold a handle
        except OSError:
            pass
    _git("branch", "-D", f"harness/{slug}")
    print(f"landed {slug}: {changed} files")
    return 0


def land_from(slug, directory):
    """Apply the plan-listed changes of an outside git worktree `directory` (e.g. a
    Claude subagent worktree) to the current tree after `check` passes, then remove
    that worktree and its branch. Returns 0 on success, 1 otherwise."""
    if check.check(slug, directory) != 0:
        print(f"check failed; nothing landed, {directory} kept")
        return 1
    src = str(Path(directory).resolve())
    plan = Plan(slug, ".harness/plans")
    pathspecs = sorted({f for t in plan.tasks for f in t.norm_files})

    # intent-to-add, so new files show up; pathspecs keep out-of-scope edits out
    _git("-C", src, "add", "-N", "--", ".")
    patch = _git("-C", src, "diff", "--binary", "HEAD", "--", *pathspecs).stdout

    plan_dir = Path(".harness") / "plans" / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    patch_file = plan_dir / "land.patch"
    patch_file.write_bytes(patch)

    numstat = _git("apply", "--numstat", input=patch).stdout.decode("utf-8", "replace")
    changed = len([line for line in numstat.splitlines() if line.strip()])

    if patch:
        checked = _git("apply", "--check", input=patch)
        if checked.returncode != 0:
            print(checked.stderr.decode("utf-8", "replace").strip())
            print(f"nothing changed; {directory} kept, patch at {patch_file}")
            return 1
        applied = _git("apply", input=patch)
        if applied.returncode != 0:
            print(applied.stderr.decode("utf-8", "replace").strip())
            print(f"apply failed; {directory} kept, patch at {patch_file}")
            return 1

    branch = _git("-C", src, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode("utf-8", "replace").strip()
    _git("worktree", "remove", "--force", src)
    if branch and branch != "HEAD":
        _git("branch", "-D", branch)
    print(f"landed {slug}: {changed} files")
    return 0
