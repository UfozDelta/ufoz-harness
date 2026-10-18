"""Acceptance: one real cell (verify-pi-pi-pi-r1) runs end to end and records a pass row."""
import csv
import subprocess
import sys
from pathlib import Path


def main():
    proc = subprocess.run([sys.executable, "bench/verify/selfcheck.py"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out[-1200:]
    path = Path("bench/verify/results.csv")
    assert path.exists(), "no results.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    hit = [r for r in rows if r.get("slug") == "verify-pi-pi-pi-r1"]
    assert hit, "no row for verify-pi-pi-pi-r1"
    assert hit[-1]["status"] == "pass", hit[-1]
    assert hit[-1]["model"] == "opencode/deepseek-v4.1-flash", hit[-1].get("model")
    print("E2E OK")
    return 0


raise SystemExit(main())
