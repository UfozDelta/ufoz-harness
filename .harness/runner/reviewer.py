"""The --review pass: one cheap headless reviewer run over the plan's files."""
import json
import subprocess
import time
from pathlib import Path


def run_reviewer(plan, all_files, metrics, slug, timeout=300):
    """One cheap (sonnet) headless pass reviewing every file the plan touched
    against a fixed checklist (reviewer.md) — catches bug classes hidden
    tests structurally can't (e.g. a side effect wired from two code paths,
    each of which looks correct read in isolation). Not a blind A/B judge;
    see .claude/agents/reviewer.md vs validator.md for the split. Writes
    <plan>/REVIEW.md. Reuses the exact headless-claude invocation shape
    bench.py's run_claude() already uses (proven: stdin closed, explicit
    timeout, json parsed defensively)."""
    goal = (plan / "plan.md").read_text(encoding="utf-8") if (plan / "plan.md").exists() else "(no plan.md)"
    checklist = Path(".claude/agents/reviewer.md").read_text(encoding="utf-8")
    # strip the YAML frontmatter (between the first pair of "---" lines) — not
    # needed in the prompt, and a prompt starting with "-" gets misparsed as
    # a CLI flag by `claude -p` (confirmed: "error: unknown option '---...'")
    if checklist.startswith("---"):
        checklist = checklist.split("---", 2)[2].lstrip()
    prompt = (
        f"Reviewer instructions:\n{checklist}\n\n---\nPlan goal:\n{goal}\n\n"
        f"Files this plan touched:\n" + "\n".join(sorted(all_files)) +
        "\n\nReview them now per the checklist above."
    )
    cmd = ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json",
           "--dangerously-skip-permissions"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        (plan / "REVIEW.md").write_text("REVIEW: SKIPPED (timed out)\n", encoding="utf-8")
        return
    try:
        data = json.loads(r.stdout)
        text = data.get("result", r.stdout)
    except json.JSONDecodeError:
        data, text = {}, r.stdout + r.stderr
    (plan / "REVIEW.md").write_text(text, encoding="utf-8")
    u = data.get("usage", {})
    tokens = {"input": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
              "output": u.get("output_tokens", 0), "reasoning": 0,
              "cache_read": u.get("cache_read_input_tokens", 0), "cost": data.get("total_cost_usd", 0) or 0}
    with metrics.open("a", encoding="utf-8") as mf:
        mf.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "slug": slug, "task": "REVIEW",
                             "kind": "review", "result": "done", "attempts": 1,
                             "seconds": round(time.time() - t0, 1), "tokens": tokens}) + "\n")
