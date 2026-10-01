# harness-suite

Capability matrix over every executor x fixture size x mode x rep. Each cell runs a real
`run_plan.py` plan in its own worktree, scores it with hidden tests + a tamper diff, and
appends one row to `results.csv`; `report.py` turns that CSV into `RESULTS.md`.

Fixtures: `fixtures/<size>/{seed,solution,plan,hidden_tests}` + `spec.md`
(`check_fixtures.py --size <size>` proves each one is RED on the seed and GREEN on the
solution, so a cell can only fail for the executor's sake, not a broken fixture).

## Usage

```bash
python bench/suite/suite.py --dry                      # build+print the matrix, run nothing
python bench/suite/suite.py --sizes small --modes serial --executors pi --reps 1
python bench/suite/suite.py --executors pi,cline --modes serial,parallel --reps 3
python bench/suite/suite.py --max-cost 20               # stop once cumulative cost exceeds it
python bench/suite/suite.py --rerun-infra              # only rows whose status is infra_error
python bench/suite/report.py                           # rebuild RESULTS.md from results.csv
```

Flags (`suite.py`):

| flag | default | meaning |
|---|---|---|
| `--sizes` | all (`small,medium,large`) | subset of `SIZES` |
| `--modes` | all (`serial,parallel,multi,window`) | subset of `MODES` |
| `--executors` | all 6 | subset of `EXECUTORS` |
| `--reps` | 3 | repetitions per cell (pass@1 vs pass^3) |
| `--seed` | 0 | shuffle seed; `order_idx` is the post-shuffle position |
| `--dry` | off | print the matrix with `[UNSUPPORTED]` marks + a run estimate, exit 0 |
| `--keep` | off | keep worktrees and work dirs after each cell |
| `--force` | off | rerun cells that already have a row in `results.csv` |
| `--cell-timeout` | 1800 | hard per-cell timeout in seconds (kills the process tree) |
| `--max-cost` | none | stop once the cumulative `cost` in `results.csv` exceeds this |
| `--rerun-infra` | off | run only the cells whose prior status was `infra_error` |

Resume is on by default: a cell whose `slug` already has a row in `results.csv` is skipped;
`--force` overrides that.

## Work dir and `{work}` templating

A cell's slug is `suite-<size>-<mode>-<executor>-r<rep>`. Its work dir is
`bench/suite/work/<slug>/` in the cell's worktree (`.worktrees/<slug>`) — **not**
gitignored on purpose, so a run's output can be inspected and diffed by hand.

`fixtures/<size>/plan/tasks.json` is copied to `.harness/plans/<slug>/tasks.json` (in the
worktree and in the main tree, so a rerun's `sync_plan` has a source) with:

- every literal `{work}` in `files`/`acceptance` replaced by `bench/suite/work/<slug>`,
- its `"slug"` rewritten to the cell slug.

That is how a plan's paths are fixture-relative in git but absolute-to-the-cell at run time.

## Hidden-test leak fix (and the accepted risk)

`worktree.ensure()` snapshots the whole tree, so every cell's worktree used to contain the
*other* sizes' `hidden_tests/` — an executor could just read the answers. `cells.prepare_cell`
now deletes everything under `bench/suite/` inside the worktree except
`bench/suite/work/<slug>/` before copying the seed in, and the hidden tests are only
copied into the work dir *after* the plan finishes, to score it.

Accepted risk: the worktree's snapshot **commit** still contains the other sizes'
`hidden_tests/` as git objects (history, not working-tree files). The executor is scored
on the working tree; digging through git history is out of scope here.

## Status enum

| status | meaning |
|---|---|
| `pass` | every hidden test / `tsc` check passed and every task row in `metrics.jsonl` passed |
| `fail` | the run produced item reports but something did not pass |
| `infra_error` | `run_plan.py` exited before any `items/T*.report.md` existed, or preflight failed mid-run |
| `timeout` | `--cell-timeout` killed the process tree |
| `unsupported` | the matrix never planned it (see below) |
| `skipped` | `preflight_executor` said the executor is not reachable |

`build_matrix` marks a cell `unsupported` (never runs it) when: `mode == "parallel"` and the
executor's registry class is not `thread_safe`; `mode` in `("multi", "parallel")` and the
executor is `llama`; or `mode == "window"` and `size != "small"`.

## Cleanup safety

`cells.cleanup_cell` only ever runs `git worktree remove --force .worktrees/<slug>` and
`git branch -D harness/<slug>`, then `shutil.rmtree` on `.harness/plans/suite-*` and
`bench/suite/work/<slug>` in the main tree. It **never** `rmtree`s a worktree path:
`node_modules` there is a junction into the root tree and following it would delete the
root's `node_modules`. Use `--keep` to inspect a cell before it is removed.

## Outputs

- `bench/suite/results.csv` — one row per cell, columns in `suite.COLUMNS` order
  (`ts,size,mode,executor,rep,status,wall_s,tests_passed,tests_total,tasks_passed,tasks_total,attempts,input,output,reasoning,cache_read,cost,window_opened,watch_ok,peak_worktrees,model,harness_sha,batch_wall_s,tampered,seed,order_idx`).
  `window_opened`/`watch_ok` are only filled for `mode == "window"`, `batch_wall_s` only for
  `mode == "multi"`, and `tampered` is `"true"`/`"false"`.
- `bench/suite/RESULTS.md` — `python bench/suite/report.py`: pass@1, pass^3, Wilson 95%
  CI, median wall, cost/tokens per solved task, parallel speedup, multi overhead, cost
  totals (Sonnet/`claude` called out separately) and a delta section between harness shas.
- `bench/suite/work/<slug>/suite.log` — raw `run_plan.py` output per cell.

No real executor matrix has been run yet: validate with `--dry` and `check_fixtures.py`
first, then launch the matrix manually.
