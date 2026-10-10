tidy-runner: behavior-preserving runner cleanup.
- plan.PLANS_ROOT replaces the ".harness/plans" literals; args.warm dropped (readers use not args.fresh).
- cli.main returns an exit code; _run split into _info, _enter_worktree, _execute, _review.
Files: .harness/runner/{plan,cli,check,planner,watch,scheduler,task_runner,report}.py, .harness/run_plan.py, tests/test_task_runner.py, tests/test_log_fixes.py.
Wiring: run_plan.py sys.exit(main()) -> cli.main -> _run -> _info/_enter_worktree/_execute.
BUILD: pass
