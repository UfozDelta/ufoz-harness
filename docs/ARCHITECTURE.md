# Architecture

How the harness works inside: the processes, the files they share, and the exact rules
`run_plan.py` applies. For the usage guide see [README.md](../README.md); for the flow as a
diagram see [mermaid.md](mermaid.md).

## 1. Roles and trust boundaries

| Component | Process | Model | Writes | Trusted to grade? |
|---|---|---|---|---|
| Main session | Claude Code (`CLAUDE.md`), or pi / opencode (`.harness/MAIN.md`) | Opus, or Bunny | plans (small tasks), review notes | no, it reads runner output |
| `@planner` | Claude Code subagent | Sonnet (`.claude/agents/planner.md`) | only `.harness/plans/<slug>/` | no |
| Planner (`--plan`) | one executor backend (`HARNESS_PLANNER`, default pi) | Bunny, or sonnet for claude | only `.harness/plans/<slug>/` | no |
| Executor | `node ~/.pi/agent/bin/pi-launcher.js -p` | Bunny (`opencode/space-bunny-free`, OpenCode Zen; `.pi/executor.md`) | only the task's `files` | no |

| Executor (llama) | `pi-launcher.js -p` with `PI_CODING_AGENT_DIR` = a throwaway dir | local GGUF on a user-started `llama-server` router (`HARNESS_LLAMA_MODEL`) | only the task's `files` | no |
| Runner | `python .harness/run_plan.py` | none | reports, feedback, logs, metrics | **yes**, the only grader |
| Reviewer (optional) | `claude -p --model sonnet` | Sonnet | `REVIEW.md` | advisory only |

Main idea: **no model's claim of success counts.** The runner runs each task's
`acceptance` command itself, hashes the file tree to see what changed, and writes the
verdict. The executor's `DONE:` line is ignored.

Git: no agent changes git state. `.pi/deny.json` plus `.pi/extensions/deny-list.ts`
deny `git add/commit/push/reset/checkout/switch/restore/stash/clean/rebase/merge/branch`,
including chained, env-prefixed, `git -C`, and `bash -c` forms, as well as writes and
edits outside cwd; reads outside cwd are allowed. `--executor claude` passes the same
list as `--disallowedTools`. The runner reads git (`git ls-files`) and, for a real run, adds
one worktree per plan (3.7); the user's index, HEAD and branches stay untouched.

## 2. Plan layout

```
.harness/plans/<slug>/
  plan.md            Goal, Decisions (Verified/Unverified/Later), interfaces, one `## T<n>` per task
  tasks.json         {"slug", "tasks": [{id, deps, files, acceptance, red_first?, expect?, brief?}]}
  checks/check_t<n>.py   optional; only when no one-line smoke command fits
  plan.lock.json     sha256 of tasks.json + checks/*.py, written on first run
  items/T<n>.report.md       verdict (runner)
  items/T<n>.metrics.json    timing + tokens (runner)
  items/T<n>.feedback.md     retry input (runner)
  items/T<n>.repair<k>.md    repair input (runner)
  logs/T<n>.pi.log           executor trace; .retry<k> / .repair<k> variants
  SUMMARY.md         written by the plan's last task, <= 600 chars + `BUILD: pass|fail <error>`
```

A task's brief is `items/<id>.md` if `"brief"` is set, otherwise its `## <id>` section of
`plan.md` (the current contract-plan format). `plan.md`'s Decisions apply to every task.

**Contract plan rules** (enforced by the planner prompt, not the runner): <= ~1.5k tokens;
3-8 tasks; acceptance is one cheap smoke command (`python -c`, `node -e`, `npx tsc --noEmit`
for TS); no full builds per task; never import `.ts` through node in a check;
last task writes `SUMMARY.md`
and runs the build only to record `BUILD:`, never to fail on it. Acceptance runs through the
OS shell (cmd.exe on Windows), so no `VAR=x cmd`, `/tmp`, `rm`, `test`.

## 3. `run_plan.py` lifecycle

```
main()
  parse args
  --stats → print_stats(), exit
  --land  → land.land(slug), exit          (the user's command)
  --plan  → planner.run_planner(), exit    (3.6)
  --parallel > 1 with a non-thread-safe executor → exit 1
  real run in a git repo → worktree.ensure(slug), chdir into .worktrees/<slug>   (3.7)
  take run.lock (a second run of the same plan exits); open the live window (Windows)
  load tasks.json
  --lint  → lint(), exit
  lock: write plan.lock.json if missing; keep it in memory
  done = tasks whose report already says "RESULT: pass"   (reruns skip them)
  todo = remaining tasks (or just --only <id>)
  sequential (default) or DAG scheduler (--parallel N)
    for each task: run_task(t, session) → (ok, lines, session)
    stop at first failure
  --review and a fresh full pass → run_reviewer() → REVIEW.md
  print summary, exit 1 if anything failed
```

### 3.1 `run_task`: the guard sequence

For one task, in this order:

1. **Lock check.** Rehash `tasks.json` + `checks/*.py`; any mismatch with the in-memory
   lock → `RESULT: lock-mismatch`, no executor call. (Deleting `plan.lock.json` mid-run
   changes nothing; the lock is held in memory.)
2. **Red-first.** If `red_first` is true (off by default; opt in with `"red_first": true`) and no earlier attempt ran, run the
   acceptance on the untouched tree. Passing → `RESULT: check-invalid`, since the check proves nothing.
3. **Baseline.** Write `RESULT: running`, take `snapshot()` (sha256 of every
   `git ls-files -co --exclude-standard` file), and count suppression markers in every
   file the task could touch.
4. **Attempt loop** (`1 + RETRIES` attempts, RETRIES = 1):
   - call the executor (see 3.3); exit 75 = rate-limited → `wait_for_quota()` and rerun
     that attempt without counting it;
   - rerun the lock check, run the acceptance, snapshot again;
   - `touched` = files whose hash changed; `stray` = touched files not in `files`
     (plus co-running tasks' files under `--parallel`), excluding runner-owned files;
   - `suppressed` = touched files with more `@ts-ignore` / `@ts-nocheck` / `eslint-disable`
     lines than at baseline;
   - `ok = acceptance passed and exit == 0 and not stray and not suppressed`;
   - stop on ok, lock change, or stray (the executor can't undo those); otherwise write
     `feedback.md` (acceptance command, suppression list, output tail of 1500 chars) and retry.
     Exit 124 (timeout) drops the warm session so the retry starts fresh.
5. **Repair loop** (`REPAIRS`, 1). Runs only for a *plain failure*: acceptance
   failed or a suppression marker was added, with no lock change, no stray files and no
   timeout. Scope widens to `files` of this task **plus every task listed before it and the
   transitive deps closure of those earlier tasks**.
   The executor gets `repair<k>.md`: the rule (fix the root cause, no suppression comments,
   don't delete features or checks), the acceptance, the suppression list, the output tail,
   and the allowed files. The same checks apply, with `stray` measured against the wider scope.
6. **Report.** `items/<id>.report.md` (result, exit, attempts incl. repairs, `repairs: n`,
   seconds split into exec / acceptance / retry, tokens, touched files, out-of-scope files,
   lock state, log path, acceptance output) and a metrics row. The summary line says
   `REPAIRED` when a repair turned a fail into a pass.

Why the repair scope is "earlier tasks": a break often surfaces in a later task's check
(the plan's last task runs the build), while the broken code sits in files an earlier task
owned. A retry can't reach those files; a repair can.

### 3.2 Result states

| `RESULT:` | Set when | Executor ran? |
|---|---|---|
| `pass` | acceptance ok, exit 0, no stray, no new suppression | yes |
| `fail` | any of the above not met after retries and repairs | yes |
| `check-invalid` | red-first acceptance passed on the untouched tree | no |
| `lock-mismatch` | tasks.json or a check changed since the lock | no |
| `running` | left behind by a crashed runner; the next run treats it like a failed attempt (no red-first) | partly |

### 3.3 Executor invocation

`run_pi(brief, log, timeout, feedback, session)`:

```
node ~/.pi/agent/bin/pi-launcher.js -p --mode json --no-extensions --no-skills
     --no-prompt-templates -e .pi/extensions/deny-list.ts
     --append-system-prompt .pi/executor.md --model $HARNESS_MODEL
     --thinking medium --session-id <id> "<prompt>"
```

- **stdin is `DEVNULL`**, or pi hangs waiting on it.
- `cwd=os.getcwd()` and `PWD=os.getcwd()` keep pi in the task's project.
- `HARNESS_PI` overrides the launcher path; missing paths stop with `pi not found: ...`.
- The pi JSON pump writes assistant text and tool calls to the log and records
  `message_end` input/output/reasoning/cacheRead tokens and total cost.
- Exit codes: `124` = runner timeout (default 900 s); `75` = only rate-limit errors for
  120 s. `wait_for_quota()` then probes every 60 s with a pi health call, for up to 6 h.
- The process tree is killed with `taskkill /F /T` on Windows (children keep pipes open).

**Warm session (default).** One pi session carries the whole plan; each task's
session id feeds the next call. `--fresh` starts a new session per task; `--session <id>`
continues an existing one.

**`--executor claude`**: the same contract via `claude -p`, with a warm session and the
executor rules appended as its system prompt (3.5). Used only for A/B cost comparisons.

**`--executor opencode`**: one warm `opencode serve` per run, driven over HTTP+SSE
(`prompt_async` + `/event` until `session.idle`). The config lives in a throwaway
`XDG_CONFIG_HOME`: snapshot, LSP, formatter, autoupdate off, share disabled, title and
summary agents disabled; permissions allow `edit`, deny `question` / `plan_enter` /
`plan_exit` / `webfetch` / external directories, and allow `bash` except the patterns in
`.pi/deny.json`. Every session is created with `question` / `plan_enter` / `plan_exit`
denied, and every prompt sends the model, `variant` = `$HARNESS_VARIANT` (default
`medium`) and `system` = `.pi/executor.md` (appended to opencode's own prompt, +188
tokens). A `question.asked` or `permission.asked` event fails the task immediately;
finished tool calls and text are logged once; a timeout aborts the session.

Why (measured in `bench/speed/latency.py`): without `variant` the model reasoned up
to ~16x more and took ~2x longer, and with the question tool allowed a session hung for
30 min. A replacement "lean" prompt made bench task `crm` fail 0/37 (it stops when the spec
is ambiguous), while opencode's default prompt got 37/37.

**`--executor llama`**: pi, unchanged, pointed at a local llama.cpp `llama-server` in router
mode (`llama.py`, a `PiExecutor` subclass). The server is user-started; `start()` only
attaches: `GET /models` (unreachable -> exit with the start command), picks the model
(`--executor llama:<model>`, else `HARNESS_LLAMA_MODEL`, else the only one listed; several -> exit
listing ids), `POST /models/load` unless its `status.value` is `loaded`/`sleeping` (the router
does not autoload `--models-dir` models for pi) and polls until loaded (300 s cap). It then writes
a `models.json` with one custom provider `llamacpp` (`openai-completions` on `<url>/v1`, cost 0,
`contextWindow` from `meta.n_ctx` else 32768) into a throwaway dir and runs pi with
`PI_CODING_AGENT_DIR` pointing there (`run_pi(..., env=)`), so the model is `llamacpp/<id>`
and `~/.pi/agent` is never read or written. `probe()` is `GET /health`; `stop()` removes the dir.

Why not pi's built-in `llama.cpp` provider: its model list only fills from an interactive
`/login llama.cpp` / `/llama`, so `-p` mode says `Model "llama.cpp/<id>" not found` even with
`LLAMA_BASE_URL` set (pi issue #9559, closed not planned). Measured live (llama.cpp b11193,
Qwen3-1.7B, CPU): usage parsed, deny-list still blocks `git branch`, warm `--session-id` keeps
context; the model itself failed a one-function smoke plan (garbled paths).

### 3.4 Parallel mode (`--parallel N`)

A DAG scheduler: a task starts when its deps have passed and no running task shares a file.
Each task records the files of tasks that ran alongside it (`co_files`) and may touch them
without counting as stray; each owner's own acceptance covers those files. Pi tasks run
independently.

Not every executor can run this way: `Executor.thread_safe` (base.py, default `True`) is
`False` on `llama` (one local model slot). `cli.py` checks `REGISTRY[args.executor].thread_safe`
before the run lock is even acquired and exits with an error if `--parallel > 1` is combined
with one of these — refused up front rather than racing two tasks on the same session.

### 3.5 The `runner/` package

`run_plan.py` is a thin shim: it puts `.harness` on `sys.path` and calls
`runner.cli.main()`. The code lives in `.harness/runner/`:
- `cli.py` (flags), `plan.py` (tasks.json + briefs), `scheduler.py` (serial / `--parallel`),
  `task_runner.py` (the guard sequence of 3.1, one shared `_attempt()`), `report.py` (report
  text + metrics rows), `lint.py`, `stats.py`, `reviewer.py`, `acceptance.py`, `guards.py`
  (snapshot/lock), `procs.py` (process tree, token keys, exit codes), `planner.py` (`--plan`),
  `worktree.py` (per-plan worktree), `land.py` (`--land`), `watch.py` (`python .harness/runner/watch.py <slug>` and the live
  window).
Who writes the code is pluggable: `executors/base.py` defines `ExecResult` and the
`Executor` ABC (`run` — takes an optional `raw_prompt`, pi-only, bypasses the standard brief
template — `probe`, `wait_for_quota`, `start`/`stop` via the context manager, class attrs
`name`/`has_sessions`/`thread_safe`). `procs.zero_usage()` is the shared zero-token/zero-cost
usage dict every executor returns on a hard failure.
`executors/__init__.py` holds `REGISTRY = {pi, claude, opencode, llama}` and `get(name, **opts)`;
`pi.py`, `claude.py`, `opencode.py` and `llama.py` implement it
(opencode = one server driven over HTTP+SSE, `.pi/executor.md` travels as the
prompt's `system` field, and the throwaway `XDG_CONFIG_HOME` config is derived from the
patterns in `.pi/deny.json`). Core modules only import `executors.get`, never a backend module.

**The claude executor** (`--executor claude`) runs `claude -p` per task with the same brief
and the same guards as pi, so A/B comparisons only differ in who wrote the code. It carries
one warm session across the plan: the first task passes a fresh `--session-id`, every later
task `--resume`s it, and `--executor claude:<model>` picks the model (default sonnet). `.pi/executor.md`
plus `AGENTS.md` are appended as its system prompt, the git commands from `.pi/deny.json` are
disallowed, and `--setting-sources project,local --strict-mcp-config` keeps the run off the
user's global settings and MCP servers. The `stream-json` events are pumped into the log as
text, `[toolCall ...]` and `[tool error]` lines, and a rate-limit event (or a usage-limit
`result`) exits `75` so `wait_for_quota()` probes again. See 3.3 for the pi counterpart.

### 3.6 The planner command (`run_plan.py --plan <spec.md>`)

`runner/planner.py` (`run_planner(slug, spec_path, plans_root, backend, model)`) plans a slug
from a spec file without a main session: it writes `PLAN_REQUEST.md` (the spec path plus the
`## Layout` + `## Rules` sections of `.claude/agents/planner.md`, verbatim) and
`planner_rules.md` (that contract without the YAML frontmatter, handed to the executor as its
`rules=`), snapshots the tree, and runs one executor (`HARNESS_PLANNER`, default `pi`, model
`HARNESS_PLANNER_MODEL`, else sonnet for claude and the backend's own default otherwise) with
a 1800 s timeout. Only paths under `.harness/plans/<slug>/` may
change; anything else fails the attempt. It then lints the plan; a lint failure is fed back
into the same warm session (2 retries max) and the result is written to `planner.json`
(`{backend, model, seconds, attempts, tokens, lint_ok}`). The CLI prints the plan path, exits
0 iff `lint_ok`, and runs no tasks.

`Executor.run(..., rules=None)` is the one parameter that makes this backend-neutral: with a
path, the executor uses its text instead of its default prompt (pi: `--append-system-prompt`;
opencode: the `system` field; claude: `--append-system-prompt` without the `AGENTS.md`
concatenation). Default `None` is every other call site's existing behavior.

### 3.7 Worktree, live window and `--land`

A real run (not `--lint` / `--plan` / `--stats` / `--land`) goes through
`worktree.py` unless `--no-worktree` or `HARNESS_WORKTREE=0`. `ensure(slug)` creates
`.worktrees/<slug>` on branch `harness/<slug>`, based on a snapshot of the current tree
(uncommitted and untracked, non-ignored files included) built with a temporary index, so the
user's index, HEAD and branches never change. `.worktrees/` goes into `.git/info/exclude`;
gitignored shared dirs (`node_modules`, `.venv`, `.opencode/node_modules`) are junctioned in,
not copied. `sync_plan` copies the plan dir into the worktree, and everything after that runs
there, so reports, logs and `SUMMARY.md` live in `.worktrees/<slug>/.harness/plans/<slug>/`.
Outside a git repo the run stays in place. On Windows `watch.open_window` also opens one shared
Windows Terminal window with a tab per plan (`--no-window` / `HARNESS_WINDOW=0` to skip).

`--land` (`land.py`) is the user's command: it refuses while `run.lock` exists, while any task has
not passed, or while the worktree is dirty. It runs `git merge --ff-only harness/<slug>`, falling
back to `git merge --no-ff` when the main tree moved; a conflict aborts the merge and the worktree
and branch stay. After a successful merge it copies the plan records into `.harness/plans/<slug>/`,
commits them, and removes the junctions, the worktree and its branch.

## 4. Lint (`--lint`)

It runs nothing but checks:
- the runner can write `items/`, `logs/`, `metrics.jsonl`;
- every task has `id`, `acceptance`, `files`; ids are unique; deps point to earlier tasks;
- the brief exists (`brief` file or a `## <id>` section);
- `checks/...` paths in the acceptance exist;
- acceptance does not load a `.ts`/`.tsx` file through node via `import(` or `require(`;
- tasks with `.ts`/`.tsx` files (excluding `.d.ts`) have `tsc` in acceptance;

- a warning when two tasks share a file with no dep between them;
- red-first: every not-yet-attempted `red_first` task's acceptance must **fail** now.

## 5. Metrics and cost

- Per task: `items/<id>.metrics.json` plus one line in `.harness/metrics.jsonl`
  `{ts, slug, task, executor, result, attempts, repairs, seconds, exec_s, accept_s, retry_s, mode, tokens{input, output, reasoning, cache_read, cost}}`.
- `--review` adds a row with `kind: review` and the exact `claude -p` cost.
- `--stats` totals executor rows per slug, lists review rows, and reads planner /
  reviewer / validator subagent usage from `~/.claude/projects/<project>/*/subagents/`.
  Those dollars are **estimates** from the `PRICES` table in `runner/stats.py`: the last usage
  entry per request id, with cache writes at 1.25x (5 min) or 2x (1 h) input. Main-session
  tokens are not included.

Token mapping is per backend: pi sums `message_end` deltas, claude sums stream-json deltas. The `mode` column reads `fresh` for a backend without sessions even without `--fresh`,
because `Executor.has_sessions` is false there. `--plan` and each run also add `kind: plan_event`
rows (`created`, `run_start`, `run_end`) that carry no tokens.

Where the money goes: the executor is free, so Claude cost = planner + main session
(+ optional review). See `.harness/bench/RESULTS.md` for benchmark numbers.

## 6. Environment variables

| Var | Effect |
|---|---|
| `HARNESS_MODEL` | override the executor model without editing `.pi/executor.md` (applies to the pi and opencode executors) |
| `HARNESS_PI` | override the pi launcher path |
| `HARNESS_VARIANT` | thinking / effort level for every executor, default `medium` |
| `HARNESS_RUNNER_FLAGS` | extra `run_plan` flags in the bench, e.g. `--executor opencode` |
| `HARNESS_ARM_LABEL` | bench arm name written into the rows and the run folder |
| `HARNESS_PLANNER` | planner backend for `run_plan.py --plan` (pi, opencode or claude), default `pi` |
| `HARNESS_PLANNER_MODEL` | model for the planner backend; unset = sonnet for claude, else the backend's own default (Bunny for pi/opencode) |
| `HARNESS_LLAMA_URL` | llama executor: `llama-server` router URL, default `http://127.0.0.1:8080` |
| `HARNESS_LLAMA_MODEL` | llama executor: router model id; unset = the only model the router lists |
| `HARNESS_WORKTREE` | `0` runs plans in place instead of in `.worktrees/<slug>` |
| `HARNESS_WINDOW` | `0` skips the live Windows Terminal window |

All of them can also be set in `.harness/.env` (template: `.harness/.env.example`), loaded by
`.harness/envfile.py`; a variable already set in the shell wins.

## 7. Known limits

- The suppression guard is text-based: it counts lines containing the three markers, and
  it can't tell a new comment that mentions `eslint-disable` from a real directive.
- The build gate is opt-in per task (`build_gate`: last task only, needs `repair_check`).
- The repair scope includes the failing task's files, every task listed before it, and
  that earlier set's transitive `deps` closure.
- A `run.lock` prevents two runs of the same plan from overlapping; a hard-killed run leaves
  it behind, and the next run tells you to delete it.
- The bench copies untracked files as well (`git ls-files -co`), so a stray file in the
  repo lands in every bench copy. It broke one K + pi rep's stage 1 (an untracked root
  `app/` file).
- The bench's start-of-run quota check always probes pi, whatever `HARNESS_RUNNER_FLAGS`
  says.
- The opencode and claude logs write a step only when it finishes, so a slow model looks
  idle in the log.
- The claude executor's new warm-session / `stream-json` path has not been run live yet.
- The llama executor never starts `llama-server`; the run fails fast if it is down. Pi's
  `--thinking` level is sent but ignored (the provider is declared `reasoning: false`), and
  `--session <id>` from an earlier run cannot resume, because each run gets a fresh
  `PI_CODING_AGENT_DIR`.
