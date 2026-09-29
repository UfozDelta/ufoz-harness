# quick-fixes

- `.harness/run_plan.py`: stdout/stderr reconfigured to UTF-8, errors="replace" (no more cp1252
  console crash on non-ASCII output).
- `.harness/MAIN.md`: specs at `.harness/plans/<slug>/SPEC.md`; output style bans narrated
  reasoning and re-litigating decisions.
- `.claude/agents/planner.md`: acceptance scripts go in `checks/check_t<n>.py`, never in a task's
  `files`.
- `.pi/extensions/deny-match.ts` adds pure `isChecksPath(cwd, p)`; `deny-list.ts` calls it before
  the `external_directory` check, denying writes under any `checks/`. Tests in
  `deny-match.test.mjs`.
