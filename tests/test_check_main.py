import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
from runner import check, guards  # noqa: E402


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=t", *args], cwd=cwd,
                   check=True, capture_output=True)


def _repo(tmp_path):
    """A one-commit repo with a plan `p` (one task that may touch a.txt)."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("1", encoding="utf-8")
    plan = tmp_path / ".harness" / "plans" / "p"
    plan.mkdir(parents=True)
    (plan / "tasks.json").write_text(json.dumps({"slug": "p", "tasks": [
        {"id": "T1", "deps": [], "files": ["a.txt"], "acceptance": "python -c \"pass\"",
         "red_first": False}]}), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _in(path, fn):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        return fn()
    finally:
        os.chdir(cwd)


def test_no_baseline_means_no_complaint(tmp_path):
    repo = _repo(tmp_path)
    assert _in(repo, lambda: check.main_changes("p")) is None


def test_untouched_main_tree_is_clean(tmp_path):
    repo = _repo(tmp_path)
    def run():
        check.write_baseline("p")
        return check.main_changes("p")
    assert _in(repo, run) == []


def test_stray_main_tree_write_is_flagged(tmp_path):
    repo = _repo(tmp_path)
    def run():
        check.write_baseline("p")
        (repo / "stray.txt").write_text("x", encoding="utf-8")
        (repo / "a.txt").write_text("2", encoding="utf-8")
        return check.main_changes("p")
    assert _in(repo, run) == ["a.txt", "stray.txt"]


def test_harness_paths_and_worktrees_are_ignored(tmp_path):
    repo = _repo(tmp_path)
    def run():
        check.write_baseline("p")
        (repo / ".harness" / "plans" / "p" / "SUMMARY.md").write_text("s", encoding="utf-8")
        (repo / ".worktrees" / "p").mkdir(parents=True)
        (repo / ".worktrees" / "p" / "x.txt").write_text("x", encoding="utf-8")
        return check.main_changes("p")
    assert _in(repo, run) == []


def test_head_move_with_no_file_change_is_flagged(tmp_path):
    repo = _repo(tmp_path)
    def run():
        check.write_baseline("p")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "sneaky")
        return check.main_changes("p")
    assert _in(repo, run) == [guards.GIT_MOVED]


def test_check_exits_1_and_names_the_main_tree_change(tmp_path, capsys):
    repo = _repo(tmp_path)
    def run():
        check.write_baseline("p")
        (repo / "stray.txt").write_text("x", encoding="utf-8")
        return check.check("p", repo)
    assert _in(repo, run) == 1
    assert "MAIN stray.txt" in capsys.readouterr().out
