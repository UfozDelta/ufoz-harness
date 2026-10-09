bench-trust: suite rows are now versioned and failures classified.
Files: bench/suite/{cells,suite,report,check_fixtures}.py, bench/speed/report.py, tests/test_harness_suite.py.
What: rows carry run_id, fixture_hash and a real harness_sha (+diff tag); window cells that open/watch badly become harness_fail (excluded from pass rate); report keeps latest row per cell and newest sha (--all-shas opts out), labels claude by its model column; speed table has a Harness column; check_fixtures --repeat flake gate.
BUILD: pass
