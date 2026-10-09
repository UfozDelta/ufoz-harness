import inspect
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".harness/plans/bench-isolate/checks")
from _common import cells, cell  # noqa: E402


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True)


def fresh():
    d = Path(tempfile.mkdtemp(prefix="tamper"))
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "a@b.c")
    git(d, "config", "user.name", "x")
    (d / "package.json").write_text("{}", encoding="utf-8")
    (d / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "commit", "-qm", "seed")
    return d, git(d, "rev-parse", "HEAD").stdout.strip()


def check(mutate, expect):
    d, seed = fresh()
    mutate(d)
    got = cells._tampered_git(d, seed, seed, set())
    shutil.rmtree(d, ignore_errors=True)
    assert got is expect, (mutate.__name__, got)


PAT = cells.TAMPER_PATTERNS[0]


def edit_pkg(d):
    (d / "package.json").write_text('{"a":1}', encoding="utf-8")


def add_harness(d):
    (d / ".harness").mkdir()
    (d / ".harness" / "n.md").write_text(PAT, encoding="utf-8")


def add_test(d):
    (d / "test_new.py").write_text("def test_a(): pass\n", encoding="utf-8")


def add_pattern(d):
    (d / "app.py").write_text("x = 1\n# " + PAT + "\n", encoding="utf-8")


def edit_app(d):
    (d / "app.py").write_text("x = 2\n", encoding="utf-8")


check(edit_pkg, True)
check(add_harness, False)
check(add_test, True)
check(add_pattern, True)
check(edit_app, False)

w = Path(tempfile.mkdtemp(prefix="reg"))
cells._copy_tree(Path(cells.REPO_ROOT) / "bench/suite/fixtures/small/seed", w)
passed, total = cells._regression_counts(w, "small", cells.REPO_ROOT)
assert total >= 1 and passed == total, (passed, total)
shutil.rmtree(w, ignore_errors=True)

b = cells._blank({"size": "small", "executor": "pi", "slug": "s"})
assert b["plan_source"] == "fixture" and "regression_total" in b and "kit_hash" in b
assert "--no-worktree" not in cells._plan_args(cell(1), None, isolated=True)
assert "--no-worktree" in cells._plan_args(cell(1), None)
assert list(inspect.signature(cells._run_project).parameters)[:3] == ["cell", "repo_root", "cell_timeout"]
print("T5 OK")
