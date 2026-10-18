"""Acceptance T5: results.csv migrated without losing rows, RESULTS.md regenerated, SUMMARY short."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, "bench/verify")
import backends  # noqa: E402

with open("bench/verify/results.csv", newline="", encoding="utf-8") as fh:
    reader = csv.DictReader(fh)
    assert reader.fieldnames == backends.CSV_FIELDS, reader.fieldnames
    rows = list(reader)
assert len(rows) >= 86, len(rows)
assert sum(1 for r in rows if r["status"] == "pass") >= 27

md = Path("bench/verify/RESULTS.md").read_text(encoding="utf-8")
assert "cache hit" in md.lower() and "By axis" in md

summary = Path(".harness/plans/verify-metrics/SUMMARY.md").read_text(encoding="utf-8")
assert 0 < len(summary) <= 600, len(summary)
assert "BUILD: pass" in summary
print("T5 OK")
