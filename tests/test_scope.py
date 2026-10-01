import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import guards  # noqa: E402
from runner import lint as lint_mod  # noqa: E402
from runner.plan import in_scope, overlaps  # noqa: E402


def test_in_scope_exact_and_directory_entries():
    entries = {"app/main.py", "fixtures/medium/"}
    assert in_scope("app/main.py", entries)
    assert in_scope("fixtures/medium/seed/lib/x.ts", entries)
    assert not in_scope("app/main.pyc", entries)
    assert not in_scope("fixtures/medium2/x.ts", entries)  # a dir entry is not a string prefix
    assert not in_scope("app/x", {"app/xy"})


def test_overlaps_is_prefix_aware():
    assert overlaps({"a/"}, {"a/b.py"})
    assert overlaps({"a/b/"}, {"a/"})
    assert overlaps({"x.py"}, {"x.py"})
    assert not overlaps({"a/"}, {"ab/c.py"})
    assert not overlaps({"a.py"}, {"b.py"})


def _lint(tmp_path, files, capsys):
    plan_dir = tmp_path / "plans" / "slug"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.md").write_text("## T1\n", encoding="utf-8")
    tasks = [{"id": "T1", "files": files, "acceptance": 'python -c "raise SystemExit(1)"'}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    return code, capsys.readouterr().out


def test_lint_accepts_a_narrow_directory_entry(tmp_path, capsys):
    code, out = _lint(tmp_path, ["bench/suite/fixtures/medium/"], capsys)
    assert code == 0, out


def test_lint_rejects_broad_directory_entries(tmp_path, capsys):
    for i, entry in enumerate(("/", "./", ".harness/", ".git/", "node_modules/", ".harness/runner/")):
        code, out = _lint(tmp_path / str(i), [entry], capsys)
        assert code == 1 and "too broad" in out, (entry, out)


def test_lint_directory_without_trailing_slash_is_an_error(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pkg").mkdir()
    code, out = _lint(tmp_path, ["pkg"], capsys)
    assert code == 1 and "end with '/'" in out


def test_written_paths_reads_every_executor_log_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "T1.pi.log"
    log.write_text(
        '[toolCall write] {"path": "app/a.py", "content": "x"}\n'                  # pi
        '[toolCall Edit] {"file_path": "' + (tmp_path / "app" / "b.py").as_posix() + '"}\n'  # claude, absolute
        '[toolCall write_to_file] {"filePath": "app\\\\c.py", "content": "trunc\n'  # cline, cut at 200
        '[toolCall read] {"path": "app/read_only.py"}\n'                           # a read is not a write
        '[toolCall bash] {"command": "echo hi > app/d.py"}\n',                     # bash: unattributable
        encoding="utf-8")
    assert guards.written_paths([log]) == {"app/a.py", "app/b.py", "app/c.py"}


def test_attribute_splits_own_strays_from_unattributed():
    own, unattributed = guards.attribute(["app/a.py", "tmp/side.txt"], {"app/a.py"})
    assert own == ["app/a.py"]
    assert unattributed == ["tmp/side.txt"]


def test_lint_rejects_a_directory_holding_many_tracked_files(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(lint_mod, "MAX_TRACKED_UNDER_DIR", 1)
    code, out = _lint(tmp_path, ["tests/"], capsys)  # the repo's own tests/ has several tracked files
    assert code == 1 and "tracked files under it" in out
