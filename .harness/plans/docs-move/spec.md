# Spec: move reference docs into docs/

## Goal

Move three pure-documentation markdown files from the repo root into a new `docs/`
folder, and fix every reference to them so nothing dangles. No behaviour changes.

## Context

`FLOWS.md`, `ARCHITECTURE.md` and `mermaid.md` are hand-written reference docs at the
repo root. They are not read by any code — no `.py` file, no config, no prompt file
references them as a path. They are only referenced by prose in each other and in
`README.md`.

`MAIN.md` is deliberately NOT part of this move: it lives at `.harness/MAIN.md` and is
a runtime input (`opencode.json` loads it via `{file:.harness/MAIN.md}`; README launch
commands pass it to `--append-system-prompt`). Moving it would break session startup.
Leave it alone.

This is a docs reorganisation, so `CLAUDE.md`, `AGENTS.md`, `mermaid.md`'s own content
and the harness itself are all out of scope.

## Files

May be created, moved or edited, and nothing else:

- `docs/FLOWS.md` (moved from `FLOWS.md`)
- `docs/ARCHITECTURE.md` (moved from `ARCHITECTURE.md`)
- `docs/mermaid.md` (moved from `mermaid.md`)
- `README.md` (edited: references only)

Do not create a `docs/README.md` or an index page. Do not touch `.harness/**`,
`packages/**`, `CLAUDE.md`, `AGENTS.md`, `opencode.json`, `skills-lock.json`.

## Must-haves

1. The three files end up at `docs/FLOWS.md`, `docs/ARCHITECTURE.md`, `docs/mermaid.md`.
   Use `git mv` so history is preserved. The originals must no longer exist at the root.

2. The three files keep their content byte-for-byte except for the link fix in (3).
   Do not reword, reformat, renumber sections or "improve" the prose. This is a move,
   not an edit.

3. `docs/ARCHITECTURE.md` line 4 links to the root README. It is now one level deeper,
   so change `[README.md](README.md)` to `[README.md](../README.md)`. That is the only
   link fix needed: the links between the three moved files are relative to each other
   and all three move together, so they stay correct as-is.

4. `README.md` gets these three edits and no others:
   - line 42: `` `ARCHITECTURE.md` explains `` → `` `docs/ARCHITECTURE.md` explains ``
   - line 47: `[mermaid.md](mermaid.md)` → `[mermaid.md](docs/mermaid.md)`
   - line 87: `see ARCHITECTURE.md for details` → `see docs/ARCHITECTURE.md for details`
   - lines 226-227, in the `Files` code block: keep the entries but show the new paths
     so the listing matches reality. Keep the existing one-space column alignment by
     padding with spaces (e.g. `docs/ARCHITECTURE.md` followed by spaces to the same
     description column as `AGENTS.md`). Do not reorder the other entries.

5. Prose mentions of these three files that are NOT links stay as plain names unless
   they sit next to a path that moved. In particular `FLOWS.md` line 3-4 and
   `mermaid.md` line 35 refer to the sibling docs by bare name; because all three moved
   together those names are still correct. Leave them.

## Acceptance

One command, must exit 0:

```
python .harness/specs/check_docs_move.py
```

The check must fail if: any of the three files is still at the repo root, any of the
three is missing from `docs/`, `README.md` still contains a bare `ARCHITECTURE.md` or a
`[mermaid.md](mermaid.md)` link, or `docs/ARCHITECTURE.md` still links to `README.md`
without `../`.

## Notes for the planner

- This is a three-file move plus six text substitutions. Do not decompose it into
  more than one task; a single task with the check above is correct.
- The check script is a plain `python` script using only the stdlib. It reads files as
  text and asserts on their contents. It must not shell out to git.
- Line numbers given above are from the current file state; locate the strings, do not
  hardcode line numbers in the edit or in the check.
