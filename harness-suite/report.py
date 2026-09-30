"""harness-suite report builder: results.csv -> markdown (RESULTS.md).

Pure-python, never raises on missing/empty/malformed CSVs: a missing file (or
one with no data rows) yields a "no results yet" stub.
"""
import csv
import math
import statistics
from collections import OrderedDict, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_CSV = REPO_ROOT / "harness-suite" / "results.csv"
RESULTS_MD = REPO_ROOT / "harness-suite" / "RESULTS.md"

# Mirror of suite.COLUMNS (kept standalone so report.py imports with no deps).
COLUMNS = [
    "ts", "size", "mode", "executor", "rep", "status", "wall_s",
    "tests_passed", "tests_total", "tasks_passed", "tasks_total", "attempts",
    "input", "output", "reasoning", "cache_read", "cost",
    "window_opened", "watch_ok", "peak_worktrees", "model", "harness_sha",
    "batch_wall_s", "tampered", "seed", "order_idx",
]

TOKEN_COLUMNS = ["input", "output", "reasoning", "cache_read"]

# Rows with these statuses are excluded from pass-rate math entirely.
EXCLUDED_STATUSES = {"infra_error"}


def load_rows(csv_path=RESULTS_CSV):
    """Read the results CSV into a list of dicts. Missing/empty -> []."""
    path = Path(csv_path)
    if not path.exists():
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = []
            for raw in reader:
                row = {}
                for key in COLUMNS:
                    row[key] = (raw.get(key) or "").strip() if isinstance(raw.get(key), str) else (raw.get(key) or "")
                rows.append(row)
            return rows
    except OSError:
        return []


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=0):
    val = _num(value)
    return default if val is None else int(val)


def wilson_ci(successes, total, z=1.959963985):
    """Wilson 95% confidence interval on a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0, 0.0)
    p = successes / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    low = max(0.0, (centre - spread) / denom)
    high = min(1.0, (centre + spread) / denom)
    return (p, low, high)


def _median(values):
    return statistics.median(values) if values else None


def _fmt(value, spec="{:.2f}", dash="-"):
    if value is None:
        return dash
    try:
        return spec.format(value)
    except (TypeError, ValueError):
        return dash


def _graded(rows):
    """Rows that count towards pass-rate math (infra_error dropped)."""
    return [r for r in rows if (r.get("status") or "") not in EXCLUDED_STATUSES]


def _group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get(key) or "?"].append(row)
    return groups


def _max_rep(rows):
    """Highest rep number in the rows (the `pass^k` column header exponent)."""
    reps = [_int(r.get("rep")) for r in rows or [] if r.get("rep") not in (None, "")]
    return max(reps) if reps else 1


def _grid_table(cells, k=3):
    k = max(1, _int(k, 1))
    lines = [
        "| executor | size | mode | n | pass@1 | pass^{k} | wilson95 | median wall_s | cost/task | tokens/task |".format(k=k),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (executor, size, mode), rows in cells.items():
        graded = _graded(rows)
        n = len(graded)
        passes = sum(1 for r in graded if r.get("status") == "pass")
        rate, low, high = wilson_ci(passes, n)
        fams = defaultdict(list)
        for r in graded:
            fams[f"{r.get('size')}-{r.get('mode')}-{r.get('executor')}"].append(r)
        all3 = sum(1 for f in fams.values()
                   if f and all(x.get("status") == "pass" for x in f))
        if fams:
            passk = f"{all3}/{len(fams)} ({all3 / len(fams) * 100:.0f}%)"
        else:
            passk = "-"
        walls = [w for w in (_num(r.get("wall_s")) for r in graded) if w is not None]
        solved = [r for r in graded if r.get("status") == "pass"]
        total_cost = sum(_num(r.get("cost"), 0.0) for r in solved)
        total_tokens = sum(sum(_int(r.get(c)) for c in TOKEN_COLUMNS) for r in solved)
        cost_per = total_cost / len(solved) if solved else None
        tok_per = total_tokens / len(solved) if solved else None
        lines.append(
            "| {e} | {s} | {m} | {n} | {rate} | {p3} | [{lo}, {hi}] | {wall} | {cost} | {tok} |".format(
                e=executor, s=size, m=mode, n=n,
                rate=f"{rate * 100:.0f}%" if n else "-",
                p3=passk,
                lo=_fmt(low * 100, "{:.0f}%"), hi=_fmt(high * 100, "{:.0f}%"),
                wall=_fmt(_median(walls), "{:.1f}"),
                cost=_fmt(cost_per, "${:.3f}"),
                tok=_fmt(tok_per, "{:.0f}"),
            )
        )
    return lines


def _mode_comparison(graded):
    """serial vs parallel speedup and multi overhead, per executor+size."""
    by_exec_size_mode = defaultdict(list)
    for row in graded:
        key = (row.get("executor") or "?", row.get("size") or "?", row.get("mode") or "?")
        by_exec_size_mode[key].append(row)

    def _med_wall(executor, size, mode):
        rows = by_exec_size_mode.get((executor, size, mode), [])
        if not rows:
            return None
        if mode == "multi":
            batch = [w for w in (_num(r.get("batch_wall_s")) for r in rows) if w is not None]
            return _median(batch)
        walls = [w for w in (_num(r.get("wall_s")) for r in rows) if w is not None]
        return _median(walls)

    lines = [
        "| executor | size | serial wall | parallel wall | speedup | multi wall | multi overhead |",
        "|---|---|---|---|---|---|---|",
    ]
    pairs = _group(graded, "executor")
    for executor in sorted(pairs):
        rows = pairs[executor]
        for size in sorted({r.get("size") or "?" for r in rows}):
            serial = _med_wall(executor, size, "serial")
            parallel = _med_wall(executor, size, "parallel")
            multi = _med_wall(executor, size, "multi")
            speedup = (serial / parallel) if (serial and parallel) else None
            overhead = (multi / serial - 1.0) if (multi and serial) else None
            lines.append(
                "| {e} | {s} | {ser} | {par} | {sp} | {mu} | {ov} |".format(
                    e=executor, s=size,
                    ser=_fmt(serial, "{:.1f}"), par=_fmt(parallel, "{:.1f}"),
                    sp=_fmt(speedup, "{:.2f}x"),
                    mu=_fmt(multi, "{:.1f}"),
                    ov=_fmt(None if overhead is None else overhead * 100, "{:+.0f}%"),
                )
            )
    return lines


def _cost_section(graded):
    lines = [
        "| executor | runs | total cost | cost/pass | notes |",
        "|---|---|---|---|---|",
    ]
    by_exec = _group(graded, "executor")
    sonnet = by_exec.get("claude", [])
    sonnet_cost = sum(_num(r.get("cost"), 0.0) for r in sonnet)
    total = 0.0
    for executor, rows in sorted(by_exec.items()):
        cost = sum(_num(r.get("cost"), 0.0) for r in rows)
        total += cost
        solved = sum(1 for r in rows if r.get("status") == "pass")
        notes = "Sonnet (paid-tier model) - reported separately" if executor == "claude" else ""
        lines.append("| {e} | {n} | {c} | {cp} | {nt} |".format(
            e=executor, n=len(rows), c=_fmt(cost, "${:.2f}"),
            cp=_fmt(cost / solved if solved else None, "${:.3f}"), nt=notes))
    lines.append("| **total** | {n} | {c} |  |  |".format(
        n=len(graded), c=_fmt(total, "${:.2f}")))
    lines.append("")
    lines.append(f"Excluding Sonnet (`claude`): {_fmt(total - sonnet_cost, '${:.2f}')}.")
    return lines


def _delta_section(rows):
    """Per-metric deltas between the newest and the previous harness_sha."""
    shas = OrderedDict()
    for row in rows:
        sha = row.get("harness_sha") or "unknown"
        entry = shas.setdefault(sha, {"n": 0, "pass": 0, "cost": 0.0, "wall": []})
        entry["n"] += 1
        if row.get("status") == "pass":
            entry["pass"] += 1
        entry["cost"] += _num(row.get("cost"), 0.0)
        w = _num(row.get("wall_s"))
        if w is not None:
            entry["wall"].append(w)

    lines = []
    for sha, entry in shas.items():
        lines.append("- `{sha}`: {n} rows, {p} pass, {c} cost, median wall {w}.".format(
            sha=sha, n=entry["n"], p=entry["pass"],
            c=_fmt(entry["cost"], "${:.2f}"), w=_fmt(_median(entry["wall"]), "{:.1f}")))
    if len(shas) <= 1:
        lines.append("")
        lines.append("Only one harness revision present; no delta available.")
        return lines

    newest = list(shas)[-1]
    previous = list(shas)[-2]
    old, new = shas[previous], shas[newest]
    old_rate = old["pass"] / old["n"] if old["n"] else 0.0
    new_rate = new["pass"] / new["n"] if new["n"] else 0.0
    lines.append("")
    lines.append(f"Delta `{previous}` -> `{newest}`: pass-rate {old_rate * 100:.0f}% -> {new_rate * 100:.0f}%, "
                 f"cost {new['cost'] - old['cost']:+.2f} USD.")
    return lines


def build_report(rows):
    """Markdown report from results rows. Safe on empty input."""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    lines = ["# harness-suite results", ""]
    if not rows:
        lines.append("No results yet. Run `python harness-suite/suite.py` to populate "
                     "`harness-suite/results.csv`.")
        return "\n".join(lines) + "\n"

    graded = _graded(rows)
    lines.append(f"Rows: {len(rows)} total, {len(graded)} counted "
                 f"({len(rows) - len(graded)} infra_error excluded).")
    lines.append("")

    lines.append("## Per executor x size x mode")
    lines.append("")
    grouped = defaultdict(list)
    for row in graded:
        grouped[(row.get("executor") or "?", row.get("size") or "?", row.get("mode") or "?")].append(row)
    ordered = OrderedDict()
    for key in sorted(grouped, key=lambda k: tuple(str(x) for x in k)):
        ordered[key] = grouped[key]
    lines.extend(_grid_table(ordered, _max_rep(rows)))
    lines.append("")

    lines.append("## Parallel speedup and multi overhead")
    lines.append("")
    lines.extend(_mode_comparison(graded))
    lines.append("")

    lines.append("## Cost")
    lines.append("")
    lines.extend(_cost_section(graded))
    lines.append("")

    lines.append("## Harness revision delta")
    lines.append("")
    lines.extend(_delta_section(rows))
    lines.append("")

    excluded = len(rows) - len(graded)
    if excluded:
        lines.append(f"Note: {excluded} infra_error row(s) excluded from all pass-rate math.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    rows = load_rows(RESULTS_CSV)
    text = build_report(rows)
    RESULTS_MD.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_MD.write_text(text, encoding="utf-8")
    print(f"wrote {RESULTS_MD} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
