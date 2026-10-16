# Plan: bench-rigor

## Goal
Every reported executor comparison carries a rep count and a confidence/spread band, and any
difference inside that band is labeled `noise` instead of being reported as a win.

## Decisions
Verified: `wilson_ci(successes,total,z=1.959963985) -> (p,low,high)` and `_median(values)` exist (`bench/suite/report.py`).
Verified: `build_report(rows, all_shas=False)` / `_grid_table(cells,k)` / `_mode_comparison(graded)` / `_delta_section(rows)` (`bench/suite/report.py`).
Verified: suite `--reps` default is 3 (`bench/suite/suite.py`), `rep` is a CSV column; do NOT change suite.py or any CLI flag, and do NOT hard-fail on `--reps < 3` — the `low-reps` label is the only advisory.
Verified: `bench/speed/report.py` already prints `Runs` + medians; add only the spread + low-rep note. No new deps.
Verified: `python -m pytest tests/test_harness_suite.py -q` -> 47 passed, 15s (baseline).
- `MIN_REPS = 3` module constant in `bench/suite/report.py`. A grid cell with `0 < reps < MIN_REPS` renders `low-reps`.
- `rep_count(rows) -> int` (new, bench/suite/report.py): distinct non-empty `rep` values; 0 when none.
- Grid header becomes `... | n | reps | pass@1 | ...`; reps cell = `-` when `rep_count==0`, else `f'{reps}'` + `' (low-reps)'` when `reps < MIN_REPS`. One footnote line after the last grid row when any cell is low-reps.
- Noise rule (suite): two 95% Wilson intervals overlap on the low/high axis ⇒ delta printed as `pass-rate delta within noise (CIs overlap ...)`.
- Noise rule (speedup): `_mode_comparison` renders `1.02x (noise)` when the 95% seeded-bootstrap CI (`random.Random(0)`, 1000 resamples, percentile) of the serial/parallel `wall_s` ratio contains `1.0`; otherwise the point speedup. No fixed 5% band; a side with `<2` reps or missing wall_s stays `-`.
- `spread(values) -> tuple|None` (new, bench/speed/report.py): `(min,max)` of the floats, `None` when <2 values. New COLUMNS entry `("wall_s min-max", "wall_s min-max")` placed directly after `("median wall_s", ...)`. Cell = `lo-hi` via `display()`, `-` when `None`.
- `build_report` (speed) appends one `Low-rep: <harness> / <task>: N run(s) (< MIN_REPS); medians and spread untrustworthy` line per harness group with <3 rows.
- Keep the existing leading space in `- ...` bullet lines of `_delta_section`. No markdown table column reordering elsewhere.
- Resolved: no task regenerates or commits `bench/*/RESULTS.md`; smoke only calls the builders. Regenerating RESULTS.md stays a manual, on-demand step (never a build task).
Later: JSON output mode for the reports; per-task Wilson bands in the speed CSV.

## interfaces
Preserve: `wilson_ci`, `_median`, `_fmt`, `first_try`, `arm_label`, `_graded`, `latest_per_cell`, `newest_sha_rows`,
`build_report(rows, all_shas=False)`, `_grid_table(cells, k)`, `_scorecard(graded, field)`, `_mode_comparison(graded)`,
`_cost_section(graded)`, `_delta_section(rows)`; speed: `COLUMNS`, `number`, `display`, `table(title, rows, level=2)`, `build_report(rows)`.
New (public, importable): `rep_count`, `MIN_REPS` (suite); `spread` (speed).

## T1 speed spread and reps
FILES: bench/speed/report.py
MUST: implement `spread(values)` per Decisions; add the COLUMNS entry in the mandated position; `table()` renders `lo-hi` and `-` for `<2` samples.
MUST: a group with 1 row still renders `-` for the spread and never raises; blank/absent `wall_s` counts as `0` via `number()`.
MUST: emit the `Low-rep: ...` note for every harness group under 3 rows, sorted by harness; no note when all groups have >= 3.
TEST: python -c "import sys; sys.path.insert(0, 'bench/speed'); import report as r; base = {'tests_passed': '1', 'tests_total': '1', 'output': '2', 'input': '3', 'cache_read': '0', 'tool_calls': '1', 'turns': '1', 'task': 'small'}; rows = [dict(base, harness='pi', wall_s=w) for w in ('10', '14')] + [dict(base, harness='opencode', wall_s='9', task='medium')]; t = r.build_report(rows); assert 'wall_s min-max' in t, t; assert '| 10-14 |' in t, t; assert 'Low-rep' in t, t"

## T2 grid reps column
FILES: bench/suite/report.py
MUST: add `rep_count` + `MIN_REPS`; add the `reps` header and cell to `_grid_table` in the Decisions position/format.
MUST: `n` keeps counting graded rows; the reps footnote appears only when at least one cell is low-reps; empty `cells` returns the bare header.
MUST: rows with `rep` missing/empty do not count; `0` reps renders `-`, never `low-reps`.
TEST: python -c "import sys; sys.path.insert(0, 'bench/suite'); import report; rows = [{'size': 'small', 'mode': 'serial', 'executor': 'pi', 'rep': r, 'status': 'pass', 'wall_s': '2.0', 'tasks_total': '1', 'attempts': '1', 'harness_sha': 'b'} for r in ('1', '2', '3')] + [{'size': 'small', 'mode': 'parallel', 'executor': 'pi', 'rep': '1', 'status': 'pass', 'wall_s': '1.0', 'tasks_total': '1', 'attempts': '1', 'harness_sha': 'b'}]; t = report.build_report(rows, all_shas=True); assert '| reps |' in t, t; assert '| 1 (low-reps) |' in t, t; assert 'low-reps' in t.split('## Per capability')[0], t"

## T3 noise labels
FILES: bench/suite/report.py
MUST: `_delta_section` compares the last two shas with `wilson_ci` on (passes, n) each; overlapping CIs render the noise wording, never a bare `old -> new` pass-rate claim.
MUST: `_mode_comparison` appends ` (noise)` to the speedup cell when the seeded-bootstrap 95% CI of the serial/parallel `wall_s` ratio contains `1.0`; a real speedup stays `2.10x`; `<2` reps or missing wall_s stays `-`.
MUST: one revision only still prints `Only one harness revision present; no delta available.`; `n == 0` on a sha renders `-` and no crash.
TEST: python -c "import sys; sys.path.insert(0, 'bench/suite'); import report; rows = [{'size': 'small', 'mode': m, 'executor': 'pi', 'rep': r, 'status': 'pass', 'wall_s': '2.0', 'tasks_total': '1', 'attempts': '1', 'harness_sha': s} for s in ('a', 'b') for r in ('1', '2', '3') for m in ('serial', 'parallel')]; t = report.build_report(rows, all_shas=True); assert 'noise' in t.lower(), t; assert 'CIs overlap' in t, t"

## T4 spec tests
FILES: tests/test_harness_suite.py
MUST: add `test_rigor_reps_column_and_low_reps_warning`, `test_rigor_noise_on_overlapping_cis`, `test_rigor_speedup_bootstrap_ci`, `test_rigor_speed_report_spread_and_low_rep_note` (insert `bench/speed` on `sys.path` inside the last one; reuse the file's existing import block).
MUST: every new test builds rows inline, no network/executor; assert the `low-reps` cell, the `noise` wording, `10-14`-style spread, and the `<3` note.
MUST: leave all 47 existing tests untouched and passing.
TEST: python -m pytest tests/test_harness_suite.py -q -k "rigor"

## T5 write summary
FILES: .harness/plans/bench-rigor/SUMMARY.md