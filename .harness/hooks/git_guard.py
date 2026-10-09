"""PreToolUse hook for the claude-executor subagent: block git state changes and --land.

Registered in .claude/agents/claude-executor.md, so it only guards that agent; the main
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


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # not our event: never block on a parse error
    command = (event.get("tool_input") or {}).get("command") or ""
    hit = blocked(command, deny_list())
    if hit:
        print(f"blocked: {hit}. Executors never change git state or land; the user does.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
