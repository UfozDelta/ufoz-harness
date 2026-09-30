# Findings: harness-suite, pi vs opencode, cost

Dates: 2026-09-28 to 2026-09-30. All numbers come from single runs (1 rep per cell) unless
stated, so treat small differences as noise.

## TL;DR

- **The harness works end to end.** On the fixed suite, 28 of 29 cells passed across pi,
  opencode, cline, cline-acp and Sonnet. Parallel runs, 3 plans at once (`multi`), the live
  window and worktree isolation all worked.
- **pi is the fastest and cheapest executor when it runs without skills.** It matched Sonnet
  on every size for $0.
- **opencode is not slow because of its architecture alone. Most of the gap is skills.**
  opencode loads about 38 skills into every turn; pi ran with `--no-skills`. With skills on
  for both, opencode was faster in our run (94s vs 158s).
- **Our lean opencode configurations made it slower.** The default opencode prompt suits the
  model better than a stripped one.
- **Cost is dominated by planning, not execution.** Claude (Sonnet) planning cost $1.90 for 3
  plans. Executing them on free or contributor-tier models costs cents.
- **Muse Spark 1.3 Contributor would cost about $0.004 per plan.** Its data is used for
  training, and OpenCode Zen only offers the free variant of it.

## 1. Suite results (clean rep 1, partial: 19 of 34 runs)

| Executor | Passed | Speed | Cost |
|---|---|---|---|
| pi (space-bunny-free) | 8/8 | fastest: multi batch 226s, large parallel 155s | $0 |
| Sonnet (`claude -p`) | 5/5 | multi batch 328s, large serial 284s | ~$0.57/plan |
| opencode (space-bunny-free) | 6/6 | ~2-3x slower than pi | $0 |
| cline-acp | 4/5 | multi batch 920s | $0 |
| cline | 5/5 | slowest, large serial 2059s | $0 |

Token use per executor, summed over the rep:

| Executor | Tokens in / out / cache-read |
|---|---|
| pi | 162k / 37k / 1.5M |
| Sonnet | 263k / 38k / 7.1M |
| opencode | 243k / 34k / 4.2M |
| cline-acp | 11.9M / 166k / 11.7M |
| cline | 11.7M / 273k / 11.1M |

- **Running 3 plans at once:** about 2-3x the throughput of running them one after another.
- **Parallel tasks within a plan:** a modest gain (opencode large: 378s parallel vs 448s serial).
- **Window mode:** worked every time it ran.
- **The only failure:** cline-acp on medium serial passed 25 of 26 hidden tests. That is a
  real miss the hidden tests caught.
- **Extrapolation:** a full rep is about 3.5h and $6 (Sonnet only); 3 reps about 10-11h and $17.

## 2. Why opencode looked slower than pi

The speed test ran both on the same model and found opencode took about 2.5x the wall time,
2x the turns (10 vs 5) and 10x the context (129k vs 13k tokens). Per-turn model latency was
the same for both, and the harness loop adds only milliseconds.

The causes, in order of size:

1. **Skills.** opencode puts about 38 skill descriptions (from `~/.claude/skills`,
   `~/.agents/skills` and the repo) into every turn's prompt. pi runs with `--no-skills`.
2. **More turns, by design.** opencode's edit tool refuses to edit a file the model has not
   read in the same session. Its default prompt also pushes exploring and to-do lists.
3. **Two system prompts.** The executor's rules are appended to opencode's own default prompt,
   not swapped in.

## 3. opencode configuration A/B (space-bunny-free, small + medium, 2 reps)

| Profile | What it changes | Passed | Median time | Median tool calls |
|---|---|---|---|---|
| **default** | nothing | 4/4 | **129s** | **16** |
| tools | denies todowrite, task, websearch, codesearch, list, lsp | 4/4 | 219s | 18 |
| agent | tools + custom executor prompt replacing opencode's default | 4/4 | 336s | 19.5 |

The first-step prompt shrank from 14.3k to 10.6k tokens, but the runs got slower. With less
guidance the model explored more. **Keep the default profile.** The profiles stay available
via `HARNESS_OPENCODE_PROFILE` and default to off.

## 4. pi vs opencode with a Claude plan (1 rep)

Sonnet planned each fixture once ($1.90 total: small $0.36, medium $0.39, large $1.14). Both
executors ran the same plan: pi on `space-bunny-free`, opencode on
`muse-spark-1.3-contributor-free`.

| Size | pi | opencode |
|---|---|---|
| small | 83s, 26/28 hidden tests | 94s, 28/28 ✓ |
| medium | 104s, 26/26 ✓ | 175s, 24/26 |
| large | T1-T8 in ~128s, then T9 hung twice (2157s total), 33/65 | 297s, 34/65 |

- **Tokens:** opencode used about 6x pi's input tokens and 3x the cache-read.
- **Quality:** a tie. On large, both passed only about half the hidden tests because Claude
  planned from the spec without seeing them, so the plan's contract differs from the tests'.
- **pi's T9 hang:** the summary/build task ran into the executor timeout twice, probably on a
  command that never exits.

## 5. Skills: like-for-like check (small, 1 rep, same Claude plan)

| Run | Skills | Time | Hidden tests | Input | Cache-read |
|---|---|---|---|---|---|
| pi | off | 83s | 26/28 | 5.5k | 139k |
| pi | **on** | 158s | 28/28 | 13k | 666k |
| opencode | on | 94s | 28/28 | 29k | 437k |
| opencode | off | crashed: the harness's log folder was deleted mid-run | - | - | - |

- **Skills roughly double pi's time and multiply its cache-read by about 5x.**
- **With skills on, opencode beat pi.** pi likely loads the skill list twice (its own
  discovery plus the folders passed with `--skill`).
- **pi with skills is behind a switch:** `HARNESS_PI_SKILLS=1`. The default is unchanged.
- **The opencode no-skills run needs a rerun,** with the worktree kept to see what deleted
  the log folder.

## 6. Cost reference (OpenCode Zen, per plan)

Estimated for a typical plan (about 18k input, 4k output, 400k cache-read tokens).

| Model | $/plan |
|---|---|
| space-bunny-free, muse-spark-1.3-contributor-free, 30+ other free models | $0 |
| Muse Spark 1.3 Contributor (paid; OpenCode Go / OpenRouter, not on Zen) | ~$0.004 |
| deepseek-v4.1-flash | ~$0.013 |
| gpt-5.1-codex-mini | ~$0.023 |
| Muse Spark 1.3 (paid) | ~$0.10 |
| Claude Sonnet 5 | ~$0.16 |
| Claude Opus 5.5 | ~$0.23 |

- **Contributor tiers use your code for training.**
- **Cache-read is 55-65% of the paid-tier cost,** because the skills prompt is re-read every
  turn. At contributor prices it barely matters.

## 7. Bugs found and fixed along the way

- **Suite scoring:** hidden tests in subfolders were never found (large always scored 0/0).
- **Fixtures:** tasks imported files other tasks write, so they failed in serial order. Seed
  stubs fixed it. Checks then passed on the stubs, so they were fixed again.
- **Tamper check:** false positives on test files the plan requires, and on the suite's own logs.
- **cline/cline-acp:** the pi model in `.env` (`HARNESS_MODEL`) leaked into them. They now
  get pinned models.
- **Cleanup:** worktree folders were left behind (junction links), and `--cleanup` matched
  plan names like `suite-fixes`. It is now limited to real cell names.
- **Harness:** a cp1252 decode crash on UTF-8 tool output; folder entries in FILES; strays in
  parallel runs are now blamed only on the task that wrote them; `--relock-only`; hidden
  tests kept out of suite worktrees; lint follows indirect deps.

## 8. Open items

- Rerun opencode without skills (the crash above).
- Find pi's T9 hang (likely a command that never exits).
- Make pi load skills once, not twice, if pi-with-skills is kept.
- Tighten the large spec so Claude plans match the hidden tests.
- When the suite is stopped, kill child executors (an orphaned `cline.exe` survived).
- The cell timeout may not fire (a 2059s cell ran past the 1800s limit; PC sleep is the
  likely cause).
- Run more reps before trusting any small speed difference.
