"""Harness runner package: the pure helpers split out of run_plan.py.

Modules here hold no executor logic: procs (process/usage constants), guards
(tree snapshots, grader lock hashes, out-of-scope and suppression-marker checks),
acceptance (running checks, parsing errors), lint (static plan validation),
stats (metrics rows, cost tables, --stats) and reviewer (the --review pass).
"""
