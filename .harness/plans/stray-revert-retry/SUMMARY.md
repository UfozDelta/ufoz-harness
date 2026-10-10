What: a stray (out-of-scope) attempt no longer ends the task. The runner reverts the strays in the worktree and retries once with a brief naming the allowed FILES and the reverted names; a second stray fails.
Files: guards.py (revert_paths), report.py (stray_feedback, final_report reverted=), task_runner.py (loop), tests/test_task_runner.py.
Wiring: run() reverts got.stray, writes stray_feedback + retry_feedback to items/T<id>.feedback.md, continues; reverted names stay in the report. A stray with nothing to undo, or GIT_MOVED, breaks as before.
BUILD: python -m pytest tests -q (157 passed)