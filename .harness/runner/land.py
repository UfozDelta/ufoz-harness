"""`run_plan.py <slug> --land`: the user's one command to bring a finished worktree
plan into the main tree.

Order: build a binary patch of the worktree's code changes (the plan records are
copied separately, never patched), always keep it at .harness/plans/<slug>/land.patch,
apply it if it is clean, copy the plan records, then drop the junctions, the worktree
and the branch. Every git call goes through subprocess.run(..., check=False) and the
patch is handled as BYTES, never decoded as text.
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
    """Apply the worktree changes of `slug` to the current (main) tree and remove the
    worktree. Returns 0 on success, 1 when there is nothing to land into."""
    wt = (Path.cwd() / worktree.path_for(slug)).resolve()
    if wt not in _known_worktrees():
        print(f"no worktree for {slug}")
        return 1
    if (wt / ".harness" / "plans" / slug / "run.lock").exists():
        print("run in progress")
        return 1

    # intent-to-add, so new files show up in the diff; only the worktree's index moves
    _git("-C", str(wt), "add", "-N", "--", ".")
    patch = _git("-C", str(wt), "diff", "--binary", "HEAD", "--", ".",
                  f":(exclude).harness/plans/{slug}").stdout

    plan_dir = Path(".harness") / "plans" / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    patch_file = plan_dir / "land.patch"
    patch_file.write_bytes(patch)

    numstat = _git("apply", "--numstat", input=patch).stdout.decode("utf-8", "replace")
    changed = len([line for line in numstat.splitlines() if line.strip()])

    if patch:
        check = _git("apply", "--check", input=patch)
        if check.returncode != 0:
            print(check.stderr.decode("utf-8", "replace").strip())
            print(f"nothing changed; patch kept at {patch_file}")
            return 1
        applied = _git("apply", input=patch)
        if applied.returncode != 0:
            print(applied.stderr.decode("utf-8", "replace").strip())
            print(f"apply failed; worktree kept, patch at {patch_file}")
            return 1

    src = wt / ".harness" / "plans" / slug
    if src.is_dir():
        shutil.copytree(src, plan_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("run.lock"))

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
