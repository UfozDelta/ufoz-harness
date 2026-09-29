import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, ".harness")
from runner import cli  # noqa: E402

a = cli.build_parser().parse_args(["x", "--watch", "--window"])
assert a.watch and a.window
src = Path(".harness/runner/cli.py").read_text(encoding="utf-8")
assert "HARNESS_WINDOW" in src and "open_window(" in src and "watch.watch(" in src
tmp = Path(tempfile.mkdtemp())
d = tmp / ".harness/plans/demo"
(d / "logs").mkdir(parents=True)
(d / "items").mkdir()
task = {"id": "T1", "deps": [], "files": ["a"], "acceptance": "echo"}
(d / "tasks.json").write_text(json.dumps({"slug": "demo", "tasks": [task]}), encoding="utf-8")
(d / "logs/T1.pi.log").write_text("DONE: a\n", encoding="utf-8")
(d / "items/T1.report.md").write_text("RESULT: pass\n", encoding="utf-8")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, str(ROOT / ".harness/run_plan.py"), "demo", "--watch"], cwd=tmp,
                   capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
                   stdin=subprocess.DEVNULL)
assert r.returncode == 0, r.stdout + r.stderr
assert "DONE: a" in r.stdout and "done: 1/1 pass" in r.stdout, r.stdout
assert not (d / "run.lock").exists()
print("OK")
