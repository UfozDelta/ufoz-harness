"""--pending: list the plan worktrees under root that are not landed yet.

One line per worktree dir: <slug>  <passed>/<total> tasks passed  <n> changed files
plus "  (running)" while the plan's run lock is there. Nothing is run and nothing
is written; a missing root or no dirs prints "no unlanded worktrees".
"""
import json
import subprocess
from pathlib import Path


def _total(worktree, slug):
    """Total tasks in the worktree's own copy of the plan (0 if it has none yet)."""
    path = worktree / ".harness" / "plans" / slug / "tasks.json"
    if not path.is_file():
        return 0
    try:
        return len(json.loads(path.read_text(encoding="utf-8")).get("tasks", []))
    except (OSError, ValueError):
        return 0


def _passed(worktree, slug):
    """How many item reports start with RESULT: pass."""
    items = worktree / ".harness" / "plans" / slug / "items"
    if not items.is_dir():
        return 0
    passed = 0
    for report in items.glob("*.report.md"):
        try:
            first = report.read_text(encoding="utf-8").splitlines()[:1]
        except OSError:
            continue
        if first and first[0].strip() == "RESULT: pass":
            passed += 1
    return passed


def _changed(worktree, slug):
    """Non-empty lines of the worktree's own git status, plan records excluded."""
    proc = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain", "--", ".",
         f":(exclude).harness/plans/{slug}"],
        capture_output=True, text=True, check=False)
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def pending(root=".worktrees"):
    """Print one line per worktree under root; always returns 0."""
    root = Path(root)
    # only real worktrees have a .git file; leftover empty dirs are skipped, no git call
    dirs = sorted(d for d in root.iterdir() if d.is_dir() and (d / ".git").exists()) \
        if root.is_dir() else []
    if not dirs:
        print("no unlanded worktrees")
        return 0
    for worktree in dirs:
        slug = worktree.name
        running = (worktree / ".harness" / "plans" / slug / "run.lock").exists()
        print(f"{slug}  {_passed(worktree, slug)}/{_total(worktree, slug)} tasks passed  "
              f"{_changed(worktree, slug)} changed files{'  (running)' if running else ''}")
    return 0
