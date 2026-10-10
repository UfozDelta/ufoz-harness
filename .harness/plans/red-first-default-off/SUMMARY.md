red-first-default-off: red_first now defaults to false (opt in per task).
- plan.Task.red_first=False; lint red-first loop runs only for `red_first: true`; red_first_reason rule gone.
- report.py check-invalid hint reworded; docs + planner agent updated.
Files: .harness/runner/{plan,lint,report}.py, tests/test_lint.py, .harness/HARNESS.md, .claude/agents/planner.md, docs/ARCHITECTURE.md, README.md, .harness/run_plan.py.
BUILD: pass
Verify: selftest OK; pytest tests 159 passed; --lint 38 plans: 36 OK, 2 pre-existing Windows POSIX-acceptance errors (map-skip-worktrees T2, plan-status T3).