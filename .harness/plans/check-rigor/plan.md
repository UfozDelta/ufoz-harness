# Plan: check-rigor

## Goal
Close the escape hatch where a weak executor passes on a loose check: red-first becomes ON by
default for tasks whose acceptance calls a plan-dir `checks/` script, and lint WARNs on a bare
substring `expect` with no checks script.

## Decisions
- Default applies ONLY when the `red_first` key is absent from the task dict AND the acceptance
  tokenises to a `checks/<name>.py` script that exists in the plan dir. Explicit `"red_first": false`
  wins; `true` stays honoured. Plans with no `checks/` behave exactly as before.
- Resolve cwd-independently: `uses_checks_script` matches a whitespace token whose path contains
  `checks/` and whose basename resolves under `plan_dir/"checks"`. Do not use `Path(tok).exists()`
  (cwd-dependent; lint already does that at its own line, leave it).
- Apply the default in `Plan.__init__` (runtime `task_runner` reads `t.red_first`) AND in
  `lint.lint`'s `todo` filter (it reads raw dicts). Both call the same helper.
- `acceptance.py` is reference only; the substring decision at line 49-50 is NOT changed.
- WARN text starts `f"{tid}: loose expect"`. Warnings never fail lint (`lint.py:187`).
- New tests go in new files `tests/test_lint_red_first.py`, `tests/test_lint_expect.py`; existing
  `tests/test_lint.py` is not edited.

Verified: red-first gate `lint.py:175-186`, worktree copies the plan dir `lint.py:80-86`; runtime
gate `task_runner.py:253-262` (`t.red_first`); substring expect `acceptance.py:49-50`;
`python -m pytest tests/test_lint.py -q` = 5 passed (`tests/`)
Unverified: whether `.harness/build_map.py --check` staleness (`stale`) affects anything here
Later: none.

## interfaces
- `runner/plan.py` (new, public): `uses_checks_script(plan_dir: Path, acceptance: str) -> bool`.
- `runner/plan.py`: `Plan.__init__` sets `t.red_first = uses_checks_script(self.dir, t.acceptance)`
  for every task whose raw dict lacks a `red_first` key.
- `runner/lint.py`: imports `uses_checks_script` from `.plan`; `todo` filter gains
  `or uses_checks_script(plan, t.get("acceptance", ""))`.

## T1 red-first default on
FILES: .harness/runner/plan.py, .harness/runner/lint.py, tests/test_lint_red_first.py
MUST:
- Add `uses_checks_script` to `plan.py`; True only for a token naming an existing `checks/*.py`
  under the given plan dir (`False` for a missing script, a bare `python -c`, or a path with no
  `checks/` segment).
- `Plan.__init__` fills the default only when `"red_first" not in t.raw`; explicit `false` and
  `true` are untouched.
- `lint.lint`'s `todo` includes defaulted tasks, so a check that passes on the untouched tree is
  still the `check-invalid` ERROR; keep the existing ERROR string verbatim.
- Tests: `test_red_first_defaults_on_for_checks_script` (helper True), `test_red_first_false_opts_out`,
  `test_no_checks_script_stays_off`, and `test_lint_red_first_proofs_defaulted_task` (lint ERROR on a
  checks-bearing task with no `red_first` key).
- Keep the existing 5 `tests/test_lint.py` tests green; do not weaken them.
TEST: python -m pytest tests/test_lint_red_first.py tests/test_lint.py -q

## T2 warn on loose expect
FILES: .harness/runner/lint.py, tests/test_lint_expect.py
MUST: T1 landed (import `uses_checks_script` from `.plan`, do not redefine it).
- For a task with a non-None `expect`, no `checks/` script in its acceptance and no `checks/` dir
  in the plan, append exactly one WARN starting `f"{tid}: loose expect"` naming the substring.
- No WARN when `expect` is absent, or when the acceptance does call a checks script.
- WARN only: `lint(...)` still returns 0 for that plan.
- Tests: `test_bare_expect_warns_without_checks`, `test_expect_with_checks_script_does_not_warn`,
  `test_expect_warning_does_not_fail_lint`.
TEST: python -m pytest tests/test_lint_expect.py -q

## T3 document the default
FILES: .harness/CHECK_PATTERNS.md, .claude/agents/planner.md
MUST: replace the "Red-first is off by default; leave red_first out" line in
`.claude/agents/planner.md` with the new rule (default on for checks-bearing tasks, `red_first:
false` opt-out); add a CHECK_PATTERNS.md section naming the default, the opt-out and that a bare
`expect` substring now WARNs. Do not restate the plan. `python -m pytest tests/test_lint.py -q` stays green.
TEST: python -c "from pathlib import Path; a=Path('.harness/CHECK_PATTERNS.md').read_text(encoding='utf-8'); b=Path('.claude/agents/planner.md').read_text(encoding='utf-8'); assert 'red_first' in a and 'checks' in a and 'red_first' in b, 'docs not updated'"

## T4 write summary
FILES: .harness/plans/check-rigor/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/check-rigor/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
