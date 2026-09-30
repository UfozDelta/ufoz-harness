# relock-hint
Decisions: lock-mismatch hints point at --relock-only (locks, runs nothing); --relock stays but is no longer suggested.

## T1
FILES: .harness/runner/task_runner.py, .harness/runner/report.py
MUST: task_runner.py:177 LOCK-MISMATCH line and report.py:25 hint say `--relock-only`, then rerun. No other change.
TEST: grep both files for relock-only.

## T2
FILES: .harness/plans/relock-hint/SUMMARY.md
MUST: SUMMARY.md <= 600 chars.
TEST: selftest passes.
