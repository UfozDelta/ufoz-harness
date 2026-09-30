# MAIN.md

Main-session rules, backend-neutral: works the same under pi, opencode or cline. `AGENTS.md` (auto-loaded by
pi/opencode/cline) holds the EXECUTOR's rules; they do not apply to this main session, so ignore them here.
These rules bias toward caution over speed; for trivial tasks, use judgment.

## 1. Think before coding

Don't assume, don't hide confusion, surface tradeoffs. State assumptions explicitly; if uncertain, ask.
If multiple interpretations exist, present them instead of picking silently. If something is unclear, stop,
name what is confusing, and ask.

## 2. Simplicity, surgical changes

Minimum code that solves the problem: nothing speculative, no unrequested flexibility, no refactors of
code that isn't broken. Match existing style. Remove only the imports and functions YOUR changes made
unused. Every changed line should trace directly to the user's request.

## 3. Goal-driven execution

Define success criteria, then loop until verified. For multi-step work, state a brief plan
(`1. [step] -> verify: [check]`). Acceptance must be a shell command that exits 0 only when the task is
really done.

---

## Plan -> execute loop

**Roles.** You (the main session) decide, review, and accept. The planner backend writes the plan; the
executor backend (`opencode/space-bunny-free`, free, effort `medium`) writes the code, driven by
`.harness/run_plan.py`; `--executor cline` swaps in the free Cline CLI (cold: a fresh session per
task), `--executor cline-acp` the same CLI over ACP (warm: one process for the whole plan, model
pinned with `CLINE_MODEL`), `--executor opencode` a warm `opencode serve`, `--executor llama` a local
llama.cpp router driven by pi (`HARNESS_LLAMA_MODEL` picks the model), `--executor claude`
`claude -p`. The main session never writes code for delegable work. Nobody commits: no agent
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

1. **Decide.** State assumptions and success criteria; settle the design with the user.
2. **Plan.** Write a spec file describing the work (goal, context, files, must-haves, constraints, a
   one-line smoke command per task). It goes at `.harness/plans/<slug>/SPEC.md` (create the directory
   yourself before running `--plan`), then run
   `python .harness/run_plan.py <slug> --plan <spec.md>`. It writes `.harness/plans/<slug>/plan.md`,
   `tasks.json` and lints them; the planner backend comes from `HARNESS_PLANNER` (default `pi`) and the
   model from `HARNESS_PLANNER_MODEL` (default `opencode/space-bunny-free`). Show the user the plan
   summary and the plan's `Unverified:` list, and ASK IN CHAT before executing anything.
3. **Approve.** Run `python .harness/run_plan.py <slug> --lint`; fix errors. Do not execute before the
   user says go.
4. **Execute.** Run in the background: `python .harness/run_plan.py <slug>` (add `--only T2` for one
   task). A real run defaults to its own git worktree (`.worktrees/<slug>`, so plans can run in
   parallel) and to a live window; `--no-worktree` / `--no-window` (or `HARNESS_WORKTREE=0` /
   `HARNESS_WINDOW=0`) opt out. It keeps ONE warm executor session for the whole plan (`--fresh` = new session per task; the
   cline arm is always fresh), runs
   the acceptance command itself, writes `items/T<n>.report.md`, and stops at the first failure. Guards:
   touching a file outside `files` fails; tasks.json (+ `checks/` if any) are hash-locked (after YOU edit them, relock with
   `python .harness/run_plan.py <slug> --relock-only`, which runs nothing; `--relock` relocks AND runs the plan, so use it
   only after the user said go); a plain acceptance failure is retried once with `items/T<n>.feedback.md`, then
   gets one repair pass. The full trace is in `.worktrees/<slug>/.harness/plans/<slug>/logs/T<n>.pi.log`;
   do not read logs unless a task failed, and then only the tail.
5. **Verify.** Read `SUMMARY.md` and the reports (short) in `.worktrees/<slug>/.harness/plans/<slug>/`, and review with
   `git -C .worktrees/<slug> diff` if in a repo. Never trust a claim of
   success without them. Health check: `python .harness/selftest.py` ($0). Cost comparison, only when
   asked: `--bench`. Totals: `run_plan.py --stats`.
6. **Decide.** Accept, fix the plan section and re-run (`run_plan.py` skips passed tasks), or discard.
   `--land` is the user's command; never run it yourself: point the user at
   `python .harness/run_plan.py <slug> --land` to land the worktree into the main tree. After the
   user's go, keep going without asking: run the whole plan, rebrief and rerun failures yourself. Stop and
   ask only on a second failure of the same task, anything destructive, or a design question.
7. **Report.** End with exactly three lines: `Blocked on me:` / `Changed:` / `Found:` (write `none` if
   empty).

### Failures

- Report lists out-of-scope files: discard those changes and re-brief with tighter FILES.
- A task fails twice after re-briefing: stop, investigate read-only, then re-brief with the diagnosis.
- Executor exit 124 (timeout) or empty log: check stdin is closed and the model is reachable before retrying.
- Any harness/tool/process quirk that SHOULD be fixed: append it to `log.md` as `what → fix (or Open)`
  under a `## <YYYY-MM-DD> <slug or topic>` heading. At Verify, copy each `items/T<n>.quirks.md` line there too.
- Unlanded worktrees: `python .harness/run_plan.py --pending`

## Output style

Plain and short. Answer first, then at most 2-3 bullets. No recap of what the user just saw, no tables
unless asked, no "what changed / what's next" boilerplate. One question at the end, only if blocked.
No narrated reasoning and no re-litigating a decision already made: state the result, not the thought
process.
