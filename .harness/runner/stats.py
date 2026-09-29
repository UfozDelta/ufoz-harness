"""Metrics rows, the price table, and --stats totals."""
import json
import os
import re
from pathlib import Path

from .procs import TOKEN_KEYS

HARNESS_AGENTS = ("planner", "reviewer", "validator")
PLAN_PATH = re.compile(r"\.harness[/\\]+plans[/\\]+([A-Za-z0-9_.-]+)[/\\]")
# $ per million tokens: (input, output, cache read). Source: claude-api skill price table,
# cached 2026-06-24. Cache writes: 1.25x input (5 min), 2x input (1 h). Unknown model -> no $.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20), "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-sonnet-5": (2.0, 10.0, 0.20), "claude-haiku-4-5": (1.0, 5.0, 0.10),
    "claude-fable-5-1": (10.0, 50.0, 0.25),
}


def write_task_metrics(plan_dir, task_id, row):
    """Write the per-task timing/token record and return its path."""
    items = Path(plan_dir) / "items"
    items.mkdir(parents=True, exist_ok=True)
    path = items / f"{task_id}.metrics.json"
    path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return path


def claude_agent_runs(project=None):
    """Planner/reviewer/validator subagent runs for this project, from Claude Code's own
    logs. Each request can be logged several times (one line per content block); only its
    last usage entry counts. Returns [] if the logs aren't there or the format changed."""
    project = Path(project or os.getcwd()).resolve()
    key = re.sub(r"[^A-Za-z0-9]", "-", str(project)).lower()
    root = Path.home() / ".claude" / "projects"
    dirs = [d for d in root.iterdir() if d.name.lower() == key] if root.is_dir() else []
    runs = []
    for d in dirs:
        for meta in d.glob("*/subagents/*.meta.json"):
            try:
                agent = json.loads(meta.read_text(encoding="utf-8")).get("agentType")
                if agent not in HARNESS_AGENTS:
                    continue
                last, writes, model = {}, {}, None
                for line in meta.with_name(meta.name.replace(".meta.json", ".jsonl")).open(encoding="utf-8"):
                    e = json.loads(line)
                    msg = e.get("message")
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("usage"):
                        last[e.get("requestId")] = msg["usage"]
                        model = msg.get("model") or model
                    for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
                        # attribute to the plan the agent WROTE to, not ones it merely read
                        if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in ("Write", "Edit"):
                            m = PLAN_PATH.search(str((c.get("input") or {}).get("file_path", "")))
                            if m:
                                writes[m.group(1)] = writes.get(m.group(1), 0) + 1
                slug = max(writes, key=writes.get) if writes else None
            except (OSError, ValueError, AttributeError):
                continue
            tok = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0}
            price = PRICES.get(model)
            for u in last.values():
                cw = u.get("cache_creation") or {}
                w5 = cw.get("ephemeral_5m_input_tokens", 0) or 0
                w1h = cw.get("ephemeral_1h_input_tokens", 0) or 0
                if not cw:
                    w5 = u.get("cache_creation_input_tokens", 0) or 0
                tok["input"] += u.get("input_tokens", 0) or 0
                tok["output"] += u.get("output_tokens", 0) or 0
                tok["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
                tok["cache_write"] += w5 + w1h
                if price:
                    pin, pout, pread = price
                    tok["cost"] += (u.get("input_tokens", 0) or 0) * pin / 1e6 \
                        + (u.get("output_tokens", 0) or 0) * pout / 1e6 \
                        + (u.get("cache_read_input_tokens", 0) or 0) * pread / 1e6 \
                        + (w5 * 1.25 + w1h * 2.0) * pin / 1e6
            runs.append({"agent": agent, "slug": slug or "(unattributed)", "model": model,
                         "priced": bool(price), **tok})
    return runs


def print_stats(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    by = {}
    for r in rows:
        if r.get("kind") in ("review", "plan_event"):
            continue
        agg = by.setdefault(r["slug"], {"tasks": 0, "passed": 0, "attempts": 0, "seconds": 0.0,
                                         "cost": 0.0, **dict.fromkeys(TOKEN_KEYS, 0)})
        agg["tasks"] += 1
        agg["passed"] += r["result"] == "pass"
        agg["attempts"] += r["attempts"]
        agg["seconds"] += r["seconds"]
        for k in (*TOKEN_KEYS, "cost"):
            agg[k] += r["tokens"].get(k, 0)
    for slug, a in by.items():
        print(f"{slug}: {a['passed']}/{a['tasks']} task runs passed, {a['attempts']} executor runs, "
              f"{a['seconds']:.0f}s, tokens in {a['input']} out {a['output']} "
              f"reasoning {a['reasoning']} cache-read {a['cache_read']}, ${a['cost']:.4f}")
    if not by:
        print(f"executor: no runs yet ({path})")
    for r in rows:
        if r.get("kind") == "review":
            t = r["tokens"]
            print(f"{r['slug']}: review (claude -p) {r['seconds']:.0f}s, tokens in {t['input']} out {t['output']} "
                  f"cache-read {t['cache_read']}, ${t['cost']:.4f} (exact)")
    last_runs = {}
    for r in rows:
        if r.get("kind") == "plan_event" and r.get("event") == "run_end":
            prev = last_runs.get(r["slug"])
            if prev is None or r["ts"] > prev["ts"]:
                last_runs[r["slug"]] = r
    for slug, r in sorted(last_runs.items()):
        print(f"{slug}: last run {r['ts']} -> {r['result']}")
    runs = claude_agent_runs()
    if not runs:
        print("claude subagents: none found in Claude Code logs for this project")
    agg = {}
    for r in runs:
        a = agg.setdefault((r["slug"], r["agent"]), {"n": 0, "input": 0, "output": 0, "cache_read": 0,
                                                     "cache_write": 0, "cost": 0.0, "priced": True})
        a["n"] += 1
        a["priced"] &= r["priced"]
        for k in ("input", "output", "cache_read", "cache_write", "cost"):
            a[k] += r[k]
    for (slug, agent), a in sorted(agg.items()):
        money = f"~${a['cost']:.2f} (estimate)" if a["priced"] else "$? (model not in price table)"
        print(f"{slug}: {agent} x{a['n']}, tokens in {a['input']} out {a['output']} "
              f"cache-read {a['cache_read']} cache-write {a['cache_write']}, {money}")
