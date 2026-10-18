"""verify-bench report: render `bench/verify/results.csv` as `bench/verify/RESULTS.md`.

`build_report` is pure (rows in, markdown out) and never raises: an empty or malformed
matrix still yields a readable stub. `main` is the only part that touches disk.
"""
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backends  # noqa: E402

RESULTS = REPO_ROOT / "bench" / "verify" / "results.csv"
REPORT = REPO_ROOT / "bench" / "verify" / "RESULTS.md"

COLUMNS = backends.COLUMNS
CSV_FIELDS = backends.CSV_FIELDS

STUB = ("# verify-bench results\n\n"
        "No cells recorded yet. Run `python bench/verify/verify.py` to fill "
        "`bench/verify/results.csv`, then regenerate this report.\n")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _fmt(value, spec):
    return "-" if value is None else format(value, spec)


def _key(row):
    return (row.get("orchestrator", ""), row.get("planner", ""), row.get("executor", ""))


def build_report(rows):
    """A markdown report: one row per (orchestrator, planner, executor) combo plus totals.

    Pure and defensive: any missing field is treated as blank and a failure returns the stub.
    """
    try:
        rows = list(rows or [])
        if not rows:
            return STUB
        # a rerun appends a new row for the same slug: only the latest counts
        rows = list({row.get("slug") or id(row): row for row in rows}.values())
        combos = {}
        order = []
        totals = {"pass": 0, "fail": 0, "other": 0, "total": 0, "rules_ok": 0, "plan_ok": 0}
        for row in rows:
            key = _key(row)
            if key not in combos:
                combos[key] = {"pass": 0, "fail": 0, "other": 0, "total": 0,
                               "rules_ok": 0, "plan_ok": 0, "wall": [], "cost": []}
                order.append(key)
            bucket = combos[key]
            bucket["total"] += 1
            totals["total"] += 1
            bucket["wall"].append(_float(row.get("wall_s")))
            costs = [_float(row.get("plan_cost")), _float(row.get("exec_cost"))]
            bucket["cost"].append(None if all(c is None for c in costs)
                                  else sum(c for c in costs if c is not None))
            status = str(row.get("status", "")).strip().lower()
            if status == "pass":
                bucket["pass"] += 1
                totals["pass"] += 1
            elif status == "fail":
                bucket["fail"] += 1
                totals["fail"] += 1
            else:
                bucket["other"] += 1
                totals["other"] += 1
            if str(row.get("rules_ok", "")).strip().lower() == "true":
                bucket["rules_ok"] += 1
                totals["rules_ok"] += 1
            if str(row.get("plan_ok", "")).strip().lower() == "true":
                bucket["plan_ok"] += 1
                totals["plan_ok"] += 1

        lines = ["# verify-bench results", "",
                 f"Cells recorded: {totals['total']}", "",
                 "## Combinations", "",
                 "| orchestrator | planner | executor | pass | fail | other | rules_ok | plan_ok | total | mean wall s | mean cost $ |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for key in order:
            bucket = combos[key]
            lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {bucket['pass']} | "
                         f"{bucket['fail']} | {bucket['other']} | {bucket['rules_ok']} | "
                         f"{bucket['plan_ok']} | {bucket['total']} | "
                         f"{_fmt(_mean(bucket['wall']), '.0f')} | "
                         f"{_fmt(_mean(bucket['cost']), '.3f')} |")
        lines += ["", "## Totals", "",
                  f"- pass: {totals['pass']}",
                  f"- fail: {totals['fail']}",
                  f"- other (skipped/infra_error/timeout): {totals['other']}",
                  f"- total: {totals['total']}",
                  f"- rules_ok: {totals['rules_ok']}",
                  f"- plan_ok: {totals['plan_ok']}", ""]
        return "\n".join(lines)
    except Exception:  # a malformed matrix must never break the report step
        return STUB


def _read_rows(path=None):
    rows = []
    try:
        with open(path or RESULTS, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("slug") or row.get("status"):
                    rows.append(row)
    except OSError:
        return []
    return rows


def main(argv=None):
    rows = _read_rows()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(rows), encoding="utf-8")
    print(f"wrote {REPORT} ({len(rows)} row(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
