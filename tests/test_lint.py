import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import lint as lint_mod  # noqa: E402


def make_plan(tmp_path, plan_md=""):
    """A plan dir two levels deep, matching the real layout: lint writes metrics.jsonl to
    plan_dir.parent.parent, so a shallower tmp dir would break unrelated to the case."""
    plan_dir = tmp_path / "plans" / "slug"
    plan_dir.mkdir(parents=True, exist_ok=True)
    if plan_md:
        (plan_dir / "plan.md").write_text(plan_md, encoding="utf-8")
    return plan_dir


def test_missing_brief_is_an_error(tmp_path, capsys):
    plan_dir = make_plan(tmp_path, "## T1\n")
    tasks = [{"id": "T1", "brief": "briefs/T1.md", "files": ["src/a.ts"],
              "acceptance": 'python -c "pass"'}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert code == 1
    assert "T1: brief briefs/T1.md not found" in out


def test_acceptance_that_passes_untouched_is_check_invalid(tmp_path, capsys):
    plan_dir = make_plan(tmp_path, "## T1\n")
    tasks = [{"id": "T1", "files": ["src/a.ts"], "acceptance": 'python -c "pass"'}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert code == 1
    assert "T1: acceptance already passes on the untouched tree (check-invalid)" in out


def test_shared_files_without_dep_warns_but_passes(tmp_path, capsys):
    plan_dir = make_plan(tmp_path, "## T1\n\n## T2\n")
    failing = 'python -c "raise SystemExit(1)"'
    tasks = [{"id": "T1", "files": ["src/a.py", "src/shared.py"], "acceptance": failing},
             {"id": "T2", "files": ["src/b.py", "src/shared.py"], "acceptance": failing}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert "WARN T1/T2: share ['src/shared.py'] without a dep between them" in out
    # warnings do not fail lint, only errors do
    assert code == 0
    assert "ERROR" not in out
