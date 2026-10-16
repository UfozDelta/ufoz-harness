# agents-md-role-split

Role rules split so main and executors load only their own.

- AGENTS.md: MAIN rules (from .harness/MAIN.md) + pointer to .harness/HARNESS.md; executor rules only in .pi/executor.md (T1/T2).
- pi: --no-context-files, model opencode/deepseek-v4.1-flash (T3).
- opencode: profile default noproj, same model (T4).
- claude: .pi/executor.md only, CLAUDE_CODE_DISABLE_CLAUDE_MDS=1 on both spawns (T5).
- opencode.json: instructions [.harness/MAIN.md, .harness/HARNESS.md], orchestrator+planner model (T6).

BUILD: fail test_preflight_executor_true_for_local_executors
