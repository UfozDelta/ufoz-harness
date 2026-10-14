# Plan: cline-cut
## Goal
Remove cline and cline-acp executors completely: code, config, docs, bench arms, tests.

## Decisions
- Delete `.harness/runner/executors/cline_acp.py`. After: REGISTRY keys = pi, claude, opencode, llama.
- No cline text left in live files (case-insensitive): includes CLINE_MODEL, HARNESS_CLINE*, "Cline CLI".
- `--executor cline-acp` and `--planner cline-acp` become unknown choices.
- Reword shared lists ("pi|claude|opencode|cline-acp|llama" -> "pi|claude|opencode|llama"); fix counts.
- Keep `has_sessions` in base.py, llama, opencode, `--session`.
- bench/speed/duel.py: strip cline arms; if nothing meaningful remains, delete the file and its refs.
- Do not touch `.harness/plans/**` (except this plan), `.harness/context/REPO_MAP.md` (generated), `bench/suite/work/**`, `bench/suite/archive/**`, `docs/flows.html`, `docs/mode-runner.svg`, `.worktrees`, `log.md` history.
- Skills text matching "decline" is NOT cline; checks use the word "cline" only in listed files.

Unverified: duel.py may be cline-only; executor decides at T2.
Unverified: tests/test_scope.py:60 comment "cline, cut at 200" — in scope for T2 (comment only).
Later: docs/flows.html (7) and docs/mode-runner.svg (1) still mention cline.
Note: tree is dirty (runner/*.py, git_guard.py, docs/harness-improvements-2026-10-10.md). Commit first; clean tree required.

## interfaces
`runner.executors.REGISTRY` keys after: pi, claude, opencode, llama.

## T1 Runner code
FILES: .harness/runner/executors/cline_acp.py, .harness/runner/executors/__init__.py, .harness/runner/executors/base.py, .harness/runner/cli.py, .harness/runner/watch.py, .harness/runner/planner.py, .harness/runner/guards.py, .harness/selftest.py, .claude/skills/harness-band/hooks/register.tsx
MUST:
- Delete cline_acp.py; drop import + REGISTRY entry.
- cli.py: `--executor`/`--planner` help and allowed tuple drop cline-acp; fix comments naming cline.
- watch.py + register.tsx EXECUTORS drop 'cline-acp'.
- selftest.py: drop the cline tool tuple and CLINE_MODEL note.
- base.py, planner.py, guards.py comments no longer name cline.
TEST: nocline check on the files + REGISTRY import check + tsc (full selftest pytest ~114s hits its 120s cap, pre-existing)

## T2 Bench and tests
FILES: bench/suite/suite.py, bench/suite/cells.py, bench/suite/README.md, bench/speed/duel.py, tests/test_harness_suite.py, tests/test_scope.py
MUST:
- Drop cline-acp from suite.py EXECUTORS, cells.py EXECUTOR_MODELS, README.
- duel.py: remove cline arms (or delete file if cline-only).
- tests/test_harness_suite.py: replace cline-acp cases (lines ~24, ~63) with remaining executors; tests stay meaningful.
- tests/test_scope.py:60 comment: drop "cline".
TEST: nocline check + `python -m pytest tests/test_harness_suite.py tests/test_scope.py -q`

## T3 Docs and env
FILES: README.md, docs/ARCHITECTURE.md, docs/FLOWS.md, docs/mermaid.md, packages/ufoz-harness/README.md, packages/ufoz-harness/kit_readme.md, .harness/.env.example, .harness/HARNESS.md, .harness/MAIN.md
MUST:
- Remove cline / cline-acp rows, sections, bullets, env vars (CLINE_MODEL, HARNESS_CLINE, HARNESS_CLINE_DATA, HARNESS_CLINE_PROVIDER, "cline / pi paths" -> "pi paths").
- HARNESS.md Roles + MAIN.md lines 3-4, 31-32: drop cline-acp clause; "pi, opencode or cline-acp" -> "pi or opencode".
- Counts stay correct. Keep other uncommitted HARNESS.md edits.
TEST: nocline check on all files

## T4 write summary
FILES: .harness/plans/cline-cut/SUMMARY.md
MUST: write <= 600 chars: what, which files, how wired; add `BUILD: pass|fail <first error>` line.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/cline-cut/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
