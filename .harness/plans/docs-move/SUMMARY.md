# docs-move

Moved `FLOWS.md`, `ARCHITECTURE.md` and `mermaid.md` from the repo root into `docs/` (content
unchanged except `docs/ARCHITECTURE.md` now links `../README.md`), fixed the four README
references and the two `Files` table entries, and added the stdlib-only acceptance checker
`.harness/specs/check_docs_move.py` (no git, no args, exit 0 = pass). Docs only, so there is
nothing to build.
BUILD: pass
