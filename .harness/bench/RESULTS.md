## TL;DR
- Recommendation: use K for cost-sensitive runs; it is the cheapest arm, while PURE is fastest.
- The early “Pure Sonnet wins everything” verdict is superseded for cost-sensitive runs by K's cost result.
- K trades some reliability: one run left the build broken, so build-gated tasks matter.

## Arm legend
| Arm | Description |
|---|---|
| A | Opus slim plan, Sonnet builds |
| P | Pure Sonnet session plans and builds |
| C | Opus slim plan, run_plan.py with fresh Muse sessions |
| S1 | Warm relay: one Muse session across the plan |
| S2 | Parallel lanes with disjoint task files |
| S3 | Self-planned Muse with cheap Haiku audit |
| L | Lean verification with Bunny |
| H | Lean verification with Haiku |
| J | Sonnet orchestrator with repo map |
| J0 | Sonnet orchestrator without repo map |
| K | Headless Sonnet planner plus run_plan.py and Bunny |

# Fast-Muse experiment — results

Branch `exp/fast-muse`. Question: which way of building mid/large tasks with the free Muse executor
gives the best cost × time, and does any beat Sonnet (from an Opus plan, or planning itself)?

## Designs (written before building)

**S1 — Warm relay (execution shape).**
Same Opus slim plan as C. The runner opens ONE opencode session for the whole plan and sends each next task
into it (`opencode run --session <id>`), so Muse keeps the codebase and earlier decisions in context.
Every per-task guard stays: red-first, hash lock, files guard, acceptance, one retry (sent into the same session).
Bet: most of C's time is cold starts re-reading plan + code; a warm session skips that.
Risk: context bloat slows later turns; one bad task can poison the session.

**S2 — Parallel lanes (work layout).**
Opus writes a lane plan: tasks grouped into lanes with disjoint files, `deps` only where truly needed, one final
`integrate` task (full build) depending on everything. The runner schedules the task DAG with N workers.
Guard redesign: lint rejects file overlap between tasks with no dep path (so concurrent tasks are disjoint);
a task's allowed files = its own + those owned by tasks running in the same window; anything else fails.
Bet: wall time drops to the longest lane. Risk: free-tier rate limits, integration breakage.

**S3 — Self-planned Muse + cheap audit (planning/verification).**
No Opus. Muse drafts the slim plan (plan.md + tasks.json) from the spec using the same planner rules.
A Haiku auditor (`claude -p --model haiku`) checks spec coverage and acceptance sanity, returning JSON gaps;
Muse revises once. Then `--lint` (Muse fixes once) and normal C execution.
Bet: planning cost falls from ~$1 to ~$0.05 with little quality loss. Risk: Muse plans miss requirements.

## Arms
- **A** — Opus slim plan, Sonnet builds (headless `claude -p`, plan implemented directly).
- **P** — pure Sonnet: one headless session plans and builds from `spec.md`. No Opus, no runner.
- **C** — slim C: Opus slim plan, `run_plan.py`, fresh Muse session per task.
- **S1 / S2 / S3** — above.
A, C and S1 share the SAME Opus plan per (task, rep): one planning run, its cost and minutes charged to each.

**S4 (optional combined) — Muse plans and builds in one warm session.** Not measured: Muse quota ran out first.

**Added during the run (user direction):** executor model `opencode/space-bunny-free` ("Bunny") at effort `medium`
(`-bunny` rows); **L** = lean verification (Opus plan with one-line smoke checks per task, no per-task tests,
one final spec-tests task) built by Bunny in a warm session; **H** = the same lean plan built by Haiku through the
runner (`--executor claude --executor-model haiku`). Muse and all rows without `-bunny` ran at effort `xhigh`.

## Results

All rows: `.harness/bench/data/arms.csv`. Totals include Opus planning (charged to every arm that used the plan),
the executor's own cost (Bunny/Muse $0, Haiku/Sonnet billed) and the Sonnet review pass.

| task | arm | reps | plan $ | build $ | review $ | total $ | plan min | build min | wall min | hidden | retries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| medium | A | 1 | 0.64 | 0.28 | 0.13 | 1.06 | 1.2 | 1.0 | 2.2 | 9/9 | 0 |
| medium | P | 1 | 0.00 | 0.20 | 0.12 | 0.32 | 0.0 | 0.7 | 0.7 | 9/9 | 0 |
| medium | C | 1 | 0.64 | 0.00 | 0.13 | 0.78 | 1.2 | 4.4 | 5.6 | 9/9 | 0 |
| medium | S1 | 1 | 0.64 | 0.00 | 0.15 | 0.80 | 1.2 | 2.4 | 3.6 | 9/9 | 0 |
| medium | S2 | 1 | 0.77 | 0.00 | 0.17 | 0.94 | 2.6 | 4.3 | 6.9 | 9/9 | 0 |
| medium | S3 | 1 | 0.14 | 0.00 | 0.15 | 0.29 | 5.8 | 3.6 | 9.4 | 9/9 | 0 |
| large | A | 2 | 0.65 | 0.39 | 0.13 | 1.17 | 2.3 | 1.1 | 3.4 | 15/15 15/15 | 0 |
| large | P | 2 | 0.00 | 0.28 | 0.13 | 0.40 | 0.0 | 0.7 | 0.7 | 15/15 15/15 | 0 |
| large | C | 2 | 0.65 | 0.00 | 0.15 | 0.80 | 2.3 | 4.3 | 6.6 | 15/15 15/15 | 0 |
| large | S1 | 2 | 0.65 | 0.00 | 0.17 | 0.82 | 2.3 | 3.5 | 5.9 | 15/15 15/15 | 0 |
| large | S2 | 2 | 0.75 | 0.00 | 0.15 | 0.91 | 2.7 | 5.1 | 7.8 | 15/15 15/15 | 0 |
| large | S3 | 2 | 0.08 | 0.00 | 0.15 | 0.23 | 5.0 | 6.1 | 11.1 | 15/15 15/15 | 0 |
| large | S1-bunny | 2 | 0.65 | 0.00 | 0.21 | 0.86 | 2.3 | 2.8 | 5.1 | 15/15 15/15 | 0 |
| large | C-bunny | 2 | 0.65 | 0.00 | 0.17 | 0.82 | 2.3 | 5.5 | 7.8 | 15/15 15/15 | 0 |
| large | S3-bunny | 1 | 0.11 | 0.00 | 0.15 | 0.26 | 1.4 | 2.4 | 3.8 | 15/15 | 0 |
| large | L | 2 | 1.14 | 0.00 | 0.16 | 1.30 | 2.0 | 2.5 | 4.5 | 15/15 15/15 | 0 |
| large | H | 2 | 1.14 | 0.77 | 0.18 | 2.08 | 2.0 | 6.3 | 8.3 | 15/15 15/15 | 0 |
| large_lego | A | 1 | 1.16 | 1.15 | 0.18 | 2.49 | 3.7 | 5.7 | 9.4 | 23/24 | 0 |
| large_lego | P | 1 | 0.00 | 0.63 | 0.20 | 0.83 | 0.0 | 3.7 | 3.7 | 24/24 | 0 |
| crm | A | 2 | 1.64 | 1.43 | 0.16 | 3.24 | 5.3 | 6.0 | 11.3 | 37/37 37/37 | 0 |
| crm | P | 2 | 0.00 | 0.85 | 0.16 | 1.01 | 0.0 | 3.1 | 3.1 | 37/37 37/37 | 0 |
| crm | S1-bunny | 1 | 1.48 | 0.00 | 0.20 | 1.68 | 5.2 | 8.3 | 13.4 | 37/37 | 0 |
| crm | L | 1 | 1.42 | 0.00 | 0.19 | 1.60 | 4.2 | 9.7 | 13.9 | 37/37 | 0 |
| crm | H | 1 | 1.42 | 1.44 | 0.21 | 3.07 | 4.2 | 12.1 | 16.3 | 37/37 | 0 |

**Ranking** (eligible = every rep passed 100% of hidden tests; score = mean total $ x mean wall min)

Caution: arms ran on different task sets (free-model arms mostly on large/crm only), so this cross-task
ranking flatters arms measured only on easy tasks. Compare within a row of the per-task table below.

| arm | eligible | fails | mean total $ | mean wall min | $ x min |
|---|---|---|---|---|---|
| S3-bunny | yes | - | 0.26 | 3.8 | 0.97 |
| P | yes | - | 0.66 | 2.0 | 1.33 |
| S3 | yes | - | 0.25 | 10.5 | 2.65 |
| S1 | yes | - | 0.82 | 5.1 | 4.16 |
| C | yes | - | 0.79 | 6.3 | 5.00 |
| C-bunny | yes | - | 0.82 | 7.8 | 6.34 |
| S2 | yes | - | 0.92 | 7.5 | 6.92 |
| S1-bunny | yes | - | 1.14 | 7.9 | 8.96 |
| L | yes | - | 1.40 | 7.6 | 10.68 |
| H | yes | - | 2.41 | 11.0 | 26.52 |
| A | no | large_lego#1 | 2.06 | 6.8 | 14.07 |

**Per task, $ x min** (mean over reps; * = a rep failed hidden tests)

| task | A | P | C | S1 | S2 | S3 | S1-bunny | C-bunny | S3-bunny | L | H |
|---|---|---|---|---|---|---|---|---|---|---|---|
| medium | 2.29 | 0.23 | 4.35 | 2.87 | 6.52 | 2.71 | - | - | - | - | - |
| large | 4.02 | 0.28 | 5.33 | 4.82 | 7.11 | 2.59 | 4.41 | 6.34 | 0.97 | 5.82 | 17.39 |
| large_lego | 23.49* | 3.04 | - | - | - | - | - | - | - | - | - |
| crm | 36.44 | 3.15 | - | - | - | - | 22.60 | - | - | 22.32 | 49.99 |


## Verdict

- **Pure Sonnet (P) wins cost x time on every task measured**: 0.7-3.7 min, $0.32-1.07, 100% hidden passes.
  No free-model arm beats it on large or crm; the free executor is 5-15x slower and Opus planning alone
  ($0.6-1.8) costs more than P's whole run on medium/large.
- **Harness default (Opus plans -> free model builds, no Claude execution): L, lean + Bunny + warm.**
  On crm it ties S1-bunny (22.3 vs 22.6 $ x min) and builds faster per task; on large it is slightly behind S1-bunny
  (5.8 vs 4.4) because a lean Opus plan costs ~$1.1 vs ~$0.65 for a slim one. Chosen for the lower executor load
  (no per-task tests), with the guards that caught real misbehaviour kept (files guard, lock).
- **Bunny vs Muse** (same plans): ~20% faster build on average, large run-to-run variance (C-bunny 2.7 vs 8.3 min).
  Muse's free tier stopped for ~8 h mid-run ("Rate limit exceeded", retried silently by opencode).
- **Warm session (S1)** ~15-20% faster than fresh sessions. **Parallel lanes (S2)** gave nothing: these tasks
  share one router file, so the lane planner had to chain everything.
- **Haiku as executor (H)** is the worst free-model-harness option: slower and $0.74-1.44 per build, and it wrote
  files outside its bench copy (`tests/test_spec.py`, `app/`, `check-t5.js` in the repo root; removed).
- **S3 (builder plans itself)** is cheapest ($0.23-0.29) and with Bunny beat everything but P on large (0.97 $ x min),
  but was ruled out: the design is main session -> Opus planner -> free builder.

## Failures and discarded rows

Discarded (harness/infra, listed in `data/discarded.csv`, not in the tables):
- `large_lego C/S1/S2 #1`: Muse rate-limited, opencode hung silently until the 900 s timeout (0 tokens).
- `crm C #1`: ran concurrently with another Muse run (a stopped driver kept running on Windows), 0/37.
Real failures kept: `large_lego A #1` 23/24 (Sonnet's own test file contains "stripe"; hidden test bans the word).
Not measured (quota): Muse C/S1/S2/S3 on large_lego and crm, all S4.

Harness bugs found and fixed on the way: slim plans had no `items/` dir (runner crashed writing reports);
`node --test a b` skips a missing file (red-first passed early); `-k` on a shared test file (red-first passed early);
parallel `opencode run` -> "database is locked" (one shared `opencode serve`); `capture_output`+timeout hangs on
Windows (probe via temp file + tree kill); timeouts never retried (now one fresh retry); rate limits hung runs
(now detected, waited out, retried uncounted); `%` in argparse help crashed the runner.

## Next ideas

1. ~~Sonnet as planner~~: done in the shop run (~$0.23 per stage plan); Pure Sonnet still wins.
2. Try Pi (lighter agent) with the same Zen models to measure how much time is opencode's client/server overhead.
3. Isolate the H/claude executor (`CLAUDE_PROJECT_DIR`, `--add-dir`) before any further Claude-executor benches.
4. More reps: free-pool speed varies 3x run to run; 2 reps is not enough for close calls (L vs S1-bunny).

## Long-range staged run: shop (2026-09-23/24)

Question: over a long, multi-stage build, does one Sonnet session's growing context cost more than the harness
(which keeps code out of Claude's context)? And does a persistent repo map save the planner from re-exploring?

Task `tasks/shop/`: Next.js dropshipping store "Nimbus Goods" in 6 stages that build on each other
(landing -> catalog -> mock payment -> contact form -> cart -> admin sales board). 59 hidden HTTP tests; after stage N,
tests s1..sN run to catch regressions. Driver: `staged.py` (one persistent Claude session per arm via `--resume`).
Rows: `data/stages.csv` (one per arm x stage).

Arms (all Claude = Sonnet; 1 rep each):
- **PURE**: one Sonnet session builds every stage itself.
- **J0**: Sonnet orchestrator (one session) -> new Sonnet `@planner` per stage -> `run_plan.py` + Bunny -> orchestrator verifies.
- **J**: J0 plus the repo map (`.harness/build_map.py` -> `.harness/context/REPO_MAP.md`): planner reads it first,
  orchestrator regenerates it and adds 3-5 Notes lines after each stage.

| arm | total $ | total min | hidden (final) | orchestrator $ | planner $ | ctx at end (tokens) |
|---|---|---|---|---|---|---|
| **PURE** | **2.70** | **10.2** | 59/59 | 2.70 | - | 165k |
| J0 | 3.05 | 40.1 | 59/59 | 1.70 | 1.35 | 139k |
| J | 3.57 | 44.5 | 59/59 | 2.20 | 1.36 | 139k |

Per stage, $ (s1..s6): PURE 0.30 0.37 0.31 0.42 0.79 0.51 | J0 0.40 0.38 0.43 0.46 0.81 0.57 | J 0.43 0.46 0.50 0.42 1.10 0.66.
Per stage, min: PURE 1.1-2.9 | J0 4.6-9.2 | J 4.1-12.1. No compactions in any arm; 0 executor retries.

Findings:
- **PURE wins again, on both cost and time**: 1.1-1.3x cheaper and ~4x faster. Its context doubled (83k -> 165k)
  but cache reads (8.3M tokens at 0.1x price) kept per-stage cost flat; no cost crossover within 6 stages.
- **The orchestrator is not lean**: it starts at ~66k tokens (system prompt, tools, plugins) and grows to ~139k
  from reports and diffs. It costs more than the planner.
- **The repo map does not pay off at this size**: planner cost unchanged ($1.36 vs $1.35), planner cache reads
  -20% (1.71M vs 2.16M), but map upkeep in the verify step adds ~$0.50 of orchestrator cost.
- The free executor was reliable (every task passed on its first attempt), but still dominates wall time.

Scoring notes:
- 2 hidden-test bugs were found and fixed in `conftest.call` after the runs; every arm's final code was rescored
  (59/59 each). The per-stage counts in `stages.csv` are pre-fix: (1) Next 16 streams `notFound()` UI only inside the
  escaped RSC payload, so `data-testid="not-found"` never appears as markup; (2) React splits `${price}` in JSX into
  `$<!-- -->29.99`. Both failed correct builds (PURE 1 test, J/J0 2-3 tests from stage 2 on).
- J ran as rep 2: rep 1's folder could not be deleted (read-only git objects of the smoke run, on Windows).
- J hit the Claude plan's session usage limit during stage 4's verify step. Stage 4 has no verify (no map notes,
  ctx not recorded); stages 5-6 were rerun with `--continue` after the reset, in the same session.

## Contract plan, headless planner: shop x3 (2026-09-24)

Question: does a short contract plan, a headless planner (no orchestrator session) and no spec tests (Bunny
writes a <= 600-char `SUMMARY.md` instead) make the harness beat one Sonnet session?

Setup changes vs the run above: every bench Claude call runs with `--setting-sources project,local
--strict-mcp-config` (no user plugins, hooks or MCP; saves ~10k tokens/call, ~40k is fixed Claude Code base);
arm prompts state caveman prose explicitly. J0 keeps the old planner (commit `1587d23`). New arm:
- **K**: per stage `claude -p` Sonnet with the planner prompt appended (no orchestrator) -> `run_plan.py` + Bunny
  -> scripted verify (rerun `run_plan.py` once on failure, no Claude call).

Rows: `data/stages.csv` (arm x rep x stage) and `data/steps.csv` (every step: plan, T<n>.exec/accept/retry, rerun).
K reps 1-2 are 2-stage smoke runs, excluded below.

| arm | reps | $ per rep | mean $ | min per rep | mean min | hidden (final) |
|---|---|---|---|---|---|---|
| **K** | 3-5 | 1.42 / 1.95 / 1.61 | **1.66** | 25.2 / 31.6 / 31.1 | 29.3 | 59, **build broken**, 59 |
| PURE | 1-3 | 4.88 / 3.65 / 3.80 | 4.11 | 14.2 / 12.2 / 11.5 | **12.6** | 59, 59, 59 |
| J0 | 1-3 | 7.23 / 5.62 / 5.24 | 6.03 | 77.7 / 54.1 / 52.1 | 61.3 | 59, 59, 58 |

K per rep, by step: plan 9.7 min / $1.66 (all its Claude cost); Bunny exec 15.7 min; acceptance 1.7 min;
retries 1.4 min; reruns 1.6 min. Planner output averages 9.1k tokens/stage although plan.md is ~1-1.3k tokens:
the cap shrank the plan, not the planner's reasoning.

Findings:
- **K is the cheapest arm by far**: ~2.5x cheaper than PURE, ~3.6x cheaper than J0. Dropping the orchestrator
  removed about half of J0's cost, as predicted.
- **PURE is still fastest** (~2.3x faster than K). K's time is mostly Bunny (16 of 29 min), then planning (10 min).
- **K is less reliable**: in rep 4, stage 5 broke `npm run build` and stage 6 never fixed it (0 hidden tests
  scored). K rep 3 had the same break at stage 5 but stage 6 repaired it. Cause: build tasks' smoke checks import
  `.ts` files through `node --experimental-strip-types`, so Bunny wrote `.ts` extension imports with `@ts-ignore`,
  which Turbopack rejects. The full build only runs in the last (SUMMARY) task, whose FILES allow only SUMMARY.md,
  so neither the retry nor the scripted rerun can fix it and the next stage starts on a broken build.
- **Baselines cost more than in the 1-rep run above** (PURE $2.70 -> $4.11 mean, J0 $3.05 -> $6.03) with similar end
  context. Not yet explained: 1-rep variance, the setting-sources change, or the two chains running at once.

Fixes to try next: run `npm run build` (or `tsc --noEmit`) in the acceptance of every task that touches app code;
forbid node-import smoke checks of `.ts` files in Next.js projects; let the scripted verify give a build failure
to Bunny with the stage's app files in scope.
