# Plan: prune-flags
## Goal
Cut run_plan.py CLI from 29 flags to 18. Add `--executor agent:haiku` (two-call prepare/grade flow). Merge model flags into `backend:model`.

## Decisions
- Final flags (exactly 18 option strings): --only --timeout --review --status --relock-only --land --yes --lint --stats --pending --fresh --session --parallel --executor --plan --planner --no-worktree --no-window.
- `--no-worktree`/`--no-window`: plain `store_true` (dest `no_worktree`/`no_window`), no BooleanOptionalAction. Env `HARNESS_WORKTREE=0` / `HARNESS_WINDOW=0` still opt out. `use_worktree(args)`/`use_window(args)` keep names, read the new dests.
- `cli.parse_backend(spec, valid) -> (backend, model|None)`: split on FIRST `:`; unknown backend -> `SystemExit` naming valid ones. `--executor` valid = REGISTRY keys + `agent`. `--planner` valid = pi, opencode, claude, cline, cline-acp; planner model falls back to env `HARNESS_PLANNER_MODEL` when spec has none. Executor model -> `get(name, model=model)` only when given (as today).
- `--review` is `nargs="?", const="", default=None, metavar="BACKEND:MODEL"`. Only backend `claude` allowed (`claude:haiku`); bare = today's sonnet. `run_reviewer(..., model="sonnet")` new kwarg. Slug must come before `--review` (docs say so).
- `task_runner.RETRIES = 1`, `task_runner.REPAIRS = 1` module constants replace `args.retries/args.repair`. Run path calls `plan.lock_grader(False)` (signature unchanged).
- `--watch` removed. Window tab runs `python .harness/runner/watch.py <slug>` (watch.py gets `__main__`). `watch_dir(slug)` moves from cli.py to watch.py; cli imports it for `--status`.
- Agent backend (`--executor agent[:model]`, default model `haiku`) handled in cli after `--plan`/`--status`, before the normal run path; not when `--lint`. Needs git repo; with `--no-worktree` print error, exit 1.
  - Call 1 (no `.harness/plans/<slug>/main.baseline.json`): `check.prepare(slug)` (moved from cli.prepare: worktree.ensure, sync_plan, write_baseline); print `worktree: <abs path>` and `handoff: spawn claude-executor (Agent tool, no isolation, run_in_background true) with slug <slug> and path <abs path>, model <model>; then rerun this command`; exit 0.
  - Call 2 (baseline exists): `check.check(slug, wt_path)`; exit its code.
  - `check.check` also writes `<root>/.harness/plans/<slug>/items/T<n>.report.md` with a line `RESULT: pass` or `RESULT: fail`, and SKIPS (prints `SKIP T<n>`) tasks whose existing report has `RESULT: pass`. Messages say "since baseline", not "--prepare".
- `land.land_from` deleted; `--land` of agent worktrees uses normal `land.land`.
- bench keeps env `HARNESS_EXECUTOR_MODEL`, now passed as `--executor backend:model`.
- Dead code goes: `cli.prepare`, watch/relock/from branches, all `args.*` of removed flags.

Verified: 29 option strings today (`git grep -n add_argument .harness/runner/cli.py`)
Verified: window tab is the only internal user of `--watch` besides bench/suite/cells.py (`git grep -n -e "--watch" -- "*.py"`)
Unverified: `--land` works on an agent worktree like a runner one (branch `harness/<slug>`); executor must not touch land.py beyond deleting `land_from`.
Unverified: docs/flows.html, docs/session-flows.html, docs/mode-claude.svg, log.md, bench/arms/* still mention old flags.
Later: refresh those docs; regenerate REPO_MAP; `agent` in watch.EXECUTORS if needed.

## interfaces
- `check.prepare(slug) -> int`, `check.check(slug, root) -> int`, `check.write_baseline(slug)`.
- `watch.watch_dir(slug) -> Path`, `watch.window_command(slug) -> list`.
- `cli.build_parser()`, `cli.parse_backend`, `cli.use_worktree(args)`, `cli.use_window(args)`, `cli.relock_only(slug)` (kept).

## T1 constants and watch
FILES: .harness/runner/task_runner.py, .harness/runner/watch.py
MUST:
- Add `RETRIES = 1`, `REPAIRS = 1` module level in task_runner.py; use them for all 4 `args.retries`/`args.repair` spots.
- watch.py: add `watch_dir(slug)` (copy of cli's, uses `worktree.path_for`), `window_command` tail = `[sys.executable, ".harness/runner/watch.py", slug]`, fix the fallback hint print, add `__main__` block: `sys.exit(watch(watch_dir(sys.argv[1])))`.
- No `--watch` string left in watch.py.
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner import task_runner as t, watch as w; assert t.RETRIES==1 and t.REPAIRS==1; assert '--watch' not in ' '.join(w.window_command('x')); assert callable(w.watch_dir)"

## T2 check and land
FILES: .harness/runner/check.py, .harness/runner/land.py
MUST:
- Move `prepare(slug)` from cli.py into check.py (same body, returns 0/1).
- `check.check`: write per-task report with RESULT line, skip tasks already `RESULT: pass`; reword `--prepare`/`--check` text to "baseline".
- Delete `land.land_from` and imports only it used.
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner import check, land; assert callable(check.prepare) and not hasattr(land,'land_from')"

## T3 cli rewrite
FILES: .harness/runner/cli.py, .harness/runner/reviewer.py, .harness/run_plan.py
MUST:
- Parser exactly the 18 flags in Decisions; help strings updated (`backend:model`, `agent:haiku`, HARNESS_* envs).
- Implement parse_backend, agent flow (calls 1 and 2), review spec, constants; delete dead code.
- run_plan.py docstring usage lists only surviving flags.
- Bad specs (`--executor nope`, `--review pi:x`) exit nonzero with a message.
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner import cli; p=cli.build_parser(); n=sum(len(a.option_strings) for a in p._actions if a.option_strings and a.dest!='help'); assert n==18, n; assert cli.parse_backend('claude:sonnet',('claude','pi'))==('claude','sonnet'); assert cli.parse_backend('pi',('claude','pi'))==('pi',None)" && python .harness/run_plan.py --stats

## T4 fix tests
FILES: tests/test_prepare.py, tests/test_git_guard.py, tests/test_harness_suite.py
MUST:
- test_prepare.py: use `check.prepare`; replace parser test: `--check`/`--prepare`/`--watch`/`--relock` rejected (SystemExit), `--executor agent:haiku` parses.
- test_git_guard.py: drop `--from d` / `--check d` usage (use `--land` / `--lint`).
- test_harness_suite.py ~L757: expect `--executor <executor>:<model>` instead of `--executor-model`.
TEST: python -m pytest -q -x tests/test_prepare.py tests/test_git_guard.py tests/test_task_runner.py tests/test_check_main.py tests/test_harness_suite.py

## T5 bench callers
FILES: bench/suite/cells.py, .harness/bench/bench.py, .harness/bench/staged.py, .harness/runner/executors/cline.py, .harness/runner/executors/cline_acp.py, .harness/runner/executors/llama.py
MUST:
- cells.py: `_plan_args` passes `--executor <exec>:<model>` (no `--executor-model`); planner call passes `--planner <p>:<model>` (no `--planner-model`); window probe matches `*runner*watch.py*`; `_watch_ok` runs `[sys.executable, ".harness/runner/watch.py", slug]`.
- bench.py L298 -> `["--executor", "claude:haiku"]`; staged.py comment likewise.
- executor messages/comments: `--executor-model` -> `--executor backend:model`.
TEST: python -c "import pathlib; t=''.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['bench/suite/cells.py','.harness/bench/bench.py','.harness/runner/executors/llama.py']); assert '--executor-model' not in t and '--planner-model' not in t"

## T6 root docs
FILES: CLAUDE.md, .harness/MAIN.md, .claude/agents/claude-executor.md
MUST:
- CLAUDE.md "Plan -> execute loop": haiku/all-Claude paragraph (step 3), steps 4 and 5 describe the single command `python .harness/run_plan.py <slug> --executor agent:haiku` (call 1 prints worktree + handoff; spawn `claude-executor` run_in_background, no isolation; call 2 same command grades, `MAIN <path>` on main-tree writes); drop `--prepare/--check/--relock/--watch/--window/--worktree` mentions (keep `--relock-only`); executor line uses `backend:model`.
- MAIN.md and claude-executor.md: same flag replacement, nothing else changed.
TEST: python -c "import pathlib,re; t=''.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['CLAUDE.md','.harness/MAIN.md','.claude/agents/claude-executor.md']); assert 'agent:haiku' in t; assert not re.search(r'run_plan[^\n]*--(prepare|watch|relock)\b(?!-)', t)"

## T7 other docs
FILES: README.md, docs/ARCHITECTURE.md, docs/FLOWS.md, packages/ufoz-harness/README.md, packages/ufoz-harness/kit_readme.md
MUST:
- Flag tables list only the 18 flags (+ `backend:model` syntax, `agent:haiku`); remove rows for deleted flags and `--land --from`.
- ARCHITECTURE: retries/repair are constants (1 each); no `--watch`/`--relock`.
- FLOWS: `--relock` rows -> `--relock-only`; `--executor-model` -> `backend:model`.
TEST: python -c "import pathlib,re; t=''.join(pathlib.Path(p).read_text(encoding='utf-8') for p in ['README.md','docs/ARCHITECTURE.md','docs/FLOWS.md','packages/ufoz-harness/README.md','packages/ufoz-harness/kit_readme.md']); assert not re.search(r'--(prepare|watch|relock|retries|repair|executor-model|planner-model)\b(?!-only)', t)"

## T8 write summary
FILES: .harness/plans/prune-flags/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/prune-flags/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
