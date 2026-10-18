import sys
sys.path.insert(0, "bench/verify")
import backends
for c in ("fail_reason", "tests_passed", "tests_total", "regression_passed", "regression_total", "logs_dir"):
    assert c in backends.CSV_FIELDS, c
assert backends.COLUMNS[-6:][0] == "fail_reason"
