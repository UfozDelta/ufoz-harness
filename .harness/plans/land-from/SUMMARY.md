`run_plan.py <slug> --land --from DIR` lands work done in an outside worktree (e.g. a Claude subagent's).
Files: .harness/runner/land.py (new `land_from(slug, directory)`), .harness/runner/cli.py (`--from` arg, requires `--land`).
Wiring: land_from runs check.check first; on pass builds a binary diff of DIR limited to the plan's task files, saves .harness/plans/<slug>/land.patch, apply --check then apply in main tree, then removes DIR worktree and its branch. Any failure keeps DIR.
