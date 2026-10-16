# Spec — AGENTS.md / CLAUDE.md role split (main-session rules vs executor rules)

## Goal
Stop the MAIN (orchestrator) session from loading EXECUTOR rules, and stop every executor
backend from loading MAIN-session rules. Each role must load exactly its own rules.

## Problem (verified)
- Root `AGENTS.md` holds EXECUTOR rules ("You are the executor..."). opencode and pi auto-load
  project `AGENTS.md` for the MAIN session (opencode uses `AGENTS.md` and ignores `CLAUDE.md`
  when both exist), so the main session wrongly gets executor rules.
- `CLAUDE.md` holds MAIN-session rules (ends with `@.harness/HARNESS.md`) and is read by Claude Code.
- Each backend auto-loads a different file: Claude Code -> `CLAUDE.md`; opencode and pi -> `AGENTS.md`.
- Executor rules are ALSO injected explicitly: `.pi/executor.md` (pi/opencode/claude plain mode) and
  `.claude/agents/claude-executor.md` (the `agent:haiku` mode has its own inline rules + a git_guard hook).

## Decisions (fixed — do not re-litigate)
1. BOTH `AGENTS.md` and `CLAUDE.md` carry MAIN-session rules. DO NOT delete `CLAUDE.md`
   (also required by `packages/ufoz-harness/export_kit.py:16` + `:42-44`,
   `packages/ufoz-harness/test/install.test.js:73`, and the Claude Code main path).
2. opencode does NOT expand `@file` imports: add `"instructions": [".harness/MAIN.md", ".harness/HARNESS.md"]`
   to the root `opencode.json`. The executor opencode uses the `noproj` profile (project config skipped),
   so this does not leak into executors.
3. Move the executor-only bits currently ONLY in `AGENTS.md` into `.pi/executor.md`: the quirks file
   (`items/T<n>.quirks.md`, one line `what -> fix`), "never edit `.harness/` (checks hash-locked)",
   "write tests ONLY when your task is the plan's final spec-tests task; build tasks are checked by a
   smoke command", and "the runner re-runs the acceptance command itself; your claim of success is
   ignored". Keep `.pi/executor.md`'s existing content and style; append only what is missing.
4. Stop executors auto-loading project rule files:
   - pi: add `--no-context-files` to the command in `run_pi` (`.harness/runner/executors/pi.py:56-61`);
     this also covers `llama`/`ollama` (PiExecutor subclasses). Adding it to `quota_ok` (`pi.py:156-161`)
     is optional (llama/ollama override `probe`).
   - opencode: default `HARNESS_OPENCODE_PROFILE` to `"noproj"` (`.harness/runner/executors/opencode.py:203`;
     `noproj` sets `OPENCODE_DISABLE_PROJECT_CONFIG=1` at `:164-165`, which gates `AGENTS.md` discovery).
     Keep it env-overridable.
   - claude: `_executor_prompt` (`.harness/runner/executors/claude.py:37-44`) must return `.pi/executor.md`
     only (stop reading/appending `AGENTS.md`); and pass
     `env=dict(os.environ, CLAUDE_CODE_DISABLE_CLAUDE_MDS="1")` to BOTH `subprocess.Popen` calls
     (`claude.py:158-160` and `claude.py:210`) — this disables Claude Code's `CLAUDE.md` AND `AGENTS.md`
     project-memory loading.
5. Use the paid model instead of the free defaults — set `opencode/deepseek-v4.1-flash`:
   - `.opencode/agent/planner.md` frontmatter `model:` -> `opencode/deepseek-v4.1-flash`
   - `opencode.json` orchestrator agent `model` -> `opencode/deepseek-v4.1-flash`
   - `DEFAULT_MODEL` in `.harness/runner/executors/pi.py` and `.harness/runner/executors/opencode.py`
     -> `opencode/deepseek-v4.1-flash`

## Files
- `AGENTS.md`
- `CLAUDE.md` (leave the `@.harness/HARNESS.md` mechanism intact; content stays MAIN rules)
- `.pi/executor.md`
- `.harness/runner/executors/pi.py`
- `.harness/runner/executors/opencode.py`
- `.harness/runner/executors/claude.py`
- `opencode.json`
- `.opencode/agent/planner.md`

## Must-haves / acceptance
- Every task is checked by a ONE-LINE smoke command that exits 0 only when the task is really done
  (no test suites, `red_first` off). Prefer `rg`/`python -c` assertions on the resulting file/command
  content, e.g. that `AGENTS.md` no longer says "You are the executor", that `pi.py` `run_pi` contains
  `--no-context-files`, that `opencode.py` defaults to `noproj`, that `claude.py` has
  `CLAUDE_CODE_DISABLE_CLAUDE_MDS` on both Popen calls and no longer reads `AGENTS.md`, that
  `.pi/executor.md` contains the merged bits, and that the model defaults are `opencode/deepseek-v4.1-flash`.
- The LAST task writes `.harness/plans/agents-md-role-split/SUMMARY.md` (<= 600 chars).
- `python .harness/run_plan.py agents-md-role-split --lint` passes.

## Constraints
- Never write `.ts`/`.tsx` extensions in import paths. No new dependencies. Match existing style.
  No refactors beyond the stated edits.

## Open item (flag it, do not silently drop)
- The `--executor agent:haiku` path spawns the `@claude-executor` subagent from the MAIN session (not via
  `run_claude_exec`), so the `CLAUDE_CODE_DISABLE_CLAUDE_MDS` env var in `claude.py` does NOT cover it.
  Inspect `.claude/settings.json` and `.claude/agents/claude-executor.md` (its inline rules + git_guard hook
  may already make it safe). Decide whether to add a task (e.g. set the env in the main-session launch or in
  `.claude/settings.json`) or list it under `Unverified:` / open questions.
