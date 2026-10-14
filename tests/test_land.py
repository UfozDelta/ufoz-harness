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


def _status(repo):
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=True,
                          capture_output=True, text=True,
                          env=dict(os.environ, **IDENTITY)).stdout.strip()


def _log(repo, *args):
    return subprocess.run(["git", "log", *args], cwd=repo, check=True, capture_output=True,
                          text=True, env=dict(os.environ, **IDENTITY)).stdout


def _repo(tmp_path, *slugs):
    """Init a repo holding a plan dir per slug; return the repo path."""
    repo = tmp_path / "repo"
    for slug in slugs:
        plan = repo / ".harness" / "plans" / slug
        plan.mkdir(parents=True)
        (plan / "tasks.json").write_text(f'{{"slug": "{slug}", "tasks": []}}\n', encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _commit(wt, name, content, message):
    (Path(wt) / name).write_text(content, encoding="utf-8")
    _git(wt, "add", name)
    _git(wt, "commit", "-q", "-m", message)


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


def test_land_two_plans_in_sequence(tmp_path, capsys, monkeypatch):
    """Landing p fast-forwards; q then needs `merge --no-ff`, which must still succeed."""
    for key, value in IDENTITY.items():
        monkeypatch.setenv(key, value)
    repo = _repo(tmp_path, "p", "q")
    home = os.getcwd()
    os.chdir(repo)
    try:
        wt_p = worktree.ensure("p")
        _commit(wt_p, "p.py", "p = 1\n", "p")
        wt_q = worktree.ensure("q")
        _commit(wt_q, "q.py", "q = 1\n", "q")

        assert land.land("p") == 0
        assert _status(repo) == ""  # records committed
        capsys.readouterr()

        assert land.land("q") == 0
        out = capsys.readouterr().out
        assert "landed q" in out
        assert _status(repo) == ""
    finally:
        os.chdir(home)
    assert (repo / "p.py").read_text(encoding="utf-8") == "p = 1\n"
    assert (repo / "q.py").read_text(encoding="utf-8") == "q = 1\n"
    merges = _log(repo, "--merges", "--oneline")
    assert merges.count("land q") == 1


def test_land_conflict_aborts(tmp_path, capsys, monkeypatch):
    """Both branches change the same line: the fallback merge aborts, nothing is lost."""
    for key, value in IDENTITY.items():
        monkeypatch.setenv(key, value)
    repo = _repo(tmp_path, "p", "q")
    (repo / "shared.txt").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "shared")
    home = os.getcwd()
    os.chdir(repo)
    try:
        wt_p = worktree.ensure("p")
        _commit(wt_p, "shared.txt", "one\nfrom p\n", "p")
        wt_q = worktree.ensure("q")
        _commit(wt_q, "shared.txt", "one\nfrom q\n", "q")

        assert land.land("p") == 0
        capsys.readouterr()
        assert _status(repo) == ""

        assert land.land("q") == 1
        out = capsys.readouterr().out
        assert "aborted" in out
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo,
                                check=True, capture_output=True, text=True,
                                env=dict(os.environ, **IDENTITY)).stdout
        assert Path(wt_q).resolve().as_posix() in listed.replace("\\", "/")
        assert Path(wt_q).is_dir()
        assert _status(repo) == ""
    finally:
        os.chdir(home)
    assert (repo / "shared.txt").read_text(encoding="utf-8") == "one\nfrom p\n"


def test_land_refuses_unpassed_task_and_dirty_worktree(tmp_path, capsys):
    repo = tmp_path / "repo"
    plan = repo / ".harness" / "plans" / "p"
    plan.mkdir(parents=True)
    (plan / "tasks.json").write_text('{"tasks": [{"id": "T1"}]}\n', encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    home = os.getcwd()
    os.chdir(repo)
    try:
        wt = Path(worktree.ensure("p"))
        assert land.land("p") == 1  # T1 has no passing report
        assert "tasks not passed" in capsys.readouterr().out
        items = wt / ".harness" / "plans" / "p" / "items"
        items.mkdir(parents=True, exist_ok=True)
        (items / "T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
        (wt / "loose.py").write_text("x = 1\n", encoding="utf-8")
        assert land.land("p") == 1  # passed, but uncommitted work would be deleted
        assert "uncommitted" in capsys.readouterr().out
        assert wt.is_dir()
    finally:
        os.chdir(home)
