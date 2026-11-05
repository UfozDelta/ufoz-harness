# Plan: cleanup-backends
## Goal
Keep only executor backends pi (default), opencode, claude (`claude -p`). Remove llama, ollama, `agent:haiku` / @claude-executor path, their flags, env vars, tests, docs.

## Decisions
- Delete outright: `.harness/runner/executors/llama.py`, `ollama.py`, `.harness/runner/check.py`, `.claude/agents/claude-executor.md`, `tests/test_llama_executor.py`, `tests/test_ollama_executor.py`, `tests/test_check_main.py`.
- Keep `.harness/hooks/git_guard.py` (planner.md still registers it); only fix its docstring.
- claude executor: drop `use_agent`, `AGENT`, agent branch in `_claude_cmd` and prompt; always plain `claude -p` path. Drop env `HARNESS_CLAUDE_AGENT`. Keep `RATES` (haiku pricing) and `claude_agent_runs` in stats.py (planner/reviewer cost).
- `parse_backend(spec, allowed)` stays; cli passes `tuple(REGISTRY)` only; `--executor agent` becomes "unknown backend" error.
- Env removed: HARNESS_LLAMA_URL/MODEL, HARNESS_OLLAMA_URL/MODEL, HARNESS_CLAUDE_AGENT.
- Do NOT edit historical data: `bench/*/results.csv`, `RESULTS.md`, `bench/verify/usage/`, existing `.harness/plans/*`, existing `log.md` lines. log.md: append one new `## 2026-11-05 cleanup-backends` entry only.
- Verify-bench impact: none (no llama/ollama/agent rows in `bench/verify/results.csv`; `bench/verify/backends.py` untouched). `bench/suite` loses llama/ollama arms; no suite results rows reference them.
- Planner backends (pi/opencode/claude via executor registry) shrink automatically; keep `@planner` subagent and `--plan`.
- Acceptance helper: `python .harness/plans/cleanup-backends/checks/absent.py REGEX PATH...` (a `!`-prefixed PATH must not exist). All checks scripts use `red_first: false`.
Verified: llama/ollama in `executors/__init__.py` REGISTRY, `watch.py` EXECUTORS, `cli.py` help, `selftest.py:212`, `bench/suite/suite.py:31-36`, `harness-band/hooks/register.tsx:15` (`grep -rniE "llama|ollama"`)
Verified: `check.py` only imported by `cli.py` and `tests/test_check_main.py`, `tests/test_prepare.py` (`grep -rn "import check"`)
Unverified: `.harness/selftest.py` and pytest cannot run in this sandbox (doctor FAIL: no pytest, no pi); acceptances therefore use absence checks + import smoke, not selftest.
Unverified: `.harness/runner/worktree.py:142` comment about agent hooks; may serve planner `--agent`. Left alone.
Unverified: `docs/*.svg`, `docs/flows.html`, `docs/mermaid.md`, `docs/harness-improvements-*.md` mention claude-executor/llama; hand-drawn diagrams, left for main session.
Later: old `.harness/bench/` (arms, judge, planners, staged.py, bench.py), `bench/speed/`, `bench/suite/` are extra benches beyond verify-bench; recommend REMOVE as separate plan once owner confirms (referenced by selftest, kit installer, tests/test_harness_suite.py).

## interfaces
- `runner.executors.REGISTRY` = {"pi","claude","opencode"}; `get(name, model=...)` unchanged.
- `runner.cli.parse_backend(spec, allowed)` unchanged.
- `runner.executors.claude._claude_cmd(prompt, model, session, resume, rules)` unchanged signature, no agent mode.

## T1 drop llama ollama
FILES: .harness/runner/executors/llama.py, .harness/runner/executors/ollama.py, .harness/runner/executors/__init__.py, .harness/runner/watch.py, .harness/.env.example, tests/test_llama_executor.py, tests/test_ollama_executor.py
MUST: delete llama.py, ollama.py and both test files; registry keeps only pi/opencode/claude; watch.py EXECUTORS = ("pi","claude","opencode"); remove llama/ollama sections from .env.example; no other file edited.
TEST: python .harness/plans/cleanup-backends/checks/absent.py "llama|ollama" .harness/runner/executors/__init__.py .harness/runner/watch.py .harness/.env.example !.harness/runner/executors/llama.py !.harness/runner/executors/ollama.py !tests/test_llama_executor.py !tests/test_ollama_executor.py && python -c "import sys; sys.path.insert(0,'.harness'); from runner.executors import REGISTRY; assert set(REGISTRY)=={'pi','claude','opencode'}"

## T2 drop agent path
FILES: .harness/runner/cli.py, .harness/runner/check.py, .harness/runner/executors/claude.py, .harness/run_plan.py, .harness/hooks/git_guard.py, .claude/agents/claude-executor.md, tests/test_claude_executor.py, tests/test_prepare.py, tests/test_check_main.py, packages/ufoz-harness/export_kit.py
MUST: delete check.py, claude-executor.md, test_check_main.py; cli.py: remove `check` import, `_agent`, "agent" backend, llama/ollama/agent help text, `!= "agent"` guards; claude.py per Decisions; test_claude_executor.py keeps only tests still valid (plain command, usage/context events), drop agent tests; test_prepare.py: assert `--executor agent:haiku` now errors in parse_backend, drop agent asserts; run_plan.py docstring and git_guard.py docstring/export_kit.py drop claude-executor; `--executor agent:x` exits non-zero.
DEPS: T1
TEST: python .harness/plans/cleanup-backends/checks/absent.py "claude-executor|use_agent|agent:|_agent\(|llama|ollama|HARNESS_CLAUDE_AGENT" .harness/runner/cli.py .harness/runner/executors/claude.py .harness/run_plan.py .harness/hooks/git_guard.py packages/ufoz-harness/export_kit.py tests/test_claude_executor.py tests/test_prepare.py !.harness/runner/check.py !.claude/agents/claude-executor.md !tests/test_check_main.py && python -c "import sys; sys.path.insert(0,'.harness'); import runner.cli"

## T3 drop bench selftest refs
FILES: .harness/selftest.py, bench/suite/suite.py, tests/test_harness_suite.py, .claude/skills/harness-band/hooks/register.tsx
MUST: selftest.py tool loop only opencode; suite.py EXECUTORS = ["pi","opencode","claude"], drop llama/ollama URL entries; test_harness_suite.py removes llama/ollama tests (keep opencode/pi cases; rewrite the parallel-unsupported case to use a remaining executor or drop it); register.tsx EXECUTORS drops 'llama'. Historical results untouched.
DEPS: T1
TEST: python .harness/plans/cleanup-backends/checks/absent.py "llama|ollama" .harness/selftest.py bench/suite/suite.py tests/test_harness_suite.py .claude/skills/harness-band/hooks/register.tsx && python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) for f in ('.harness/selftest.py','bench/suite/suite.py','tests/test_harness_suite.py')]" && npx tsc --noEmit --incremental --tsBuildInfoFile .harness/tsc.tsbuildinfo

## T4 docs and log
FILES: .harness/HARNESS.md, .harness/MAIN.md, AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/FLOWS.md, packages/ufoz-harness/README.md, packages/ufoz-harness/kit_readme.md, log.md
MUST: remove every llama/ollama/`agent:haiku`/@claude-executor/"native executor" mention, the haiku-agent Loop paragraph in HARNESS.md, README sections "llama details", "ollama details", env table rows, Claude-mode agent flow; keep wording for pi/opencode/claude intact; HARNESS.md/MAIN.md/AGENTS.md stay equivalent. log.md: append only `## 2026-11-05 cleanup-backends` with one line per removal; no existing line changed.
DEPS: T2, T3
TEST: python .harness/plans/cleanup-backends/checks/absent.py "llama|ollama|claude-executor|agent:haiku" .harness/HARNESS.md .harness/MAIN.md AGENTS.md README.md docs/ARCHITECTURE.md docs/FLOWS.md packages/ufoz-harness/README.md packages/ufoz-harness/kit_readme.md && python -c "import subprocess; d=subprocess.check_output(['git','diff','--numstat','--','log.md'],text=True).split(); assert d[1]=='0', d"

## T5 write summary
FILES: .harness/plans/cleanup-backends/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
DEPS: T4
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/cleanup-backends/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
