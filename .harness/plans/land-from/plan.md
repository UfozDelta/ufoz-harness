# Plan: land-from

Goal: `run_plan.py <slug> --land --from DIR` lands work a Claude subagent did in a Claude worktree (`.claude/worktrees/agent-*`). PREREQ: `--check` (plan haiku-guards) is already in main.

## Decisions
- `--from DIR` is valid only with `--land`. Plan files stay in the main tree; DIR is payload only.
- `land.land_from(slug, directory)` -> int, new function; the existing `land(slug)` is untouched.
- Order: (1) refuse (return 1) unless `check.check(slug, directory) == 0` (it prints PASS/FAIL/SCOPE/LOCK); (2) build a binary patch from DIR: `git -C DIR add -N -- .` then `git -C DIR diff --binary HEAD -- <pathspecs>`, pathspecs = every task's `files` entry (Plan(slug, ".harness/plans").tasks[].norm_files), so out-of-scope edits can never land; (3) save it as `.harness/plans/<slug>/land.patch`, `git apply --check` in the main tree, fail with a message and keep DIR if it does not apply (main drifted / uncommitted edits in those files); (4) `git apply`; (5) only then `git -C DIR rev-parse --abbrev-ref HEAD` for the branch, `git worktree remove --force DIR`, `git branch -D <branch>`; print `landed <slug>: N files`.
- Reuse land.py's `_git` helper. Patch is BYTES, never decoded. No commits, no stash.
- cli: `--from DIR` arg; `if args.land:` calls `land.land_from(args.slug, args.from_dir)` when set, else `land.land(args.slug)`.

## T1 land_from
FILES: .harness/runner/land.py, .harness/runner/cli.py
MUST: as Decisions. Smoke in tasks.json.

## T2 summary
FILES: .harness/plans/land-from/SUMMARY.md
MUST: <=600 chars: what, files, wiring.
