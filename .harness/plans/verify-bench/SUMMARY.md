Added bench/verify/: a 27-cell orchestrator x planner x executor (claude/pi/opencode) verification bench.
Files: backends.py (axes, matrix, commands, rules check), verify.py (CLI: plan, run, land, score, resume, CSV), report.py (RESULTS.md), README.md, selfcheck.py (one-cell e2e). bench/suite/cells.py gained commit_plan and score_project.
Wired via bench/suite make_project/plan_for_project; results go to bench/verify/results.csv.
BUILD: pass
