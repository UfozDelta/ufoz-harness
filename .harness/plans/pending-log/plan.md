# Plan: pending-log

## Goal
1) `run_plan.py --pending`: list unlanded plan worktrees. 2) Quirk logging: main session logs harness hiccups to log.md; executors report theirs via a runner-owned `items/T<n>.quirks.md`.

## Decisions
- New module `.harness/runner/pending.py` with `pending(root=".worktrees") -> int` (prints, returns 0). No slug needed: `--pending` handled in `cli._run` right after `--stats`, before the slug check.
- One line per dir in root: `<slug>  <passed>/<total> tasks passed  <n> changed files` + `  (running)` if `.harness/plans/<slug>/run.lock` exists. total = len(tasks.json "tasks"); passed = items/*.report.md whose first line is `RESULT: pass`. changed = non-empty lines of `git -C <wt> status --porcelain -- . ":(exclude).harness/plans/<slug>"` via `subprocess.run(..., capture_output=True, check=False)`. Missing root or no dirs: print `no unlanded worktrees`.
- Executor quirks file: `.harness/plans/<slug>/items/T<n>.quirks.md`; guards.runner_owned treats `items/*.quirks.md` like `.report.md` (not a stray).
- log.md entry format (matches existing log.md): `## <YYYY-MM-DD> <slug or topic>` then one line per item `what → fix (or Open)`.
- Verified: runner_owned suffix tuple at .harness/runner/guards.py:59; `--stats` early-return at cli.py:152.

## T1 pending command
FILES: .harness/runner/pending.py, .harness/runner/cli.py
MUST:
- `--pending` flag (store_true, help "List plan worktrees not landed yet; run nothing.") and early return in `_run`.
- Output format exactly per Decisions; exit 0; works with no `.worktrees/`.
TEST: see tasks.json

## T2 quirks guard
FILES: .harness/runner/guards.py
MUST:
- Add `.quirks.md` to the items/ suffix tuple in `runner_owned`. No other change.
TEST: see tasks.json

## T3 executor rule
FILES: AGENTS.md
MUST:
- In the `.harness/` exception bullet, also allow `.harness/plans/<slug>/items/T<n>.quirks.md`.
- New bullet: a harness/tool/process quirk that should be fixed (not your task's own bug) -> one line per quirk in that file, `what → suggested fix`. Never edit log.md.
TEST: see tasks.json

## T4 main-session rule
FILES: CLAUDE.md, .harness/MAIN.md, log.md
MUST:
- CLAUDE.md and MAIN.md: add under `### Failures` a bullet: any hiccup or quirk (harness, tools, executor, process) that SHOULD be fixed -> append to `log.md` in the Decisions format; at Verify also copy each `items/T<n>.quirks.md` line there.
- CLAUDE.md and MAIN.md: in the same `### Failures` section, add a bullet `Unlanded worktrees: python .harness/run_plan.py --pending`.
- Edit ONLY the `### Failures` section of CLAUDE.md and MAIN.md (another unlanded plan edits steps 4-6). Nothing in step 7.
- log.md item 6 (`--relock` executes the plan): mark `→ **Fixed**: --relock-only locks and runs nothing.` Change nothing else in log.md.
TEST: see tasks.json

## T6 skip empty dirs
FILES: .harness/runner/pending.py, .harness/runner/land.py, .harness/plans/pending-log/SUMMARY.md
MUST:
- pending(): skip dirs in root that have no `.git` entry (real worktrees always have a `.git` file). No git call for this.
- land(): right after `git worktree remove --force`, if `wt` still exists and is empty, `wt.rmdir()`; ignore OSError (Windows lock). No rmtree.
- Append one line to SUMMARY.md (stay <= 600 chars): empty leftover dirs skipped by --pending and removed by --land.
TEST: see tasks.json

## T5 write summary
FILES: .harness/plans/pending-log/SUMMARY.md
MUST: write <= 600 chars: what was made, which files, how wired. Run `python .harness/run_plan.py --pending`; add `BUILD: pass` if exit 0 else `BUILD: fail <first error line>`.
TEST: see tasks.json
