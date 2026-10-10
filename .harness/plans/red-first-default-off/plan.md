# Plan: red-first-default-off
## Goal
red_first defaults false. Opt in with `"red_first": true`. Drop red_first_reason lint rule + planner rule 6. Fix docs.
## Decisions
- Default flips in `.harness/runner/plan.py` (dataclass field + `d.get("red_first", True)`) to False.
- `.harness/runner/lint.py`: delete the "red_first false needs a red_first_reason" check (lines ~107-108). Red-first lint loop (line ~135) must skip unless `t.get("red_first") is True` (default False).
- `report.py` check_invalid message: say `set "red_first": false (or drop the key)`; no red_first_reason.
- Existing plans keep `red_first_reason` keys: extra key harmless, do NOT edit them.
- Out of scope: `packages/ufoz-harness/kit/**` (stale copy), bench/**.
Verified: only tests/test_lint.py:28 relies on default-on (`grep -n red tests/test_lint.py`).
Verified: selftest.py has no red_first refs.
## interfaces
Task.red_first: bool = False. tasks.json key `red_first` optional.
## T1 runner default
FILES: .harness/runner/plan.py, .harness/runner/lint.py, .harness/runner/report.py
MUST: default False in both plan.py spots (field line 30, `d.get("red_first", True)` line 39); lint.py line 135 must not use `get("red_first", True)`; lint rule removed; lint red-first loop runs only for `red_first: true`; report.py text updated.
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner.plan import Task; import inspect; assert 'red_first: bool = False' in inspect.getsource(Task); from pathlib import Path; assert 'needs a red_first_reason' not in Path('.harness/runner/lint.py').read_text(); assert all('get(\"red_first\", True)' not in Path('.harness/runner/'+f).read_text() for f in ('plan.py','lint.py'))"
## T2 fix tests
FILES: tests/test_lint.py
MUST: test at line 28 (`test_acceptance_that_passes_untouched_is_check_invalid`) sets `"red_first": True` on its task. Add `test_red_first_default_off_skips_untouched_check`: task without red_first, passing acceptance -> `lint OK`, return 0. Add `test_red_first_false_needs_no_reason`: `red_first: False` without reason lints OK.
TEST: python -m pytest tests/test_lint.py tests/test_task_runner.py -q -k "default_off or needs_no_reason or check_invalid"
## T3 docs
FILES: .harness/HARNESS.md, .claude/agents/planner.md, docs/ARCHITECTURE.md, README.md, docs/FLOWS.md, .harness/run_plan.py, packages/ufoz-harness/kit_readme.md
MUST: HARNESS.md line ~40: edit the file as it stands at run time; replace "(no tests; red-first is on by default, so set `red_first_reason` ... off)" with "(no tests, red-first off by default; opt in per task with `\"red_first\": true`)". planner.md: line 26 -> "Red-first is off by default; leave `red_first` out."; line 49 drop `"red_first": false, "red_first_reason"...`; rule 6 (line 62): delete its red_first sentence, keep Windows-shell sentences (keep numbering 6). ARCHITECTURE.md: remove `red_first_reason` (~37,54,311) and change line 88 "(the default)" to say off by default, opt in with true. README.md ~150: drop `red_first_reason` text. kit_readme.md lines 52,54: drop `red_first_reason`, say red-first is opt-in (not on by default). FLOWS.md line 57 has no red_first_reason; only reword if it implies default-on. run_plan.py docstring ~22: remove red_first_reason mention. Do not touch docs/flows.html.
TEST: python -c "from pathlib import Path; fs=['.harness/HARNESS.md','.claude/agents/planner.md','docs/ARCHITECTURE.md','README.md','packages/ufoz-harness/kit_readme.md']; assert not [f for f in fs if 'red_first_reason' in Path(f).read_text(encoding='utf-8')]; assert '(the default)' not in Path('docs/ARCHITECTURE.md').read_text(encoding='utf-8'); assert 'with reason' not in Path('.claude/agents/planner.md').read_text(encoding='utf-8')"
## T4 verify
FILES: .harness/plans/red-first-default-off/SUMMARY.md
MUST: run `python .harness/selftest.py` and `python -m pytest tests -q`; `python .harness/run_plan.py <slug> --lint` for every dir in .harness/plans containing tasks.json (skip this plan); record result lines in SUMMARY.md.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/red-first-default-off/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
