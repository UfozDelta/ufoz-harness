import sys
from pathlib import Path

sys.path.insert(0, ".harness")
from runner import cli  # noqa: E402

a = cli.build_parser().parse_args(["x", "--land"])
assert a.land
src = Path(".harness/runner/cli.py").read_text(encoding="utf-8")
assert "land.land(args.slug)" in src
assert src.find("land.land(args.slug)") < src.find("Plan(args.slug"), "land must exit before the plan loads"
print("OK")
