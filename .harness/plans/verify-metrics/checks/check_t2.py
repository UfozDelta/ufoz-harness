"""Acceptance T2: new columns, json flags, and parse_stream for claude / pi / opencode."""
import json
import sys

sys.path.insert(0, "bench/verify")
import backends as b  # noqa: E402

for col in ("orch_wall_s", "orch_in", "orch_cache_write", "plan_cache_read", "exec_tool_calls",
            "orch_cost", "orch_turns", "plan_attempts", "plan_cached", "exec_attempts", "usage_json"):
    assert col in b.COLUMNS, col
assert b.COLUMNS[:16][0] == "ts" and "plan_cost" in b.COLUMNS and "exec_cost" in b.COLUMNS
assert b.CSV_FIELDS[0] == "slug"
assert len(b.build_matrix(b.ORCHESTRATORS, b.PLANNERS, b.EXECUTORS, 1)) == 27

assert "stream-json" in b.orchestrator_command("claude", "sonnet", "x")
assert "--verbose" in b.orchestrator_command("claude", "sonnet", "x")
pi_cmd = b.orchestrator_command("pi", "m", "x")
assert pi_cmd[pi_cmd.index("--mode") + 1] == "json"
assert "json" not in " ".join(b.orchestrator_command("opencode", "m", "x"))

claude = "\n".join([
    json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "hi"},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "AGENTS.md"}}]}}),
    "garbage line",
    json.dumps({"type": "result", "is_error": False, "result": "done", "num_turns": 3,
                "total_cost_usd": 0.25,
                "usage": {"input_tokens": 10, "output_tokens": 20,
                          "cache_read_input_tokens": 300, "cache_creation_input_tokens": 40}}),
])
usage, rendered = b.parse_stream("claude", claude)
assert (usage["in"], usage["out"], usage["cache_read"], usage["cache_write"]) == (10, 20, 300, 40), usage
assert usage["cost"] == 0.25 and usage["turns"] == 3 and usage["tool_calls"] == 1, usage
assert "[toolCall Read]" in rendered and "AGENTS.md" in rendered and "garbage line" in rendered

event = json.dumps({"type": "message_end", "message": {
    "role": "assistant",
    "usage": {"input": 5, "output": 6, "cacheRead": 70, "cacheWrite": 8, "cost": {"total": 0.01}},
    "content": [{"type": "text", "text": "ok"},
                {"type": "toolCall", "name": "Bash", "arguments": {"command": "ls"}}]}})
usage, rendered = b.parse_stream("pi", event + "\n" + event)
assert (usage["in"], usage["out"], usage["cache_read"], usage["cache_write"]) == (10, 12, 140, 16), usage
assert usage["turns"] == 2 and usage["tool_calls"] == 2 and abs(usage["cost"] - 0.02) < 1e-9, usage
assert "[toolCall Bash]" in rendered

usage, rendered = b.parse_stream("opencode", "plain text")
assert rendered == "plain text" and all(v is None for v in usage.values()), usage
usage, rendered = b.parse_stream("claude", "no json here")
assert all(v is None for v in usage.values()) and "no json here" in rendered
print("T2 OK")
