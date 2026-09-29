"""Run a plan's tasks through the pi executor agent (the default).

Usage: python .harness/run_plan.py <slug> [--only T2] [--timeout 900] [--review] [--relock]
                                             [--lint] [--retries 1] [--repair 1]
                                             [--executor pi|claude|opencode|cline|cline-acp]
       python .harness/run_plan.py --stats

Reads .harness/plans/<slug>/tasks.json, runs tasks in list order, writes
.harness/plans/<slug>/logs/<id>.<executor>.log and .harness/plans/<slug>/items/<id>.report.md,
stops at the first failure, prints a short summary. Never touches git state.
An opt-in final build_gate can use repair_check in the repair pass and gate on SUMMARY.md.

A task's brief is items/<id>.md ("brief" key) or, when "brief" is absent, the
`## <id>` section of plan.md (slim plans: no items/, acceptance = the project's tests).

Guards (no model calls): tasks.json + checks/*.py are hashed into plan.lock.json on
first run and must not change; each acceptance must FAIL before the executor runs
(red-first; opt out per task with "red_first": false); any touched file not in the
task's "files" fails the task (content hashes, so already-dirty files count too).
A plain acceptance failure reruns the executor with items/<id>.feedback.md, then
optionally repairs it with the failing task's and earlier tasks' files in scope.

Metrics: every task appends {slug, task, result, attempts, repairs, seconds, executor tokens}
to .harness/metrics.jsonl (a --review pass adds a row with its exact cost); --stats
totals it per plan and adds planner/reviewer/validator subagent usage read from
Claude Code's own logs (~/.claude/projects/<this project>/*/subagents/).

The implementation lives in the runner/ package (see runner/cli.py); this file stays
the entry point and the place bench.py and selftest.py import from.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Windows consoles default to a non-UTF-8 code page (cp1252); summary output contains
# characters like "->" arrows. Reconfigure so printing them never crashes.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import envfile  # noqa: E402
envfile.load_env()

from runner.cli import main  # noqa: E402
from runner.executors.pi import quota_ok  # noqa: E402,F401  (re-exported for bench/selftest)
from runner.stats import PRICES, claude_agent_runs  # noqa: E402,F401


if __name__ == "__main__":
    main()
