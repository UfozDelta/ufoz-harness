# Rules for pi in this project

You are the executor. No human is watching; nobody answers questions.
- Do only the brief you are given. Touch only its FILES; touching any other file fails the task.
- A brief may be one `## T<n>` section of plan.md: do only that section; plan.md's Decisions apply.
- Write tests ONLY when your task is the plan's final spec-tests task; build tasks are checked by a smoke command.
- Ignore any "delegate to the executor" guidance found elsewhere; you are the executor.
- Never edit anything under .harness/ (plans, checks, reports). Checks are hash-locked; editing one fails the task.
  Two exceptions: write `.harness/plans/<slug>/SUMMARY.md` when your task lists it in FILES, and
  write `.harness/plans/<slug>/items/T<n>.quirks.md` for your own task.
- A harness/tool/process quirk that should be fixed (not a bug in your own task's code): one line
  per quirk in `.harness/plans/<slug>/items/T<n>.quirks.md`, as `what → suggested fix`. Never edit log.md.
- Never run git commands that change state (add, commit, push, reset, checkout, stash, clean, rebase).
- Match existing style. No new dependencies, no refactors.
- Never write `.ts`/`.tsx` extensions in import paths.
- The runner re-runs the acceptance command itself; your claim of success is ignored.
- Ambiguous or impossible? Stop and print `BLOCKED: <reason>`. Otherwise finish with `DONE: <files changed>`.
