"""`run_plan.py <slug> --land`: the user's one command to bring a finished worktree
plan into the main tree.

Order: a git merge --ff-only brings in the code changes, then the worktree's plan
records are copied into .harness/plans/<slug>. On success, drop the junctions,
the worktree and the branch. On failure, print git's message and leave everything
in place for manual recovery.
"""
import os
import shutil
import subprocess
from pathlib import Path

from . import worktree


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

    # Count the files that will change (for the report message)
    numstat = _git("diff", "--numstat", f"HEAD...harness/{slug}", "--", ".",
                    f":(exclude).harness/plans/{slug}").stdout.decode("utf-8", "replace")
    changed = len([line for line in numstat.splitlines() if line.strip()])

    # Attempt the fast-forward merge
    merge = _git("merge", "--ff-only", f"harness/{slug}")
    if merge.returncode != 0:
        print(merge.stderr.decode("utf-8", "replace").strip())
        return 1

    # Copy plan records after the merge: the branch may already carry tracked ones (SUMMARY.md),
    # and an untracked copy in this tree would make the merge abort.
    src = wt / ".harness" / "plans" / slug
    if src.is_dir():
        plan_dir = Path(".harness") / "plans" / slug
        plan_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, plan_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("run.lock"))

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
