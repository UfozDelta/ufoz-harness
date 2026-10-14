# Harness improvements, 2026-10-10

Written for: the repo owner, as a record of what changed in the plan → execute harness and why.

## How it came about

1. Summarised how the harness works from `.harness/HARNESS.md`.
2. An Opus agent checked the summary against the docs and code. It found no false claims but several omissions, and two doc errors (clean-tree check only runs in worktree mode; red-first default).
3. A second Opus agent looked for friction and ranked 8 improvements.
4. Seven `@planner` agents wrote one plan each. A Sonnet agent audited them and found 6 of 7 needed fixes (weak acceptance checks, missing scope, test setup gaps). All were fixed and re-linted.
5. The plans ran through the harness one at a time. Each diff was reviewed and landed before the next started.

## What landed (in order)

| Plan | Change |
|---|---|
| `skip-plan-dir-dirty` | The clean-tree check ignores `.harness/plans/<slug>/` for the slug being run (matched on a path boundary, so `x` does not hide `xy`). No more "chore(plans)" commit before each run. Other dirty paths still refuse. |
| `land-merge-fallback` | `--land` tries `merge --ff-only`, falls back to `merge --no-ff` when main has moved, and aborts cleanly on conflict (worktree and branch kept). Copied plan records are now committed, so the tree stays clean. |
| `stray-revert-retry` | An attempt that touches files outside its task's `files` is reverted (tracked files restored, untracked deleted) and retried once with feedback naming the allowed files, the reverted files and the acceptance output. A second stray still fails the task. |
| `lint-hardening` | `--lint` runs red-first checks in a throwaway detached worktree instead of the main tree. On win32 it errors on acceptance commands starting with `!`, `test ` or `rm `. Duplicate ancestor loop removed. |
| `red-first-default-off` | `red_first` now defaults to false; opt in per task with `"red_first": true`. The `red_first_reason` lint rule is gone. Docs and `planner.md` updated. Plans with no key stop running red-first. |
| `land-drop-yes` | Removed the interactive-terminal gate on `--land` and the `interactive()` helper. `--yes` stays as a hidden no-op for one release. Agents are still blocked from landing by `git_guard.py` and `.pi/deny.json`. |
| `prune-executors` | Removed the cold `cline` executor, `--planner cline`, its bench arms and docs, and a duplicate `log.md` section. `cline-acp`, `llama` and `--session` stay (they are used outside bench copies). |
| `cline-cut` | Removed the `cline-acp` executor (`cline_acp.py`, `--executor`/`--planner cline-acp`, `CLINE_MODEL`, `HARNESS_CLINE*`), its bench arms, tests and docs. Registry is now pi, claude, opencode, llama. |

## Decided against

- `haiku-path-simplify` (drop the `agent:haiku` backend for `claude:haiku`) was planned, then dropped. The `agent:haiku` route and its agents-panel view stay as they were.

## Verification

- `python .harness/selftest.py`: doctor OK, unit tests OK, pi executor PASS.
- `python -m pytest tests -q`: 159 passed.
- `run_plan.py --pending`: no unlanded worktrees.

## Open follow-ups

- `--lint` now flags POSIX-style acceptance on Windows in two older plans: `map-skip-worktrees` T2 and `plan-status` T3. They were already broken on Windows.
- `HARNESS.md` Failures still says "discard + re-brief" for out-of-scope files. That is now automatic (one revert and retry).
- `docs/findings.md` keeps cline results as benchmark history. `packages/ufoz-harness/kit/` is stale until the next prepack.
- `agent:haiku` problems noted but not fixed: the `git_guard` hook did not fire in two live probes (`log.md`), and `SUMMARY.md` needs a heredoc workaround.
- `run_plan.py` docstring says it never touches git state, but worktree mode creates branches and worktrees.
