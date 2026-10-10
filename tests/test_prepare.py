import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
import pytest  # noqa: E402
from runner import check, cli  # noqa: E402

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
    _git(repo, "add", ".harness")  # a plan worktree starts at HEAD, so the tree must be clean
    _git(repo, "commit", "-q", "-m", "plan")


def test_prepare_creates_worktree_and_is_idempotent(tmp_path):
    repo = tmp_path / "repo"
    _make_repo(repo)
    home = os.getcwd()
    os.chdir(repo)
    try:
        assert check.prepare("p") == 0
        assert (repo / ".worktrees" / "p" / ".harness" / "plans" / "p" / "tasks.json").exists()
        assert check.prepare("p") == 0
    finally:
        os.chdir(home)


def test_removed_flags_rejected_and_backend_specs_parse():
    parser = cli.build_parser()
    for flag in ("--check", "--prepare", "--watch", "--relock", "--from", "--window", "--worktree",
                 "--retries", "--repair", "--executor-model", "--planner-model"):
        with pytest.raises(SystemExit):
            parser.parse_args(["p", flag])
    assert parser.parse_args(["p", "--executor", "agent:haiku"]).executor == "agent:haiku"
    assert cli.parse_backend("agent:haiku", ("pi", "agent")) == ("agent", "haiku")
    assert cli.parse_backend("pi", ("pi", "agent")) == ("pi", None)
    with pytest.raises(SystemExit):
        cli.parse_backend("nope", ("pi", "agent"))
