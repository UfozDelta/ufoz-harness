# Plan: opencode-lean

## Goal
Env-gated opencode executor profiles for an A/B on turns/tokens/wall time. Default behaviour unchanged.

## Decisions
- `HARNESS_OPENCODE_PROFILE` = `default` (unset) | `tools` | `agent` | `noproj`; each includes the one
  before. Read once in `OpenCodeExecutor.__init__` into `self.profile`; any other value -> ValueError.
- `tools`: permission `deny` for todowrite, task, websearch, codesearch, list, lsp. `skill` is never
  denied (user keeps skills for frontend work).
- `agent`: config gets `agent.executor` = {"mode": "primary", "prompt": <.pi/executor.md text> + "\n\n" +
  BATCH_LINE}. BATCH_LINE = "Read the brief and every FILES entry in ONE response using parallel tool
  calls; batch independent edits; do not glob or list before writing a new file."
  The prompt body sends `"agent": "executor"` and no `system`, unless `run()` got custom `rules`, which
  are then sent as `system`.
- `noproj`: serve env adds `OPENCODE_DISABLE_PROJECT_CONFIG=1`. Never set OPENCODE_DISABLE_CLAUDE_CODE or
  OPENCODE_DISABLE_EXTERNAL_SKILLS.
- Signatures (the check imports them): `opencode_config(deny_bash, profile="default")`,
  `_prompt_body(model, prompt, system, profile="default")`,
  `_serve_env(base_env, config_dir, cwd, profile="default")` -> dict: base_env + XDG_CONFIG_HOME + PWD
  (+ the noproj flag). `start()` uses `_serve_env(os.environ, ...)`.
Verified: an agent `prompt` replaces opencode's provider prompt; `system` is appended (opencode binary,
LLMRequestPrep). The env flag exists in the binary.

## T1 profiles
FILES: .harness/runner/executors/opencode.py
MUST: implement the Decisions; `default` output identical to today's config and body.
TEST: python -m pytest .harness/plans/opencode-lean/checks/test_profiles.py -q

## T2 write summary
FILES: .harness/plans/opencode-lean/SUMMARY.md
MUST: <= 600 chars: what changed, which file. Add `BUILD: pass` if `python -m pytest tests -q` passes, else `BUILD: fail <first error>`.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/opencode-lean/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
