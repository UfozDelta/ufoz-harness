# Plan: harness-suite

## Goal
New top-level `harness-suite/` folder: capability suite over every executor, sizes, modes, with
REAL-world fixtures (FastAPI, Next.js/TS, full-stack) and reference solutions. Builds fixtures +
`check_fixtures.py` + `suite.py` + `cells.py` + `report.py` + tests. No real executor matrix run
happens during this plan (manual step after `--dry` / `check_fixtures.py` pass).

## Decisions
Verified: run_plan.py flags: `--executor {pi,claude,opencode,cline,cline-acp,llama}`, `--parallel N`,
`--no-worktree`, `--no-window`, `--watch`, `--land`, `--lint` (`run_plan.py --help`).
Verified: fastapi 0.115.0, httpx 0.28.1, pytest 9.1.1 installed; sqlalchemy NOT installed (`pip show`).
Verified: root `package.json` has `devDependencies: {typescript}` only, `type: commonjs`, no `next`/`vitest` yet (`cat package.json`).
Verified: `worktree.SHARED_DIRS = ("node_modules", ".venv", ".opencode/node_modules")`, `worktree.ensure(slug)` creates-or-reuses `.worktrees/<slug>` from a full snapshot (tracked + uncommitted + untracked non-ignored files) (`.harness/runner/worktree.py`).
Verified: `REGISTRY` + per-class `thread_safe` at `.harness/runner/executors/__init__.py` and `.../executors/{base,cline,cline_acp,llama}.py`: base default `True`; `cline`, `cline_acp`, `llama` `False`.
Verified: `.harness/bench/tasks/large/seed/{app/models.py,app/main.py,tests/test_items.py}` is a working in-memory Items API (FastAPI, pydantic, no DB) — base for the small/large FastAPI seeds.
metrics.jsonl (checked in stats.py/cli.py): run_plan chdirs into the worktree, so rows land in `.worktrees/<slug>/.harness/metrics.jsonl` (fallback: repo-root `.harness/metrics.jsonl`). Task row: `{"ts","slug","task","executor","result","attempts","seconds","tokens":{"input","output","reasoning","cache_read","cost"}}`; rows with a `kind` key (plan_event/review) are skipped.
Unverified: `npx vitest run` / `npx tsc --noEmit` exact stdout shape for parsing pass/fail counts (no existing vitest usage in repo to copy from).
Unverified: Win32 process command-line visibility for `window_opened` (PowerShell `Get-CimInstance Win32_Process` — assumed to expose `CommandLine` with the slug and `--watch`, not tested here).
Later: real matrix execution across executors.
Pinned versions (T0, exact, no `^`): next 16.3.6, react 19.3.0, react-dom 19.3.0, vitest 5.0.2, jsdom 30.1.1, @testing-library/react 16.3.3, @testing-library/dom 10.4.2, @types/react 19.3.0, @types/react-dom 19.3.0, @types/node 26.6.3, @vitejs/plugin-react 6.1.1 (current npm latest 2026-09-28; if `npm install` hits a peer conflict, drop to the newest mutually compatible pair and note it in the T0 report) (typescript stays `^5.9.3`, already present).

## interfaces (suite.py / cells.py / report.py / check_fixtures.py — do not rename)
- `SIZES=["small","medium","large"]`, `MODES=["serial","parallel","multi","window"]`,
  `EXECUTORS=["pi","opencode","cline","cline-acp","llama","claude"]`. Import `sys.path.insert(0,str(repo_root/".harness"))` then `from runner.executors import REGISTRY` for `thread_safe` (no hand-copied dict).
- `build_matrix(sizes, modes, executors, reps, seed=0) -> list[dict]`: keys `size,mode,executor,rep,slug,status,order_idx,seed`. `slug=f"suite-{size}-{mode}-{executor}-r{rep}"`. `status="unsupported"` when (mode=="parallel" and not `REGISTRY[executor].thread_safe`) or (mode in ("multi","parallel") and executor=="llama") or (mode=="window" and size!="small"); else `"pending"`. Rows are shuffled with `random.Random(seed).shuffle`, then `order_idx` = post-shuffle position. `"skipped"` is set later by `preflight_executor` or resume; never by `build_matrix`.
- `preflight_executor(name) -> bool` (llama: `HARNESS_LLAMA_URL` reachable; others best-effort True).
- Status enum (final CSV `status`): `pass|fail|infra_error|timeout|unsupported|skipped`. `infra_error` = run_plan exited before any `items/T*.report.md` existed, or executor preflight failed mid-run. `timeout` = `--cell-timeout` (default 1800s) killed the process tree.
- CSV columns in order: `ts,size,mode,executor,rep,status,wall_s,tests_passed,tests_total,tasks_passed,tasks_total,attempts,input,output,reasoning,cache_read,cost,window_opened,watch_ok,peak_worktrees,model,harness_sha,batch_wall_s,tampered,seed,order_idx`. `model`=executor's model id/name as passed to run_plan. `harness_sha` = `git rev-parse --short HEAD` + `-dirty` if `git status --porcelain .harness` is non-empty. `window_opened`/`watch_ok` only set for mode `"window"`, else empty string. `batch_wall_s` only set for mode `"multi"` (else empty). `tampered` = `"true"`/`"false"` (see runner below).
- Work dir: `harness-suite/work/<slug>/` (NOT gitignored). `cells.prepare_cell(cell, repo_root)`: call `worktree.ensure(slug)` (imported per above) to get `wt`; inside `wt`, delete everything under `harness-suite/` except `harness-suite/work/<slug>/` (fixes the hidden-test leak: `_snapshot` copied all of `harness-suite/`); copy `fixtures/<size>/seed/*` into `wt/harness-suite/work/<slug>/`; copy `fixtures/<size>/plan/*` into `wt/.harness/plans/<slug>/` (and into the main tree's `.harness/plans/<slug>/` too, so `sync_plan` on rerun has a source); string-replace literal `{work}` with `harness-suite/work/<slug>` in the copied tasks.json `files`/`acceptance`; rewrite its `"slug"`. README notes: the worktree's snapshot *commit* still contains other sizes' `hidden_tests/` as git objects (not working-tree files) — accepted risk.
- `cells.run_cell(cell, repo_root, cell_timeout=1800, keep=False) -> dict`: calls `prepare_cell`, then launches `run_plan.py <slug> --executor <e> --no-window [--parallel 3 if mode=="parallel"]` (mode `"window"` omits `--no-window`) with a hard timeout that kills the process tree -> `status="timeout"`; on early exit with no `items/*.report.md` -> `status="infra_error"`. Mode `"multi"`: instead launches the small+medium+large cells for this `(executor,rep)` as 3 concurrent subprocesses, samples `len(glob('.worktrees/suite-*'))` every 1s for `peak_worktrees`, records `batch_wall_s`, returns one row per size. Mode `"window"`: after launch, poll (PowerShell `Get-CimInstance Win32_Process | Where CommandLine like '*<slug>*--watch*'`) for up to 15s for `window_opened`; after the cell ends, run a separate headless `run_plan.py <slug> --watch` subprocess and set `watch_ok` = output contains `"done:"`. After the run: copy that size's `hidden_tests/*` into `wt/harness-suite/work/<slug>/`, run pytest (`-p no:cacheprovider --rootdir <work>`, cwd=work) and/or `npx vitest run` + `npx tsc --noEmit` there, parse pass/total; diff `wt/harness-suite/work/<slug>` against `fixtures/<size>/seed` for `tampered` (true if a change outside the fixture's task `files` touches tsconfig/package.json/vitest.config/conftest/visible test files, or adds `skip`/`xfail`/`@ts-ignore`/`@ts-expect-error`); read metrics.jsonl per Decisions for slug rows (missing file/field -> 0/None, never raise); then `cleanup_cell` unless `keep`.
- `cells.cleanup_cell(cell, repo_root)`: `git worktree remove --force .worktrees/<slug>` + `git branch -D harness/<slug>` + `shutil.rmtree` ONLY on `.harness/plans/suite-*` and `harness-suite/work/<slug>` in the main tree. NEVER `shutil.rmtree` a worktree path directly (the `node_modules` junction can be followed into root and delete it).
- `report.load_rows(csv_path) -> list[dict]`, `report.build_report(rows) -> str` (markdown).

## T0 node deps root
FILES: package.json, package-lock.json
MUST: add exact-pinned devDependencies from Decisions; run `npm install` at repo root (junction-shared into worktrees).
TEST: node -e "require.resolve('next');require.resolve('vitest')"

## T1 check fixtures script
FILES: harness-suite/check_fixtures.py
MUST:
- `--size {small,medium,large}` (omitted = loop all three that exist yet, skip missing gracefully for now).
- For a size: copy `fixtures/<size>/seed` to a temp dir, copy in `hidden_tests`, run them (pytest / vitest+tsc as applicable); assert FAIL (print `RED OK: <size>`); then overlay `fixtures/<size>/solution` onto the same temp copy, rerun; assert PASS (print `GREEN OK: <size>`); nonzero exit with a clear message on any unexpected result.
- A missing tool (exit 127, 'command not found') or other infra error is NOT red: print `INFRA: <size>: <why>` and exit 2; RED OK only when the tools ran and tests/tsc genuinely failed. Temp work dirs live under `harness-suite/.check-tmp/` (gitignored) and are removed afterwards.
- Windows: resolve `npx` via `shutil.which("npx")` (finds `npx.cmd`) before building commands; a bare `["npx", ...]` fails with CreateProcess. Same for any node tool.
TEST: python harness-suite/check_fixtures.py --help

## T2 fixture small
DEPS: T1
FILES: harness-suite/fixtures/small/seed/**, harness-suite/fixtures/small/solution/**, harness-suite/fixtures/small/plan/plan.md, harness-suite/fixtures/small/plan/tasks.json, harness-suite/fixtures/small/hidden_tests/test_hidden.py, harness-suite/fixtures/small/spec.md
MUST:
- seed/ = copy of `.harness/bench/tasks/large/seed` as-is (existing Items API).
- 2 independent tasks, disjoint files, both `deps:[]`: (a) `/tags` router + its own store module, (b) query filters + pagination on `GET /items` in a separate module (not both editing `app/main.py`).
- solution/ = a full green overlay implementing both features (files at the same relative paths the tasks would produce).
- tasks.json files/acceptance use `{work}` prefix; hidden_tests/test_hidden.py: pytest + fastapi TestClient covering both features; spec.md 5-10 lines.
TEST: python harness-suite/check_fixtures.py --size small

## T3 fixture medium
NOTE: create ONLY the exact paths in this task's FILES, with those exact names (the scope guard matches exact paths). Reuse the existing hidden_tests files; do not add new ones. The seed must NOT contain solution files (no lib/todos-store.ts in seed/).
DEPS: T0, T1
FILES: harness-suite/fixtures/medium/seed/**, harness-suite/fixtures/medium/solution/**, harness-suite/fixtures/medium/plan/plan.md, harness-suite/fixtures/medium/plan/tasks.json, harness-suite/fixtures/medium/hidden_tests/**, harness-suite/fixtures/medium/spec.md
MUST:
- seed/ = minimal Next.js App Router app: `app/layout.tsx`, `app/page.tsx`, `lib/`, `tsconfig.json`, `next-env.d.ts`, `vitest.config.ts` (environment jsdom, `@vitejs/plugin-react`), `package.json` with zero deps of its own.
- 4 independent tasks (disjoint files, `deps:[]`): `app/api/todos/route.ts`, `lib/todos-store.ts`, `lib/validate.ts`, `components/TodoList.tsx`; plus join task T5 (`deps` = all four) wiring `app/page.tsx`.
- solution/ = full green overlay for all 5 tasks' outputs.
- tasks.json files/acceptance use `{work}` prefix; hidden_tests: vitest specs (route via `new Request(...)`, component via `@testing-library/react`+jsdom); spec.md 5-10 lines.
TEST: python harness-suite/check_fixtures.py --size medium

## T4 fixture large
NOTE: create ONLY the exact paths in this task's FILES, with those exact names (the scope guard matches exact paths; any other file fails the task).
DEPS: T0, T1
FILES: harness-suite/fixtures/large/seed/backend/**, harness-suite/fixtures/large/seed/web/**, harness-suite/fixtures/large/solution/**, harness-suite/fixtures/large/plan/plan.md, harness-suite/fixtures/large/plan/tasks.json, harness-suite/fixtures/large/hidden_tests/**, harness-suite/fixtures/large/spec.md
MUST:
- seed/backend = FastAPI items API (in-memory/sqlite3 stdlib, no sqlalchemy); seed/web = minimal Next.js app (with `next-env.d.ts`, `vitest.config.ts` like T3).
- 6 independent tasks (disjoint files, `deps:[]`): backend models, store, CRUD router, search/stats endpoint; web typed API client, list/detail components. 2 join tasks: backend app wiring + OpenAPI contract test (`deps` = 4 backend leaves), web page wiring (`deps` = 2 web leaves).
- solution/ = full green overlay for all 8 tasks' outputs. tasks.json uses `{work}` prefix throughout; hidden_tests split backend/web; spec.md 8-12 lines.
TEST: python harness-suite/check_fixtures.py --size large

## T5 suite matrix cli
FILES: harness-suite/suite.py
MUST:
- Define `SIZES,MODES,EXECUTORS`, `build_matrix`, `preflight_executor` per interfaces.
- argparse: `--executors,--sizes,--modes,--reps` (default 3), `--seed` (default 0), `--dry,--keep,--force,--cell-timeout` (default 1800), `--max-cost` (float, stop once cumulative `cost` from `results.csv` rows exceeds it), `--rerun-infra` (rerun only rows with `status=="infra_error"`).
- `--dry`: build the matrix, print it with unsupported cells marked, and an estimated count of real (non-unsupported) runs; exit 0, no runner/network calls.
- Resume: before running a cell, if its `slug` already has a row in `results.csv` and not `--force`, skip it.
TEST: python harness-suite/suite.py --dry
(must print "3 sizes x 3 modes x 6 executors x 3 reps" substring and exit 0)

## T6 cells core
NOTE: resolve `npx` via `shutil.which("npx")` (npx.cmd on Windows), never a bare `"npx"` in a subprocess list.
FILES: harness-suite/cells.py
MUST: implement `prepare_cell, run_cell, cleanup_cell` exactly per interfaces (worktree.ensure + harness-suite/ prune, `{work}` templating, cell-timeout/infra_error detection, multi/window mode handling, tamper diff, metrics.jsonl read, cleanup via `git worktree remove --force`/`git branch -D` only).
TEST: python -c "import sys; sys.path.insert(0,'harness-suite'); import cells; assert hasattr(cells,'run_cell') and hasattr(cells,'cleanup_cell') and hasattr(cells,'prepare_cell')"

## T7 report builder
FILES: harness-suite/report.py
MUST:
- `load_rows(csv_path)` reads CSV per the column list into list[dict].
- `build_report(rows)` returns markdown: per executor x size x mode — pass@1, pass^3 (all reps of a slug-family pass), Wilson 95% CI on pass@1, median wall_s, cost per solved task, tokens per solved task; parallel speedup vs serial and multi overhead vs serial per executor+size; cost totals with Sonnet (`claude`) called out separately; a delta section vs the previous `harness_sha` when more than one appears in rows. Excludes `infra_error` rows from pass-rate math.
- `main()` writes `harness-suite/RESULTS.md` from `harness-suite/results.csv` if present else a "no results yet" stub; never raises on missing/empty CSV.
TEST: python -c "import sys; sys.path.insert(0,'harness-suite'); import report; assert report.build_report([{'executor':'pi','size':'small','mode':'serial','status':'pass','wall_s':'1.0','cost':'0'}])"

## T8 readme and tests
DEPS: T5, T6, T7
FILES: harness-suite/README.md, tests/test_harness_suite.py
MUST:
- README: usage of `suite.py` flags, work dir + `{work}` templating, hidden-test-leak fix + accepted git-object risk, status enum, cleanup safety rule, where results.csv/RESULTS.md land.
- tests import `build_matrix`, `preflight_executor` from suite.py, `load_rows` from report.py (path-insert `harness-suite/`).
- Cover: unsupported rows (parallel+non-thread-safe, multi/parallel+llama, window+non-small); resume skip via a fake existing `results.csv` row + `--force` override; CSV round-trip (DictWriter with the full column list, then `load_rows` returns equal rows).
TEST: python -m pytest tests/test_harness_suite.py -q

## T9 wire suite and summary
DEPS: T2, T3, T4, T5, T6, T7, T8
FILES: harness-suite/suite.py, .harness/plans/harness-suite/SUMMARY.md
MUST:
- Non-dry `main()`: for each pending cell (in `order_idx` order), skip per resume rule, else `preflight_executor` (False -> `"skipped"`), else `cells.run_cell` with `--cell-timeout`; always `cells.cleanup_cell` unless `--keep`; append every row to `harness-suite/results.csv` (header once); stop early once `--max-cost` exceeded; `--rerun-infra` filters to prior `infra_error` rows.
- SUMMARY.md (<=600 chars): what was built, files, how wired. Add `BUILD: pass` (run `python harness-suite/suite.py --dry`) or `BUILD: fail <first error line>`.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/harness-suite/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"

Note: the suite module is `cells.py`, not `runner.py`, so it does not shadow the `.harness/runner` package imported for REGISTRY/worktree.

## T10 review fixes
DEPS: T9
FILES: harness-suite/suite.py, harness-suite/cells.py, tests/test_harness_suite.py
MUST:
- suite.main(): write each row to results.csv as soon as it exists (open append, header if file empty, flush), not once after the loop; a crash mid-matrix keeps the finished rows, so resume skips them.
- multi mode: `cells.run_cell` returns a list for multi. Run it ONCE per (executor, rep): the first multi cell of that pair triggers it, and the pair's other multi cells are skipped with no row. Resume skips the pair when all three per-size slugs are already in results.csv. Handle the list (write every row, sum cost over all rows).
- main(): no extra `cleanup_cell` after a multi run (`_run_multi` already cleans each size); keep it for single cells.
- cells._run_multi: track timed_out like `_run_single`; when the deadline kills a survivor, that size's row gets status "timeout", not the `_finish` result.
- test names MUST contain `multi_once`, `rows_persist`, `multi_timeout` (acceptance selects them with -k).
- tests (monkeypatch `cells.run_cell`/`cleanup_cell`/`preflight_executor`, tmp results.csv, no real runs): multi runs once per executor+rep; a list return writes 3 rows; rows persist when a later cell raises; the timeout mapping for a multi survivor.
TEST: python -m pytest tests/test_harness_suite.py -q -k "multi_once or rows_persist or multi_timeout" && python -m pytest tests/test_harness_suite.py -q && python harness-suite/suite.py --dry
