# Plan: agents-md-role-split
## Goal
The MAIN session loads only MAIN rules; every executor loads only executor rules. AGENTS.md and
CLAUDE.md carry MAIN rules, executor rules live in .pi/executor.md, and each backend stops
auto-loading the other role's project rule files.

## Decisions
Verified: pi loads context files verbatim with no `@` import expansion (`rg loadContextFileFromDir dist/core/resource-loader.js` in the installed pi package); `--no-context-files` disables AGENTS.md/CLAUDE.md discovery (`docs/cli.md:168`); opencode `noproj` sets `OPENCODE_DISABLE_PROJECT_CONFIG=1` (`opencode.py:164-165`); CLAUDE.md ends with `@.harness/HARNESS.md`.  Unverified: the `--executor agent:haiku` subagent does not get CLAUDE_CODE_DISABLE_CLAUDE_MDS (spawned by the main session, not via run_claude_exec); its inline rules + git_guard hook may already suffice.  Later: MAIN.md/HARNESS.md still name the old executor model `opencode/muse-spark-1.3`.

- Model id is exactly `opencode/deepseek-v4.1-flash` wherever a default is set (pi.py, opencode.py, opencode.json orchestrator, .opencode/agent/planner.md).
- opencode profile name is exactly `noproj`; `HARNESS_OPENCODE_PROFILE` stays env-overridable.
- AGENTS.md carries MAIN-session rules (same rules text as `.harness/MAIN.md`), with no executor wording, plus a line telling the reader to also read `.harness/HARNESS.md` (pi does not expand `@` imports; this closes the pi-main parity gap). CLAUDE.md content is unchanged. `.harness/MAIN.md` is NOT edited here (the main session fixes its stale sentence separately).
- `.pi/executor.md`: keep existing text and style; append ONLY the missing executor bits (the quirks file `items/T<n>.quirks.md` as one line `what -> fix`; never edit `.harness/` because checks are hash-locked; write tests only when the task is the plan's final spec-tests task, build tasks are checked by a smoke command; the runner re-runs the acceptance command itself, the claim of success is ignored).
- claude.py: `_executor_prompt` returns `.pi/executor.md` only (remove every AGENTS.md reference, docstring included); BOTH `subprocess.Popen` calls pass exactly `env=dict(os.environ, CLAUDE_CODE_DISABLE_CLAUDE_MDS="1")`.
- opencode.json: add top-level `"instructions": [".harness/MAIN.md", ".harness/HARNESS.md"]`; orchestrator `model` becomes the model id.
- No new dependencies, no refactors beyond these edits.

## interfaces
- `Executor.run/probe`, `run_pi(...) -> (code, usage, session)`, `run_claude_exec(...)`, `opencode_config(deny_bash, profile)` signatures unchanged.
- `opencode.json` stays valid JSON; `agent.orchestrator` keeps its existing keys (only `model` changes) plus the new `instructions`.

## T1 main rules in AGENTS.md
FILES: AGENTS.md
MUST:
- AGENTS.md no longer contains executor rules; it carries the MAIN-session rules (same rules text as `.harness/MAIN.md`).
- AGENTS.md tells the reader to also read `.harness/HARNESS.md` (pi does not expand `@` imports; this closes the pi-main parity gap).
- no file outside FILES is touched.
TEST: python -c "from pathlib import Path; a=Path('AGENTS.md').read_text(encoding='utf-8'); assert 'You are the executor' not in a; assert 'Think before coding' in a; assert 'Plan -> execute loop' in a; assert '.harness/HARNESS.md' in a"

## T2 merge executor rules
FILES: .pi/executor.md
MUST:
- append only the missing executor bits; existing content and style are kept.
- mentions the quirks file `items/T<n>.quirks.md` as one line `what -> fix`, that `.harness/` checks are hash-locked, that tests are written only on the plan's final spec-tests task (build tasks use a smoke command), and that the runner re-runs acceptance.
TEST: python -c "from pathlib import Path; t=Path('.pi/executor.md').read_text(encoding='utf-8'); assert 'quirks.md' in t; assert 'hash-locked' in t; assert 'smoke command' in t; assert 're-runs the acceptance' in t"

## T3 pi executor
FILES: .harness/runner/executors/pi.py
MUST:
- `run_pi`'s command includes `--no-context-files` (adding it to quota_ok is optional).
- module `DEFAULT_MODEL` is exactly `opencode/deepseek-v4.1-flash`.
TEST: python -c "from pathlib import Path; t=Path('.harness/runner/executors/pi.py').read_text(encoding='utf-8'); ls=[l for l in t.splitlines() if l.startswith('DEFAULT_MODEL')]; assert ls and 'opencode/deepseek-v4.1-flash' in ls[0]; b=t.split('def run_pi',1)[1].split('def quota_ok',1)[0]; assert '--no-context-files' in b"

## T4 opencode executor
FILES: .harness/runner/executors/opencode.py
MUST:
- `HARNESS_OPENCODE_PROFILE` defaults to `noproj` and stays env-overridable.
- module `DEFAULT_MODEL` is exactly `opencode/deepseek-v4.1-flash`.
TEST: python -c "from pathlib import Path; t=Path('.harness/runner/executors/opencode.py').read_text(encoding='utf-8'); d=[l for l in t.splitlines() if l.startswith('DEFAULT_MODEL')]; assert d and 'opencode/deepseek-v4.1-flash' in d[0]; p=[l for l in t.splitlines() if 'HARNESS_OPENCODE_PROFILE' in l]; assert p and 'noproj' in p[0]"

## T5 claude executor
FILES: .harness/runner/executors/claude.py
MUST:
- `_executor_prompt` returns `.pi/executor.md` only; no `AGENTS.md` reference remains anywhere in the file (docstring included).
- both `subprocess.Popen` calls pass `env=dict(os.environ, CLAUDE_CODE_DISABLE_CLAUDE_MDS="1")`.
TEST: python -c "from pathlib import Path; t=Path('.harness/runner/executors/claude.py').read_text(encoding='utf-8'); assert 'AGENTS.md' not in t; assert t.count('CLAUDE_CODE_DISABLE_CLAUDE_MDS') == 2; assert t.count('env=dict(os.environ,') == 2"

## T6 backend configs
FILES: opencode.json, .opencode/agent/planner.md
MUST:
- opencode.json gains `"instructions": [".harness/MAIN.md", ".harness/HARNESS.md"]` and orchestrator model `opencode/deepseek-v4.1-flash`; still valid JSON.
- planner.md frontmatter `model:` is `opencode/deepseek-v4.1-flash`.
TEST: python -c "import json; from pathlib import Path; c=json.loads(Path('opencode.json').read_text(encoding='utf-8')); assert c['instructions'] == ['.harness/MAIN.md', '.harness/HARNESS.md']; assert c['agent']['orchestrator']['model'] == 'opencode/deepseek-v4.1-flash'; p=Path('.opencode/agent/planner.md').read_text(encoding='utf-8'); assert 'model: opencode/deepseek-v4.1-flash' in p"

## T7 write summary
FILES: .harness/plans/agents-md-role-split/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/agents-md-role-split/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
