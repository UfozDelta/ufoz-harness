# Plan: verify-isolation
## Goal
A verify-bench cell cannot read other cells' projects or hidden tests, and a cell that tries is not counted as a pass.

## Decisions
- Layer 1 (remove source): before `cells.make_project`, delete every dir in `cells.TEMP_ROOT` whose name starts with `verify-` and is not this cell's slug. Never touch `_kit`, `_specs` or non-`verify-` dirs (suite runs share the root).
- Layer 2 (detect): `backends.check_escape(log_text, slug) -> (ok, offending_line)`. A line is an escape when it mentions `ufoz-bench` followed by a path segment starting `verify-` or `suite-` that is not `slug`, or contains `hidden_tests`, `test_hidden` or `suite/fixtures`. Offending line written to `rules_failures.log` as `<slug>: escape: <line>`.
- Wiring: after the headless orchestrator run, check its raw output; if it escaped return `finish("fail", "escaped_cwd")`. At the end of a scored cell, check plan.log + exec.log text; an escape turns status pass into `fail` with `fail_reason=escaped_cwd` and `rules_ok=false`.
- Layer 3 (nudge): `_plan_brief` gains one sentence: work only inside the current directory; never read paths outside it.

## interfaces
- `backends.check_escape(log_text, slug) -> (bool, str)`.
- `verify._wipe_stale(cells, slug)`.

## T1 detector
FILES: bench/verify/backends.py
MUST:
- Add `check_escape` per Decisions (regex, case-insensitive, `\` and `/` separators both match).
TEST: python .harness/plans/verify-isolation/checks/check_t1.py

## T2 wiring
FILES: bench/verify/verify.py
MUST:
- Add `_wipe_stale`, call it before `make_project`; extend `_plan_brief`; wire escape checks per Decisions, reusing the `rules_failures.log` append pattern of `_rules_check`.
TEST: python .harness/plans/verify-isolation/checks/check_t2.py

## T3 summary
FILES: .harness/plans/verify-isolation/SUMMARY.md
MUST:
- SUMMARY.md (<= 600 chars: what, files, how wired) ending `BUILD: pass` after `python bench/verify/verify.py --dry` exits 0. Write it with a bash heredoc.
TEST: python .harness/plans/verify-isolation/checks/check_t3.py
