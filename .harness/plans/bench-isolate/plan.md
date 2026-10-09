# Plan: bench-isolate

## Goal
Each suite cell runs like real use: temp git project (seed + installed kit), plan from fixture or real planner, run_plan in project, `--land`, score the landed tree. Old lab-worktree path stays behind `--legacy`.

## Decisions
PREREQ: plan `bench-fixtures` landed (seed tests/package files). Kit sources `.harness/hooks/git_guard.py`, `.claude/settings.strict.json` must be committed, else export_kit fails in the worktree.
- Do not touch `.harness/runner`, `.harness/plans/bench-real`. Reuse its ideas, new code here.
- export_kit.py: `parse_args(argv=None)` with `--kit-dir` (attr `kit_dir`, default None); `main(argv=None)` sets module `KIT` from it (default unchanged).
- Fixture plans: new dirs `bench/suite/fixtures/<size>/plan_project/{plan.md,tasks.json}` generated from `plan/` (leave `plan/` untouched for legacy): `cd {work}/X && ` -> `cd X && `, `cd {work} && ` -> ``, `{work}/` -> ``, other `{work}` -> `.`; also rewrite medium/large text saying node_modules comes from the repo root ("node_modules is preinstalled in the project").
- cells.py new (exact names): `class ProjectError(Exception)`; `TEMP_ROOT = Path(tempfile.gettempdir())/"ufoz-bench"`; `PLAN_CACHE = Path(REPO_ROOT)/"bench/suite/plan_cache"`; `ensure_kit(repo_root=REPO_ROOT) -> (Path, str)` (exports to `TEMP_ROOT/_kit/kit` via `export_kit.py --kit-dir`, copies `index.js`+`package.json` to `TEMP_ROOT/_kit`, kit_hash = sha256 of sorted relpath+bytes [:8], cached per process; failure -> ProjectError); `node_modules_cache(size, repo_root) -> Path|None` (small: None; lockfile = medium `seed/package-lock.json`, large `seed/web/package-lock.json`; dir `TEMP_ROOT/_nm/<sha256(lock)[:12]>/` holds package.json, lock, runs `npm ci` once, returns its node_modules; npm failure -> ProjectError); `make_project(cell, repo_root=REPO_ROOT, kit=None) -> Path` (`kit` = injected `(kit_root, kit_hash)`, else `ensure_kit`); `cleanup_project(cell)`.
- `make_project`: dir `TEMP_ROOT/<slug without "suite-">`; `_remove_leftover` it first; copy seed; write `.gitignore` (node_modules/, .next/, __pycache__/); `git init -b main`, local user.name/email, commit `seed`; `node <kit_root>/index.js --yes --dir <project>` (nonzero -> ProjectError); commit `harness`; junction `node_modules` (medium: root, large: `web/`; `mklink /J`, symlink off Windows) to the cache. Sets `cell["project"]`, `cell["seed_commit"]`, `cell["kit_hash"]`.
- `plan_for_project(cell, project, repo_root=REPO_ROOT, kit_hash="", runner=subprocess.run) -> float` (plan cost): fixture: copy `plan_project/*` into `<project>/.harness/plans/<slug>/`, set tasks.json `slug`. planner: key `<size>-<planner>-<planner_model|default>-<sha8 spec.md>-<kit_hash>`; hit in `PLAN_CACHE/<key>/` (plan.md, tasks.json, checks/, meta.json {"cost","slug"}) -> copy, replace old slug by cell slug, cost 0.0; miss: `runner([python, ".harness/run_plan.py", slug, "--plan", <spec copy in TEMP_ROOT/_specs>, "--planner", p, "--planner-model", m], cwd=project, timeout=1800)`, rc!=0 or no plan.md/tasks.json -> ProjectError; cost = `.harness/plans/<slug>/planner.json` field `cost` (0.0 if absent); cache it. Then commit `plan`; set `cell["base_commit"]`.
- Scoring in cells.py: `_regression_counts(project, size, repo_root) -> (passed,total)`: copy ONLY pristine seed test files (via `_hidden_layout(seed)`) over the project, count with `_pytest_counts`/`_vitest_counts` like `_run_tests`; no tests -> (0,0). `_tampered_git(project, seed_commit, base_commit, allowed) -> bool`: `git diff --name-status seed..HEAD`; ignore `.harness/ .claude/ .pi/ .opencode/ .agents/`, CLAUDE.md, AGENTS.md, opencode.json, skills-lock.json, .gitignore; tamper = TAMPER_SENSITIVE seed file modified/deleted and not in allowed, OR added test-looking file (`_looks_like_test`) not in allowed, OR added line (`git diff -U0`) containing a TAMPER_PATTERNS entry.
- Run `_run_project(cell, repo_root, cell_timeout)`: `make_project`, `plan_for_project`, then `_plan_args(cell, project, isolated=True)` (as today minus `--no-worktree`), Popen cwd=project, log `bench/suite/work/_logs/<slug>.log` in lab repo. Before landing read reports `<project>/.worktrees/<slug>/.harness/plans/<slug>/items/*.report.md` and `_metrics(slug, wt, project)`. Then `run_plan.py <slug> --land --yes` in project (rc!=0 -> `harness_fail`). Then tamper, regression, hidden (`_run_tests(project, ...)`). Status `pass` only if hidden passed==total, tasks all pass, AND regression_passed==regression_total. ProjectError -> `infra_error` row, no executor run. Non-pass: copy project plan `items/` and `logs/` to `bench/suite/failed/<slug>/`. Always `cleanup_project` unless keep. `mode multi` in new path: print a note, use legacy `_run_multi`. `run_cell`: `cell.get("legacy")` -> old code unchanged.
- COLUMNS (suite.py and report.py, equal): append at END `plan_source`, `planner`, `plan_cost`, `regression_passed`, `regression_total`, `kit_hash`. `_blank`: `plan_source=cell.get("plan_source","fixture")`, `planner=cell.get("planner","")`, `plan_cost`/`regression_*`/`kit_hash` "" (kit_hash from cell if set).
- suite.py flags: `--plan-source fixture|planner` (default fixture), `--planner` (default `claude`), `--planner-model` (default `sonnet`), `--legacy`. After `build_matrix`, set `plan_source, planner, planner_model, legacy` on each cell. `--cleanup` also removes `TEMP_ROOT` projects (not `_kit`/`_nm`) via `cleanup_project`.
- report.py: grid gets last column `regressions` (graded rows with regression_total set and passed<total); line `Planner cost (not billed to executors): $X`; header shows distinct non-empty `kit_hash`. Old rows (blank new keys) must not raise.
- `.gitignore` gets `bench/suite/plan_cache/`, `bench/suite/failed/`.

Verified: export_kit has fixed `KIT`; index.js reads `./kit/` beside itself (read both).
Unverified: `run_plan.py --land --yes`, `--plan/--planner-model` flags; metrics/worktree location in project; run_plan worktree sees junctioned node_modules; `planner.json` field `cost`; npm ci on lockfile; node index.js preflight needs pi.
Later: multi mode in project path; remove legacy.

## interfaces
Keep `prepare_cell`, `_finish`, `_run_tests`, `_run_single`, `_run_multi`, `cleanup_cell`, `build_matrix`, `report.build_report(rows)`.

## T1 export kit dir
FILES: packages/ufoz-harness/export_kit.py
MUST: `--kit-dir` per Decisions; no arg = old behavior; unknown arg errors.
TEST: python -c "import sys; sys.path.insert(0,'packages/ufoz-harness'); import export_kit as e; assert str(e.parse_args(['--kit-dir','x']).kit_dir)=='x'; assert e.parse_args([]).kit_dir is None"

## T2 project plans
FILES: bench/suite/fixtures/small/plan_project/plan.md, bench/suite/fixtures/small/plan_project/tasks.json, bench/suite/fixtures/medium/plan_project/plan.md, bench/suite/fixtures/medium/plan_project/tasks.json, bench/suite/fixtures/large/plan_project/plan.md, bench/suite/fixtures/large/plan_project/tasks.json
MUST: rewrite per Decisions via one-off script; no `{work}` or `bench/suite/work` left; tasks.json valid, same task ids/deps as `plan/`.
TEST: python .harness/plans/bench-isolate/checks/check_t2.py

## T3 make project
FILES: bench/suite/cells.py
MUST: ProjectError, TEMP_ROOT, ensure_kit, node_modules_cache, make_project, cleanup_project (unlink junction before rmtree) per Decisions; legacy code untouched.
TEST: python .harness/plans/bench-isolate/checks/check_t3.py

## T4 project plan
FILES: bench/suite/cells.py
MUST: `plan_for_project` per Decisions; planner runner called exactly once per cache key (second call = hit, cost 0.0).
TEST: python .harness/plans/bench-isolate/checks/check_t4.py

## T5 score and run
FILES: bench/suite/cells.py
MUST: `_regression_counts`, `_tampered_git`, `_blank` keys, `_plan_args(..., isolated=False)`, `_run_project`, `run_cell` dispatch per Decisions; land and metrics read once each.
TEST: python .harness/plans/bench-isolate/checks/check_t5.py

## T6 suite and report
FILES: bench/suite/suite.py, bench/suite/report.py
MUST: COLUMNS, flags, cell keys, cleanup, report changes per Decisions; `--dry` output unchanged.
TEST: python .harness/plans/bench-isolate/checks/check_t6.py

## T7 tests and ignore
FILES: .gitignore, tests/test_harness_suite.py
MUST: .gitignore lines per Decisions; tests `test_make_project_commits` (fake kit), `test_plan_cache_hit_once`, `test_tampered_git_flags`, `test_report_regressions`.
TEST: python -m pytest -q tests/test_harness_suite.py -k "make_project_commits or plan_cache_hit_once or tampered_git_flags or report_regressions"

## T8 write summary
FILES: .harness/plans/bench-isolate/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run `python -m pytest -q tests/test_harness_suite.py` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/bench-isolate/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
