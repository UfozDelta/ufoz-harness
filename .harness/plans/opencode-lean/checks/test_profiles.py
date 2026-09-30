"""HARNESS_OPENCODE_PROFILE: default | tools | agent | noproj (each stacks on the one before).
Skills stay available in every profile (the user wants them for frontend work)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".harness"))
from runner.executors import opencode as oc  # noqa: E402

TRIMMED = ("todowrite", "task", "websearch", "codesearch", "list", "lsp")


def test_default_profile_is_unchanged():
    cfg = oc.opencode_config([], "default")
    assert "executor" not in cfg["agent"]
    assert not any(cfg["permission"].get(t) == "deny" for t in TRIMMED)
    body = oc._prompt_body("opencode/m", "p", "SYS", "default")
    assert body["system"] == "SYS" and "agent" not in body


@pytest.mark.parametrize("profile", ["tools", "agent", "noproj"])
def test_trimmed_tools_are_denied_and_skills_kept(profile):
    perm = oc.opencode_config([], profile)["permission"]
    for tool in TRIMMED:
        assert perm.get(tool) == "deny", (profile, tool)
    assert perm.get("skill") != "deny"


@pytest.mark.parametrize("profile", ["agent", "noproj"])
def test_agent_profiles_replace_the_default_prompt(profile):
    cfg = oc.opencode_config([], profile)
    agent = cfg["agent"]["executor"]
    assert agent["mode"] == "primary"
    assert Path(".pi/executor.md").read_text(encoding="utf-8").strip()[:80] in agent["prompt"]
    assert "parallel tool calls" in agent["prompt"]  # the batching line
    body = oc._prompt_body("opencode/m", "p", None, profile)
    assert body["agent"] == "executor"
    assert "system" not in body  # the rules live in the agent prompt, not sent twice
    assert oc._prompt_body("opencode/m", "p", "CUSTOM RULES", profile)["system"] == "CUSTOM RULES"


def test_only_noproj_disables_project_config(tmp_path):
    for profile in ("default", "tools", "agent"):
        assert "OPENCODE_DISABLE_PROJECT_CONFIG" not in oc._serve_env({}, tmp_path, "C:/x", profile)
    env = oc._serve_env({"KEEP": "1"}, tmp_path, "C:/x", "noproj")
    assert env["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"
    assert env["KEEP"] == "1" and env["XDG_CONFIG_HOME"] == str(tmp_path)
    for flag in ("OPENCODE_DISABLE_CLAUDE_CODE", "OPENCODE_DISABLE_EXTERNAL_SKILLS"):
        assert flag not in env  # skills stay


def test_unknown_profile_is_an_error(monkeypatch):
    monkeypatch.setenv("HARNESS_OPENCODE_PROFILE", "bogus")
    with pytest.raises(ValueError):
        oc.OpenCodeExecutor()
