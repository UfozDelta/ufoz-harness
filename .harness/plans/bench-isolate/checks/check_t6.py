import sys

sys.path.insert(0, "bench/suite")
import report  # noqa: E402
import suite  # noqa: E402

assert suite.COLUMNS == report.COLUMNS
assert suite.COLUMNS[-6:] == ["plan_source", "planner", "plan_cost", "regression_passed",
                              "regression_total", "kit_hash"]
a = suite.parse_args(["--legacy", "--plan-source", "planner"])
assert a.legacy and a.plan_source == "planner" and a.planner == "claude" and a.planner_model == "sonnet"
d = suite.parse_args([])
assert not d.legacy and d.plan_source == "fixture"
row = dict(size="small", mode="serial", executor="pi", rep="1", status="fail",
           regression_passed="1", regression_total="2", plan_cost="0.5", kit_hash="ab12")
text = report.build_report([row])
assert "regressions" in text and "Planner cost" in text and "ab12" in text
report.build_report([dict(size="small", mode="serial", executor="pi", rep="1", status="pass")])
print("T6 OK")
