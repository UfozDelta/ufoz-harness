import sys, tempfile
from pathlib import Path
sys.path.insert(0, "bench/verify")
import verify
assert verify._score_reason({"status": "pass"}) == ""
assert verify._score_reason({"status": "fail", "tasks_passed": 1, "tasks_total": 3}) == "tasks_failed"
assert verify._score_reason({"status": "fail", "tasks_passed": 3, "tasks_total": 3,
                             "tests_passed": 1, "tests_total": 4}) == "tests_failed"
assert verify._score_reason({"status": "fail", "tasks_passed": 3, "tasks_total": 3,
                             "tests_passed": 4, "tests_total": 4,
                             "regression_passed": 1, "regression_total": 2}) == "regression_failed"
assert verify._score_reason({"status": "infra_error"}) == "no_reports"
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    src = t / "src"; (src / "logs").mkdir(parents=True); (src / "logs" / "a.log").write_text("x")
    verify._save_logs(t, "s", src, "project", "STAMP")
    assert (t / "bench/verify/logs/s__STAMP/project/logs/a.log").read_text() == "x"
    verify._save_logs(t, "s", t / "missing", "wt", "STAMP")  # never raises
