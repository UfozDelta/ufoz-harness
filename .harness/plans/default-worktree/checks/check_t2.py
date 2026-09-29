import os
import sys
from pathlib import Path

sys.path.insert(0, ".harness")
from runner import cli  # noqa: E402

ap = cli.build_parser()
a = ap.parse_args(["x"])
assert a.worktree is None and a.window is None
b = ap.parse_args(["x", "--no-worktree", "--no-window"])
assert b.worktree is False and b.window is False
c = ap.parse_args(["x", "--worktree", "--window"])
assert c.worktree is True and c.window is True
for k in ("HARNESS_WORKTREE", "HARNESS_WINDOW"):
    os.environ.pop(k, None)
assert cli.use_worktree(a) and cli.use_window(a)
assert not cli.use_worktree(b) and not cli.use_window(b)
os.environ["HARNESS_WORKTREE"] = "0"
os.environ["HARNESS_WINDOW"] = "0"
assert not cli.use_worktree(a) and not cli.use_window(a)
assert cli.use_worktree(c) and cli.use_window(c)
os.environ["HARNESS_WINDOW"] = "1"
assert cli.use_window(a)
src = Path(".harness/runner/cli.py").read_text(encoding="utf-8")
for s in ["sync_plan(", "in_git_repo(", "not a git repo: running in place", "BooleanOptionalAction"]:
    assert s in src, s
from runner import watch  # noqa: E402
orig = watch.shutil.which
watch.shutil.which = lambda c: "C:/wt.exe" if c == "wt" else None
cmd = watch.window_command("demo")
watch.shutil.which = orig
assert cmd[:6] == ["wt", "-w", "harness", "new-tab", "--title", "harness demo"], cmd
assert cmd[-1] == "--watch", cmd
i_lock, i_sync, i_plan = src.find("_acquire_run_lock(", src.find("worktree.ensure(")), src.find("sync_plan("), src.find("Plan(args.slug")
assert 0 < i_lock < i_sync < i_plan, (i_lock, i_sync, i_plan)
print("OK")
