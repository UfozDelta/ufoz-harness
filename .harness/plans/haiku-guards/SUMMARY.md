# haiku-guards

What: --check DIR grades work done outside the runner (haiku-executor in a worktree): grader lock, file scope, each task's acceptance run in DIR; exit 0 only if clean. Haiku 5.5 cost now from token counts at RATES, not the CLI's total_cost_usd.

Files: .harness/runner/check.py (new), .harness/runner/cli.py (--check flag), .harness/runner/executors/claude.py (RATES, rated_cost).

Wiring: cli._run dispatches check.check(slug, DIR) after --relock-only and exits with its code; run_claude_exec overrides usage cost when the model is in RATES.
