import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import status  # noqa: E402


def make_plan(tmp_path, slug="slug"):
    """A plan dir with tasks.json for T1..T3 and an empty items dir."""
    plan_dir = tmp_path / "plans" / slug
    (plan_dir / "items").mkdir(parents=True, exist_ok=True)
    tasks = [{"id": tid, "deps": [], "files": [], "acceptance": 'python -c "pass"'}
             for tid in ("T1", "T2", "T3")]
    (plan_dir / "tasks.json").write_text(json.dumps({"slug": slug, "tasks": tasks}),
                                         encoding="utf-8")
    return plan_dir


def write_report(plan_dir, tid, text):
    (plan_dir / "items" / f"{tid}.report.md").write_text(text, encoding="utf-8")


def test_states_first_failure_tail_and_next_command(tmp_path):
    plan_dir = make_plan(tmp_path)
    write_report(plan_dir, "T1", "RESULT: pass\ndone\n")
    body = [f"line{i:02d}" for i in range(1, 21)]
    write_report(plan_dir, "T2", "RESULT: fail\n" + "\n".join(body) + "\n")

    out = status.render("slug", plan_dir)
    lines = out.splitlines()

    assert "T1 pass" in out
    assert "T2 FAIL" in out
    assert "T3 pending" in out
    assert "line20" in out            # the report's last line is inside the tail
    assert "line01" not in out        # the first of 20 lines is cut by the 15-line tail
    assert lines[-1] == "next: python .harness/run_plan.py slug"


def test_all_pass_nexts_the_land_command(tmp_path):
    plan_dir = make_plan(tmp_path)
    for tid in ("T1", "T2", "T3"):
        write_report(plan_dir, tid, f"RESULT: pass\n{tid} done\n")

    out = status.render("slug", plan_dir)

    assert "T1 pass" in out and "T2 pass" in out and "T3 pass" in out
    assert out.splitlines()[-1] == "next: python .harness/run_plan.py slug --land"


def test_lock_mismatch_nexts_the_relock_only_command(tmp_path):
    plan_dir = make_plan(tmp_path)
    write_report(plan_dir, "T1", "RESULT: pass\ndone\n")
    write_report(plan_dir, "T2", "RESULT: fail\nLOCK-MISMATCH: plan.lock.json is stale\n")
    write_report(plan_dir, "T3", "RESULT: pass\ndone\n")

    out = status.render("slug", plan_dir)

    assert "LOCK-MISMATCH" in out
    assert out.splitlines()[-1] == "next: python .harness/run_plan.py slug --relock-only"
