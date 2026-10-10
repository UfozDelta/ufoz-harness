"""PreToolUse hook for the claude-executor subagent: block git state changes and --land, and
keep its file writes inside a worktree directory (.worktrees/<slug>, the runner's own layout).

Registered in .claude/agents/claude-executor.md and planner.md (the latter with `--writes .harness/plans`), so it only guards those agents; the main
session keeps normal permission prompts. The deny list is .pi/deny.json (the same one the
runner executors use), so there is one source. Exit 2 blocks the call and shows the message.
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_DENY = ["git add", "git commit", "git push", "git reset", "git checkout", "git switch",
                "git restore", "git stash", "git clean", "git rebase", "git merge", "git branch",
                "git worktree"]
SEGMENT = re.compile(r"&&|\|\||;|\||\n")
# `git`, then global options (-C dir, -c k=v, --git-dir=..), then the subcommand
GIT = re.compile(r"^\s*git\s+(?:(?:-[Cc]\s+\S+|--\S+)\s+)*([a-z][a-z-]*)")
LAND = re.compile(r"run_plan\.py\b.*--land\b")


def deny_list():
    path = Path(__file__).resolve().parents[2] / ".pi" / "deny.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("bash", DEFAULT_DENY)
    except (OSError, ValueError):
        return DEFAULT_DENY


def blocked(command, deny):
    """The denied thing a shell command would run, or None."""
    for part in SEGMENT.split(command):
        if LAND.search(part):
            return "run_plan.py --land"
        m = GIT.match(part)
        if m and f"git {m.group(1)}" in deny:
            return f"git {m.group(1)}"
    return None


WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
WORKTREE_DIRS = (".worktrees", ".claude/worktrees")


def outside_worktree(path):
    """True when a path to write is not inside a worktree dir. Relative paths resolve against
    the main tree, so they count as outside: the agent is told to use absolute paths."""
    norm = "/" + str(path).replace("\\", "/").lstrip("/")
    return not any(f"/{d}/" in norm for d in WORKTREE_DIRS) or not Path(str(path)).is_absolute()


def outside_dir(path, allowed):
    """True when a path is not under the allowed dir (`--writes DIR`, relative to the repo root)."""
    root = Path(__file__).resolve().parents[2]
    try:
        Path(path if Path(path).is_absolute() else root / path).resolve().relative_to((root / allowed).resolve())
        return False
    except ValueError:
        return True


def main():
    allowed = sys.argv[sys.argv.index("--writes") + 1] if "--writes" in sys.argv else None
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # not our event: never block on a parse error
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") in WRITE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if allowed and path and outside_dir(path, allowed):
            print(f"blocked: write outside {allowed} ({path}).", file=sys.stderr)
            return 2
        if not allowed and path and outside_worktree(path):
            print(f"blocked: write outside a worktree ({path}). Edit only under .worktrees/<slug>, "
                  "with absolute paths.", file=sys.stderr)
            return 2
        return 0
    command = tool_input.get("command") or ""
    hit = blocked(command, deny_list())
    if hit:
        print(f"blocked: {hit}. Subagents never change git state or land; the main session does.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
