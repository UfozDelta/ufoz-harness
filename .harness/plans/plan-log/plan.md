# Plan: plan-log

## Goal
Answer "when was this plan created / when did it last run, pass or fail" without guessing from
file mtimes or scanning `items/T*.report.md`. Extend the existing `.harness/metrics.jsonl`
(already timestamped, already read by `--stats`) instead of adding a new file format.

## Decisions
1. Three new row kinds in `metrics.jsonl`, same shape as the existing `"kind": "review"` row
   (see `reviewer.py`): `{"ts", "slug", "kind": "plan_event", "event", ...}`.
   - `event: "created"` — written once, right after a headless `--plan spec.md` lints OK.
     Hand-written plans (main session writes plan.md itself) have no code path to hook, so they
     stay answered by git history, same as everything else in this repo.
   - `event: "run_start"` — written right before the executor loop starts (i.e. after lint/lock,
     not on `--lint`-only or `--plan`-only invocations).
   - `event: "run_end"` — written right after the run finishes: `result` ("pass"/"fail"),
     `duration_s`, `tasks_done` (count of tasks in `result.done`).
2. `planner.json` also gets a `created_at` field (ISO, `time.strftime("%Y-%m-%dT%H:%M:%S")`) —
   belt and suspenders for the headless-plan case, since that file is already the per-plan
   planning record.
3. `stats.py`'s `print_stats` must not crash on the new rows (they have no `result`/`attempts`/
   `tokens` keys): skip `kind in ("review", "plan_event")` in the existing aggregation loop, same
   as it already skips `"review"`. Add one short block printing each slug's latest `run_end` row
   (`slug: last run <ts> -> pass/fail`), sorted by slug.

## T1 log plan_event rows
FILES: .harness/runner/report.py, .harness/runner/cli.py, .harness/runner/planner.py
MUST:
- report.py: add `record_plan_event(metrics_path, slug, event, **extra)` — appends one line to
  `metrics_path` (open "a", same `time.strftime("%Y-%m-%dT%H:%M:%S")` pattern already used by
  `record_metrics`/reviewer.py): `{"ts": ..., "slug": slug, "kind": "plan_event", "event": event,
  **extra}`. No lock needed (single-writer per invocation, same as reviewer.py's write).
- cli.py `_run()`: after `planner.run_planner(...)` returns `lint_ok=True` (the existing
  `args.plan` branch, before `sys.exit(...)`), call `record_plan_event(metrics, args.slug,
  "created", backend=args.planner or "pi")`.
- cli.py `_run()`: right before `with get(args.executor, **opts) as executor:`, capture
  `run_started = time.time()` and call `record_plan_event(metrics, args.slug, "run_start",
  executor=args.executor)`. Import `time` at the top of cli.py.
- cli.py `_run()`: right after `summary, failed = result.summary, result.failed`, call
  `record_plan_event(metrics, args.slug, "run_end", executor=args.executor,
  result=("fail" if failed else "pass"), duration_s=round(time.time() - run_started, 1),
  tasks_done=len(result.done))`. Do this only when tasks actually ran this invocation, i.e. skip
  it when `not result.ran_any` (an all-already-passed rerun) — check `scheduler.run_all`'s result
  object for the right attribute name before wiring this, don't guess.
- planner.py: add `"created_at": time.strftime("%Y-%m-%dT%H:%M:%S")` to the `data` dict written to
  `planner.json` (same file, same time format as the rest of the runner).
TEST: checks/check_t1.py

## T2 stats.py handles the new rows + summary
FILES: .harness/runner/stats.py, .harness/plans/plan-log/SUMMARY.md
MUST:
- `print_stats`: change the existing `if r.get("kind") == "review": continue` guard (in the main
  aggregation loop) to skip `"review"` and `"plan_event"` both.
- After the existing review-rows loop, add one block: collect the latest `run_end` row per slug
  (max by `ts`), print one line each: `f"{slug}: last run {ts} -> {result}"`, sorted by slug. Skip
  entirely (print nothing) if there are none.
- SUMMARY.md <= 600 chars: what was made, which files, how wired.
TEST: checks/check_t2.py
