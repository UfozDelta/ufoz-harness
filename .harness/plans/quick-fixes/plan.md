# Plan: quick-fixes

## Goal
Five small fixes found while running pi as the main session (docs-move dry run): a Windows
console crash, two undocumented conventions, and one real guard gap (executor can edit its own
hash-locked acceptance check before the lock check catches it).

## Decisions
1. `run_plan.py` reconfigures stdout/stderr to UTF-8 at the top, so `→` and other non-ASCII
   summary output never crashes on Windows' cp1252 console. `--relock` running the whole plan is
   existing, documented behavior (README/CLAUDE.md already say so) — not touched here.
2. `MAIN.md` gets an explicit spec-file convention: `.harness/plans/<slug>/SPEC.md`, not
   `.harness/specs/` — keeps a plan's input next to its output.
3. `.claude/agents/planner.md` gets an explicit rule: any acceptance script the plan needs goes in
   `checks/check_t<n>.py` (hash-locked), never in a task's `files` list.
4. `.pi/extensions/deny-match.ts` gains a pure `isChecksPath(cwd, p)` helper; `deny-list.ts` denies
   any write/edit under a `checks/` directory in real time, regardless of `external_directory`,
   so the pi executor can't touch its own acceptance check before the post-hoc hash check runs.
   Main session already added, before this run: root `tsconfig.json` + `package.json`
   (typescript devDependency) + `.pi/extensions/pi-coding-agent.d.ts` ambient shim, so
   `npx tsc --noEmit` on these files is finally possible (the cached global `tsc` was 4.9.5 and
   can't resolve `.ts`-extension imports or `@earendil-works/pi-coding-agent`'s types) — the repo's
   own docs already assumed this worked. `.gitignore` gained `.harness/tsc.tsbuildinfo`.
5. `MAIN.md` Output style gets one line banning narrated reasoning / re-litigating a decision
   already made, matching the terseness the main session is supposed to have everywhere.

## T1 utf-8 stdout
FILES: .harness/run_plan.py
MUST: right after the `sys.path.insert` line, reconfigure both `sys.stdout` and `sys.stderr` to
UTF-8 with `errors="replace"` (guard with `hasattr(sys.stdout, "reconfigure")` for non-tty
redirects). No other lines change.
TEST: checks/check_t1.py (already written, hash-locked): proves stdout is UTF-8 and that printing
U+2192 (the arrow `run_plan.py`'s own summaries use) no longer crashes.

## T2 spec-file convention
FILES: .harness/MAIN.md
MUST: in the Plan step (step 2 of the loop), after "write a spec file describing the work", add
that it goes at `.harness/plans/<slug>/SPEC.md` (create the dir yourself before running `--plan`).
Do not reword anything else in that step.
TEST: python -c "s=open('.harness/MAIN.md',encoding='utf-8').read(); assert '.harness/plans/<slug>/SPEC.md' in s"

## T3 planner checks/ contract
FILES: .claude/agents/planner.md
MUST: add one rule near the acceptance/checks guidance (around the existing `checks/check_t<n>.py`
mentions in the Layout section) stating that any acceptance script a plan needs must live at
`checks/check_t<n>.py` and must never appear in a task's `files` list. Do not touch the example
JSON blocks.
TEST: python -c "s=open('.claude/agents/planner.md',encoding='utf-8').read(); assert 'never' in s.lower() and 'check_t' in s and s.lower().count('checks') >= 2"

## T4 deny checks/ writes
FILES: .pi/extensions/deny-match.ts, .pi/extensions/deny-list.ts, .pi/extensions/deny-match.test.mjs
MUST:
- deny-match.ts: add `export function isChecksPath(cwd: string, p: string): boolean` — true when
  the path (resolved relative to cwd) has a path segment exactly equal to `checks`.
- deny-list.ts: in the write/edit handler, before the existing `external_directory` check, deny
  (reason: `denied: checks/ is hash-locked, the executor may not edit acceptance checks`) when
  `isChecksPath(ctx.cwd, p)` is true, regardless of `external_directory`.
- deny-match.test.mjs: add cases proving `isChecksPath` is true for `checks/check_t1.py` and
  `.harness/plans/x/checks/check_t1.py`, false for `.harness/plans/x/plan.md`.
TEST: node .pi/extensions/deny-match.test.mjs && npx tsc --noEmit --incremental --tsBuildInfoFile .harness/tsc.tsbuildinfo

## T5 tighten main-session output style
FILES: .harness/MAIN.md
MUST: in the "Output style" section, add one line: no narrated reasoning and no re-litigating a
decision already made — state the result, not the thought process. Do not reword the existing
lines.
TEST: python -c "s=open('.harness/MAIN.md',encoding='utf-8').read(); assert 'narrat' in s.lower()"

## T6 write summary
FILES: .harness/plans/quick-fixes/SUMMARY.md
MUST: write <= 600 chars covering what was made (utf-8 stdout fix, spec-file convention, planner
checks/ contract, deny-list checks/ hardening, output-style line), which files, how wired.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/quick-fixes/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
