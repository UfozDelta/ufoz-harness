# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Plan → execute loop

**Roles.** You (the main session) decide, review, and accept. `@planner` (sonnet subagent) writes
plans. The pi executor (`opencode/space-bunny-free`, free, effort `medium`) writes the code, driven by
`.harness/run_plan.py`; `--executor cline` swaps in the free Cline CLI (cold: a fresh session per
task, no warm session), `--executor cline-acp` the same CLI over ACP (warm: one process for the
whole plan, `CLINE_MODEL` picks the model), `--executor opencode` a warm `opencode serve`,
`--executor llama` a local llama.cpp router driven by pi (`HARNESS_LLAMA_MODEL` picks the model),
`--executor claude` `claude -p`. Claude never writes code for delegable work. Nobody commits: no agent
runs `git add/commit/push/reset/checkout/stash/clean/rebase`; the user reviews commits separately.

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
   in the plan. Every task is checked by a one-line smoke command (no tests, red-first off); the LAST task writes
   `.harness/plans/<slug>/SUMMARY.md` (<= 600 chars: what, which files, how wired) plus the build smoke. No brief files;
   `checks/check_t<n>.py` only when no test runner fits (packaging, CLI e2e).
   Acceptance must be a shell command that exits 0 only when the task is really done.
3. **Approve.** Run `python .harness/run_plan.py <slug> --lint`; fix errors. Show the user the plan summary.
   Do not execute before they say go.
4. **Execute.** Run in the background: `python .harness/run_plan.py <slug>` (add `--only T2` for one task).
   A real run defaults to its own git worktree (`.worktrees/<slug>`, so plans can run in parallel) and to a
   live window; `--no-worktree` / `--no-window` (or `HARNESS_WORKTREE=0` / `HARNESS_WINDOW=0`) opt out.
   It keeps ONE warm pi session for the whole plan (`--fresh` = new session per task), runs the acceptance
   command itself, writes `items/T<n>.report.md`, and stops at the first failure. Guards:
   touching a file outside `files` fails; tasks.json (+ checks/ if any) are hash-locked (after YOU edit them, relock with
   `python .harness/run_plan.py <slug> --relock-only`, which runs nothing; `--relock` relocks AND runs the plan, so use it
   only after the user said go);
   a plain acceptance failure is retried once with `items/T<n>.feedback.md`, then receives one repair pass. The full trace is in `.worktrees/<slug>/.harness/plans/<slug>/logs/T<n>.pi.log`
   (the user can `tail -f` it). Do not read logs unless a task failed, and then only the tail.
5. **Verify.** Read `SUMMARY.md` and the reports (short) in `.worktrees/<slug>/.harness/plans/<slug>/`, and review with
   `git -C .worktrees/<slug> diff` if in a repo. Never trust a claim of success without them.
   Health check: `python .harness/selftest.py` ($0). Cost comparison, only when asked: `--bench`. Totals: `run_plan.py --stats`.
   If the plan touches side effects (analytics, storage, events) or client state, run `@reviewer` with the plan goal and
   the touched files.
6. **Decide.** Accept, fix the plan section and re-run (`run_plan.py` skips passed tasks), or discard.
   `--land` is the user's command; never run it yourself: tell the user to run
   `python .harness/run_plan.py <slug> --land` to bring the worktree's changes into the main tree.
   After the user's go, keep going without asking: run the whole plan, rebrief and rerun failures yourself.
   Stop and ask only on a second failure of the same task, anything destructive, or a design question.
7. **Report.** End with exactly three lines: `Blocked on me:` / `Changed:` / `Found:` (write `none` if empty).

**Raw pi calls.** Only when needed: `node ~/.pi/agent/bin/pi-launcher.js -p --mode json --no-extensions --no-skills --no-prompt-templates -e .pi/extensions/deny-list.ts --append-system-prompt .pi/executor.md --model opencode/space-bunny-free --thinking medium "<prompt>" > <log> 2>&1 < /dev/null`.
Always redirect output (keeps the trace out of context) and always close stdin (`< /dev/null`),
or pi hangs waiting on it.

### Failures
- Report lists out-of-scope files: discard those changes and re-brief with tighter FILES.
- A task fails twice after re-briefing: stop, investigate read-only, then re-brief with the diagnosis.
- pi exit 124 (timeout) or empty log: check stdin is closed and the model is reachable before retrying.
- Any harness/tool/process quirk that SHOULD be fixed: append it to `log.md` as `what → fix (or Open)`
  under a `## <YYYY-MM-DD> <slug or topic>` heading. At Verify, copy each `items/T<n>.quirks.md` line there too.
- Unlanded worktrees: `python .harness/run_plan.py --pending`

# Explain Decisions
For architecture or naming decisions, invoke the adhd skill first.

# Output Style
Caveman full, every reply. Keep replies under ~80 words unless the user asks for detail.
No recap of what the user just saw, no tables unless asked, no "what changed / what's next" boilerplate.
Answer first, then at most 2-3 bullets. One question at the end, only if blocked.
`@planner` follows the same rules (it preloads the `caveman` skill; architecture questions come back to the main session for adhd).