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
# a command starts after a separator, a subshell/command-substitution opener or a backtick
SEGMENT = re.compile(r"&&|\|\||;|\||\n|\r|`|\$\(|\(|\)")
TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|' + r"'([^']*)'|(\S+)")
WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "xargs"}
SHELLS = {"sh", "bash", "zsh", "dash", "sh.exe", "bash.exe"}
# `git`, then global options that take a separate value, then the subcommand
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
LAND = re.compile(r"run_plan\.py\b.*--land\b")


def deny_list():
    path = Path(__file__).resolve().parents[2] / ".pi" / "deny.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("bash", DEFAULT_DENY)
    except (OSError, ValueError):
        return DEFAULT_DENY


def _base(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _check(tokens, deny, depth):
    i = 0
    while i < len(tokens) and (re.match(r"^[A-Za-z_]\w*=", tokens[i]) or tokens[i] in WRAPPERS
                               or (i and tokens[i].startswith("-") and tokens[i - 1] in WRAPPERS)):
        i += 1
    if i >= len(tokens):
        return None
    head = _base(tokens[i])
    if head in SHELLS:
        if "-c" in tokens[i + 1:] and depth < 3:
            c = tokens.index("-c", i + 1)
            if c + 1 < len(tokens):
                return blocked(tokens[c + 1], deny, depth + 1)
        return None
    if head not in ("git", "git.exe"):
        return None
    j = i + 1
    while j < len(tokens) and tokens[j].startswith("-"):
        opt = tokens[j].split("=")[0]
        j += 2 if opt in GIT_OPTS_WITH_VALUE and "=" not in tokens[j] else 1
    if j < len(tokens) and f"git {tokens[j]}" in deny:
        return f"git {tokens[j]}"
    return None


def blocked(command, deny, depth=0):
    """The denied thing a shell command would run, or None. Looks at every command position,
    through wrappers (env, sudo, xargs ...), `sh -c "..."` and subshells."""
    for part in SEGMENT.split(command):
        if LAND.search(part):
            return "run_plan.py --land"
        tokens = [m[1] or m[2] or m[3] for m in TOKEN.finditer(part)]
        hit = _check(tokens, deny, depth)
        if hit:
            return hit
    return None


WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
WORKTREE_DIRS = (".worktrees", ".claude/worktrees")


def outside_worktree(path):
    """True when a path to write is not inside a worktree dir. Relative paths resolve against
    the main tree, so they count as outside: the agent is told to use absolute paths. The
    path is resolved first, so `.worktrees/x/../../src/a.py` does not count as inside."""
    if not Path(str(path)).is_absolute():
        return True
    norm = "/" + Path(str(path)).resolve().as_posix().lstrip("/")
    return not any(f"/{d}/" in norm for d in WORKTREE_DIRS)


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
