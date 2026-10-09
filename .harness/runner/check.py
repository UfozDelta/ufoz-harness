"""Grade work done outside the runner (e.g. by @haiku-executor in a git worktree): the grader
lock, the file scope, and every task's acceptance, run inside that worktree."""
import json
import os
import subprocess
from pathlib import Path

from .acceptance import run_acceptance
from .guards import GIT_MOVED, git_state, snapshot
from .plan import Plan, in_scope

# Paths the harness itself writes or Claude Code keeps: never part of a task's scope.
IGNORED_PREFIXES = (".harness/plans/", ".claude/", ".worktrees/")
# Main-tree paths a run may legitimately touch while an agent works in its worktree.
IGNORED_MAIN = (".harness/plans/", ".harness/metrics.jsonl", ".worktrees/", ".claude/worktrees/")
BASELINE = "main.baseline.json"


def write_baseline(slug):
    """Photograph the main tree (file hashes + git HEAD/branch) for `--check` to compare against.
    Written by `--prepare`, because the agent is meant to touch only its worktree."""
    plan_dir = Path(".harness/plans") / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = git_state()
    (plan_dir / BASELINE).write_text(
        json.dumps({"files": snapshot(), "git": list(state) if state else None}), encoding="utf-8")


def main_changes(slug):
    """Main-tree paths that differ from the `--prepare` photograph (plus GIT_MOVED if HEAD or the
    branch moved). None when there is no photograph, i.e. the worktree was not made by --prepare."""
    path = Path(".harness/plans") / slug / BASELINE
    if not path.is_file():
        return None
    base = json.loads(path.read_text(encoding="utf-8"))
    now = snapshot()
    changed = []
    if now is not None and base.get("files") is not None:
        before = base["files"]
        changed = sorted(f for f in before.keys() | now.keys()
                         if before.get(f) != now.get(f)
                         and not f.startswith(IGNORED_MAIN) and not f.endswith(".tsbuildinfo"))
    state = git_state()
    if base.get("git") and state and list(state) != base["git"]:
        changed.append(GIT_MOVED)
    return changed


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
    moved = main_changes(slug) or []
    for path in moved:
        print(f"MAIN {path}")
    if moved:
        print("main tree changed since --prepare: an agent write outside the worktree, or your own edit")
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
    return 0 if all_passed and not broken and not violations and not moved else 1
