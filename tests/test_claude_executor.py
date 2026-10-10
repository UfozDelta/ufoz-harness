"""Tests for the claude executor's command shape: agent mode vs plain `claude -p`."""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.executors import claude  # noqa: E402
from runner.executors.claude import _claude_cmd, use_agent  # noqa: E402


def _has(cmd, flag):
    return flag in cmd


def test_use_agent_follows_the_model_name(monkeypatch):
    monkeypatch.delenv("HARNESS_CLAUDE_AGENT", raising=False)
    assert use_agent("claude-haiku-5-5") is True
    assert use_agent("claude:haiku") is True
    assert use_agent("sonnet") is False


def test_use_agent_env_override(monkeypatch):
    monkeypatch.setenv("HARNESS_CLAUDE_AGENT", "0")
    assert use_agent("claude-haiku-5-5") is False
    monkeypatch.setenv("HARNESS_CLAUDE_AGENT", "1")
    assert use_agent("sonnet") is True


def test_haiku_runs_the_agent(monkeypatch):
    monkeypatch.delenv("HARNESS_CLAUDE_AGENT", raising=False)
    cmd = _claude_cmd("do it", "claude-haiku-5-5", "sid", False)
    assert _has(cmd, "--agent") and "claude-executor" in cmd
    assert not _has(cmd, "--append-system-prompt")
    assert cmd[cmd.index("--allowedTools") + 1] == "Bash"  # tools come from the agent file; Bash is pre-allowed
    # the rest of the invocation is unchanged
    assert "--model" in cmd and "claude-haiku-5-5" in cmd
    assert "--effort" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert cmd[cmd.index("--setting-sources") + 1] == "project,local"
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert "--disallowedTools" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "sid"


def test_sonnet_keeps_the_plain_command(monkeypatch):
    monkeypatch.delenv("HARNESS_CLAUDE_AGENT", raising=False)
    cmd = _claude_cmd("do it", "sonnet", "sid", False)
    assert not _has(cmd, "--agent")
    assert _has(cmd, "--append-system-prompt")
    assert _has(cmd, "--allowedTools")


def test_env_zero_turns_haiku_off(monkeypatch):
    monkeypatch.setenv("HARNESS_CLAUDE_AGENT", "0")
    cmd = _claude_cmd("do it", "claude-haiku-5-5", "sid", False)
    assert not _has(cmd, "--agent")
    assert _has(cmd, "--append-system-prompt")


def test_env_one_turns_sonnet_on(monkeypatch):
    monkeypatch.setenv("HARNESS_CLAUDE_AGENT", "1")
    cmd = _claude_cmd("do it", "sonnet", "sid", False)
    assert _has(cmd, "--agent")
    assert not _has(cmd, "--append-system-prompt")


def test_non_agent_command_is_unchanged(monkeypatch):
    monkeypatch.delenv("HARNESS_CLAUDE_AGENT", raising=False)
    assert _claude_cmd("p", "sonnet", "sid", True) == [
        "claude", "-p", "p",
        "--model", "sonnet",
        "--effort", claude.os.environ.get("HARNESS_VARIANT", "medium"),
        "--output-format", "stream-json", "--verbose",
        "--setting-sources", "project,local", "--strict-mcp-config",
        "--permission-mode", "acceptEdits",
        "--allowedTools", claude.ALLOWED_TOOLS,
        "--disallowedTools", claude._deny_bash(),
        "--append-system-prompt", claude._executor_prompt(),
        "--resume", "sid"]


def test_agent_prompt_names_the_worktree(monkeypatch, tmp_path):
    monkeypatch.delenv("HARNESS_CLAUDE_AGENT", raising=False)
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        raise claude.subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(claude.subprocess, "Popen", fake_popen)
    with pytest.raises(claude.subprocess.TimeoutExpired):
        claude.run_claude_exec("b.md", str(tmp_path / "log.txt"), 5, model="claude-haiku-5-5")
    assert f"Worktree (absolute): {claude.os.getcwd()}." in seen["cmd"][2]
    assert "Do ONLY this one task, then stop" in seen["cmd"][2]


def test_assistant_event_records_the_context_size():
    state = {"limited": False, "error": False, "ctx": 0}
    claude._handle_event(
        {"type": "assistant",
         "message": {"usage": {"input_tokens": 1200, "cache_creation_input_tokens": 3000,
                               "cache_read_input_tokens": 40000},
                     "content": []}},
        io.BytesIO(), {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cost": 0.0},
        state)
    assert state["ctx"] == 44200


def test_assistant_event_without_usage_counts_zero():
    state = {"limited": False, "error": False, "ctx": 0}
    claude._handle_event({"type": "assistant", "message": {"content": []}},
                         io.BytesIO(), {"input": 0, "output": 0, "reasoning": 0,
                                        "cache_read": 0, "cost": 0.0}, state)
    assert state["ctx"] == 0


def test_rotate_limit_reads_the_env(monkeypatch):
    monkeypatch.delenv("HARNESS_CLAUDE_ROTATE", raising=False)
    assert claude.rotate_limit() == 100000
    monkeypatch.setenv("HARNESS_CLAUDE_ROTATE", "5000")
    assert claude.rotate_limit() == 5000


def test_rotated_only_past_the_limit():
    assert claude.rotated(150000, 100000) is True
    assert claude.rotated(100000, 100000) is False
    assert claude.rotated(90000, 100000) is False


def test_rotate_zero_never_rotates(monkeypatch):
    monkeypatch.setenv("HARNESS_CLAUDE_ROTATE", "0")
    assert claude.rotate_limit() == 0
    assert claude.rotated(10_000_000, claude.rotate_limit()) is False


def test_rated_cost_matches_alias_and_full_id():
    from runner.executors import claude
    usage = {"input": 1_000_000, "output": 1_000_000, "cache_read": 1_000_000}
    assert claude.rated_cost("haiku", usage) == claude.rated_cost("claude-haiku-5-5", usage) == 0.61
    assert claude.rated_cost("sonnet", usage) is None


def test_assistant_event_logs_context_usage(tmp_path):
    import io
    from runner.executors import claude
    buf, state = io.BytesIO(), {"ctx": 0}
    event = {"type": "assistant", "message": {"usage": {"input_tokens": 5, "cache_read_input_tokens": 95,
                                                        "output_tokens": 7}, "content": []}}
    claude._handle_event(event, buf, {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cost": 0.0}, state)
    assert b"[usage] ctx=100 out=7" in buf.getvalue()


def test_agent_mode_allows_bash_but_keeps_the_deny_list():
    cmd = _claude_cmd("p", "haiku", "sid", False)
    assert cmd[cmd.index("--allowedTools") + 1] == "Bash"
    assert "--disallowedTools" in cmd and "--agent" in cmd
