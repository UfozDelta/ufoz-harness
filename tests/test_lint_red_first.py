import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import lint as lint_mod  # noqa: E402
from runner import plan as plan_mod  # noqa: E402


def make_plan(tmp_path, plan_md="## T1\n"):
    """A plan dir two levels deep with a checks/verify.py, matching the real layout."""
    plan_dir = tmp_path / "plans" / "slug"
    (plan_dir / "checks").mkdir(parents=True, exist_ok=True)
    (plan_dir / "checks" / "verify.py").write_text("", encoding="utf-8")
    if plan_md:
        (plan_dir / "plan.md").write_text(plan_md, encoding="utf-8")
    return plan_dir


def write_tasks(plan_dir, tasks):
    (plan_dir / "tasks.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


def test_red_first_defaults_on_for_checks_script(tmp_path):
    plan_dir = make_plan(tmp_path)
    assert plan_mod.uses_checks_script(plan_dir, "python checks/verify.py") is True
    assert plan_mod.uses_checks_script(plan_dir, "python checks/missing.py") is False
    assert plan_mod.uses_checks_script(plan_dir, 'python -c "pass"') is False
    assert plan_mod.uses_checks_script(plan_dir, "python runner/verify.py") is False


def test_red_first_false_opts_out(tmp_path):
    plan_dir = make_plan(tmp_path)
    write_tasks(plan_dir, [{"id": "T1", "acceptance": "python checks/verify.py",
                            "files": ["src/a.py"], "red_first": False}])
    plan = plan_mod.Plan("slug", plans_root=str(plan_dir.parent))
    assert plan.by_id["T1"].red_first is False


def test_no_checks_script_stays_off(tmp_path):
    plan_dir = make_plan(tmp_path)
    write_tasks(plan_dir, [{"id": "T1", "acceptance": 'python -c "pass"', "files": ["src/a.py"]}])
    plan = plan_mod.Plan("slug", plans_root=str(plan_dir.parent))
    assert plan.by_id["T1"].red_first is False


def test_lint_red_first_proofs_defaulted_task(tmp_path, capsys):
    plan_dir = make_plan(tmp_path)
    tasks = [{"id": "T1", "files": ["src/a.py"],
              "acceptance": 'python -c "pass" checks/verify.py'}]
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    out = capsys.readouterr().out
    assert code == 1
    assert "T1: acceptance already passes on the untouched tree (check-invalid)" in out
