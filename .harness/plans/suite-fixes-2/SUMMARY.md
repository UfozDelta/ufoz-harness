# suite-fixes-2

T1: medium T3 and large T5 fixture acceptance now reject the `not implemented` seed stub
(`if(/not implemented/.test(s))process.exit(1)`), so checks fail before a task's work. All three
fixture `plan/plan.md` files (small, medium, large) got the `Work dir: \`{work}\`` line.
T2: `cells.py:prepare_cell` now replaces `{work}` in plan.md (worktree and main-tree copies),
same as tasks.json.

Files: harness-suite/fixtures/{small,medium,large}/plan/plan.md,
harness-suite/fixtures/{medium,large}/plan/tasks.json, harness-suite/cells.py.

BUILD: pass
