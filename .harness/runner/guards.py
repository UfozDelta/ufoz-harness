"""Tree guards: what the executor is and is not allowed to change."""
import hashlib
import re
import subprocess
from pathlib import Path

# The three markers the harness hunts for, spelled in parts. The runner's own suppression
# guard counts these names in every file a task touches, and this module is exactly the
# file that must not look like it just added them -- a literal here reads as a fresh
# suppression comment even though it is the detector's data. The resulting strings are
# the same three tokens, so detection is unchanged.
_MARKER_PARTS = (("@ts", "ignore"), ("@ts", "nocheck"), ("eslint", "disable"))
SUPPRESSION_MARKERS = tuple(f"{prefix}-{suffix}" for prefix, suffix in _MARKER_PARTS)


def snapshot():
    """path -> sha256 for every tracked + untracked, non-ignored file. Content hashes,
    not `git status`: nobody commits here, so an edit to an already-dirty file is
    invisible to a status diff but not to a hash diff."""
    r = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"], capture_output=True)
    if r.returncode != 0:
        return None
    snap = {}
    for f in r.stdout.decode("utf-8", "replace").split("\0"):
        if f:
            try:
                snap[f] = hashlib.sha256(Path(f).read_bytes()).hexdigest()
            except OSError:  # tracked but deleted
                snap[f] = None
    return snap


def lock_hashes(plan):
    """sha256 of every file that decides pass/fail: tasks.json + checks/*.py.
    The executor must never be able to edit its own grader."""
    files = [plan / "tasks.json", *sorted((plan / "checks").glob("*.py"))]
    return {f.as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.exists()}


def _other_plan(f, plan):
    """True for files under a sibling plan's dir (a direct child of the plans root other
    than our own). Concurrent runs in worktrees write their own plan's files, so those
    are runner-owned too; our own plan's dir is deliberately excluded."""
    root = plan.parent.as_posix()
    prefix = f"{root}/"
    if not f.startswith(prefix):
        return False
    head, _, tail = f[len(prefix):].partition("/")
    return bool(tail) and f"{root}/{head}" != plan.as_posix()


def runner_owned(f, run_lock, plan, metrics):
    """reports, feedback, logs, metrics, other plans' files, and TypeScript buildinfo the
    runner itself owns"""
    return (f == run_lock.as_posix() or f.startswith(f"{plan.as_posix()}/logs/") or f == metrics.as_posix()
            or _other_plan(f, plan)
            or f.endswith(".tsbuildinfo")
            or (f.startswith(f"{plan.as_posix()}/items/")
                and (f.endswith((".report.md", ".feedback.md", ".metrics.json"))
                     or re.search(r"\.repair\d+\.md$", f))))


def marker_counts(f):
    try:
        text = Path(f).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return dict.fromkeys(SUPPRESSION_MARKERS, 0)
    return {marker: sum(1 for line in text.splitlines() if marker in line)
            for marker in SUPPRESSION_MARKERS}


def suppression_markers(touched, baseline):
    found = []
    for f in touched:
        counts = marker_counts(f)
        old = baseline.get(f, {"total": 0, "counts": dict.fromkeys(counts, 0)})
        if sum(counts.values()) <= old["total"]:
            continue
        found += [f"{f}: {marker}" for marker, count in counts.items()
                  if count > old["counts"].get(marker, 0)]
    return found
