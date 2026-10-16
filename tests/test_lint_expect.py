import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import lint as lint_mod  # noqa: E402


def make_plan(tmp_path, checks=False):
    """A plan dir two levels deep, matching the real layout for metrics.jsonl."""
    plan_dir = tmp_path / "plans" / "slug"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.md").write_text("## T1\n", encoding="utf-8")
    if checks:
        (plan_dir / "checks").mkdir(exist_ok=True)
        (plan_dir / "checks" / "verify.py").write_text("", encoding="utf-8")
    return plan_dir


def test_bare_expect_warns_without_checks(tmp_path, capsys):
    plan_dir = make_plan(tmp_path)
    tasks = [{"id": "T1", "files": ["src/a.py"], "acceptance": 'python -c "pass"',
              "expect": "DONE"}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert "T1: loose expect 'DONE'" in out
    assert code == 0


def test_expect_with_checks_script_does_not_warn(tmp_path, capsys):
    plan_dir = make_plan(tmp_path, checks=True)
    tasks = [{"id": "T1", "files": ["src/a.py"], "expect": "DONE",
              "acceptance": 'python -c "raise SystemExit(1)" checks/verify.py'}]
    lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert "loose expect" not in out


def test_expect_warning_does_not_fail_lint(tmp_path, capsys):
    plan_dir = make_plan(tmp_path)
    tasks = [{"id": "T1", "files": ["src/a.py"], "acceptance": 'python -c "pass"',
              "expect": "OK"}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert out.startswith("WARN T1: loose expect")
    assert code == 0
