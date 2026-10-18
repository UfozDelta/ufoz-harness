# Spec — bench/verify: orchestrator × planner × executor verification bench

## Goal
A new bench that runs every combination of **orchestrator (main session) × planner backend ×
executor** through the real harness on a tiny fixture, scores the result, and asserts rule-role
isolation. One row per cell in `bench/verify/results.csv`; `report.py` renders `RESULTS.md`.

## Context (reuse, do not reinvent)
- `bench/suite/suite.py` — the capability matrix: `build_matrix`, `--dry`, resume via
  `results.csv`, `preflight_executor`, `COLUMNS`/`CSV_FIELDS`. Mirror its shape.
- `bench/suite/cells.py` — `prepare_cell` / `cleanup_cell` / scoring (hidden tests held out until
  the plan finishes). Reuse these for prepare + score.
- `bench/suite/tasks.py` — `discover_tasks`, `cell_slug`, `parse_arms`.
- `bench/suite/fixtures/small/{seed,solution,plan,hidden_tests}` + `spec.md` — the tiny fixture.
- `bench/suite/report.py` — CSV → RESULTS.md pattern.
- `python .harness/run_plan.py <slug> --plan SPEC.md --planner BACKEND[:MODEL]` and
  `python .harness/run_plan.py <slug> --executor BACKEND[:MODEL]`.

## Axes
- `ORCHESTRATORS = ["claude", "pi", "opencode"]` (the main session)
- `PLANNERS = ["pi", "opencode", "claude"]` (the planner backend)
- `EXECUTORS = ["pi", "opencode", "claude"]`
- 3×3×3 = 27 cells, `--reps` default 1. Cell slug `verify-<O>-<P>-<E>-r<rep>`.
- Default models: pi/opencode → `opencode/deepseek-v4.1-flash`; claude → `sonnet`.

## Per-cell flow
1. **Prepare** — reuse `cells.prepare_cell`: worktree `.worktrees/<slug>` + the `small` fixture,
   hidden tests held out.
2. **Plan (exercises O + P)** — the orchestrator plans, by default headless:
   - claude: `claude -p "<brief>" --allowedTools ...` (loads `CLAUDE.md` main rules; plans with `@planner`).
   - pi: `node ~/.pi/agent/bin/pi-launcher.js -p "<brief>"` (loads `AGENTS.md` main rules; plans with `.pi/planner.md`).
   - opencode: `opencode run --agent orchestrator "<brief>"` (loads `AGENTS.md` + `instructions`).
   Brief: plan the task in `SPEC.md` into `.harness/plans/<slug>/{plan.md,tasks.json}` and lint it.
   Assert `plan.md` + `tasks.json` exist and `python .harness/run_plan.py <slug> --lint` prints `lint OK`.
   With `--plan-via runner`: skip the orchestrator, call `run_plan.py <slug> --plan SPEC.md --planner P`.
3. **Execute (exercises E)** — `python .harness/run_plan.py <slug> --executor E[:MODEL]`; the runner
   drives E and grades each task.
4. **Score** — reuse the suite scoring: restore hidden tests, run them + `tsc`, tamper diff, read
   `items/T*.report.md` → status `pass` / `fail` / `infra_error` / `timeout` / `skipped`.
5. **Rules-role check** (the bug class this repo just fixed), asserted from each phase's captured log:
   - O loaded main rules (claude `CLAUDE.md`; pi/opencode `AGENTS.md`) and NOT executor rules.
   - E loaded `.pi/executor.md` and NOT project `AGENTS.md`.
   Record `rules_ok` (`true`/`false`) and, on failure, the offending line.
6. **Record** — append a row: `ts,orchestrator,planner,executor,rep,status,rules_ok,plan_ok,wall_s,
   tasks_passed,tasks_total,plan_cost,exec_cost,harness_sha,model,seed`.

## CLI / guardrails
`--dry` (build + print the 27 cells, run nothing, exit 0), `--orchestrators`/`--planners`/`--executors`
(subset), `--only <slug>` , `--reps`, `--task` (fixture, default `small`), `--max-cost`,
`--plan-via runner`, `--keep`, `--force`. Resume by slug (skip a cell already in `results.csv`).
Preflight each backend (reuse `preflight_executor`); unreachable → status `skipped`, never run.

## Must-haves / acceptance
- Every task's acceptance is ONE line that exits 0 only when done. Prefer `python -c` assertions.
- `python bench/verify/verify.py --dry` must print exactly 27 cells and exit 0.
- A tiny end-to-end self-check must run ONE cell (e.g. `--only verify-pi-pi-pi-r1 --plan-via runner`)
  against the `small` fixture and exit 0 on `pass`; the executor+planner model is
  `opencode/deepseek-v4.1-flash`. This is the smoke that proves the wiring.
- `report.py` turns `results.csv` into `RESULTS.md` (pass/fail per combo + totals).
- The LAST task writes `.harness/plans/verify-bench/SUMMARY.md` (<= 600 chars) + a `BUILD:` line.
- `python .harness/run_plan.py verify-bench --lint` passes.

## Constraints
- Reuse `bench/suite/*` helpers; do not duplicate cell prep/scoring. No new dependencies
  (stdlib only, matching the repo). Never write `.ts`/`.tsx` import extensions. Match existing
  style. Do not touch `.harness/runner/*`.
- `bench/verify/` is new; the fixture and hidden tests are read-only inputs.

## Open item (encode, do not drop)
- The headless orchestrator plan step (phase 2) is non-deterministic and can be slow/expensive;
  `--plan-via runner` is the deterministic fallback. Note this in the README and in `Unverified:`.
- llama/ollama are intentionally out of scope (executors limited to pi/opencode/claude).
