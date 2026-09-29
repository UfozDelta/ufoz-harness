# Plan: npx-package

## Goal
`npx ufoz-harness` installs the current harness into a project. Package restored from git
(`4c10f0b^`) into `packages/ufoz-harness/`; bring it up to date with the reworked harness.

## Decisions
1. Keep design: `export_kit.py` builds `kit/` (gitignored) from repo; `index.js` copies kit into
   target, backs up changed files to `.harness/backup/<ts>/`, appends `.gitignore` lines only.
2. Kit contents (explicit list, nothing else):
   - `CLAUDE.md`, `AGENTS.md`, `opencode.json`
   - `.claude/agents/planner.md`, `.claude/agents/reviewer.md` (NOT validator.md)
   - `.claude/settings.json` copied from repo `.claude/settings.json` (kit_settings.json no longer exists)
   - every dir in `.claude/skills/` (all skills), minus `__pycache__`
   - `.pi/deny.json`, `.pi/executor.md`, `.pi/extensions/deny-list.ts`, `.pi/extensions/deny-match.ts`
   - `.opencode/agent/` (whole dir), `.opencode/package.json`, `.opencode/package-lock.json` (NOT node_modules)
   - every dir in `.agents/skills/`, minus `__pycache__`; `skills-lock.json`
   - `.harness/run_plan.py`, `selftest.py`, `build_map.py`, `envfile.py`, `.env.example`, `MAIN.md`,
     `CHECK_PATTERNS.md`, and the whole `.harness/runner/` tree (`*.py` only, no `__pycache__`)
   - `.harness/README.md` from `kit_readme.md`; `.harness/plans/.gitkeep`
   - Never: `.opencode/node_modules`, `.harness/.env`, `bench/`, `context/`, `metrics.jsonl`, `tests/`, `*.test.mjs`.
3. `index.js` IGNORE_LINES gains `.harness/.env` (secrets); test file's IGNORE_LINES mirrors it.
4. package.json: version `0.3.0`, `scripts.prepack` = `python export_kit.py`, `scripts.test` =
   `node --test`; keep bin/files/engines. Description mentions pi executor (not opencode).

## T1 export + installer
FILES: export_kit.py, package.json, index.js, test/install.test.js (all under packages/ufoz-harness/)
MUST:
- export_kit.py produces exactly Decision 2's kit; missing source file -> exit 1 (keep fail_missing).
- Apply Decisions 3 and 4. Keep existing index.js flags/behavior otherwise.
TEST: check_t1.py (exports, checks kit list, runs node --test, installs into tmp and runs
`python .harness/run_plan.py --help` there, `npm pack --dry-run` lists kit files).

## T2 docs + summary
FILES: packages/ufoz-harness/README.md, kit_readme.md, THIRD_PARTY_NOTICES.md, .harness/plans/npx-package/SUMMARY.md
MUST:
- README Requirements: Node 18+, Python 3, git, pi (`~/.pi/agent/bin/pi-launcher.js` or `pi` on PATH);
  other executors optional. Add a "Publishing" section: `cd packages/ufoz-harness && npm publish`
  (prepack builds kit). Mention `.harness/.env.example`.
- kit_readme.md: fix anything stale vs repo README.md (six executors, `.harness/.env`,
  `build_map.py`); keep it short.
- THIRD_PARTY_NOTICES.md: add "anthropics/skills — https://github.com/anthropics/skills — Apache-2.0: frontend-design (LICENSE.txt shipped in the skill dir)"; fix header line that says every source is MIT.
- SUMMARY.md <= 600 chars: what, which files, how wired.
TEST: check_t2.py.
