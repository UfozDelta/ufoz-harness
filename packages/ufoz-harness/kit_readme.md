# harness

A plan/execute harness for Claude Code. Claude plans and reviews; one of six
executors writes the code; a Python runner checks every task with shell commands,
so no model decides whether work passed. The main session never writes code for
delegable work, which keeps its context small and the bill low.

Executors: `pi` (default, Bunny `opencode/space-bunny-free`, one warm session per
plan, $0), `opencode` (warm `opencode serve`, also free on Bunny), `claude` (bills
you; for comparisons), `cline` and `cline-acp` (Cline CLI, headless, `cline-acp`
keeps one warm process per plan), and `llama` (pi against a local `llama-server`
you start). Pick one with `--executor <name>`; the others are optional.

## How it works

```
main session (Claude)          decides with you, approves plans, reviews results
   │
   ▼
@planner (sonnet subagent)     explores (Bash for inspection only), writes the plan,
   │                           runs --lint itself, lists Verified/Unverified facts
   ▼
.harness/plans/<slug>/         plan.md (Decisions + one `## T<n>` section per task:
   │                           FILES / MUST / TEST) and tasks.json. No brief files.
   │
   ▼
python .harness/run_plan.py <slug>
   │  first run: hashes tasks.json (+ checks/ if any) into plan.lock.json
   │  per task, in order:
   │    lock unchanged?            else RESULT: lock-mismatch
   │    test fails before work?    else RESULT: check-invalid (the test proves nothing)
   │    the executor session does its plan.md section (tests only in the last task)
   │    runner runs the acceptance command itself
   │    file touched outside the task's `files`?  → fail
   │    plain failure → one retry with items/T<n>.feedback.md
   │    writes items/T<n>.report.md (result, seconds, tokens, cost)
   │  --review: one Sonnet pass over touched files → REVIEW.md
   ▼
you read the reports and the diff. Nobody in this chain commits.
```

## Using it

1. **Decide.** Agree on scope and success criteria with Claude.
2. **Plan.** Claude writes a small plan itself or calls `@planner` for larger work.
   Plans are lean: one `plan.md` with a `## T<n>` section per task (FILES, 2-5 MUST
   bullets, TEST command) plus a short `tasks.json`. Rules every plan follows:
   - Build tasks write no tests. Acceptance is a one-line smoke command that proves the
     task landed (`python -c "..."`, `node -e "..."`, `npx tsc --noEmit`), with
     `"red_first": false, "red_first_reason": "lean smoke check"`.
   - The last task writes one spec test file covering every MUST and runs it with the
     build. Its file doesn't exist yet, so red-first stays on for it.
   - `files` lists every file the task may touch, including generated ones.
   - Side-effect wiring (analytics, storage writes, events) gets an "exactly once" MUST.
   - A `checks/check_t<n>.py` script only where no test runner fits (packaging, CLI
     end-to-end); see `.harness/CHECK_PATTERNS.md`. Old plans with `items/T<n>.md`
     briefs still run.
3. **Approve.** `python .harness/run_plan.py <slug> --lint` must print `lint OK`. Check
   the plan's `Unverified:` list, then say go.
4. **Execute.** `python .harness/run_plan.py <slug>` (run it in the background from
   Claude Code; it can take minutes). After your go, Claude keeps going on its own and
   stops only on a second failure of the same task, a destructive step, or a design
   question.
5. **Verify.** Claude reads the reports and the diff and reruns checks itself.
6. **Report.** Claude ends with `Blocked on me:` / `Changed:` / `Found:`.

### Results and what to do

| Result | Meaning | Next step |
|---|---|---|
| `pass` | check passed, only listed files touched | review the diff |
| `fail` | check failed, executor error, or out-of-scope file | fix the brief, rerun (passed tasks are skipped) |
| `check-invalid` | the acceptance passed before any work | tighten the test or acceptance |
| `running` | a runner was interrupted mid-task | rerun; red-first is skipped for it |
| `lock-mismatch` | tasks.json or a check changed after the first run | your edit: rerun with `--relock`; the executor's: discard it |

### Runner flags

| Flag | Does |
|---|---|
| `--lint` | validate the plan, prove every acceptance fails, check the runner can write reports; runs nothing else |
| `--only T2` | run one task |
| `--retries N` | executor reruns on a plain failure (default 1) |
| `--review` | cheap Sonnet review pass after a fresh full run → `REVIEW.md` |
| `--relock` | re-record the check hashes after you edited a check |
| `--executor pi\|opencode\|claude\|cline\|cline-acp\|llama` | which executor writes the code (default pi) |
| `--stats` | cost and time totals (see below) |
| `--timeout S` | per-task executor timeout, default 900 |

## Test and measure

- `python .harness/selftest.py`: checks python, git, pi and the executor model,
  then runs a one-task smoke plan in a throwaway temp repo. $0; never touches this
  project.
- `python .harness/selftest.py --bench`: fair A/B comparison. `@planner` plans once,
  then the same plan runs with the pi executor and with a Claude (Sonnet)
  executor, both with `--review`. Only who writes the code differs. Rows go to
  `.harness/bench.csv`. About $0.50 per run; run it only when you want numbers.
  Historical opencode benchmark: 1-function task, opencode $0.32 total, Claude $0.56 total (planning
  $0.20 and review $0.12 in both; execution $0 vs $0.25).
- Lab bench (`.harness/bench/RESULTS.md` in the lab repo): lean plan + Bunny + warm session
  passed 15/15 and 37/37 hidden tests; build ~2.5 min on a 6-endpoint API and ~10 min on a
  Next.js CRM, $0 executor. Honest caveat: a single Sonnet session was faster and about as
  cheap on every task measured; this harness is for keeping Claude out of execution.
- `python .harness/run_plan.py --stats`: per plan, executor time/tokens/cost from
  `.harness/metrics.jsonl`, `--review` cost (exact), and planner/reviewer usage read
  from Claude Code's own logs (estimated dollars). The main session's own
  tokens are not included.

## Settings

Copy `.harness/.env.example` to `.harness/.env` (gitignored) and uncomment what you
want to change; a real env var in your shell wins over the file. `HARNESS_MODEL`
overrides the executor model, `HARNESS_PI` the path to pi, `HARNESS_LLAMA_URL` the
`llama-server` router.

## Guardrails

- The executor (`.pi/executor.md` with the `.pi/deny.json` deny list) is denied git state commands and runs
  with the rules in `AGENTS.md`: only the brief's files, never `.harness/`, finish
  with `DONE:` or `BLOCKED:`.
- `.claude/settings.json` denies `git add/commit/push/reset/checkout/stash/clean/rebase`
  for Claude too. You commit from your own terminal.
- Claude's own reports are never taken as proof; reports come from the runner.

## Files

```
CLAUDE.md                    main-session rules and the plan → execute loop
AGENTS.md                    executor rules (~10 lines on purpose; add a line only when a failure earns it)
.claude/settings.json        allow the runner; deny git state changes
.claude/agents/planner.md    plan writer (sonnet)
.claude/agents/reviewer.md   post-run checklist reviewer (sonnet), used by --review
.claude/skills/              caveman, adhd, animation/design skills
.pi/executor.md               pi executor (`opencode/space-bunny-free`, free)
.pi/deny.json                 pi deny list
.pi/extensions/deny-list.ts   pi deny-list extension
.pi/extensions/deny-match.ts  pi deny matcher
.harness/run_plan.py         the runner (shim over .harness/runner/)
.harness/runner/             the runner package: executors, guards, planner, metrics
.harness/build_map.py        builds the repo map the planner reads
.harness/MAIN.md             backend-neutral plan → execute loop, for non-Claude mains
.harness/selftest.py         doctor, smoke test, --bench
.harness/.env.example        settings template (copy to .harness/.env)
.harness/CHECK_PATTERNS.md   check-script shapes, for the rare task no test runner fits
.harness/plans/<slug>/       one plan: plan.md, tasks.json, plan.lock.json, items/ (reports), logs/, REVIEW.md
.harness/metrics.jsonl       per-task metrics (gitignored)
.harness/bench.csv           --bench results (gitignored)
```

## Requirements

- Claude Code, Python 3 (stdlib only), git.
- pi installed with its `~/.pi/agent/bin/pi-launcher.js` (or `pi` on PATH), using the free
  `opencode/space-bunny-free` model. Override per run with `HARNESS_MODEL=provider/model`.
- Optional, only for the executor you pick: opencode on PATH, the claude CLI, the
  Cline CLI (`npm i -g cline`), or llama.cpp plus a `llama-server` you start.
