verify-isolation: a verify cell cannot read other cells' projects or hidden tests; an escaping cell is not a pass.
Files: bench/verify/backends.py (check_escape: flags ufoz-bench/verify-* or suite-* other than this slug, hidden_tests, test_hidden, suite/fixtures); bench/verify/verify.py (_wipe_stale, _escape_check, _plan_brief sentence).
Wiring: run_cell wipes stale verify- dirs before make_project; orchestrator output checked (escaped_cwd); plan.log and exec.log checked at scoring (pass becomes fail escaped_cwd, rules_ok false). Hits logged to rules_failures.log.
BUILD: pass
