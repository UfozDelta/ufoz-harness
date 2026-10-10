# Plan: claude-agent-exec

## Goal
Haiku always runs as the `claude-executor` agent definition (not ad-hoc `claude -p` flags), in runner mode and in the bench, and a claude session is rotated once its context passes 100k tokens.

## Decisions
- `claude -p --agent claude-executor` runs the agent file `.claude/agents/claude-executor.md` as the session's agent (tools, frontmatter hook, system prompt). Verified the `--agent` flag exists; Unverified: the frontmatter PreToolUse hook fires when the agent is the main agent, and `--agent` combines with `--model`, `--session-id`, `--resume`, `--permission-mode`.
- Scope: model name contains "haiku" -> agent mode. Any other model keeps today's `claude -p` command. Opt-out `HARNESS_CLAUDE_AGENT=0`; force for all models `HARNESS_CLAUDE_AGENT=1`. Bench needs no change: arm `claude:haiku` / `claude:claude-haiku-5-5` takes the new path through `--executor-model`.
- Agent mode keeps the runner's per-task grading, retry, repair, scope and lock guards (same worktree/check/land as before). The agent prompt names the cwd as the worktree; the agent file says "ABSOLUTE worktree path", so the brief prompt passes `os.getcwd()`.
- Rotation: context size after a task = last assistant message usage `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. If it exceeds `HARNESS_CLAUDE_ROTATE` (default 100000, `0` disables), `run_claude_exec` returns session `""` (a falsy non-None value). `task_runner` keeps the old session only when the executor returns `None`: `session = res.session if res.session is not None else session`. Empty string then means the next task starts fresh (`if session:` is false). Applies to every claude model, not only haiku.
- Rotation loses nothing: tasks are graded by files and acceptance commands, not by chat memory. The brief of every task is self-contained.

## interfaces
- `claude.py`: `use_agent(model) -> bool`; `_claude_cmd(prompt, model, session, resume, rules=None)` adds `--agent claude-executor` and drops `--append-system-prompt` when `use_agent`; `ROTATE_TOKENS()` reads env; `run_claude_exec` unchanged signature.
- `task_runner.py`: one-line session rule above.

## T1 agent command
FILES: .harness/runner/executors/claude.py, tests/test_claude_executor.py
MUST: add `use_agent(model)` (haiku substring, env override per Decisions). In `_claude_cmd`, when `use_agent(model)`: include `--agent claude-executor`, keep `--model`, `--effort`, stream-json flags, `--setting-sources project,local`, `--strict-mcp-config`, `--permission-mode acceptEdits`, `--disallowedTools`, session flags; omit `--append-system-prompt` and `--allowedTools` (the agent file defines tools). In `run_claude_exec`, when `use_agent(model)`, append to the prompt ` Worktree (absolute): <os.getcwd()>.`. Non-haiku commands must be byte-identical to today's. Tests in tests/test_claude_executor.py: haiku cmd has `--agent` and no `--append-system-prompt`; sonnet cmd has neither `--agent` and still has `--append-system-prompt`; env `HARNESS_CLAUDE_AGENT=0` turns haiku off; `=1` turns sonnet on.
TEST: python -m pytest tests/test_claude_executor.py -q

## T2 session rotation
FILES: .harness/runner/executors/claude.py, .harness/runner/task_runner.py, tests/test_claude_executor.py, tests/test_task_runner.py
MUST: in `_handle_event` for `assistant` events store `state["ctx"]` = input + cache_creation + cache_read of `message.usage` (missing keys 0). `rotate_limit()` returns `int(os.environ.get("HARNESS_CLAUDE_ROTATE", 100000))`. At the end of `run_claude_exec`, if `0 < limit < state["ctx"]`, return session `""` instead of the session id (also for the error and rate-limit returns: keep the id there). In task_runner `_attempt`, replace `session = res.session or session` with `session = res.session if res.session is not None else session`. Add tests: `_handle_event` records ctx from an assistant event; with a fake `Popen`-free helper, test the decision as a pure function `rotated(ctx, limit) -> bool` (add it to claude.py); `HARNESS_CLAUDE_ROTATE=0` never rotates; task_runner keeps the old session for `None` and drops it for `""` (use the existing fake executor style in tests/test_task_runner.py).
TEST: python -m pytest tests/test_claude_executor.py tests/test_task_runner.py -q

## T3 summary
FILES: .harness/plans/claude-agent-exec/SUMMARY.md
MUST: write SUMMARY.md (<= 600 chars: what, which files, how wired). Then run the full suite as the build smoke.
TEST: python -m pytest tests -q -x
