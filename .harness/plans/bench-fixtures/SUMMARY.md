bench-fixtures: medium and large seeds now have their own tests and package files.
Files: medium/seed/lib/format.test.ts, large/seed/web/lib/format.test.ts, large/seed/backend/tests/test_seed_contract.py, package.json + package-lock.json for both, bench/suite/check_fixtures.py (seed checks + package check), tests/test_harness_suite.py.
Wiring: check_fixtures runs the seed's own pytest/vitest on the seed and on the solution; check_package compares lockfile devDependencies.
BUILD: pass
