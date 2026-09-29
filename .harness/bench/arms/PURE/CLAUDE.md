# Benchmark arm PURE — one Sonnet session, staged

You build a web shop in stages, all in this one session. Each prompt names one stage spec, `spec/stages/s<N>.md`.
Read `spec/spec.md` (shared decisions) and that stage file, then build the stage yourself: plan it, implement it,
write and run whatever tests you judge useful, and run `npm run build`. Earlier stages must keep working.
Only the current and earlier stage files exist; do not look for later ones.
Write all prose (replies, plans, reports) caveman-terse: drop articles, filler and hedging; fragments OK. Code stays normal.

Do not use the Agent tool, opencode, or `.harness/run_plan.py`. Never run git commands that change state.
Finish a stage only when it works, then reply with exactly three lines: `Blocked on me:` / `Changed:` / `Found:`.
