# Plan: verify-bench
## Goal
Add `bench/verify/`: a 3x3x3 orchestrator x planner x executor matrix over the `small` fixture that
plans, executes and scores one cell per row in `bench/verify/results.csv`, checks rule-role isolation,
and renders `bench/verify/RESULTS.md`.

## Decisions
- Axes exactly `ORCHESTRATORS = PLANNERS = EXECUTORS = ["claude", "pi", "opencode"]`; `DEFAULT_MODELS` pi/opencode `opencode/deepseek-v4.1-flash`, claude `sonnet`; 27 cells, slug `verify-<O>-<P>-<E>-r<rep>`.
- Reuse the suite's isolated project path, not the legacy worktree: `cells.make_project`, `cells.plan_for_project` (runner mode), `cells.cleanup_project`; add public `cells.commit_plan` + `cells.score_project`. Reason: planner-written plans use work-dir-relative paths, which only the temp-project root satisfies.
- `verify.py` is the only entry point; `--dry` prints one line per cell whose first token is the slug, then exits 0.
- Row columns exactly: `ts,orchestrator,planner,executor,rep,status,rules_ok,plan_ok,wall_s,tasks_passed,tasks_total,plan_cost,exec_cost,harness_sha,model,seed`; the CSV has a leading `slug`. `status` in `pass/fail/infra_error/timeout/skipped`.
- Rule markers: a main-rules file contains `think before coding` and not `you are the implementer`; `.pi/executor.md` contains `you are the implementer`. A plan log naming `.pi/executor.md`, or an exec log naming `AGENTS.md`, fails `rules_ok`; append `<slug>: <offending line>` to `bench/verify/rules_failures.log`.
- Phase 2 headless command (fixed): claude `claude -p <brief> --allowedTools Bash,Read,Write,Edit --model <m>`; pi `node <home>/.pi/agent/bin/pi-launcher.js -p <brief> --model <m>`; opencode `opencode run --agent orchestrator <brief>`. `--plan-via runner` instead calls `run_plan.py <slug> --plan SPEC.md --planner P[:m]`.
- Phase 3 always `run_plan.py <slug> --executor E[:m] --no-window`, then `--land`, then score. Default fixture `small`; `--reps` default 1; preflight failure -> `skipped`, never run.

Verified: suite reuses `make_project`/`plan_for_project`/`_score_project` for planner plans (`bench/suite/cells.py:821`); `.pi/executor.md` starts `You are the implementer.`; `AGENTS.md` contains `Think before coding`; the kit installs `AGENTS.md`/`CLAUDE.md`/`.pi/executor.md` into a project (`packages/ufoz-harness/export_kit.py:16-25`).  Unverified: the headless orchestrator plan step is non-deterministic and can be slow/expensive; `--plan-via runner` is the deterministic fallback.  Later: no llama/ollama arms.

## interfaces
- `bench/verify/backends.py`: `ORCHESTRATORS`, `PLANNERS`, `EXECUTORS`, `DEFAULT_MODELS`, `MAIN_RULES`, `EXECUTOR_RULES`, `COLUMNS`, `CSV_FIELDS`, `cell_slug(o, p, e, rep)`, `build_matrix(orchestrators, planners, executors, reps, seed=0)`, `orchestrator_command(backend, model, brief) -> list[str]`, `preflight(backend, model) -> bool`, `check_rules(phase, backend, log_text, project) -> tuple[bool, str]`.
- `bench/verify/verify.py`: `parse_args(argv=None)`, `main(argv=None) -> int`.
- `bench/verify/report.py`: `build_report(rows) -> str`, `main(argv=None) -> int`.
- `bench/suite/cells.py` gains `commit_plan(cell, project) -> str` and `score_project(cell, project, repo_root=REPO_ROOT) -> dict`; existing signatures unchanged.

## T1 verify backends
FILES: bench/verify/backends.py
MUST:
- Constants and `build_matrix` produce exactly 27 cells for the full 3 axes at reps 1, slug `verify-<O>-<P>-<E>-r<rep>`.
- `DEFAULT_MODELS` = pi/opencode `opencode/deepseek-v4.1-flash`, claude `sonnet`; `MAIN_RULES` = claude `CLAUDE.md`, pi/opencode `AGENTS.md`; `EXECUTOR_RULES` = `.pi/executor.md`.
- `orchestrator_command` returns the fixed per-backend argv; `preflight` lazily wraps `suite.preflight_executor`; `check_rules` returns `(ok, offending_line)` per Decisions.
TEST: python -c "import sys; sys.path.insert(0,'bench/verify'); import backends as b; m=b.build_matrix(b.ORCHESTRATORS,b.PLANNERS,b.EXECUTORS,1); assert len(m)==27; assert {'verify-pi-pi-pi-r1','verify-claude-opencode-claude-r1'} <= {c['slug'] for c in m}; assert b.EXECUTOR_RULES=='.pi/executor.md'; assert b.MAIN_RULES['claude']=='CLAUDE.md'; print('BACKENDS OK')"

## T2 cells project helpers
FILES: bench/suite/cells.py
MUST:
- `commit_plan(cell, project)` retags `tasks.json` to the slug, commits `plan`, sets `cell['base_commit']`, returns the sha; reuses `_retag_plan`/`_must_git`.
- `score_project(cell, project, repo_root=REPO_ROOT)` reads the worktree reports + `_metrics`, then `_score_project`, returns the row dict with `status`.
- No existing public signature changes; `tests/test_harness_suite.py` still passes.
TEST: python -c "import sys; sys.path.insert(0,'bench/suite'); import cells; assert callable(cells.commit_plan) and callable(cells.score_project); print('CELLS OK')"

## T3 verify CLI + flow
FILES: bench/verify/verify.py
MUST:
- Flags: `--dry`, `--orchestrators`, `--planners`, `--executors`, `--only`, `--reps` (default 1), `--task` (default `small`), `--max-cost`, `--plan-via runner`, `--keep`, `--force`.
- `--dry` prints one line per cell (first token the slug) and exits 0 without running anything.
- Per cell: preflight -> `make_project` -> plan (headless command captured to the project log, or `plan_for_project` when `--plan-via runner`) -> lint -> execute (`--no-window`) -> `--land` -> `score_project` -> `check_rules` -> append the row to `bench/verify/results.csv`; resume skips slugs already in the CSV unless `--force`; a preflight failure records `skipped` and runs nothing.
- Writes phase logs under the project plan dir; `--keep` keeps the project, else `cleanup_project`.
TEST: python .harness/plans/verify-bench/checks/check_t3.py

## T4 verify report
FILES: bench/verify/report.py
MUST:
- `build_report(rows)` is pure and renders pass/fail per `(orchestrator, planner, executor)` combo plus totals; missing/empty rows yield a stub, never raises.
- `main()` reads `bench/verify/results.csv` and writes `bench/verify/RESULTS.md`.
TEST: python .harness/plans/verify-bench/checks/check_t4.py

## T5 verify readme
FILES: bench/verify/README.md
MUST:
- Documents the 27-cell axes, the flags, `--plan-via runner`, and that the headless orchestrator plan step is non-deterministic and can be slow/expensive.
TEST: python -c "from pathlib import Path; t=Path('bench/verify/README.md').read_text(encoding='utf-8'); assert '27' in t and '--plan-via runner' in t and 'non-deterministic' in t; print('README OK')"

## T6 e2e self-check
FILES: bench/verify/selfcheck.py, bench/verify/results.csv
MUST:
- `selfcheck.py` runs exactly one cell, `verify-pi-pi-pi-r1 --plan-via runner --force`, via `verify.py`, and returns its exit code.
- The run records one `pass` row in `bench/verify/results.csv` with `model` = `opencode/deepseek-v4.1-flash`.
TEST: python .harness/plans/verify-bench/checks/check_t6.py

## T7 write summary
FILES: .harness/plans/verify-bench/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/verify-bench/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
