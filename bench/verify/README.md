# verify-bench

The verification matrix for the harness: every combination of orchestrator x planner x
executor over one fixture, one cell per row in `results.csv`, scored and rendered into
`RESULTS.md`.

## Axes

Three backends, each usable as all three roles:

- `ORCHESTRATORS = ["claude", "pi", "opencode"]`
- `PLANNERS = ["claude", "pi", "opencode"]`
- `EXECUTORS = ["claude", "pi", "opencode"]`

That is **3 x 3 x 3 = 27 cells** at the default `--reps 1`. Each cell's slug is
`verify-<orchestrator>-<planner>-<executor>-r<rep>`. Default models live in
`backends.DEFAULT_MODELS`: pi and opencode use `opencode/deepseek-v4.1-flash`, claude
uses `sonnet`.

## Running

`verify.py` is the only entry point.

```
python bench/verify/verify.py --dry
python bench/verify/verify.py --plan-via runner --only verify-pi-pi-pi-r1 --force
```

Per cell the flow is: preflight -> `make_project` -> plan -> lint -> execute
(`--no-window`) -> `--land` -> `score_project` -> `check_rules` -> append a row to
`results.csv`. A preflight failure records `skipped` and runs nothing; a slug already in
`results.csv` is skipped on resume unless `--force`.

Phase logs are written under the temp project's `.harness/plans/<slug>/logs/`. The temp
project is removed after each cell unless `--keep` is given. Before cleanup every cell, pass
or fail, copies its plan dir to `bench/verify/logs/<slug>__<stamp>/` (`wt/` = worktree,
`project/` = landed tree; gitignored); `logs_dir` in the row points at it.

A phase that exceeds `--cell-timeout` has its whole process tree killed (a grandchild
holding the output pipe used to hang the run) and the cell is recorded as `timeout`.

`report.py` reads `results.csv` and writes `RESULTS.md`:

```
python bench/verify/report.py
```

## Flags

| flag | meaning |
| --- | --- |
| `--dry` | print the matrix (one line per cell, first token the slug) and exit 0; run nothing |
| `--orchestrators` | comma list of `backend[:model]` (default: all three) |
| `--planners` | comma list of `backend[:model]` (default: all three) |
| `--executors` | comma list of `backend[:model]` (default: all three) |
| `--only` | comma list of cell slugs to run |
| `--reps` | repetitions per cell (default 1) |
| `--seed` | matrix shuffle seed (default 0) |
| `--task` | fixture to run (default `small`) |
| `--max-cost` | stop once cumulative plan+exec cost reaches this |
| `--plan-via` | `headless` (default) or `runner` |
| `--cell-timeout` | per-phase timeout seconds (default 1800) |
| `--keep` | keep the temp project after each cell |
| `--force` | rerun slugs already present in `results.csv` |

## Planning: headless vs `--plan-via runner`

By default the **orchestrator** backend plans the cell: `verify.py` builds a brief from the
fixture spec and runs the fixed per-backend headless command
(`backends.orchestrator_command`), capturing its output to the plan log. This step is
**non-deterministic** and can be **slow and expensive**: the orchestrator is a full agent
turn that may or may not produce a valid `plan.md` / `tasks.json`, so the same cell can
plan differently (or fail) from one run to the next, and it costs real tokens.

`--plan-via runner` is the deterministic fallback: it skips the orchestrator and calls
`run_plan.py <slug> --plan SPEC.md --planner <P>[:<model>]`, so the plan comes from the
planner backend through the normal, lint-checked planner contract.

## Rule-role isolation

`check_rules` verifies that the main rules file (`CLAUDE.md` for claude, `AGENTS.md` for pi
and opencode) looks like an orchestrator file (`think before coding`, no executor marker)
and that `.pi/executor.md` looks like an executor file. A plan log naming `.pi/executor.md`,
or an exec log naming `AGENTS.md`, fails the cell's `rules_ok` and appends the offending
line to `rules_failures.log`.

## Why a cell did not pass

`fail_reason` (blank on pass) is a short code: `skipped_preflight`, `plan_error`,
`timeout_orch|lint|exec|land`, `no_plan_files`, `lint_failed`, `land_failed`, `no_reports`,
`tasks_failed`, `tests_failed`, `regression_failed`, `escaped_cwd`, `cell_exception`.
`tests_passed/total` and `regression_passed/total` are recorded too. Read the saved logs under
`logs_dir` before trusting a single fail: cells are non-deterministic and a fail can be a flake.

## Cell isolation

A cell must not read other cells' projects or hidden tests. Three layers:

1. `_wipe_stale` deletes other `verify-*` dirs from the temp root before each cell (`_kit`,
   `_specs` and non-`verify-` dirs stay).
2. `backends.check_escape` scans the orchestrator output and the plan/exec logs for paths
   naming another cell (`ufoz-bench/verify-*|suite-*` other than its own slug) or hidden
   grader material (`hidden_tests`, `test_hidden`, `suite/fixtures`). A hit records
   `escaped_cwd`, sets `rules_ok=false` and appends `escape: <line>` to `rules_failures.log`.
3. `_plan_brief` tells the planner to stay in the cwd and not to read `.pi/`.

Layer 2 is the guarantee; there is no OS sandbox.
