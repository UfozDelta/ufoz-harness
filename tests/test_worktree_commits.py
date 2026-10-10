import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
from runner import guards  # noqa: E402


def _git(cwd, *args):
    """Run git command in cwd with minimal config."""
    subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", *args], cwd=cwd,
                   check=True, capture_output=True)


def test_git_state_detects_commit_moved_head(tmp_path):
    """Executor-side commit is still detected as GIT_MOVED: git_state() changes on commit."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Snapshot and git_state before task
        state_before = guards.git_state()
        assert state_before is not None, "git_state should return a value in a repo"

        # Executor makes a commit (this would fail with guards, but simulating it here)
        _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "executor commit")

        # git_state after the commit is different
        state_after = guards.git_state()
        assert state_before != state_after, "git_state should change after a commit"
        # The guard in task_runner.py line 190 would detect this and add GIT_MOVED
    finally:
        os.chdir(cwd)


def test_snapshot_baseline_absorbed_on_new_task(tmp_path):
    """A commit between tasks is absorbed: next task re-takes snapshot/git_state baseline.

    This verifies Decision 6: task_runner.run() re-takes `before = snapshot()` and
    `st.git0 = git_state()` per task, so a commit landing between tasks is absorbed
    into the next task's baseline (no GIT_MOVED unless HEAD moves DURING the task).
    """
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Task 1: snapshot baseline before task
        snap1_before = guards.snapshot()
        git1_before = guards.git_state()

        # Task 1: edit file in scope
        (tmp_path / "a.txt").write_text("y", encoding="utf-8")

        # Task 1 passes, a commit happens
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "task1 work")

        # Task 2: re-takes baseline AFTER task 1's commit
        snap2_before = guards.snapshot()
        git2_before = guards.git_state()

        # The baselines are different because task 1 committed
        assert git1_before != git2_before, "git_state should differ across tasks after a commit"

        # Task 2: if only listed files are edited, no stray
        (tmp_path / "a.txt").write_text("z", encoding="utf-8")
        snap2_after = guards.snapshot()
        git2_after = guards.git_state()

        # git_state unchanged within the task (no commit in this task)
        assert git2_before == git2_after, "git_state should not change if no commit in this task"
        # Files modified are in snapshot
        assert snap2_before != snap2_after
        # No GIT_MOVED because git_state didn't change during this task
    finally:
        os.chdir(cwd)


def test_out_of_scope_edit_detected_after_prior_commit(tmp_path):
    """Out-of-scope edit is still a stray when prior task's commit moved HEAD.

    After a prior task commits (HEAD moves between task 1 and 2), an out-of-scope
    edit in task 2 is still caught as a stray file.
    """
    _git(tmp_path, "init", "-q")
    (tmp_path / "task1.txt").write_text("t1", encoding="utf-8")
    (tmp_path / "other.txt").write_text("other", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Task 1: edits task1.txt (in scope), commits
        snap1_before = guards.snapshot()
        (tmp_path / "task1.txt").write_text("t1 modified", encoding="utf-8")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "task1 work")
        snap1_after = guards.snapshot()

        # Task 2 starts: re-takes baseline (which includes the commit from task 1)
        snap2_before = guards.snapshot()
        git2_before = guards.git_state()

        # Task 2: edits only task1.txt (in scope for task 2)
        (tmp_path / "task1.txt").write_text("t1 modified again", encoding="utf-8")
        snap2_after = guards.snapshot()
        git2_after = guards.git_state()

        # Touch only task1.txt -> it's in snap before and after
        touched = {f for f in snap2_before.keys() | snap2_after.keys()
                   if snap2_before.get(f) != snap2_after.get(f)}
        assert touched == {"task1.txt"}, f"touched files should only be task1.txt, got {touched}"
        assert git2_before == git2_after, "git_state unchanged within task 2"

        # Now edit out-of-scope file
        (tmp_path / "other.txt").write_text("other modified", encoding="utf-8")
        snap2_after_oob = guards.snapshot()

        # out-of-scope edit is in snapshot diff
        touched = {f for f in snap2_before.keys() | snap2_after_oob.keys()
                   if snap2_before.get(f) != snap2_after_oob.get(f)}
        assert "other.txt" in touched, "out-of-scope file should be in touched set"
    finally:
        os.chdir(cwd)


def test_only_listed_files_is_clean_after_commit(tmp_path):
    """A task touching only its listed files after a commit is clean.

    When HEAD moves between tasks, a task that only edits files in its scope
    and doesn't move HEAD itself should have no GIT_MOVED and no strays.
    """
    _git(tmp_path, "init", "-q")
    (tmp_path / "t1.txt").write_text("t1", encoding="utf-8")
    (tmp_path / "t2.txt").write_text("t2", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Task 1: edits t1.txt, commits
        (tmp_path / "t1.txt").write_text("t1 modified", encoding="utf-8")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "task1")

        # Task 2 starts: baseline is reset after task 1's commit
        snap2_before = guards.snapshot()
        git2_before = guards.git_state()

        # Task 2: edits only t2.txt (its listed file)
        (tmp_path / "t2.txt").write_text("t2 modified", encoding="utf-8")
        snap2_after = guards.snapshot()
        git2_after = guards.git_state()

        # Check for strays: only t2.txt was touched
        touched = {f for f in snap2_before.keys() | snap2_after.keys()
                   if snap2_before.get(f) != snap2_after.get(f)}
        assert touched == {"t2.txt"}, f"only t2.txt should be touched, got {touched}"

        # No GIT_MOVED: git_state unchanged during task 2
        assert git2_before == git2_after, "git_state should not change within task 2"

        # Task 2 passes and commits
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "task2")

        # Task 3 starts: baseline reset again
        snap3_before = guards.snapshot()
        git3_before = guards.git_state()

        # Task 3: edits both files but only t1.txt is in scope
        (tmp_path / "t1.txt").write_text("t1 modified again", encoding="utf-8")
        (tmp_path / "t2.txt").write_text("t2 modified 2", encoding="utf-8")
        snap3_after = guards.snapshot()

        # Touched set includes both, but only t1.txt is in scope for task 3
        touched = {f for f in snap3_before.keys() | snap3_after.keys()
                   if snap3_before.get(f) != snap3_after.get(f)}
        assert "t1.txt" in touched and "t2.txt" in touched
        # t2.txt would be a stray if task 3's scope is only ["t1.txt"]
    finally:
        os.chdir(cwd)
