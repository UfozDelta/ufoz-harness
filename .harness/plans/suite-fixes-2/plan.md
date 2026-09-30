# Plan: suite-fixes-2

## Goal
Fixture checks must fail before a task's own work, and every brief names its work dir.

## Decisions
- A task's acceptance must FAIL on seed + its deps' finished files (seed stubs included) and PASS
  once its own files are done. Seed stubs throw/raise "not implemented"; a check that only tests
  an export exists passes on a stub. Make such checks call the function or reject the stub text
  (medium T2 already does: `if(/not implemented/.test(s))process.exit(1)`).
  Found today: medium T3 (`lib/validate.ts`), large T5 (`web/lib/api-client.ts`).
- Every fixture `plan/plan.md` gets, right under its title, the line:
  `Work dir: \`{work}\` - every path in this plan is relative to it; cd there before running anything.`
- `cells.prepare_cell` replaces `{work}` in plan.md exactly like tasks.json (worktree copy and
  main-tree copy).
Verified: `checks/check_red.py` fails today on exactly those two tasks plus the missing lines.

## T1 fixture checks and briefs
FILES: harness-suite/fixtures/small/plan/, harness-suite/fixtures/medium/plan/, harness-suite/fixtures/large/plan/
MUST:
- Fix medium T3 and large T5 acceptance per Decisions; touch no other task's check.
- Add the Work dir line to all three fixture plan.md files.
TEST: python .harness/plans/suite-fixes-2/checks/check_red.py && python .harness/plans/suite-fixes-2/checks/check_iso.py && python harness-suite/check_fixtures.py

## T2 template plan.md
FILES: harness-suite/cells.py
MUST: prepare_cell templates `{work}` in plan.md per Decisions.
TEST: python .harness/plans/suite-fixes-2/checks/check_t2.py

## T3 write summary
FILES: .harness/plans/suite-fixes-2/SUMMARY.md
MUST: <= 600 chars: what changed, which files. Add `BUILD: pass` if `python -m pytest tests/test_harness_suite.py -q` passes, else `BUILD: fail <first error>`.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/suite-fixes-2/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
