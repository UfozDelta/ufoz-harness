import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".harness")
from runner import cli  # noqa: E402

a = cli.build_parser().parse_args(["x", "--worktree"])
assert a.worktree
a = cli.build_parser().parse_args(["x", "--watch", "--window"])
assert a.watch and a.window
src = Path(".harness/runner/cli.py").read_text(encoding="utf-8")
assert "worktree.ensure(" in src and "os.chdir(" in src
tmp = Path(tempfile.mkdtemp())
os.chdir(tmp)
assert cli.watch_dir("s") == Path(".harness/plans/s")
(tmp / ".worktrees/s/.harness/plans/s").mkdir(parents=True)
assert cli.watch_dir("s") == Path(".worktrees/s/.harness/plans/s")
print("OK")
