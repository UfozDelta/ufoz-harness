# Plan: prune-executors
## Goal
Delete cold `cline` executor (cline-acp stays), its docs/refs/bench arms, and stale duplicate log.md section. Update HARNESS.md Roles.

## Decisions
- Delete `.harness/runner/executors/cline.py`. KEEP `cline_acp.py`, `llama.py`, `--session` (all in real use).
- After change `--executor cline` and `--planner cline` are unknown (cline-acp remains for both).
- Remove only plain `cline` mentions; every `cline-acp` / `CLINE_MODEL` / `HARNESS_CLINE*` / "Cline CLI" reference needed by cline-acp stays. Reword shared lines, e.g. "cline, cline-acp, llama" -> "cline-acp, llama".
- Remove prose used only by cold cline: FALLBACK_MODELS probe, `CLINE_COMMAND_PERMISSIONS`, global plan/act settings, `has_sessions False` notes, "executors pi, opencode and cline".
- `has_sessions` in base.py stays; drop "(cline today)" from its comment.
- Do not touch `.harness/plans/**` (except this plan), `docs/flows.html`, `docs/mode-runner.svg`, `.worktrees`.

Verified: llama used outside bench copies: selftest.py:213, README, .env.example, tests/test_llama_executor.py, bench/suite/suite.py (`rg -n llama`)
Verified: `--session` used: cli.py, run_plan.py usage, bench.py:499, docs/FLOWS.md:87 (`rg -n -- --session`)
Verified: cline.py imported only by executors/__init__.py (`git grep -n "executors.cline"`)
Unverified: llama and --session NOT removed (usage found); the "bench copies only" premise was wrong.
Unverified: register.tsx has no tsc check here.
Later: docs/flows.html (7 hits) and docs/mode-runner.svg (1) still mention cline.
Later: .harness/runner/guards.py:83 comment lists cline.
Note: .harness/HARNESS.md is dirty in git; commit it before running (clean tree required).

## interfaces
`runner.executors.REGISTRY` keys after: pi, claude, cline-acp, opencode, llama.

## T1 Remove runner cline
FILES: .harness/runner/executors/cline.py, .harness/runner/executors/__init__.py, .harness/runner/executors/base.py, .harness/runner/cli.py, .harness/runner/watch.py, .harness/runner/planner.py, .harness/selftest.py, .claude/skills/harness-band/hooks/register.tsx
MUST:
- Delete cline.py; drop its import and REGISTRY entry.
- cli.py: `--executor` help and `--planner` help/allowed tuple drop plain cline; keep cline-acp.
- watch.py EXECUTORS and register.tsx EXECUTORS drop 'cline'.
- selftest.py: drop the ("cline","cline") tuple; CLINE_MODEL note names only `--executor cline-acp`; base.py and planner.py comments no longer name cline.
TEST: python .harness/plans/prune-executors/checks/check_t1.py && npx tsc --noEmit --incremental --tsBuildInfoFile .harness/tsc.tsbuildinfo

## T2 Prune bench arms
FILES: bench/suite/suite.py, bench/suite/cells.py, bench/suite/README.md, bench/speed/duel.py, tests/test_harness_suite.py
MUST:
- suite.py EXECUTORS, cells.py EXECUTOR_MODELS, README example drop `cline` (keep cline-acp).
- duel.py: remove the plain `cline` arm (harness name, model defaults, `--json` branch, validation sets); cline-acp arm intact.
- No quoted `"cline"` left in suite.py, cells.py, duel.py (a `shutil.which("cline")` lookup may stay).
- tests/test_harness_suite.py: replace plain "cline" cases with cline-acp; tests stay meaningful and pass.
TEST: python .harness/plans/prune-executors/checks/check_t2.py

## T3 Prune docs
FILES: README.md, docs/ARCHITECTURE.md, docs/FLOWS.md, docs/mermaid.md, packages/ufoz-harness/README.md, packages/ufoz-harness/kit_readme.md, .harness/.env.example
MUST:
- Remove cline executor rows/sections/bullets (README Executors list, ARCHITECTURE table row + `--executor cline` section + cold-cline notes, FLOWS row and `--session`-with-cline row).
- `.harness/.env.example`: planner line ("cline or cline-acp") and HARNESS_MODEL line ("pi, opencode and cline") drop plain cline.
- Counts ("All six") and lists like `pi|claude|opencode|cline-acp|llama` stay correct.
- cline-acp, llama, CLINE_MODEL, HARNESS_CLINE* docs remain.
TEST: python .harness/plans/prune-executors/checks/check_t3.py

## T4 Update Roles
FILES: .harness/HARNESS.md, .harness/MAIN.md
MUST:
- Roles paragraph (HARNESS.md) and matching paragraph in MAIN.md (~line 31): delete the `--executor cline` clause; cline-acp clause reads "`--executor cline-acp` the free Cline CLI over ACP (warm: ...)".
- MAIN.md ~line 71 "cline arm is always fresh" reworded or removed.
- Keep other uncommitted HARNESS.md edits.
TEST: python .harness/plans/prune-executors/checks/check_t4.py

## T5 Drop stale log
FILES: log.md
MUST:
- Delete the second `## 2026-09-29 oc-speed` section (lines ~111-120; all items already Fixed under `## 2026-09-30 oc-speed`) plus one blank line.
- No other line changes.
TEST: python .harness/plans/prune-executors/checks/check_t5.py

## T6 write summary
FILES: .harness/plans/prune-executors/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/prune-executors/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
