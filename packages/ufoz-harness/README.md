# ufoz-harness

Installer for the plan/execute harness. Copies the planner and reviewer agents, the
main-session rules (`CLAUDE.md` for Claude Code, `.harness/MAIN.md` + `opencode.json` for pi
or opencode), the pi executor, the Python runner, and skills into a project.

Plans are lean: one `plan.md` with a section per task plus a short `tasks.json`.
Every task is checked by a one-line smoke command; the last task writes `SUMMARY.md` and
records the build result. The free executor (`space-bunny-free`, effort `medium`) works
through the whole plan in one warm session, in its own git worktree.

## Usage

```
npx ufoz-harness
npx ufoz-harness --yes
npx ufoz-harness --dry-run
npx ufoz-harness --dir <path>
```

| Flag | Does |
|---|---|
| `--yes` | skip prompts, accept defaults |
| `--dry-run` | print what would be copied, change nothing |
| `--dir <path>` | install into `<path>` instead of the current directory |

Existing harness files are overwritten. Changed files are backed up to
`.harness/backup/<timestamp>/` first. `.gitignore` is only appended to, never
rewritten.

## Requirements

- Node 18+
- Python 3
- git
- pi, installed with its `~/.pi/agent/bin/pi-launcher.js` (or `pi` on PATH)

Other executors are optional: opencode on PATH for `--executor opencode`, the
claude CLI for `--executor claude`, the Cline CLI (`npm i -g cline`) for
`--executor cline` / `cline-acp`, and a local `llama-server` for
`--executor llama`. The default pi executor needs none of them.

## Configuration

The kit ships `.harness/.env.example`. Copy it to `.harness/.env` (gitignored, and
the installer adds that to your `.gitignore`) and uncomment what you want to
change. A real env var in your shell always wins over the file.

## Publishing

`prepack` rebuilds `kit/` from the repo, so the published tarball always matches
the current harness.

```
cd packages/ufoz-harness && npm publish
```

## First step after install

```
python .harness/selftest.py
```
