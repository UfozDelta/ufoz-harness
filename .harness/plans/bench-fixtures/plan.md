# Plan: bench-fixtures

## Goal
Medium and large fixture seeds get real passing tests plus real package.json + lockfile, so a seed is self-contained. check_fixtures.py proves seed tests green on seed and on seed+solution.

## Decisions
- Only real seed code gets tests. Stubs (medium `lib/validate.ts`, `lib/todos-store.ts`; large `backend/app/store.py`, `models.py` classes) throw on use: NEVER test them.
- Medium: `bench/suite/fixtures/medium/seed/lib/format.test.ts` (`formatCount`: 0, 1, n -> "0 todos", "1 todo", "5 todos"). 3 tests.
- Large web: `.../large/seed/web/lib/format.test.ts` (`pluralItems`, same 3 cases, items). Large backend: `.../large/seed/backend/tests/test_seed_contract.py`: inserts the backend dir (parents[1]) in sys.path, asserts `NAME_MAX == 60`, `SKU_MAX == 32`, `issubclass(DuplicateSku, ValueError)`; imports only `app.models`/`app.store` (never instantiate). 3 tests.
- Tests import `describe, it, expect` explicitly from "vitest"; relative imports (`./format`).
- package.json: keep existing name/scripts, add scripts `test: vitest run`, `typecheck: tsc --noEmit` if missing; `dependencies` stays `{}`; `devDependencies` = EXACT copy of repo-root `package.json` devDependencies (same pins). Locations: medium `seed/package.json`, large `seed/web/package.json`.
- Lockfile: `package-lock.json` beside each, = repo-root `package-lock.json` with top-level `name` and `packages[""].name` set to that package.json's name (`packages[""].version` = its version). Produce with a one-off `python -c` json copy; no npm.
- check_fixtures.py new: `seed_checks_for(work) -> list[(label, cmd)]`: `pytest` entry only if any `test_*.py` under work, `vitest` entry only if any `*.test.ts(x)`; no tsc; `[]` if none. `check_package(size) -> bool`: package.json (medium `seed/`, large `seed/web/`; small: skip, True) and lockfile parse, lock `packages[""].devDependencies` == package.json `devDependencies`. `check_size` order: package check, SEED check (copy seed only, all seed checks exit 0), existing RED, existing GREEN, then SOLUTION-WITHOUT-HIDDEN check (seed+solution, seed checks exit 0). Any failure prints `FAIL: ...` and returns False. `--size`/`--repeat` unchanged.
- Never run npm. Never edit seed stubs, solution, hidden_tests, plan dirs.

Verified: root `package.json` pins in devDependencies and tracked `package-lock.json` exist (`git ls-files package-lock.json`).
Verified: medium/large seed stubs throw (read `lib/validate.ts`, `store.py`).
Unverified: vitest seed tests were not executed; `npm ci` on the derived lockfile; tsc accepts the new test files; pytest seed test imports `app.models` (pydantic) fine.
Later: small-fixture parity.

## interfaces
Keep `copy_into`, `make_work`, `checks_for`, `run_all`, `runs_agree`, `check_size(size, repeat)`, `main`.

## T1 seed tests
FILES: bench/suite/fixtures/medium/seed/lib/format.test.ts, bench/suite/fixtures/large/seed/web/lib/format.test.ts, bench/suite/fixtures/large/seed/backend/tests/test_seed_contract.py
MUST: per Decisions; python test passes on the seed; no stub is exercised.
TEST: python -m pytest -q -p no:cacheprovider bench/suite/fixtures/large/seed/backend/tests && npx tsc --noEmit --incremental --tsBuildInfoFile .harness/tsc.tsbuildinfo

## T2 package files
FILES: bench/suite/fixtures/medium/seed/package.json, bench/suite/fixtures/medium/seed/package-lock.json, bench/suite/fixtures/large/seed/web/package.json, bench/suite/fixtures/large/seed/web/package-lock.json
MUST: per Decisions; lock `packages[""].devDependencies` equals package.json `devDependencies`; JSON valid.
TEST: python .harness/plans/bench-fixtures/checks/check_t2.py

## T3 check_fixtures
FILES: bench/suite/check_fixtures.py, tests/test_harness_suite.py
MUST: `seed_checks_for`, `check_package`, and the `check_size` flow per Decisions; add test `test_seed_checks_for` (tmp dir with one `test_x.py` -> only `pytest`; with `a.test.ts` -> only `vitest`; empty -> `[]`).
TEST: python -m pytest -q tests/test_harness_suite.py -k seed_checks_for

## T4 write summary
FILES: .harness/plans/bench-fixtures/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run `python -m pytest -q tests/test_harness_suite.py` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/bench-fixtures/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
