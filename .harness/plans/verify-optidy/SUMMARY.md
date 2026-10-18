What: opencode runtime files no longer dirty worktrees; headless planners told not to read .pi/.
Files: .harness/runner/worktree.py (OPENCODE_PKG gains .opencode/.gitignore, copied into worktrees); bench/verify/verify.py (_plan_brief adds "Do not read anything under .pi/.").
Wiring: worktree setup copies OPENCODE_PKG entries into the new worktree; _plan_brief feeds the planner prompt. rules_ok check remains the enforcement.
BUILD: pass
