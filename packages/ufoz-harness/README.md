# ufoz-harness

Installer for a plan/execute coding harness. A main session (Claude Code, pi or opencode)
decides and plans; a cheap executor writes the code; a Python runner grades every task with a
shell command, so no model marks its own work. You land the result; nobody commits for you.

## Usage

```
node packages/ufoz-harness/index.js --dir <your-project> --dry-run   # preview
node packages/ufoz-harness/index.js --dir <your-project> --yes       # install
```

Not on npm yet, so run it from a checkout of this repo (after `npm publish` it becomes
`npx ufoz-harness`). Run `python packages/ufoz-harness/export_kit.py` first if you changed the
harness: it rebuilds `kit/`, and `prepack` does the same on publish.

| Flag | Does |
|---|---|
| `--yes` | skip prompts, accept defaults |
| `--dry-run` | print what would be copied, change nothing |
| `--dir <path>` | install into `<path>` instead of the current directory |

Existing harness files are overwritten; changed ones are backed up to
`.harness/backup/<timestamp>/` first. `.gitignore` is only appended to, never rewritten. The kit
ships **no** `.claude/settings.json`, so installing never overwrites your permissions.

## What it installs

- `CLAUDE.md` (Claude Code main-session rules), `.harness/MAIN.md` + `opencode.json` (pi / opencode).
- Agents in `.claude/agents/`: `planner` (writes the plan), `reviewer` (post-run checklist),
  `claude-executor` (Claude as the executor, Haiku by default).
- The runner: `.harness/run_plan.py` and `.harness/runner/`, plus `selftest.py` and the build map.
- The pi executor (`.pi/`), the shared deny list `.pi/deny.json`, and
  `.harness/hooks/git_guard.py`, the hook that keeps `@claude-executor` off git state.
- `.claude/settings.strict.json`: optional hard denies on git state and `--land` for the main
  session. Copy it over `.claude/settings.json` if you want them.
- Skills under `.claude/skills/` and `.agents/skills/`.

## Two ways to run a plan

**Runner mode (pi / opencode).** `python .harness/run_plan.py <slug>` drives a free executor (pi by
default, or `--executor opencode|cline|cline-acp|llama|claude`) in its own worktree
`.worktrees/<slug>` **on a clean tree** (no uncommitted changes or untracked files). The runner checks the grader lock, file scope and suppression comments, and
retries and repairs a failing task. `python .harness/run_plan.py <slug> --land` merges it into your tree with `--ff-only`.

**Claude mode.** Once you approve a plan, `run_plan.py <slug> --prepare` makes the same worktree the
runner would use, and the main session spawns `@claude-executor`, a Claude Code subagent that edits
files in it. `--prepare` records a baseline of your tree, and `--check` fails if the agent wrote outside
its worktree or moved git HEAD (an agent hook tries to block this too, but it may not load). Grade it with
`run_plan.py <slug> --check`, land it with `run_plan.py <slug> --land`: the same check and land as
runner mode. The runner is not driving, so there is no automatic retry; `--check` applies the lock,
scope and acceptance checks afterwards.

## Guardrails

- The runner fails a task that touches a file outside its list, adds a suppression comment, or moves
  git HEAD or the branch.
- Executors never commit, push, reset or switch branches (`.pi/deny.json`; for
  `@claude-executor`, the hook plus the `--check` baseline).
- `--land` refuses unless stdin is a terminal (or you pass `--yes`), so an agent cannot run it.
- The main session commits or lands only when you ask.

## Requirements

- Node 18+, Python 3, git
- pi, installed with its `~/.pi/agent/bin/pi-launcher.js` (or `pi` on PATH). The installer's
  preflight requires it today, even if you only plan to use Claude mode.

Other executors are optional: opencode on PATH for `--executor opencode`, the claude CLI for
`--executor claude`, the Cline CLI (`npm i -g cline`) for `--executor cline` / `cline-acp`, and a local
`llama-server` for `--executor llama`. The default pi executor needs none of them.

## Configuration

The kit ships `.harness/.env.example`. Copy it to `.harness/.env` (gitignored, and the installer adds
that to your `.gitignore`) and uncomment what you want to change. A real env var in your shell always
wins over the file.

## First step after install

```
python .harness/selftest.py
```

It checks python, git, pi and the executor model, then runs a one-task smoke plan in a throwaway
temp repo. $0, and it never touches your project.

## Known limits

- The kit installs every bundled skill, including design and animation ones.
