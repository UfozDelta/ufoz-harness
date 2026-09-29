import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import plan, task_runner  # noqa: E402
from runner.executors.base import ExecResult, Executor  # noqa: E402

Plan = plan.Plan


class FakeExecutor(Executor):
    """Fails the first N attempts, then does the work. Everything it writes lives under the
    tmp plan dir: snapshot() runs `git ls-files` in the real repo, so a file written anywhere
    else would show up as a stray edit and fail the task for the wrong reason."""

    name = "fake"
    has_sessions = False
    thread_safe = True

    def __init__(self, plan_dir, done, succeed_on):
        self.plan_dir = plan_dir
        self.done = done
        self.succeed_on = succeed_on
        self.calls = 0

    def run(self, brief, log, timeout, feedback=None, session=None, rules=None, raw_prompt=None):
        self.calls += 1
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with open(log, "ab") as f:
            f.write(f"[fake] attempt {self.calls} feedback={feedback}\n".encode())
        if self.calls >= self.succeed_on:
            self.done.write_text("done\n", encoding="utf-8")
            return ExecResult(code=0, usage={"input": 1, "output": 1, "reasoning": 0,
                                            "cache_read": 0, "cost": 0.0}, session=None)
        return ExecResult(code=1, usage={"input": 1, "output": 1, "reasoning": 0,
                                        "cache_read": 0, "cost": 0.0}, session=None)

    def probe(self) -> bool:
        return True


def make_plan(tmp_path, succeed_on):
    plan_dir = tmp_path / "plans" / "slug"
    (plan_dir / "checks").mkdir(parents=True)
    done = plan_dir / "done.txt"
    check = plan_dir / "check.py"
    check.write_text(
        "import pathlib, sys\n"
        f"sys.exit(0 if pathlib.Path({str(done)!r}).is_file() else 1)\n",
        encoding="utf-8")
    task = {"id": "T1", "acceptance": f'python "{check.as_posix()}"', "files": [done.as_posix()]}
    (plan_dir / "tasks.json").write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    plan = Plan("slug", tmp_path / "plans")
    plan.prepare()
    plan.lock_grader()
    args = argparse.Namespace(slug="slug", executor="fake", timeout=60, retries=1, repair=1,
                              warm=False, parallel=1)
    executor = FakeExecutor(plan_dir, done, succeed_on)
    return plan, args, executor


def test_retry_then_repair_feedback_files_and_eventual_pass(tmp_path):
    plan, args, executor = make_plan(tmp_path, succeed_on=3)
    ok, lines, session = task_runner.TaskRunner(plan, args, executor).run(plan.tasks[0])

    items = plan.items
    # first plain failure -> exactly one retry, and the retry feedback brief is written
    assert executor.calls == 3, f"expected 2 attempts + 1 repair, got {executor.calls}"
    assert (items / "T1.feedback.md").is_file()
    # retry also failed -> the repair pass starts with its own brief
    assert (items / "T1.repair1.md").is_file()
    # the repair pass did the work, so the task passes
    assert ok is True
    assert any(line.startswith("T1 REPAIRED") for line in lines)
    assert session is None
    assert "RESULT: pass" in plan.report_text("T1")


def test_still_failing_after_repair_is_not_ok(tmp_path):
    plan, args, executor = make_plan(tmp_path, succeed_on=99)
    ok, lines, _ = task_runner.TaskRunner(plan, args, executor).run(plan.tasks[0])

    assert executor.calls == 3
    assert ok is False
    assert (plan.items / "T1.repair1.md").is_file()
    assert "RESULT: fail" in plan.report_text("T1")
    assert lines[0].startswith("T1 FAIL")
