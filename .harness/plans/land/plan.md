# Plan: land

## Goal
`run_plan.py <slug> --land` = the user's one command to bring a finished worktree plan into the main tree:
apply its code changes, copy its plan records, remove the worktree + branch. The main session never runs it.

## Decisions
1. New module `.harness/runner/land.py`, stdlib only, `land(slug) -> int`, cwd = main tree. Steps in order:
   a. `wt = worktree.path_for(slug)`; not in `git worktree list --porcelain` (resolved paths) ->
      print `no worktree for <slug>`, return 1.
   b. `wt/.harness/plans/<slug>/run.lock` exists -> print `run in progress`, return 1.
   c. `git -C <wt> add -N -- .` (intent-to-add, so new files show in the diff; touches only the worktree's index).
   d. patch = stdout BYTES of `git -C <wt> diff --binary HEAD -- . ":(exclude).harness/plans/<slug>"`.
      Always write it to main `.harness/plans/<slug>/land.patch` (mkdir parents).
   e. Non-empty patch: `git apply --check` with the bytes on stdin (cwd main); fails -> print git's stderr,
      `nothing changed; patch kept at <path>`, return 1 (worktree untouched). Else `git apply` the same way.
   f. Copy `wt/.harness/plans/<slug>/` into main `.harness/plans/<slug>/` (dirs_exist_ok), skipping run.lock.
   g. Unlink junctions first: for each name in `worktree.SHARED_DIRS`, if `os.path.isjunction(wt/name)`
      -> `os.rmdir(wt/name)` (removes the link only, never the target). THEN
      `git worktree remove --force <wt>` and `git branch -D harness/<slug>`.
   h. print `landed <slug>: <n> files` (n = lines of `git apply --numstat` on the patch; 0 if empty), return 0.
2. All git calls via `subprocess.run(..., check=False)`; bytes for the patch (no text decoding: PowerShell-safe).
3. cli: `--land` (store_true, help says: user command, applies worktree changes + removes worktree). Right after
   the slug check: `sys.exit(land.land(args.slug))`.
Verified: worktree.py exposes `path_for`, `SHARED_DIRS`; Python 3.14 has `os.path.isjunction`.

## T1 land module
FILES: .harness/runner/land.py
MUST: Decisions 1-2 exactly.
TEST: python .harness/plans/land/checks/check_t1.py

## T2 cli flag
FILES: .harness/runner/cli.py
MUST: Decision 3 only; keep every existing flag.
TEST: python .harness/plans/land/checks/check_t2.py

## T3 docs + summary
FILES: README.md, CLAUDE.md, .harness/MAIN.md, .harness/plans/land/SUMMARY.md
MUST: README documents `--land` (steps, conflict case keeps the worktree + land.patch). CLAUDE.md + MAIN.md
step 6: "`--land` is the user's command; never run it yourself." SUMMARY.md <= 600 chars.
TEST: python .harness/plans/land/checks/check_t3.py
