"""--status: where is this plan and what do I run next. One screen, nothing run, nothing written.

One line per task in tasks.json order: "T1 pass (1 attempt)", "T2 FAIL (2 attempts)",
"T3 pending". Then the FIRST failed task's report tail (last 15 lines, indented), and a
last line "next: <command>". State comes from files only: a report containing
"RESULT: pass" is a pass, a report without it is a fail, no report is pending.
"""
import json
from pathlib import Path

TAIL_LINES = 15


def _tasks(plan_dir):
    """Task ids in tasks.json order ([] when there is no plan here)."""
    try:
        raw = json.loads((plan_dir / "tasks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [t.get("id") for t in raw.get("tasks", []) if t.get("id")]


def _attempts(plan_dir, tid):
    """Attempt count from the task's metrics file, when it recorded one."""
    try:
        metrics = json.loads((plan_dir / "items" / f"{tid}.metrics.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    attempts = metrics.get("attempts")
    return attempts if isinstance(attempts, int) and attempts > 0 else None


def _report(plan_dir, tid):
    try:
        return (plan_dir / "items" / f"{tid}.report.md").read_text(encoding="utf-8")
    except OSError:
        return None


def _line(tid, state, plan_dir):
    if state == "pending":
        return f"{tid} pending"
    attempts = _attempts(plan_dir, tid)
    count = f" ({attempts} attempt{'s' if attempts != 1 else ''})" if attempts else ""
    return f"{tid} {'pass' if state == 'pass' else 'FAIL'}{count}"


def render(slug, plan_dir):
    """The whole --status screen for slug, read from plan_dir (no lock, no run)."""
    plan_dir = Path(plan_dir)
    lines, first_fail, first_fail_report = [], None, None
    any_unfinished = False
    for tid in _tasks(plan_dir):
        text = _report(plan_dir, tid)
        if text is None:
            state = "pending"
            any_unfinished = True
        else:
            state = "pass" if "RESULT: pass" in text else "fail"
            if state == "fail" and first_fail is None:
                first_fail, first_fail_report = tid, text
        lines.append(_line(tid, state, plan_dir))

    if first_fail is not None:
        tail = first_fail_report.splitlines()[-TAIL_LINES:]
        lines.append("")
        lines.append(f"{first_fail} report tail:")
        lines.extend(f"  {line}" for line in tail)
        if "LOCK-MISMATCH" in first_fail_report:
            lines.append(f"next: python .harness/run_plan.py {slug} --relock-only")
        else:
            lines.append(f"next: python .harness/run_plan.py {slug}")
    elif any_unfinished:
        lines.append(f"next: python .harness/run_plan.py {slug}")
    elif lines:
        lines.append(f"next: python .harness/run_plan.py {slug} --land")
    return "\n".join(lines)
