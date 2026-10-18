# Plan: verify-metrics
## Goal
Record per-phase time, tokens, cache and cost for every verify-bench cell, and report them (cache hit rate, cost per pass, per-axis rankings).

## Decisions
- Phases `orch` (headless orchestrator plan), `plan` (runner planner), `exec` (executor). Per phase columns `{p}_wall_s,{p}_in,{p}_out,{p}_reason,{p}_cache_read,{p}_cache_write,{p}_tool_calls`; `in` is uncached input only. Cost columns: new `orch_cost`, existing `plan_cost`, `exec_cost`. Extra: `orch_turns,plan_attempts,plan_cached,exec_attempts,usage_json`. All appended after the existing columns in `backends.COLUMNS`; `wall_s` stays the cell total.
- A value a backend cannot report is blank (null), never 0. Unreported: orchestrator opencode (all usage), executor claude `cache_write` (folded into `in`).
- Orchestrator capture: claude adds `--output-format stream-json --verbose`, pi adds `--mode json`; opencode stays plain text. `backends.parse_stream(backend, text) -> (usage, rendered)` turns events back into text lines incl. `[toolCall Name] {json[:200]}` so `check_rules` keeps working.
- Headless mode ignores the planner axis: unless `--planners` is given or `--plan-via runner`, the default planner list is `["pi"]` (9 cells).
- Executor usage: read `metrics.jsonl` rows (slug, task set, no `kind`; tokens dict) from the worktree before `--land`; tool_calls = count of `[toolCall` in `<wt>/.harness/plans/<slug>/logs/T*.pi.log`. Runner records `cache_write` for pi and opencode (T1).
- A cached plan (runner returns cost 0.0) writes blank `plan_cost` and `plan_cached=true`.
- No repricing (no verified price table); cost is whatever the backend reports.
- Report derives, never stores: cache hit = cache_read / (in + cache_read + cache_write or 0); cost per pass = total cost / passing cells.

## interfaces
- `runner.procs.TOKEN_KEYS` gains `cache_write`.
- `backends`: `USAGE_FIELDS`, `COLUMNS`, `CSV_FIELDS`, `parse_stream(backend, text)`; usage dict keys `in,out,reason,cache_read,cache_write,cost,turns,tool_calls`, value None when unreported.
- `verify`: `_exec_usage(slug, wt) -> dict`, `migrate_csv(path)`; `_append_row` migrates an old header first.
- `report.build_report(rows)` still pure and total.

## T1 runner cache_write
FILES: .harness/runner/procs.py, .harness/runner/executors/pi.py, .harness/runner/executors/opencode.py, .harness/runner/planner.py
MUST:
- Add `"cache_write"` to `TOKEN_KEYS`.
- pi.py: accumulate `u.get("cacheWrite")`; opencode.py: accumulate `tokens.cache.write`; planner.py: copy `cache_write` into planner.json tokens like the other keys.
- Do not change claude.py. `python .harness/selftest.py` still exits 0.
TEST: python .harness/plans/verify-metrics/checks/check_t1.py

## T2 backends
FILES: bench/verify/backends.py
MUST:
- Add `USAGE_FIELDS`, extend `COLUMNS` per Decisions, add `parse_stream`, and the json flags in `orchestrator_command`.
- claude events: `assistant` message content `text`/`tool_use` blocks; `result` event has `usage{input_tokens,output_tokens,cache_read_input_tokens,cache_creation_input_tokens}`, `total_cost_usd`, `num_turns`, `result`. pi events: `message_end` with `message.role=="assistant"`, `usage{input,output,reasoning,cacheRead,cacheWrite,cost{total}}`, content `text`/`toolCall{name,arguments}`; sum over events, turns = event count.
- Non-JSON lines pass through to `rendered`. opencode returns all-None usage and the text unchanged. No JSON usage found means all None.
TEST: python .harness/plans/verify-metrics/checks/check_t2.py

## T3 capture
FILES: bench/verify/verify.py
MUST:
- Time each phase and fill the columns from Decisions; headless: write raw output to `logs/plan.raw.jsonl`, rendered text to `plan.log`; runner: read `planner.json` (tokens, seconds, attempts).
- `exec_*` from `_exec_usage`; write `bench/verify/usage/<slug>__<ts>.json` (per-phase usage) and put its relative path in `usage_json`.
- `migrate_csv(path)` rewrites an old-header CSV under `CSV_FIELDS` (old values kept, new blank) via temp file then rename; `_append_row` calls it. `_existing_cost` also adds `orch_cost`. Default planners per Decisions.
TEST: python .harness/plans/verify-metrics/checks/check_t3.py

## T4 report
FILES: bench/verify/report.py
MUST:
- Combos table adds: n, pass %, mean wall s, mean cost $, total tokens, cache hit, cost per pass; sorted by pass % desc then cost per pass asc (null last). Rows with n < 3 get a `†` and a note "rank provisional".
- Add "By axis" tables for orchestrator, planner and executor, and a per-phase table (mean in/out/cache_read/cache_write/cost/wall per combo phase). Means skip blanks; empty shows `-`; stdev only when n >= 2.
- Keep the Totals section. Legacy rows without the new columns still render.
TEST: python .harness/plans/verify-metrics/checks/check_t4.py

## T5 migrate and summarize
FILES: bench/verify/results.csv, bench/verify/RESULTS.md, .harness/plans/verify-metrics/SUMMARY.md
MUST:
- Run `python -c "import sys; sys.path.insert(0,'bench/verify'); import verify; verify.migrate_csv(verify.RESULTS)"`, then `python bench/verify/report.py`.
- Write SUMMARY.md (<= 600 chars: what, files, how wired; note opencode orchestrator and claude exec cache_write are null) and end with the BUILD smoke below.
TEST: python .harness/plans/verify-metrics/checks/check_t5.py
