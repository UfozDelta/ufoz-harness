import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".harness"))
from runner import land, worktree  # noqa: E402

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@localhost",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@localhost"}


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env=dict(os.environ, **IDENTITY))


def test_land_with_plan_file_committed_on_branch(tmp_path, capsys):
    """SUMMARY.md is committed on the branch; copying records before the merge made git abort."""
    repo = tmp_path / "repo"
    plan = repo / ".harness" / "plans" / "p"
    plan.mkdir(parents=True)
    (plan / "tasks.json").write_text('{"slug": "p", "tasks": []}\n', encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    home = os.getcwd()
    os.chdir(repo)
    try:
        wt = worktree.ensure("p")
        wt_plan = Path(wt) / ".harness" / "plans" / "p"
        (wt_plan / "SUMMARY.md").write_text("done\n", encoding="utf-8")
        (wt_plan / "items").mkdir(exist_ok=True)
        (wt_plan / "items" / "T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
        _git(wt, "add", "-f", ".harness/plans/p/SUMMARY.md")
        (Path(wt) / "code.py").write_text("x = 1\n", encoding="utf-8")
        _git(wt, "add", "code.py")
        _git(wt, "commit", "-q", "-m", "summary")
        assert land.land("p") == 0
        assert "landed p: 1 files" in capsys.readouterr().out
    finally:
        os.chdir(home)
    assert (plan / "SUMMARY.md").read_text(encoding="utf-8") == "done\n"
    assert (plan / "items" / "T1.report.md").exists()
