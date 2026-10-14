# Plan → execute harness

Portable: copy `.harness/`, `.pi/`, `.claude/agents/`, add `@.harness/HARNESS.md` to CLAUDE.md. Remove that line to disable.

**Default / override.** Delegable work goes through the harness by default. If the user says "do it here", "inline" or "no harness" for a task, implement it in the session: no plan, no clean-tree check. The override covers that task only unless the user says "always".

**Roles.** You (the main session) decide, review, and accept. `@planner` (sonnet subagent) writes
plans. The pi executor (`opencode/muse-spark-1.3`, cheap, effort `medium`) writes the code, driven by
`.harness/run_plan.py`; `--executor BACKEND[:MODEL]` picks who codes (e.g. `claude:sonnet`); `--executor opencode` a warm `opencode serve`,
`--executor llama` a local llama.cpp router driven by pi (`HARNESS_LLAMA_MODEL` picks the model),
`--executor claude` `claude -p`, `--executor agent:haiku` the `@claude-executor` agent (below). Executors and `@planner` never touch git or land: enforced by `.pi/deny.json`, the runner's HEAD check, and
`.harness/hooks/git_guard.py` (registered on `@claude-executor` and `@planner`). The main session is not restricted:
it may commit and run `--land` itself. Confirm first only for outward-facing or destructive actions (push, force, delete).

**Clean tree required.** A run needs a clean working tree: no uncommitted changes or untracked files
(outside `.gitignore`). If the tree is dirty, `run_plan.py` exits with a message naming the dirty
paths and refuses to run. The check lives in worktree setup, so `--no-worktree` skips it. The
`.harness/plans/<slug>/` dir of the slug being run is ignored by the check (no plan-add commit
needed); every other dirty path still refuses.

**Delegate** (plan it, then run it):
- Well-specified changes: boilerplate, CRUD, mechanical edits, renames
- Writing or extending tests for known behavior
- Repetitive multi-file edits with a clear pattern
- Applying a design you've already decided on

**Do not delegate** (handle yourself):
- Architecture and design decisions
- Ambiguous requirements or anything needing user clarification
- Debugging problems with an unknown cause
- Security-sensitive code (auth, crypto, permissions, secrets)
- Final review and the decision to accept or discard work

### Loop
1. **Decide.** State assumptions, success criteria; settle design with the user.
2. **Plan.** Small task: write `.harness/plans/<slug>/` yourself. Large or exploratory task: call `@planner`
   (it runs `--lint` itself; check its plan.md `Unverified:` list at approval).
   Layout: `plan.md` (Decisions + one `## T<n>` section per task: FILES / MUST / TEST), `tasks.json`
   (id, deps, files, acceptance). Contract plan, <= ~1.5k tokens: Decisions, interfaces, tasks; do not solve the task
   in the plan. Every task is checked by a one-line smoke command (no tests, red-first off by default; opt in per task with `"red_first": true`); the LAST task writes
   `.harness/plans/<slug>/SUMMARY.md` (<= 600 chars: what, which files, how wired) plus the build smoke. No brief files;
   `checks/check_t<n>.py` only when no test runner fits (packaging, CLI e2e).
   Acceptance must be a shell command that exits 0 only when the task is really done.
3. **Approve.** Run `python .harness/run_plan.py <slug> --lint`; fix errors. Show the user the plan summary.
   Do not execute before they say go.
   **"haiku" / "all-Claude" / "native" executor** (same worktree, reports and land as the runner): run
   `python .harness/run_plan.py <slug> --executor agent:haiku` (call 1 prints `worktree: <abs path>` and a handoff), then spawn
   `claude-executor` with the Agent tool, NO `isolation`, `run_in_background: true` (so it shows in the agents panel), passing the slug and that path.
   Haiku edits inside `.worktrees/<slug>` and runs acceptance itself. When it is done, rerun the SAME command (call 2): it grades the
   worktree (lock, file scope, acceptance; `MAIN <path>` on any main-tree write or HEAD move since call 1), writes `items/T<n>.report.md`,
   commits passing tasks and skips ones already passed. The agent's Write tool refuses SUMMARY.md: it uses a bash heredoc.
   Land with `--land`.
4. **Execute.** Run in the background: `python .harness/run_plan.py <slug>` (add `--only T2` for one task).
   A real run defaults to its own git worktree (`.worktrees/<slug>`, so plans can run in parallel) and to a
   live window; `--no-worktree` / `--no-window` (or `HARNESS_WORKTREE=0` / `HARNESS_WINDOW=0`) opt out.
   It keeps ONE warm pi session for the whole plan (`--fresh` = new session per task), runs the acceptance
   command itself, writes `items/T<n>.report.md`, and stops at the first failure. Guards:
   touching a file outside `files` fails; tasks.json (+ checks/ if any) are hash-locked (after YOU edit them, relock with
   `python .harness/run_plan.py <slug> --relock-only`, which runs nothing);
   a plain acceptance failure is retried once with `items/T<n>.feedback.md`, then receives one repair pass. The full trace is in `.worktrees/<slug>/.harness/plans/<slug>/logs/T<n>.pi.log`
   (the user can `tail -f` it). Do not read logs unless a task failed, and then only the tail.
5. **Verify.** Read `SUMMARY.md` and the reports (short) in `.worktrees/<slug>/.harness/plans/<slug>/`, and review with
   `git -C .worktrees/<slug> diff` if in a repo. Never trust a claim of success without them.
   Health check: `python .harness/selftest.py` ($0). Cost comparison, only when asked: `--bench`. Totals: `run_plan.py --stats`.
   If the plan touches side effects (analytics, storage, events) or client state, run `@reviewer` with the plan goal and
   the touched files.
6. **Decide.** Accept, fix the plan section and re-run (`run_plan.py` skips passed tasks), or discard.
   Land accepted work yourself: `python .harness/run_plan.py <slug> --land` brings the worktree's changes into the main tree.
   After the user's go, keep going without asking: run the whole plan, rebrief and rerun failures yourself.
   Stop and ask only on a second failure of the same task, anything destructive, or a design question.
7. **Report.** End with exactly three lines: `Blocked on me:` / `Changed:` / `Found:` (write `none` if empty).

**Raw pi calls.** Only when needed: `node ~/.pi/agent/bin/pi-launcher.js -p --mode json --no-extensions --no-skills --no-prompt-templates -e .pi/extensions/deny-list.ts --append-system-prompt .pi/executor.md --model opencode/muse-spark-1.3 --thinking medium "<prompt>" > <log> 2>&1 < /dev/null`.
Always redirect output (keeps the trace out of context) and always close stdin (`< /dev/null`),
or pi hangs waiting on it.

### Failures
- Report lists out-of-scope files: the runner already reverted them and retried once; if the report still lists them, re-brief with tighter FILES.
- A task fails twice after re-briefing: stop, investigate read-only, then re-brief with the diagnosis.
- pi exit 124 (timeout) or empty log: check stdin is closed and the model is reachable before retrying.
- Any harness/tool/process quirk that SHOULD be fixed: append it to `log.md` as `what → fix (or Open)`
  under a `## <YYYY-MM-DD> <slug or topic>` heading. At Verify, copy each `items/T<n>.quirks.md` line there too.
- Unlanded worktrees: `python .harness/run_plan.py --pending`
