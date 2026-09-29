"""Acceptance check for T6. Run from project root: python .harness/plans/bench-plan/checks/check_t6.py

Runs the suite and verifies the required new tests exist.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())

REQUIRED = [
    "test_put_replaces_item",
    "test_put_keeps_list_position",
    "test_put_missing_item_404",
    "test_put_invalid_returns_422",
    "test_delete_removes_item",
    "test_delete_missing_item_404",
    "test_delete_does_not_reuse_ids",
    "test_filter_min_price",
    "test_filter_max_price",
    "test_filter_name_contains_case_insensitive",
    "test_filters_combined",
    "test_filter_no_matches_returns_empty",
    "test_filter_invalid_query_returns_422",
]

source = open(os.path.join("tests", "test_items.py"), encoding="utf-8").read()
missing = [name for name in REQUIRED if f"def {name}(" not in source]
assert not missing, f"missing tests in tests/test_items.py: {missing}"

for name in ("test_health", "test_create_item", "test_get_missing_item_404"):
    assert f"def {name}(" in source, f"existing test {name} was removed"

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_items.py", "-q"],
    cwd=os.getcwd(),
)
assert result.returncode == 0, "tests/test_items.py must pass"

print("TESTS OK")
