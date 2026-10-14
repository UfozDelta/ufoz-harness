<div align="center">

<img src="docs/hero.svg" alt="ufoz-harness: Claude plans, a cheap executor (pi, opencode or Haiku) writes the code, a runner checks every task" width="100%">

![executor cost](https://img.shields.io/badge/executor-%240-1f7a45)
![main session](https://img.shields.io/badge/main%20session-Claude%20%7C%20pi%20%7C%20opencode-1f6f5c)
![executors](https://img.shields.io/badge/executors-6-5d6864)
![python](https://img.shields.io/badge/python-3%20stdlib%20only-5d6864)

[Why](#why) · [Quick start](#quick-start) · [Run modes](#run-modes) · [How it works](#how-it-works) · [Flags](#runner-flags) · [Architecture](docs/ARCHITECTURE.md)

</div>

A plan/execute harness: a main session (Claude Code, or pi / opencode) plans and reviews, a cheap
executor writes the code, and a Python runner checks every task with shell commands, so no model
decides whether work passed.

This repo is the lab where the harness is built and tested (`CLAUDE.md`, agents, skills,
`run_plan.py`, `selftest.py`, benchmarks). `packages/ufoz-harness` ships it to other projects
(`npx ufoz-harness`).

## Why

Coding agents are expensive when the smart model types every line, and unreliable when the same
model decides its own work is done. The harness splits those jobs.

- **No model grades its own work.** A Python runner runs each task's acceptance command, hashes
  the file tree, and writes the verdict. An executor's "done" is ignored.
- **The expensive model only thinks.** Claude (or any main session) plans and reviews; a free
  model writes the code. On the staged benchmark that cut the bill 2–3x.
- **Mistakes stay contained.** Each run gets its own git worktree, a task that touches a file
  outside its list fails, and no agent can commit. You land the result with one command.
- **Nothing is locked in.** Three main sessions (Claude Code, pi, opencode), five runner
  executors, plus a native in-Claude executor (`@claude-executor`, Haiku by default), all behind
  the same brief and the same checks.

<img src="docs/bench-cost.svg" alt="Staged shop bench: pure Sonnet $3.39 in 13.6 min, harness + opencode $1.18 in 22.1 min, harness + pi $1.47 in 26.4 min" width="100%">

The trade-off is time: a free model is slower, so a run takes longer than one Sonnet session.
More runs in [Test and measure](#test-and-measure).

## Quick start

```
python .harness/selftest.py                          # checks the setup, one $0 smoke task
cp .harness/.env.example .harness/.env               # optional: pick planner, models
claude                                               # or pi / opencode, see below
# describe the task, approve the plan, then:
python .harness/run_plan.py <slug> --land            # bring the finished run into your tree
```

The main session writes the plan, runs `run_plan.py <slug>` after your go, and reviews the
reports. You review the diff and commit. See [Requirements](#requirements) for what to install.

## Run modes

Two ways to run the same plan. The plan, the acceptance commands and the rule that nobody
commits are identical; what differs is who types the code and who enforces the guards.

### Claude mode

<img src="docs/mode-claude.svg" alt="Claude mode: Decide, Plan with @planner, Execute with @claude-executor, Check by rerunning --executor agent:haiku, Land with --land" width="100%">

Stay inside Claude Code. After your go, `run_plan.py <slug> --executor agent:haiku` creates the same worktree the
runner would use (`.worktrees/<slug>`, a snapshot of your tree with the plan files copied in), then
the main session spawns the `claude-executor` subagent (`.claude/agents/claude-executor.md`) in the
background so it shows up in the agents panel. It defaults to Haiku; pass `model: sonnet` or
`model: opus` for harder work. It edits only each task's `files` inside that worktree, runs each acceptance command, and retries
once. That first call also records a baseline of your main tree, so the second call fails (`MAIN <path>`) if
the agent wrote anything outside its worktree or moved HEAD. A hook in the agent file also blocks
this, but Claude Code does not always load agent hooks, so the second call is the guarantee.

```
python .harness/run_plan.py <slug> --executor agent:haiku   # call 1: worktree: <abs path> + handoff; runs nothing
python .harness/run_plan.py <slug> --executor agent:haiku   # call 2, after the agent: grade it, report, commit
python .harness/run_plan.py <slug> --land                   # you: the same land as runner mode
```

Trade-off: the runner is not driving, so there is no automatic retry-with-feedback or repair pass.
Call 2 applies the lock, scope and acceptance checks afterwards, writes the same `items/T<n>.report.md`,
commits each passing task and skips tasks that already passed.

### Runner mode (pi / opencode)

<img src="docs/mode-runner.svg" alt="Runner mode: Decide with Claude, pi or opencode, Plan, Execute with pi or opencode, Check with retry and repair, Land" width="100%">

`run_plan.py <slug>` drives a free executor (pi by default, or `--executor opencode`) in its own
`.worktrees/<slug>`. The runner does the checking: lock, scope, suppression guard, one retry with
feedback, one repair pass. The main session can be Claude, pi or opencode. This is the mode the
benchmarks measure, and the cheapest.

```
python .harness/run_plan.py <slug>            # pi; add --executor opencode
python .harness/run_plan.py <slug> --land     # you
```

## How it works

![Harness data flow](docs/harness-flow.svg)

Only the main session changes between Claude Code, pi and opencode. More diagrams (open the
`.html` files in a browser; GitHub shows them as source):
[session-flows.html](docs/session-flows.html) (terminal to `--land` per main session),
[flows.html](docs/flows.html) (every path in `docs/FLOWS.md`), [mermaid.md](docs/mermaid.md).

<details>
<summary>Step by step</summary>

```
main session (Claude)          decides with you, approves plans, reviews results
   │
   ▼
@planner (sonnet subagent)     explores (Bash for inspection only), writes the plan,
   │                           runs --lint itself, lists Verified/Unverified facts
   ▼
.harness/plans/<slug>/         plan.md (Decisions + one ## T<n> per task), tasks.json; checks/ only if no smoke fits
   │
   ▼
python .harness/run_plan.py <slug>
   │  runs in its own worktree .worktrees/<slug>, one run.lock per plan
   │  first run: hashes tasks.json + checks/ into plan.lock.json
   │  per task, in order:
   │    lock unchanged?            else RESULT: lock-mismatch
   │    check fails before work?   else RESULT: check-invalid (the check proves nothing)
   │    executor (pi / opencode / claude / llama) does the brief
   │    runner runs the check itself
   │    file touched outside the task's `files`?  → fail
   │    new @ts-ignore / @ts-nocheck / eslint-disable line?  → fail
   │    plain failure → one retry with items/T<n>.feedback.md
   │    still failing → one repair pass: error + files of this and all earlier tasks
   │  last task writes SUMMARY.md (<= 600 chars) and a BUILD: pass/fail line
   │    writes items/T<n>.report.md (result, seconds, tokens, cost)
   │  --review: one Sonnet pass over touched files → REVIEW.md
   ▼
you read the reports and the diff, then run --land. Nobody in this chain commits.
```

</details>

### Using it

1. **Decide.** Agree on scope and success criteria with Claude.
2. **Plan.** Claude writes a small plan itself or calls `@planner` for larger work. Every plan
   is a contract plan, <= ~1.5k tokens:
   - Each task's acceptance is one cheap smoke command that exits 0 only when the task landed
     (`python -c ...`, `node -e ...`, plus `npx tsc --noEmit --incremental --tsBuildInfoFile .harness/tsc.tsbuildinfo`
     for TS tasks with TypeScript files). No full builds.
   - Never smoke-check `.ts` files by importing them through node: it leads the executor to
     `.ts`-extension imports that bundlers reject.
   - Red-first is off by default, so lean smoke checks skip the prove-it-fails-first step
     (see docs/ARCHITECTURE.md); opt a task in with `"red_first": true`.
   - `files` lists every file the task may touch, including generated ones.
   - The last task writes `SUMMARY.md`, runs the build if any and records `BUILD: pass` or
     `BUILD: fail <error>`; the build never fails the task.
   - Side-effect wiring (analytics, storage writes, events) gets an "exactly once" check; see
     `.harness/CHECK_PATTERNS.md`.
3. **Approve.** `python .harness/run_plan.py <slug> --lint` must print `lint OK`. Check the
   plan's `Unverified:` list, then say go.
4. **Execute.** `python .harness/run_plan.py <slug>` (in the background from Claude Code; it can
   take minutes). After your go, Claude keeps going and stops only on a second failure of the
   same task, a destructive step, or a design question.
5. **Verify.** Claude reads the reports and the diff and reruns checks itself.
6. **Report.** Claude ends with `Blocked on me:` / `Changed:` / `Found:`.

### Results and what to do

| Result | Meaning | Next step |
|---|---|---|
| `pass` | check passed, only listed files touched (summary says `REPAIRED` if a repair pass fixed it) | review the diff |
| `fail` | check failed, executor error, out-of-scope file, or a new suppression comment | fix the brief, rerun (passed tasks are skipped) |
| `check-invalid` | the check passed before any work | tighten the check |
| `lock-mismatch` | tasks.json or a check changed after the first run | your edit: rerun with `--relock-only`; the executor's: discard it |

## Runner flags

| Flag | Does |
|---|---|
| `--land` | your command, not the agent's: apply a finished worktree run here, copy its plan records, remove the worktree and branch ([details](#landing-a-finished-run---land)) |
| `--lint` | validate the plan and prove every check fails; runs nothing else |
| `--only T2` | run one task |
| `--review [claude[:MODEL]]` | cheap review pass after a fresh full run → `REVIEW.md` (claude only, bare = sonnet; slug goes before it) |
| `--relock-only` | re-record the check hashes after you edited a check; runs nothing |
| `--status` | task states, the first failure's tail and the next command; runs nothing |
| `--pending` | list worktrees not landed yet; runs nothing |
| `--no-window` | a real run opens a shared Windows Terminal window with a live tab (Windows only, on by default; this or `HARNESS_WINDOW=0` opts out) |
| `--executor BACKEND[:MODEL]` | which executor writes the code, with an optional model: pi, opencode, claude, llama, or `agent:haiku` (the `@claude-executor` agent; run twice, see Claude mode). Default pi; see [Executors](#executors) and [Requirements](#requirements) |
| `--stats` | cost and time totals (see [Test and measure](#test-and-measure)) |
| `--timeout S` | per-task executor timeout, default 900 |
| `--fresh` | a new executor session per task instead of one warm session for the plan |
| `--session ID` | continue an existing executor session (refused with `--fresh` or `--parallel > 1`) |
| `--plan SPEC.md` | have the planner backend write and lint the plan for `<slug>`; runs no tasks ([details](#main-session-without-claude)) |
| `--planner BACKEND[:MODEL]` | planner backend and model for `--plan` (default `HARNESS_PLANNER` / `HARNESS_PLANNER_MODEL`, else pi) |
| `--parallel N` | run up to N tasks at once (DAG scheduler, no shared files); refused for `llama` (one local model slot, not thread-safe) |
| `--no-worktree` | run in place instead of in its own git worktree (the worktree is the default for a real run; `HARNESS_WORKTREE=0` opts out globally) |

## Executors

All four runner executors follow the same brief and guards; pick one with `--executor <name>`.
pi, opencode and claude keep one warm session per plan (llama too, since it is pi underneath). The main
session never writes code for delegable work, which keeps its context small and the bill low.

- **pi** (default): writes code with Bunny (`opencode/space-bunny-free`, an OpenCode Zen model),
  so a run is free.
- **opencode**: one warm `opencode serve` per run over HTTP+SSE, also free on Bunny.
- **claude**: `claude -p` per task; bills you; for comparisons. `--executor claude:<model>` defaults to
  sonnet (pi and opencode honor that flag too, each with its own default).

<details>
<summary>llama details</summary>

- **llama**: pi against a local GGUF served by a llama.cpp `llama-server` in router mode that you
  start yourself. `HARNESS_LLAMA_MODEL` picks the model (default: the only one the server lists)
  and `HARNESS_LLAMA_URL` the server (default `http://127.0.0.1:8080`). Pi's built-in llama.cpp
  provider needs an interactive `/login`, so the executor writes its own `models.json` into a
  throwaway `PI_CODING_AGENT_DIR`; your `~/.pi/agent` is never touched. Free, offline, warm
  session, but only as good as the local model.

</details>

`docs/ARCHITECTURE.md` explains the internals: guard order, repair scope, executor invocation,
metrics. Read both before changing harness internals.

## Worktrees and the live window

A real run (`run_plan.py <slug>`, no `--lint`/`--plan`/`--stats`) happens in its own git
worktree at `.worktrees/<slug>` on branch `harness/<slug>`, so several plans can run at once, and
opens a shared Windows Terminal window with a tab per plan. **The tree must be clean** (no unstaged
changes or untracked files outside `.gitignore`); if not, `worktree.ensure()` refuses with a message
naming the dirty paths and exits. Opt out per run with `--no-worktree` / `--no-window`, or globally
with `HARNESS_WORKTREE=0` / `HARNESS_WINDOW=0`. Outside a git repo the run stays in place
(`not a git repo: running in place`).

<details>
<summary>What the worktree contains</summary>

The plan's own files are copied into the worktree, so its reports, logs and `SUMMARY.md` live in
`.worktrees/<slug>/.harness/plans/<slug>/` (the copy in your main tree stays as the source). The
base is the current HEAD: the worktree branch `harness/<slug>` starts at HEAD and all downstream
commits are real git. Your index, HEAD and branches stay untouched. `.worktrees/` goes into
`.git/info/exclude` (local, no tracked file changes), and shared, gitignored dirs
(`node_modules`, `.venv`, `.opencode/node_modules`) are junctioned into the worktree, not copied.

</details>

Nobody commits. When the run is done, review the diff and merge or discard by hand:

```
git -C .worktrees/<slug> diff        # what the run changed
git worktree remove .worktrees/<slug>
```

### Landing a finished run: `--land`

`python .harness/run_plan.py <slug> --land` brings a finished run into the main tree using a
fast-forward merge. In order it:

1. checks that `.worktrees/<slug>` is a real worktree and no run is in progress (no `run.lock`),
2. copies the plan's records (reports, logs, `SUMMARY.md`) into `.harness/plans/<slug>/`,
3. `git merge --ff-only harness/<slug>` to fast-forward your HEAD to the branch tip: on success
   the merged commits are now in your tree; on failure (your main tree moved after the plan started),
   nothing changes, the worktree and branch stay, and you can rebase the worktree or resolve by hand,
4. removes the shared-dir junctions (never their targets), the worktree and the branch
   `harness/<slug>`, then prints `landed <slug>: <n> files`.

The agent never runs `--land`; you do, once you are happy with the diff.

## Main session without Claude

`.harness/MAIN.md` holds the same plan → execute loop, backend-neutral. Start it directly, no
wrapper script:

- **pi**: `pi --no-context-files --append-system-prompt .harness/MAIN.md --model opencode/space-bunny-free`
  (`--no-context-files` keeps the executor's `AGENTS.md` out of the main session). On PowerShell
  `~` doesn't expand, so if `pi` isn't on PATH use the full path:
  `node "$env:USERPROFILE\.pi\agent\bin\pi-launcher.js" ...` (bash: `node ~/.pi/agent/bin/pi-launcher.js ...`).
- **opencode**: `opencode --agent orchestrator`; the repo's `opencode.json` defines that agent
  with `MAIN.md` as its prompt.

Planning is a command, not a subagent: write a spec file, then

```
python .harness/run_plan.py <slug> --plan <spec.md>
```

It runs `runner/planner.py` only, which asks the planner backend for
`.harness/plans/<slug>/plan.md` + `tasks.json`, lints them (retrying the same session twice with
the lint output as feedback), writes `planner.json`, and exits 0 iff the plan lints. No tasks run;
execute later with `python .harness/run_plan.py <slug>`.

Under Claude Code the main session follows `CLAUDE.md` and plans with `@planner`
(`.claude/agents/planner.md`); `--plan` reuses that file's layout and rules.

## Configuration

Copy `.harness/.env.example` to `.harness/.env` (gitignored) and uncomment what you want to
change. A real env var already set in your shell always wins over the same key in that file.

<details>
<summary>All environment variables</summary>

| Var | Default | Effect |
|---|---|---|
| `HARNESS_PLANNER` | `pi` | planner backend for `--plan`: `pi`, `opencode` or `claude` |
| `HARNESS_PLANNER_MODEL` | unset | model for the planner backend; falls back to sonnet for claude, else the backend's own default |
| `HARNESS_MODEL` | `opencode/space-bunny-free` | executor model for pi and opencode |
| `HARNESS_PI` | unset | path to pi; falls back to `~/.pi/agent/bin/pi-launcher.js` |
| `HARNESS_VARIANT` | `medium` | reasoning effort for every executor (pi `--thinking`, opencode `variant`, claude `--effort`) |
| `HARNESS_WORKTREE` | on | `0` runs every plan in place instead of in `.worktrees/<slug>` |
| `HARNESS_WINDOW` | on | `0` skips the live Windows Terminal window |
| `HARNESS_RUNNER_FLAGS` | empty | bench only: extra flags appended to `run_plan.py` |
| `HARNESS_ARM_LABEL` | unset | bench only: cosmetic arm label written into the results csv |
| `HARNESS_LLAMA_URL` | `http://127.0.0.1:8080` | llama executor: the `llama-server` router to attach to |
| `HARNESS_LLAMA_MODEL` | unset | llama executor: router model id; unset = the only model the router lists |

</details>

## Test and measure

<img src="docs/bench-flow.svg" alt="Benchmark cell flow: Seed, Project, Plan, Run, Land, Score" width="100%">

`bench/suite/suite.py` runs a matrix of executor x size x mode x rep. Each cell is an isolated temp
project (committed seed, kit installed, plan at the root), run and landed like a real user's work,
then scored on hidden tests, the seed's own tests and a tamper diff. `--plan-source planner` has
`@planner` write the plan instead of using the fixture's; `--legacy` keeps the old lab-worktree path.

- `python .harness/selftest.py`: checks python, git, pi and the executor model, then runs a
  one-task smoke plan in a throwaway temp repo. $0; never touches this project.
- `python .harness/selftest.py --bench`: fair A/B. `@planner` plans once, then the same plan runs
  with the pi executor and with a Claude (Sonnet) executor, both with `--review`; only who writes
  the code differs. Rows go to `.harness/bench.csv`. About $0.50 per run.
- `python .harness/run_plan.py --stats`: per plan, executor time/tokens/cost from
  `.harness/metrics.jsonl`, `--review` cost (exact), and planner/reviewer/validator usage read
  from Claude Code's own logs (estimated dollars). The main session's own tokens are not included.

<details>
<summary>Benchmark details and results</summary>

- `bench/speed/`: `duel.py` compares opencode and pi on the same model and hidden tests,
  then `report.py` writes `RESULTS.md` from `results.csv`. `bench.py` copies the current on-disk
  tree (`git ls-files -co --exclude-standard`, skipping deleted files and `bench/speed/`), not
  HEAD, and `staged.py` honors `HARNESS_ARM_LABEL`. Across 9 small/medium/large runs each, both
  passed 100%; pi's median was 15 s versus 38 s, with about 10x fewer input tokens and half the
  tool calls. That is why pi became the default executor; opencode is back as an optional
  executor (`--executor opencode`) for whole-task runs.
- Staged benchmark, post-ts-guard pi arm K-pi2 (3 reps): finished all 6 stages every time, 56,
  57 and 58/59 hidden checks in 15–18 min for $1.13–$1.32, no crashes. Prior opencode K runs
  passed 59/59 in 25–31 min for $1.42–$1.61, or crashed once in 31 min for $1.95. Every pi rep
  missed stage 2's unknown-slug 404 page (`test_detail_page_unknown_slug_404`).
- `bench/speed/latency.py`: measures "Reply OK" startup. `--oc-tune 0..4` walks the opencode
  speedups: 1 = one warm server plus `run --attach`, 2 = plus a lean config, 3 = plus a lean
  agent, 4 = warm server over HTTP with the current fixes (default agent). Startup medians: pi
  1.71 s, opencode over HTTP 3.14 s, opencode `run --attach` 6.78 s. On whole tasks HTTP is about
  equal to `run --attach` (~5% faster, within noise).
- Staged shop bench, 2026-09-25, one rep each (rows in `.harness/bench/runs/stages.csv`):
  K + opencode (rep 3) 59/59 for $1.18 in 22.1 min with no retries; PURE Sonnet (rep 4) 59/59
  for $3.39 in 13.6 min; K + pi (rep 2) 58/59 for $1.47 in 26.4 min, its stage 1 broken by a
  stray untracked root `app/` file. Pitfall: the bench copies untracked files too
  (`git ls-files -co`), so one stray file lands in every bench copy.

</details>

## Guardrails

- The executor (`.pi/executor.md` with `.pi/deny.json` and `.pi/extensions/deny-list.ts`) is
  denied git state commands and writes/edits outside cwd, and runs with the rules in `AGENTS.md`:
  only the brief's files, never `.harness/`, finish with `DONE:` or `BLOCKED:`. Reads outside cwd
  are not blocked.
- The runner fails any task that moves git HEAD or the branch, even if no file changed.
- `@claude-executor` is guarded by `.harness/hooks/git_guard.py`, a PreToolUse hook set in its
  agent file; it reads the same `.pi/deny.json` and also blocks `--land`.
- `--land` has no terminal gate: agents are stopped from running it by the `git_guard` hook and the `.pi/deny.json` deny list instead, and the main session lands the worktree itself.
- The kit ships no `.claude/settings.json`, so installing never overwrites your permissions.
  `.claude/settings.strict.json` holds the old hard denies if you want them: copy it over.
- The main session commits or lands only when you ask (rule in `CLAUDE.md`).
- Claude's own reports are never taken as proof; reports come from the runner.

## Requirements

- Python 3 (stdlib only), git, Node (for pi), and a main session: Claude Code, pi or opencode.
- pi installed with its `~/.pi/agent/bin/pi-launcher.js` (or `pi` on PATH), using Bunny.
  Override per run with `HARNESS_MODEL=provider/model`.
- opencode on PATH for `--executor opencode`, the claude CLI for `--executor claude`.
- For `--executor llama`: llama.cpp (`winget install ggml.llamacpp`) and a GGUF model with tool
  calling, served as `llama-server --models-dir <dir> --jinja --port 8080`. The executor loads the
  model itself. A small model on CPU is slow and weak: Qwen3-1.7B ran the pipeline end to end but
  failed a one-function task (it garbled file paths).

Full form: `--executor pi|claude|opencode|llama` (pi is the default).

## Files

<details>
<summary>Repo layout</summary>

```
CLAUDE.md                    main-session rules and the plan → execute loop
AGENTS.md                    executor rules (~10 lines on purpose; add a line only when a failure earns it)
docs/mermaid.md              the plan → execute flow as a diagram
docs/FLOWS.md                every path through the harness in tables (commands, executors, results)
docs/ARCHITECTURE.md         runner internals: guards, retry/repair, executor calls, metrics
docs/session-flows.html      start-to-finish flow for Claude Code, pi and opencode
docs/flows.html              FLOWS.md as pictures
docs/harness-flow.svg        the data-flow diagram shown above
docs/hero.svg, bench-cost.svg README banner and benchmark chart
docs/mode-claude.svg         Claude mode diagram (native subagent executor)
docs/mode-runner.svg         Runner mode diagram (pi / opencode)
docs/bench-flow.svg          Benchmark cell flow diagram
docs/harness.css             shared style for the docs pages
.claude/settings.json        allow the runner (no denies; see settings.strict.json)
.claude/settings.strict.json optional: the same allows plus hard git/--land denies
.harness/hooks/git_guard.py  PreToolUse hook that keeps @claude-executor off git state
.claude/agents/planner.md    plan writer (sonnet)
.claude/agents/claude-executor.md  native executor subagent (haiku default), see Run modes
.claude/agents/reviewer.md   post-run checklist reviewer (sonnet), used by --review
.claude/agents/validator.md  blind A/B code-quality judge (opus), used by the lab bench
.claude/skills/              caveman, adhd, animation/design skills
.pi/executor.md              pi executor (Bunny, free)
.pi/deny.json                pi deny list
.pi/extensions/deny-list.ts  pi deny-list extension
.pi/extensions/deny-match.ts pi deny matcher (pure helper; exports a no-op default so
                             bare `pi` can auto-load it as an extension too)
opencode.json                opencode `orchestrator` agent: MAIN.md as the main session
.harness/MAIN.md             backend-neutral main-session rules (pi / opencode)
.harness/.env.example        every env var, commented out; copy to .harness/.env
.harness/envfile.py          loads .harness/.env (a real env var wins)
.harness/run_plan.py         the runner
.harness/runner/             the runner package; run_plan.py is its shim
.harness/selftest.py         doctor, smoke test, --bench
.harness/build_map.py        writes .harness/context/REPO_MAP.md for the planner
.harness/CHECK_PATTERNS.md   reusable check shapes (the planner reads it)
.harness/plans/<slug>/       one plan: plan.md, tasks.json, plan.lock.json, items/, checks/, logs/, REVIEW.md
.harness/metrics.jsonl       per-task metrics (gitignored)
.harness/bench.csv           --bench results (gitignored)
.harness/bench/              lab benchmark on larger frozen tasks
bench/speed/                 executor duel and startup latency (duel.py, latency.py)
bench/suite/                 capability matrix: executor x size x mode (suite.py)
docs/findings.md             benchmark findings
packages/ufoz-harness/       npm package that installs the kit into another project
```

</details>
