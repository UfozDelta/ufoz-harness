# Plan: docs-move

## Goal
Move FLOWS.md, ARCHITECTURE.md, mermaid.md from repo root into docs/ (git mv, byte-identical
content except one link fix), fix README.md references, and add the missing acceptance
checker script. No behaviour changes.

## Decisions
Verified: root files FLOWS.md, ARCHITECTURE.md, mermaid.md, README.md exist (`ls`).
Verified: .harness/specs/check_docs_move.py does NOT exist yet (`ls .harness/specs`) — must be
created by this task; it is the acceptance command, so create it first or alongside the moves.
Verified: README.md line 42 `` `ARCHITECTURE.md` explains ``, line 47
`[mermaid.md](mermaid.md)`, line 87 `see ARCHITECTURE.md for details`, lines 226-227 list
`FLOWS.md` / `ARCHITECTURE.md` in a padded two-column table (`grep -n`).
Unverified: exact byte content/line count of docs/ARCHITECTURE.md line 4 link — locate by
string search, do not hardcode line numbers.
Later: none.

## interfaces
No code interfaces. Only doc files and one new stdlib-only checker script,
`.harness/specs/check_docs_move.py`, invoked as `python .harness/specs/check_docs_move.py`
(no CLI args, exit 0 = pass). It must not shell out to git.

## T1 move docs and fix refs
FILES: FLOWS.md, ARCHITECTURE.md, mermaid.md, docs/FLOWS.md, docs/ARCHITECTURE.md, docs/mermaid.md, README.md
NOTE: the acceptance check is `.harness/plans/docs-move/checks/check_t1.py`. It is written and
hash-locked by the main session. Do NOT create, edit or run any other checker, and do not touch
`.harness/**` at all.
MUST:
- `git mv FLOWS.md docs/FLOWS.md`, `git mv ARCHITECTURE.md docs/ARCHITECTURE.md`,
  `git mv mermaid.md docs/mermaid.md`. Content stays byte-for-byte identical except the one
  link fix below — no rewording, reformatting, or renumbering.
- In `docs/ARCHITECTURE.md`, find the link to the root README and change
  `[README.md](README.md)` to `[README.md](../README.md)`. No other link changes in the
  three moved files.
- In `README.md`, make exactly these substitutions (locate by string, not line number):
  `` `ARCHITECTURE.md` explains `` → `` `docs/ARCHITECTURE.md` explains ``;
  `[mermaid.md](mermaid.md)` → `[mermaid.md](docs/mermaid.md)`;
  `see ARCHITECTURE.md for details` → `see docs/ARCHITECTURE.md for details`;
  in the `Files` code block, prefix the `FLOWS.md` and `ARCHITECTURE.md` entries with `docs/`,
  padding with spaces so the description column stays aligned with the other entries
  (e.g. `AGENTS.md`); do not reorder or touch other entries.
- Do not touch `.harness/**`, `packages/**`, `CLAUDE.md`, `AGENTS.md`, `opencode.json`, `skills-lock.json`. Do not create `docs/README.md`.
TEST: python .harness/plans/docs-move/checks/check_t1.py

## T2 write summary
FILES: .harness/plans/docs-move/SUMMARY.md
MUST: write <= 600 chars covering what was made (3 docs moved to docs/, README references
fixed, checker script added), which files, and how it was wired. No build step for this
plan (docs only) — add line `BUILD: pass`.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/docs-move/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
