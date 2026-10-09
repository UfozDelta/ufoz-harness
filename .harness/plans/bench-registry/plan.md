# Plan: bench-registry

## Goal
Suite gets a task registry (fixtures/ dirs + optional task.toml) and arms (executor:model). Report gains first-try rate and capability scorecard. Legacy small/medium/large and old slugs/CSV rows keep working.

## Decisions
- Scope: bench/suite/*.py, bench/suite/README.md, fixtures/{small,medium,large}/task.toml, tests/test_harness_suite.py. Never touch .harness/runner.
- New `bench/suite/tasks.py` (stdlib only, no heavy imports):
  - `discover_tasks() -> dict[str, dict]`; keys per task: id, capability, lang, source, licence, description, has_plan_project (bool). Every dir under fixtures/ (skip names starting `_` or `.`). Parse `task.toml` with tomllib; no toml -> capability `multi-file-feature`, other fields "".
  - `model_slug(model) -> str`: lowercase, runs of non `[a-z0-9]` -> `-`, strip `-`.
  - `cell_slug(task, mode, executor, model, rep) -> str`: `suite-<task>-<mode>-<executor>[-<model_slug>]-r<rep>`; no model -> old slug.
  - `parse_arms(value) -> list[tuple[str, str]]`: comma list of `exec[:model]` (split on first `:`); bare = (exec, "").
- task.toml for legacy: capability `multi-file-feature`, source `authored`, licence `MIT`, lang `python` (small) / `typescript` (medium, large), one-line description.
- suite.py: `SIZES = sorted(discover_tasks())` (list of ids); add `LEGACY_SIZES = ["small","medium","large"]`. COLUMNS gains `"capability"` appended LAST (report.COLUMNS identical). Cell fields: size (= task id), executor, model ("" if bare), capability. build_matrix keeps its signature; third arg items may be str (bare arm) or (executor, model) tuple; slug via `cell_slug`. `multi` mode supported only for LEGACY_SIZES tasks (else status unsupported); `_multi_slugs` uses LEGACY_SIZES and model.
- CLI: `--arms`, `--tasks` (alias of `--sizes`, giving both = SystemExit), `--capability X[,Y]` (filters tasks; empty result = SystemExit with clear message). `--executors` = shorthand bare arms; `--arms` + `--executors` together = SystemExit.
- Plan source: in suite.main, a cell whose task has no plan_project gets `plan_source="planner"` (print a note). cells.plan_for_project fixture path raises ProjectError whose text says `missing fixture plan <path>; use --plan-source planner` (run_cell maps ProjectError to infra_error).
- cells.py: `is_cell_slug` accepts old and new slugs, still rejects `suite-fixes`. `_plan_args` model = `cell.get("model")` or env HARNESS_EXECUTOR_MODEL or EXECUTOR_MODELS; `_blank` row model = same chain, last fallback executor. `_run_multi` builds sub slug via `cell_slug`. `node_modules_cache` returns None when seed has no package-lock.json (was: size == "small").
- report.py: `latest_per_cell` key adds model. Arm label = `executor` if model empty or equals executor else `executor:model`. `first_try` = status pass AND attempts <= tasks_total (both numeric, else False). Existing `pass@1` column unchanged (after retries); grid table gets `first_try` column after it and groups by arm label.
- check_fixtures.py: `--size` accepts any dir under fixtures/ (drop argparse choices); unknown id -> print `unknown task: <id>`, return 1; no `--size` = every dir with seed/ and hidden_tests/.
Verified: python 3.14.5 (`python --version`). Unverified: ProjectError maps to infra_error in run_cell; medium/large seeds are TypeScript; project licence is MIT. Later: window mode only for small stays.

## interfaces
Existing: `suite.build_matrix(sizes, modes, executors, reps, seed=0)`, `cells._plan_args(cell, wt, parallel=0, isolated=False)`, `report.build_report(rows, all_shas=False)`, `report.wilson_ci`. Old tests pass unchanged.

## T1 tasks registry
FILES: bench/suite/tasks.py, bench/suite/fixtures/small/task.toml, bench/suite/fixtures/medium/task.toml, bench/suite/fixtures/large/task.toml
MUST: functions per Decisions; toml with bad syntax raises ValueError naming the file; no-toml legacy default; `has_plan_project` true for legacy three.
TEST: python -c "import sys; sys.path.insert(0,'bench/suite'); import tasks; t=tasks.discover_tasks(); assert {'small','medium','large'}<=set(t) and t['small']['capability']=='multi-file-feature' and t['large']['has_plan_project']; assert tasks.cell_slug('small','serial','pi','',1)=='suite-small-serial-pi-r1'; assert tasks.cell_slug('small','serial','pi','opencode/x-free',1)=='suite-small-serial-pi-opencode-x-free-r1'; assert tasks.parse_arms('pi:a/b,claude')==[('pi','a/b'),('claude','')]"

## T2 suite cli
FILES: bench/suite/suite.py
DEPS: T1
MUST: per Decisions (SIZES, LEGACY_SIZES, COLUMNS, arms, --tasks, --capability, plan-source override, multi). `--dry` still imports nothing heavy. Bare `--executors pi` gives old slugs.
TEST: python -c "import subprocess,sys; o=subprocess.run([sys.executable,'bench/suite/suite.py','--dry','--arms','pi:opencode/x-free,claude','--tasks','small','--modes','serial','--reps','1'],capture_output=True,text=True); assert o.returncode==0,o.stderr; assert 'suite-small-serial-pi-opencode-x-free-r1' in o.stdout and 'suite-small-serial-claude-r1' in o.stdout,o.stdout"

## T3 cells model
FILES: bench/suite/cells.py
DEPS: T1
MUST: per Decisions (is_cell_slug, _plan_args, _blank, _run_multi, node_modules_cache, plan_for_project message). Import helpers from `tasks` (bench/suite on sys.path).
TEST: python -c "import sys; from pathlib import Path; sys.path.insert(0,'bench/suite'); import cells; assert cells.is_cell_slug('suite-small-serial-pi-r1') and cells.is_cell_slug('suite-fix-failing-test-serial-opencode-opencode-muse-spark-1-3-contributor-free-r2') and not cells.is_cell_slug('suite-fixes'); a=cells._plan_args({'slug':'s','executor':'pi','model':'m/x','mode':'serial'},Path('.')); assert a[a.index('--executor-model')+1]=='m/x'"

## T4 report scorecard
FILES: bench/suite/report.py
MUST: COLUMNS mirror with `capability` last; load_rows reads old CSVs (missing capability = ""); first_try in grid; new section `## Per capability` (capability x arm: n, first_try, pass-after-retry, Wilson 95%) and per task x arm table; rows with empty capability show `?`.
TEST: python -c "import sys; sys.path.insert(0,'bench/suite'); import report; r=[dict({c:'' for c in report.COLUMNS},size='t',mode='serial',executor='pi',model='m1',rep=str(i),status='pass',attempts=str(i),tasks_total='1',capability='bug-fix-prose') for i in (1,2)]; o=report.build_report(r); assert 'first_try' in o and 'bug-fix-prose' in o and 'Per capability' in o, o"

## T5 fixtures check
FILES: bench/suite/check_fixtures.py, bench/suite/README.md
MUST: `--size` per Decisions; README documents task registry, task.toml fields, `--arms`, `--tasks`, `--capability`, first_try, capability column (keep terse).
TEST: python -c "import subprocess,sys; o=subprocess.run([sys.executable,'bench/suite/check_fixtures.py','--size','nosuch'],capture_output=True,text=True); assert o.returncode==1 and 'unknown task' in o.stdout+o.stderr, o"

## T6 registry tests
FILES: tests/test_harness_suite.py
DEPS: T1, T2, T3, T4
MUST: add tests named: test_discover_tasks_legacy_and_toml (tmp fixtures dir via monkeypatch), test_parse_arms_and_slugs, test_plan_args_model_wins_over_env, test_planner_forced_without_plan_project, test_report_first_try_and_capability. Old tests untouched and green.
TEST: python -m pytest -q tests/test_harness_suite.py -k "discover_tasks_legacy or parse_arms_and_slugs or plan_args_model or planner_forced or report_first_try"

## T7 write summary
FILES: .harness/plans/bench-registry/SUMMARY.md
DEPS: T1, T2, T3, T4, T5, T6
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run `python -m pytest -q tests/test_harness_suite.py` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/bench-registry/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
