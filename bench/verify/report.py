"""verify-bench report: render `bench/verify/results.csv` as `bench/verify/RESULTS.md`.

`build_report` is pure (rows in, markdown out) and never raises: an empty or malformed
matrix still yields a readable stub. `main` is the only part that touches disk. Every
number is derived from the rows at report time; nothing is stored.
"""
import csv
import statistics
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

PHASES = ("orch", "plan", "exec")
PHASE_COST = {"orch": "orch_cost", "plan": "plan_cost", "exec": "exec_cost"}
TOKEN_FIELDS = ("in", "out", "reason", "cache_read", "cache_write")
AXES = ("orchestrator", "planner", "executor")
PROVISIONAL_BELOW = 3  # combos with fewer cells get a dagger: their rank is provisional
SEP = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _total(values):
    """Sum of the reported values; None when nothing was reported."""
    got = [v for v in values if v is not None]
    return sum(got) if got else None


def _stat(values, spec):
    """Mean of the reported values, with ` ± stdev` when there are at least two; `-` when none."""
    got = [v for v in values if v is not None]
    if not got:
        return "-"
    text = format(sum(got) / len(got), spec)
    if len(got) >= 2:
        text += " ± " + format(statistics.stdev(got), spec)
    return text


def _group(rows, key):
    groups = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    return groups


def _key(row):
    return (row.get("orchestrator", ""), row.get("planner", ""), row.get("executor", ""))


def _status(row):
    return str(row.get("status", "")).strip().lower()


def _flag(row, name):
    return str(row.get(name, "")).strip().lower() == "true"


def _row_cost(row):
    return _total([_float(row.get(PHASE_COST[p])) for p in PHASES])


def _row_tokens(row, field):
    """One token field summed over the phases; None when no phase reported it."""
    return _total([_float(row.get(f"{p}_{field}")) for p in PHASES])


def _cache_hit(rows):
    """Pooled cache hit in %: cache_read / (in + cache_read + cache_write). None without tokens."""
    read_sum = den = 0.0
    for row in rows:
        read = _row_tokens(row, "cache_read") or 0.0
        den += (_row_tokens(row, "in") or 0.0) + read + (_row_tokens(row, "cache_write") or 0.0)
        read_sum += read
    return read_sum / den * 100 if den else None


def _stats(rows):
    """Derived numbers for a group of rows, as display strings (plus the raw values sorting uses)."""
    passed = sum(1 for r in rows if _status(r) == "pass")
    cost = _total([_row_cost(r) for r in rows])
    per_pass = cost / passed if cost is not None and passed else None
    hit = _cache_hit(rows)
    tokens = _total([_total([_row_tokens(r, f) for f in TOKEN_FIELDS]) for r in rows])
    return {"n": len(rows), "pass": passed, "pass_pct": passed / len(rows) * 100,
            "wall": _stat([_float(r.get("wall_s")) for r in rows], ".0f"),
            "cost": _stat([_row_cost(r) for r in rows], ".3f"),
            "tokens": "-" if tokens is None else f"{tokens:.0f}",
            "hit": "-" if hit is None else f"{hit:.1f}%",
            "per_pass": "-" if per_pass is None else f"{per_pass:.3f}",
            "per_pass_num": per_pass}


def _combo_lines(rows):
    groups = _group(rows, _key)
    stats = {key: _stats(group) for key, group in groups.items()}
    # pass % desc, then cost per pass asc with the unknown ones last
    order = sorted(groups, key=lambda k: (-stats[k]["pass_pct"], stats[k]["per_pass_num"] is None,
                                          stats[k]["per_pass_num"] or 0.0))
    lines = ["| orchestrator | planner | executor | n | pass | pass % | rules_ok | plan_ok "
             "| mean wall s | mean cost $ | total tokens | cache hit | cost per pass |", SEP]
    provisional = False
    for key in order:
        s, group = stats[key], groups[key]
        n_text = str(s["n"])
        if s["n"] < PROVISIONAL_BELOW:
            n_text += "†"
            provisional = True
        rules_ok = sum(_flag(r, "rules_ok") for r in group)
        plan_ok = sum(_flag(r, "plan_ok") for r in group)
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {n_text} | {s['pass']} | "
                     f"{s['pass_pct']:.0f}% | {rules_ok} | {plan_ok} | {s['wall']} | {s['cost']} | "
                     f"{s['tokens']} | {s['hit']} | {s['per_pass']} |")
    if provisional:
        lines += ["", "† n < 3: rank provisional."]
    return lines


def _axis_lines(rows):
    lines = ["## By axis"]
    for axis in AXES:
        groups = _group(rows, lambda r, a=axis: r.get(a, ""))
        lines += ["", f"### {axis}", "",
                  f"| {axis} | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for value in sorted(groups):
            s = _stats(groups[value])
            lines.append(f"| {value} | {s['n']} | {s['pass_pct']:.0f}% | {s['wall']} | {s['cost']} | "
                         f"{s['tokens']} | {s['hit']} | {s['per_pass']} |")
    return lines


def _phase_lines(rows):
    groups = _group(rows, _key)
    lines = ["## Per phase", "",
             "| orchestrator | planner | executor | phase | mean wall s | mean in | mean out "
             "| mean cache_read | mean cache_write | mean cost $ |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for key, group in groups.items():
        for phase in PHASES:
            cells = [_stat([_float(r.get(f"{phase}_{field}")) for r in group], spec)
                     for field, spec in (("wall_s", ".1f"), ("in", ".0f"), ("out", ".0f"),
                                         ("cache_read", ".0f"), ("cache_write", ".0f"))]
            cells.append(_stat([_float(r.get(PHASE_COST[phase])) for r in group], ".3f"))
            lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {phase} | " + " | ".join(cells) + " |")
    return lines


def build_report(rows):
    """A markdown report: combinations, per-axis and per-phase tables, then totals.

    Pure and defensive: any missing field is treated as blank and a failure returns the stub.
    """
    try:
        rows = list(rows or [])
        if not rows:
            return STUB
        # a rerun appends a new row for the same slug: only the latest counts
        rows = list({row.get("slug") or id(row): row for row in rows}.values())
        status = [_status(r) for r in rows]
        passed = status.count("pass")
        failed = status.count("fail")
        lines = ["# verify-bench results", "",
                 f"Cells recorded: {len(rows)}", "",
                 "## Combinations", ""]
        lines += _combo_lines(rows)
        lines += [""] + _axis_lines(rows)
        lines += [""] + _phase_lines(rows)
        lines += ["", "## Totals", "",
                  f"- pass: {passed}",
                  f"- fail: {failed}",
                  f"- other (skipped/infra_error/timeout): {len(rows) - passed - failed}",
                  f"- total: {len(rows)}",
                  f"- rules_ok: {sum(_flag(r, 'rules_ok') for r in rows)}",
                  f"- plan_ok: {sum(_flag(r, 'plan_ok') for r in rows)}", ""]
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
