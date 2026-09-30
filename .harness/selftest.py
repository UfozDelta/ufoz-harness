"""Check the harness works in this project, and optionally benchmark it.

Usage: python .harness/selftest.py            doctor + one smoke task via the harness ($0,
                                              fixed brief, no planner)
       python .harness/selftest.py --bench    fair A/B, logged to .harness/bench.csv: @planner
                                              plans once, then the SAME plan runs with each
                                              executor (pi vs claude sonnet), both with
                                              --review. Only who writes the code differs.
                                              ~$0.40-0.60 per run; only when you want numbers

Everything runs in throwaway git repos in the system temp dir; this project is never
touched except for the bench.csv rows. Both arms are graded by the same independent
check, run after they finish.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / ".harness"))
import envfile  # noqa: E402
envfile.load_env()

import run_plan  # noqa: E402  (reuses its Claude-log cost reader)
# the whole runner package the shim imports, so a new module is never left behind
RUNNER_COPY = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / ".harness/runner").rglob("*.py")
                     if "__pycache__" not in p.parts)
COPY = [".harness/run_plan.py", ".harness/envfile.py", ".pi/deny.json", ".pi/executor.md",
        ".pi/extensions/deny-list.ts", ".pi/extensions/deny-match.ts", "AGENTS.md", ".gitignore"] \
    + RUNNER_COPY
PLANNER_COPY = [".claude/agents/planner.md", ".harness/CHECK_PATTERNS.md"]
TASK = """Add `smoke/mathx.py` with a function `clamp(x, lo, hi)`: return `lo` if `x < lo`, `hi` if
`x > hi`, otherwise `x`; raise `ValueError` if `lo > hi`. Stdlib only, no other functions."""

BRIEF = """GOAL: Create `smoke/mathx.py` with a function `clamp(x, lo, hi)`.

FILES (create; touch nothing else):
- `smoke/mathx.py`

REQUIREMENTS:
- `clamp(x, lo, hi)` returns `lo` if `x < lo`, `hi` if `x > hi`, otherwise `x`.
- If `lo > hi`, raise `ValueError`.
- Stdlib only, no other functions.

ACCEPTANCE: `python .harness/plans/smoke/checks/check_t1.py` prints `SMOKE OK` and exits 0.

END: finish with `DONE: <files>` or `BLOCKED: <reason>`.
"""

CHECK = """import sys
sys.path.insert(0, "smoke")
try:
    from mathx import clamp
except ImportError as e:
    sys.exit(f"FAIL: {e}")
assert clamp(5, 0, 10) == 5 and clamp(-1, 0, 10) == 0 and clamp(11, 0, 10) == 10
assert clamp(0, 0, 0) == 0
try:
    clamp(1, 5, 0)
    sys.exit("FAIL: lo > hi must raise ValueError")
except ValueError:
    pass
print("SMOKE OK")
"""

TASKS = {"slug": "smoke", "tasks": [{"id": "T1", "brief": "items/T1.md", "deps": [], "files": ["smoke/mathx.py"],
                                     "acceptance": "python .harness/plans/smoke/checks/check_t1.py",
                                     "expect": "SMOKE OK"}]}


def sh(cmd, cwd, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=timeout, shell=isinstance(cmd, str))
        return r.returncode, r.stdout + r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def doctor():
    problems = []
    if sys.version_info < (3, 10):
        problems.append("python 3.10+ needed")
    for tool in ("git", "node"):
        if shutil.which(tool) is None:
            problems.append(f"{tool} not on PATH")
    try:
        import pytest  # noqa: F401  (the unit-test step below needs it)
    except ImportError:
        problems.append("pytest not importable (pip install pytest)")
    launcher = Path(os.environ.get("HARNESS_PI", str(Path.home() / ".pi" / "agent" / "bin" / "pi-launcher.js")))
    if not launcher.exists():
        problems.append(f"pi not found: {launcher}")
    for f in COPY:
        if not (ROOT / f).exists():
            problems.append(f"missing {f}")
    if not problems:
        model = os.environ.get("HARNESS_MODEL", "opencode/space-bunny-free")
        code, out = sh(["node", str(launcher), "--list-models", "opencode"], ROOT, timeout=90)
        models = {f"{fields[0]}/{fields[1]}" for line in out.splitlines() if len(fields := line.split()) > 1}
        if code != 0 or model not in models:
            problems.append(f"executor model {model} not listed by `pi --list-models opencode`")
    return problems


def scratch_repo(name):
    d = Path(tempfile.mkdtemp(prefix=f"harness-{name}-"))
    sh(["git", "init", "-q", "."], d)
    return d


def copy_into(d, files):
    for f in files:
        if (ROOT / f).exists():
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / f, d / f)


def claude_json(out):
    try:
        return json.loads(out[out.index("{"):])
    except ValueError:
        return {}


def write_fixed_plan(d):
    plan = d / ".harness/plans/smoke"
    (plan / "items").mkdir(parents=True)
    (plan / "checks").mkdir()
    (plan / "items/T1.md").write_text(BRIEF, encoding="utf-8")
    (plan / "checks/check_t1.py").write_text(CHECK, encoding="utf-8")
    (plan / "tasks.json").write_text(json.dumps(TASKS, indent=2), encoding="utf-8")


def make_plan():
    """@planner (headless) plans the task once; both bench arms then run that same plan."""
    d = scratch_repo("plan")
    copy_into(d, COPY + PLANNER_COPY)
    if (ROOT / ".claude/skills/caveman").is_dir():  # planner preloads it
        shutil.copytree(ROOT / ".claude/skills/caveman", d / ".claude/skills/caveman")
    prompt = ("Use the planner subagent to write the plan with slug `smoke` for the task below. "
              "Do not implement anything and do not run the plan; stop when the planner returns.\n\n" + TASK)
    t0 = time.time()
    code, out = sh(["claude", "-p", prompt, "--model", "haiku", "--output-format", "json",
                    "--dangerously-skip-permissions"], d, timeout=1800)
    # total_cost_usd should include the subagent; fall back to its own log if it doesn't
    cost = max(claude_json(out).get("total_cost_usd", 0) or 0,
               sum(r["cost"] for r in run_plan.claude_agent_runs(d)))
    # the planner may pick its own slug; take whatever plan it wrote
    plans = sorted((d / ".harness/plans").glob("*/tasks.json"))
    return (plans[0].parent if plans else None), round(cost, 4), round(time.time() - t0, 1), out[-300:]


def run_arm(executor, plan_src=None, review=False):
    """Run the smoke plan (planner-made if plan_src, else the fixed one) with one executor."""
    d = scratch_repo(executor)
    copy_into(d, COPY)
    slug = plan_src.name if plan_src else "smoke"
    if plan_src:
        shutil.copytree(plan_src, d / ".harness/plans" / slug,
                        ignore=shutil.ignore_patterns("logs", "plan.lock.json", "*.report.md", "*.feedback.md"))
        if review:
            copy_into(d, [".claude/agents/reviewer.md"])
    else:
        write_fixed_plan(d)
    t0 = time.time()
    cmd = [sys.executable, ".harness/run_plan.py", slug, "--executor", executor,
           "--no-worktree", "--no-window"] + (["--review"] if review else [])
    code, out = sh(cmd, d, timeout=1800)
    tok, review_cost = {}, 0.0
    mpath = d / ".harness/metrics.jsonl"
    for row in (mpath.read_text(encoding="utf-8").splitlines() if mpath.exists() else []):
        r = json.loads(row)
        if r.get("kind") == "review":
            review_cost += r["tokens"].get("cost", 0)
            continue
        if r.get("kind") == "plan_event":  # lifecycle rows carry no tokens
            continue
        for k, v in r["tokens"].items():
            tok[k] = tok.get(k, 0) + v
    # grade with an independent check, written only after the run
    (d / "_bench_check.py").write_text(CHECK, encoding="utf-8")
    graded, _ = sh([sys.executable, "_bench_check.py"], d)
    return {"arm": executor, "pass": code == 0 and graded == 0, "seconds": round(time.time() - t0, 1),
            "input_tokens": tok.get("input", 0), "output_tokens": tok.get("output", 0) + tok.get("reasoning", 0),
            "cache_read_tokens": tok.get("cache_read", 0), "exec_cost_usd": round(tok.get("cost", 0), 4),
            "review_cost_usd": round(review_cost, 4), "dir": d, "detail": out.strip()[-600:]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", action="store_true", help="also run Claude directly and log both to .harness/bench.csv")
    args = ap.parse_args()

    problems = doctor()
    if problems:
        print("doctor: FAIL\n" + "\n".join(f"  - {p}" for p in problems))
        sys.exit(1)
    print("doctor: OK")
    code, out = sh([sys.executable, "-m", "pytest", "tests", "-q"], ROOT, timeout=120)
    if code != 0:
        print(f"unit tests: FAIL\n{out}")
        sys.exit(1)
    print("unit tests: OK")
    for tool, needs in (("opencode", "opencode"), ("cline", "cline"), ("cline-acp", "cline"),
                        ("llama", "llama-server")):
        # optional: only the matching --executor needs it; cline-acp runs the same `cline` binary
        if shutil.which(needs) is None:
            print(f"  note: {needs} not on PATH (--executor {tool} unavailable)")
    if not os.environ.get("CLINE_MODEL"):
        print("  note: CLINE_MODEL unset (--executor cline / cline-acp use the default model)")
    if args.bench and shutil.which("claude") is None:
        sys.exit("--bench needs the `claude` CLI on PATH")

    if not args.bench:
        results = [run_arm("pi")]
    else:
        plan, plan_cost, plan_s, plan_out = make_plan()
        if plan is None:
            sys.exit(f"planner wrote no plan (${plan_cost} spent):\n{plan_out}")
        print(f"planner: plan written in {plan_s}s, ${plan_cost} (shared by both arms)")
        results = [run_arm("pi", plan, review=True), run_arm("claude", plan, review=True)]
        for r in results:
            r.update(plan_cost_usd=plan_cost, plan_seconds=plan_s)
    for r in results:
        r["cost_usd"] = round(r.get("plan_cost_usd", 0) + r["exec_cost_usd"] + r["review_cost_usd"], 4)
        extra = (f" = plan ${r['plan_cost_usd']} + exec ${r['exec_cost_usd']} + review ${r['review_cost_usd']}"
                 if args.bench else "")
        print(f"{r['arm']} executor: {'PASS' if r['pass'] else 'FAIL'} {r['seconds']}s, exec tokens in "
              f"{r['input_tokens']} out {r['output_tokens']} cache-read {r['cache_read_tokens']}, "
              f"${r['cost_usd']}{extra}")
        if r["pass"]:
            shutil.rmtree(r["dir"], ignore_errors=True)
        else:
            print(f"  kept for debugging: {r['dir']}\n  {r['detail']}")

    if args.bench:
        out = ROOT / ".harness/bench.csv"
        fields = ["ts", "executor", "pass", "plan_seconds", "exec_seconds", "input_tokens", "output_tokens",
                  "cache_read_tokens", "plan_cost_usd", "exec_cost_usd", "review_cost_usd", "cost_usd"]
        new = not out.exists()
        with out.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            if new:
                w.writeheader()
            for r in results:
                w.writerow({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "executor": r["arm"],
                            "exec_seconds": r["seconds"], **r})
        print(f"bench rows appended: {out}")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


if __name__ == "__main__":
    main()
