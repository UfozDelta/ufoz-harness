# Benchmark arm A — Claude implements directly

You are given a frozen plan at `.harness/plans/bench-plan/`: `plan.md` (goal, decisions) plus either
`items/T<n>.md` briefs or, in a slim plan, one `## T<n>` section per task in `plan.md`; `tasks.json` has each task's
FILES and acceptance command. Implement every task yourself, in order, respecting each brief's FILES
and CONSTRAINTS. Do not use the Agent tool, do not delegate, do not run opencode.
Never run git commands that change state (add, commit, push, reset, checkout, stash, clean).
When done, run each task's ACCEPTANCE command yourself and fix failures before moving on.
