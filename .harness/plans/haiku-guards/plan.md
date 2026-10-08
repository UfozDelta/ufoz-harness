# Plan: haiku-guards

Goal: give the in-Claude haiku-executor path the runner's guards, and fix haiku 5.5 cost reporting.

## Decisions
- New `--check DIR` on run_plan.py: verifies work done OUTSIDE the runner (e.g. by @haiku-executor in a git worktree). Plan files come from the main tree `.harness/plans/<slug>/`; DIR is the worktree root. Runs nothing else, no worktree creation.
- `--check` does three things: (1) grader lock: `Plan(slug, ".harness/plans").lock_broken()` (locks first if no lock yet); (2) scope: every changed/untracked file in DIR (via `git -C DIR status --porcelain -uall`) must be `in_scope` of the union of all tasks' `files`, ignoring paths under `.harness/plans/`, `.claude/`, `.worktrees/`; (3) each task's acceptance run with cwd=DIR via `run_acceptance(cmd, expect)` (honour task.expect). Prints `PASS|FAIL <id>` per task and `SCOPE <path>` per violation; exit 0 only if all clean.
- Haiku 5.5 cost: the claude CLI's `total_cost_usd` is wrong for it. `RATES` dict in claude.py, $/M tokens `(input, output, cache_read)`, `{"claude-haiku-5-5": (0.10, 0.50, 0.01)}`. When the run's model is in RATES, cost = (usage.input*in + usage.output*out + usage.cache_read*cr)/1e6 (output already includes thinking; do not add reasoning). Other models keep the CLI cost.

## T1 check module
FILES: .harness/runner/check.py, .harness/runner/cli.py
MUST: check.py exposes `changed_files(root)`, `scope_violations(changed, task_files)` (pure: returns sorted paths not in scope, after the ignore prefixes) and `check(slug, root)` -> int. cli.py: add `--check DIR` arg and dispatch in `_run` right after `--relock-only` handling (before worktree logic), `sys.exit(check.check(args.slug, args.check))`. Reuse `plan.in_scope`, `acceptance.run_acceptance`, `Plan`.
TEST: smoke command in tasks.json.

## T2 haiku cost
FILES: .harness/runner/executors/claude.py
MUST: `RATES` + cost override after the usage is parsed in `run_claude_exec`, using its `model` arg. Small pure helper `rated_cost(model, usage)` -> float | None (None when model not in RATES).

## T3 summary
FILES: .harness/plans/haiku-guards/SUMMARY.md
MUST: <=600 chars: what, files, wiring. Then existing tests still pass.
