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
project is removed after each cell unless `--keep` is given.

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
