"""Grade work done outside the runner (e.g. by @haiku-executor in a git worktree): the grader
lock, the file scope, and every task's acceptance, run inside that worktree."""
import os
import subprocess
from pathlib import Path

from .acceptance import run_acceptance
from .plan import Plan, in_scope

# Paths the harness itself writes or Claude Code keeps: never part of a task's scope.
IGNORED_PREFIXES = (".harness/plans/", ".claude/", ".worktrees/")


def changed_files(root):
    """Changed and untracked files of the git worktree at `root`, one path per file."""
    proc = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-uall"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, proc.stdout, proc.stderr)
    paths = set()
    for line in proc.stdout.splitlines():
        path = line[3:]
        if " -> " in path:  # renames: the new path is the one that exists now
            path = path.split(" -> ", 1)[1]
        paths.add(path.strip('"').replace("\\", "/"))
    return sorted(paths)


def scope_violations(changed, task_files):
    """Sorted changed paths that no task's `files` entry covers (ignored prefixes skipped)."""
    entries = [f.replace("\\", "/") for f in task_files]
    out = []
    for path in changed:
        path = path.replace("\\", "/")
        if path.startswith(IGNORED_PREFIXES) or in_scope(path, entries):
            continue
        out.append(path)
    return sorted(out)


def check(slug, root):
    """Print PASS|FAIL per task, LOCK per broken grader file, SCOPE per violation; 0 only if clean."""
    root = Path(root).resolve()
    plan = Plan(slug, ".harness/plans")  # plan files come from the main tree, the cwd here
    broken = plan.lock_broken()
    for path in broken:
        print(f"LOCK {path}")
    try:
        changed = changed_files(root)
    except subprocess.CalledProcessError as err:
        print(f"ERROR git status failed in {root}: {err.stderr.strip() if err.stderr else err}")
        return 1
    allowed = sorted({f for t in plan.tasks for f in t.norm_files})
    violations = scope_violations(changed, allowed)
    for path in violations:
        print(f"SCOPE {path}")
    all_passed = True
    home = Path.cwd()
    os.chdir(root)  # acceptance commands run from the worktree root
    try:
        for t in plan.tasks:
            passed, out = run_acceptance(t.acceptance, t.expect)
            print(f"{'PASS' if passed else 'FAIL'} {t.id}")
            if not passed:
                all_passed = False
                print(out.strip()[-500:])
    finally:
        os.chdir(home)
    return 0 if all_passed and not broken and not violations else 1
