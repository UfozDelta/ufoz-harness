import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
sys.path.insert(0, str(ROOT / ".harness" / "hooks"))
import git_guard  # noqa: E402
from runner import guards  # noqa: E402

DENY = git_guard.DEFAULT_DENY


def test_blocks_git_state_commands():
    for cmd in ["git commit -m x", "git stash", "git -C . reset --hard", "git -c a=b checkout main",
                "ls && git add -A", "echo hi | git push", "git worktree remove x"]:
        assert git_guard.blocked(cmd, DENY), cmd


def test_blocks_land():
    assert git_guard.blocked("python .harness/run_plan.py slug --land", DENY)
    assert git_guard.blocked("cd x; python .harness/run_plan.py slug --land --yes", DENY)


def test_allows_read_only_and_other_commands():
    for cmd in ["git status", "git diff HEAD", "git log --oneline", "git -C . status",
                "python .harness/run_plan.py slug --lint", "pytest -q", "echo git commit"]:
        assert git_guard.blocked(cmd, DENY) is None, cmd


def test_hook_exit_codes():
    script = str(ROOT / ".harness/hooks/git_guard.py")

    def run(stdin):
        return subprocess.run([sys.executable, script], input=stdin, capture_output=True, text=True)
    blocked = run(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git stash"}}))
    assert blocked.returncode == 2 and "git stash" in blocked.stderr
    assert run(json.dumps({"tool_input": {"command": "git status"}})).returncode == 0
    assert run("not json").returncode == 0


def test_deny_json_is_the_source():
    deny = json.loads((ROOT / ".pi/deny.json").read_text(encoding="utf-8"))["bash"]
    assert "git worktree" in deny
    assert set(git_guard.deny_list()) == set(deny)


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", *args], cwd=cwd,
                   check=True, capture_output=True)


def test_git_state_sees_a_commit_that_changes_no_file_hash(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        first = guards.git_state()
        _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "two")  # no file changes
        assert guards.git_state() != first
        assert guards.git_state()[1].startswith("refs/heads/")
    finally:
        os.chdir(cwd)


def test_git_state_none_outside_a_repo(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert guards.git_state() is None
    finally:
        os.chdir(cwd)


def test_land_refuses_without_a_terminal():
    out = subprocess.run([sys.executable, str(ROOT / ".harness/run_plan.py"), "nope", "--land"],
                         cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert out.returncode == 1 and "run it in a terminal" in out.stdout


def _hook(event):
    return subprocess.run([sys.executable, str(ROOT / ".harness/hooks/git_guard.py")],
                          input=json.dumps(event), capture_output=True, text=True)


def test_writes_must_stay_inside_a_worktree(tmp_path):
    # tmp_path is outside any worktree whatever ROOT is (this repo may itself sit in .worktrees/)
    inside = str(tmp_path / ".worktrees" / "p" / "a.py")
    assert _hook({"tool_name": "Write", "tool_input": {"file_path": inside}}).returncode == 0
    for bad in [str(tmp_path / "a.py"), ".worktrees/p/a.py", "a.py"]:
        out = _hook({"tool_name": "Edit", "tool_input": {"file_path": bad}})
        assert out.returncode == 2 and "outside a worktree" in out.stderr, bad
    claude_wt = str(tmp_path / ".claude" / "worktrees" / "agent-1" / "a.py")
    assert _hook({"tool_name": "Write", "tool_input": {"file_path": claude_wt}}).returncode == 0
