# Flows

Every path through the harness, in tables. `mermaid.md` has the happy path as a diagram,
`ARCHITECTURE.md` the internals. Commands run from the repo root; `run_plan.py` means
`python .harness/run_plan.py`.

## 1. The loop (who does what)

| Step | Who | Does | Output | Goes to |
|---|---|---|---|---|
| 1 Decide | you + main session | scope, assumptions, success criteria | agreement | 2 |
| 2 Plan (small) | main session | writes `plan.md` + `tasks.json` | `.harness/plans/<slug>/` | 3 |
| 2 Plan (large) | `@planner` (sonnet) | `build_map.py`, explores, writes plan, runs `--lint` | same + `Unverified:` list | 3 |
| 2 Plan (no Claude) | `run_plan.py <slug> --plan spec.md` | planner backend writes + lints the plan | same | 3 |
| 3 Approve | main session → you | `--lint`, shows summary + `Unverified:` | your go | 4 |
| 4 Execute | runner + executor | runs every task through the guards (section 4) | reports, logs, metrics, `SUMMARY.md` | 5 |
| 5 Verify | main session | reads `SUMMARY.md`, reports, `git diff` | verdict | 6 |
| 6 Decide | main session | accept, re-brief + rerun, or discard | — | 7 or 4 |
| 7 Report | main session | `Blocked on me:` / `Changed:` / `Found:` | 3 lines | you commit |

## 2. Commands

| Command | Runs executor? | Writes | Exit |
|---|---|---|---|
| `run_plan.py <slug>` | yes, every task not already `pass` | reports, logs, metrics, lock | 0 all pass, 1 any fail |
| `run_plan.py <slug> --only T2` | yes, T2 only | same, for T2 | same |
| `run_plan.py <slug> --lint` | no | nothing | lint result |
| `run_plan.py <slug> --relock` | yes (it runs the plan too) | re-records `plan.lock.json` first | same as a run |
| `run_plan.py <slug> --review` | yes, then a sonnet review after a fresh full pass | + `REVIEW.md` | same as a run |
| `run_plan.py <slug> --plan spec.md` | no (planner only) | plan files | 0 lint ok, 1 not |
| `run_plan.py --stats` | no | nothing | 0 |
| `python .harness/selftest.py` | yes, one pi smoke plan | temp copy | 0 ok |
| `python .harness/selftest.py --bench` | yes, pi and claude arms | `.harness/bench.csv` | 0 ok |
| `python .harness/build_map.py [--check]` | no | repo map | 0 fresh |

## 3. Executors (`--executor`)

| Executor | Transport | Model (default → override) | Warm session | `--parallel > 1` | Cost | Needs |
|---|---|---|---|---|---|---|
| `pi` (default) | `pi-launcher.js -p` per task, `--session-id` | `opencode/space-bunny-free` → `HARNESS_MODEL` / `--executor-model` | yes | allowed | free | pi |
| `opencode` | one `opencode serve`, HTTP+SSE | same as pi | yes | allowed | free | opencode on PATH |
| `claude` | `claude -p` per task, `--resume` | sonnet → `--executor-model` | yes | allowed | billed | claude CLI |
| `cline` | `cline --json` per task | probes `cline-free/deepseek-v4.1-flash` then `FALLBACK_MODELS` → `HARNESS_MODEL` | no (fresh per task) | refused | free, daily cap | `npm i -g cline` |
| `cline-acp` | one `cline --acp` process, ACP | `stealth/space-bunny-alpha` → `CLINE_MODEL` (verified before task 1) | yes | refused | free | `npm i -g cline` |
| `llama` | pi with a throwaway `PI_CODING_AGENT_DIR` | the only model on the router → `HARNESS_LLAMA_MODEL` / `--executor-model` | yes | refused | free, local | running `llama-server` router |

Planner backends (`--planner`, `HARNESS_PLANNER`): `pi` (default), `opencode`, `claude`,
`cline`, `cline-acp`. No `llama` planner.

## 4. One task through the guards

| # | Step | Condition | Outcome |
|---|---|---|---|
| 1 | Lock check | `tasks.json` / `checks/*.py` hash ≠ lock | `lock-mismatch`, executor not called, plan stops |
| 2 | Red-first | `red_first` true, first attempt, acceptance already passes | `check-invalid`, executor not called, plan stops |
| 3 | Baseline | always | `RESULT: running`, file-tree snapshot, suppression counts |
| 4 | Attempt | executor runs the brief | exit code, usage, session |
| 4a | Rate limit | exit 75 | `wait_for_quota()` probes every 60 s, attempt rerun uncounted |
| 4b | Timeout | exit 124 | warm session dropped; retry starts fresh; no repair |
| 4c | Grade | acceptance ok, exit 0, no stray file, no new suppression | `pass` → next task |
| 4d | Stray / lock edit | file outside `files` touched, or lock changed | `fail` at once, no retry, no repair |
| 4e | Plain failure | acceptance failed or suppression added | `feedback.md`, retry (`--retries`, default 1) |
| 5 | Repair | still a plain failure after retries | `repair<k>.md`, scope = this task + all earlier tasks' files (`--repair`, default 1) |
| 5a | Repair ok | grade passes | `pass`, summary says `REPAIRED` |
| 5b | Repair fails | grade fails | `fail`, plan stops |
| 6 | Report | always | `items/T<n>.report.md` + metrics row |

## 5. End states and what to do

| Result | Meaning | You / main session do |
|---|---|---|
| `pass` | graded ok (maybe `REPAIRED`) | review the diff |
| `fail` | check, exit code, stray file or suppression after retries + repair | fix the brief, rerun (passed tasks skipped); second fail of the same task → stop, investigate read-only |
| `check-invalid` | check passed before any work | tighten the check, rerun with `--relock` (the check is hash-locked) |
| `lock-mismatch` | `tasks.json` or a check changed | your edit → run with `--relock`; the executor's edit → discard it |
| `running` | runner crashed mid-task | rerun; counts as a failed attempt, no red-first |

## 6. Edge flows

| Situation | What happens |
|---|---|
| `--session` with `--fresh` or `--parallel > 1` | exits 1 before anything runs |
| `--parallel > 1` with `cline` / `cline-acp` / `llama` | exits 1 before the run lock |
| Second run of the same plan while one runs | refused by `run.lock` |
| `--session <id>` with `cline` | task fails with code 1 (no sessions) |
| `llama`: server down | exits with the `llama-server` start command |
| `llama`: several models, none chosen | exits listing the model ids |
| `llama`: model unloaded | `POST /models/load`, waits up to 300 s |
| Executor claims `DONE:` but check fails | ignored; only the runner's grade counts |
| Last task | writes `SUMMARY.md` and runs the build smoke |
