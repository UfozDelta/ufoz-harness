import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
from runner import cli  # noqa: E402

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@localhost",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@localhost"}


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env=dict(os.environ, **IDENTITY))


def _make_repo(repo):
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    plan = repo / ".harness" / "plans" / "p"
    plan.mkdir(parents=True)
    (plan / "tasks.json").write_text('{"slug": "p", "tasks": []}\n', encoding="utf-8")


def test_prepare_creates_worktree_and_is_idempotent(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    home = os.getcwd()
    os.chdir(repo)
    try:
        assert cli.prepare("p") == 0
        assert (repo / ".worktrees" / "p" / ".harness" / "plans" / "p" / "tasks.json").exists()
        assert cli.prepare("p") == 0
    finally:
        os.chdir(home)


def test_check_and_prepare_flags_parse():
    parser = cli.build_parser()
    assert parser.parse_args(["p", "--check"]).check == ""
    assert parser.parse_args(["p", "--check", "d"]).check == "d"
    assert parser.parse_args(["p", "--prepare"]).prepare is True
