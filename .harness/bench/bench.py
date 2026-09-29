"""Benchmark runner: one (task, arm) at a time.

Usage: python .harness/bench/bench.py run <task> <arm> [--rep N]
       python .harness/bench/bench.py score <task> <arm> [--rep N]
       python .harness/bench/bench.py plan <task> full|slim [--rep N]
       python .harness/bench/bench.py arm <task> A|P|C|S1|S2|S3 [--rep N]   (fast-muse experiment)

Copies the on-disk tracked and untracked files into a plain, git-free directory
(pi needs a self-contained project rather than folding this copy into the main
checkout).
Applies the arm's overlay files, copies the task's frozen plan in, runs
that arm's Claude session headless (`claude -p --output-format json`),
then scores the result against the task's hidden tests. Appends one row
to .harness/bench/runs/results.csv. Never commits, never touches the
main checkout.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / ".harness" / "bench"

sys.path.insert(0, str(ROOT / ".harness"))
import envfile  # noqa: E402
envfile.load_env()

ARM_PROMPTS = {
    "A": "Read CLAUDE.md and follow it: implement the frozen plan yourself, task by task.",
    "B": "Read CLAUDE.md and follow it: delegate each task to the executor subagent, in order.",
    "C": "Read CLAUDE.md and follow it: run the plan runner as an ordinary FOREGROUND "
         "Bash command (run_in_background must be false or omitted). It can take several "
         "minutes, longer than the Bash tool's default 120-second timeout, so you MUST "
         "pass an explicit timeout of at least 600000 (milliseconds) on that tool call, "
         "or the tool itself will force it to the background before it finishes — do not "
         "rely on the default. Do not launch it in the background: this is a single "
         "headless turn with no way to check on or resume a backgrounded command, so "
         "backgrounding it means the plan never finishes and you must not report it as "
         "running or as done. Only report a result once the "
         "foreground command has actually returned its exit code to you.",
}
ARM_PROMPTS["D"] = ARM_PROMPTS["C"]  # same runner call; only the plan differs (plan_slim/)
ARM_MODEL = {"A": "sonnet", "B": "haiku", "C": "haiku", "D": "haiku"}  # main-session model; B/C mostly orchestrate


def plan_dir(task, arm):
    """Arm D gets the slim plan (plan.md sections + tasks.json, no items/ or checks/)."""
    return BENCH / "tasks" / task / ("plan_slim" if arm == "D" else "plan")


def worktree_path(task, arm, rep):
    return BENCH / "runs" / task / f"{arm}-{rep}"


def make_worktree(task, arm, rep, copy_plan=True, overlay_name=None):
    """Plain copy of the on-disk tracked and untracked files, with no .git."""
    wt = worktree_path(task, arm, rep)
    if wt.exists():
        shutil.rmtree(wt)
    wt.parent.mkdir(parents=True, exist_ok=True)
    wt.mkdir()
    files = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8", "replace").split("\0")
    for rel in files:
        # never ship hidden tests / other runs into a builder's copy; skills are copied below (symlinks resolved)
        if not rel or rel.startswith((".harness/bench/", "packages/", ".claude/skills/", ".agents/", "harness-speed-test/")):
            continue
        src, dst = ROOT / rel, wt / rel
        if not src.is_file():  # tracked but deleted on disk
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # some tasks build on a prior task's output (e.g. "large" extends "medium"'s
    # app/); the git baseline never includes generated code, so seed it from a
    # known-good reference copy instead
    seed = BENCH / "tasks" / task / "seed"
    if seed.exists():
        shutil.copytree(seed, wt, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".next"))
    if (wt / "package-lock.json").exists():  # Node seeds ship a lockfile, not node_modules
        subprocess.run("npm ci --no-audit --no-fund", cwd=wt, shell=True, check=True,
                       capture_output=True, timeout=900)
    # design skills are untracked (not in HEAD); copy them in, symlinks resolved
    skills = ROOT / ".claude" / "skills"
    if skills.exists():
        shutil.copytree(skills, wt / ".claude" / "skills", dirs_exist_ok=True)

    overlay = BENCH / "arms" / (overlay_name or arm)
    (wt / "CLAUDE.md").write_bytes((overlay / "CLAUDE.md").read_bytes())
    if (overlay / "executor.md").exists():
        (wt / ".claude" / "agents" / "executor.md").write_bytes((overlay / "executor.md").read_bytes())

    # same destination for every arm, matching real (non-bench) convention,
    # so a single acceptance path in tasks.json/T<n>.md works for all arms
    if copy_plan:
        plan_src = plan_dir(task, arm)
        plan_dst = wt / ".harness" / "plans" / "bench-plan"
        shutil.copytree(plan_src, plan_dst, dirs_exist_ok=True)
    return wt


def run_claude(wt, arm):
    log = wt / "claude_run.json"
    cmd = ["claude", "-p", ARM_PROMPTS[arm], "--model", ARM_MODEL[arm],
           "--output-format", "json", "--dangerously-skip-permissions"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=5400)
    wall_s = time.time() - t0
    log.write_text(r.stdout, encoding="utf-8")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"is_error": True, "result": r.stdout[-2000:] + "\n" + r.stderr[-2000:]}
    data["_wall_s"] = wall_s
    return data


NOISE_DIRS = ("__pycache__\\", "__pycache__/", ".pytest_cache\\", ".pytest_cache/")


def snapshot(wt):
    """relpath -> mtime+size, for baseline files present before the arm ran.
    Skips Python cache dirs, which are real but not signal for a code-quality diff."""
    return {str(p.relative_to(wt)): (p.stat().st_mtime_ns, p.stat().st_size)
            for p in wt.rglob("*") if p.is_file()
            and not str(p.relative_to(wt)).startswith(NOISE_DIRS)}


def diff_stat(before, after):
    added = sorted(p for p in after if p not in before)
    changed = sorted(p for p in after if p in before and after[p] != before[p])
    removed = sorted(p for p in before if p not in after)
    return (f"added: {added}\nchanged: {changed}\nremoved: {removed}").strip()


def plan_complete(wt):
    """True only if every task in tasks.json has a report.md saying RESULT: pass.
    Guards against a partial run (e.g. arm C stopping mid-plan) still scoring
    full marks because the hidden tests happened not to need the missing task."""
    plan = wt / ".harness" / "plans" / "bench-plan"
    tj = plan / "tasks.json"
    if not tj.exists():
        return True  # arm doesn't use run_plan.py (e.g. arm A); nothing to check here
    tasks = json.loads(tj.read_text(encoding="utf-8"))["tasks"]
    for t in tasks:
        rep = plan / "items" / f"{t['id']}.report.md"
        if not rep.exists() or "RESULT: pass" not in rep.read_text(encoding="utf-8"):
            return False
    return True


def score(wt, task):
    hidden = BENCH / "tasks" / task / "hidden_tests"
    dst = wt / "_hidden_tests"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(hidden, dst)
    r = subprocess.run([sys.executable, "-m", "pytest", "_hidden_tests", "-q"],
                       cwd=wt, capture_output=True, text=True, timeout=1500)
    out = r.stdout + r.stderr
    import re
    mp = re.search(r"(\d+) passed", out)
    mf = re.search(r"(\d+) failed", out)
    ferr = re.search(r"(\d+) error", out)
    passed = int(mp.group(1)) if mp else 0
    failed = int(mf.group(1)) if mf else 0
    errors = int(ferr.group(1)) if ferr else 0
    # r.returncode 5 = pytest collected zero tests (e.g. app/ import failed);
    # that's a hard failure, not a 0/0 pass, or a silently-green scorer lies.
    collected_none = r.returncode == 5 or (passed == 0 and failed == 0 and errors == 0)
    if collected_none:
        failed = max(failed, 1)
    return {"hidden_passed": passed, "hidden_failed": failed + errors,
            "collected_none": collected_none, "pytest_tail": out[-1500:]}


def review(wt, task, arm, timeout=900, files=None):
    """Cheap sonnet single-pass reviewer, run on BOTH arms so the comparison
    stays fair — arm A never calls run_plan.py's --review itself (A doesn't
    use run_plan.py at all), so without this, only arm C would ever get the
    safety net. Mirrors .harness/run_plan.py's run_reviewer(), reimplemented
    here with cwd=wt so Read/Grep resolve against the worktree, not bench.py's
    own cwd, and copies reviewer.md in directly (it may not be committed yet,
    so it won't be in the worktree copy make_worktree() already did)."""
    reviewer_md = ROOT / ".claude" / "agents" / "reviewer.md"
    dst = wt / ".claude" / "agents" / "reviewer.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(reviewer_md.read_bytes())

    checklist = reviewer_md.read_text(encoding="utf-8")
    # strip YAML frontmatter — a prompt starting with "-" gets misparsed as a
    # `claude` CLI flag (confirmed: "error: unknown option '---...'")
    if checklist.startswith("---"):
        checklist = checklist.split("---", 2)[2].lstrip()

    plan = wt / ".harness" / "plans" / "bench-plan"
    if files is None:
        tasks = json.loads((plan / "tasks.json").read_text(encoding="utf-8"))["tasks"]
        files = {f for t in tasks for f in t.get("files", [])}
    all_files = sorted(files)
    goal = ((plan / "plan.md").read_text(encoding="utf-8") if (plan / "plan.md").exists()
            else (BENCH / "tasks" / task / "spec.md").read_text(encoding="utf-8"))
    prompt = (f"Reviewer instructions:\n{checklist}\n\n---\nPlan goal:\n{goal}\n\n"
              f"Files this plan touched:\n" + "\n".join(all_files) +
              "\n\nReview them now per the checklist above.")
    cmd = ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json",
           "--dangerously-skip-permissions"]
    try:
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"review_text": "SKIPPED (timed out)", "review_cost_usd": 0.0}
    try:
        data = json.loads(r.stdout)
        text = data.get("result", r.stdout)
        cost = data.get("total_cost_usd", 0.0)
    except json.JSONDecodeError:
        text, cost = r.stdout + r.stderr, 0.0
    (wt / "REVIEW.md").write_text(text, encoding="utf-8")
    return {"review_text": text, "review_cost_usd": round(cost, 4)}


def append_csv(row):
    csv = BENCH / "runs" / "results.csv"
    header = ("task,arm,rep,cost_usd,wall_s,turns,hidden_passed,hidden_failed,plan_complete,"
              "is_error,review_cost_usd,review_flag\n")
    if not csv.exists():
        csv.write_text(header, encoding="utf-8")
    with open(csv, "a", encoding="utf-8") as f:
        f.write(",".join(str(row[k]) for k in
                 ["task", "arm", "rep", "cost_usd", "wall_s", "turns", "hidden_passed",
                  "hidden_failed", "plan_complete", "is_error", "review_cost_usd", "review_flag"]) + "\n")


def run_planner_arm(task, variant, rep):
    """Measure the Opus planner itself: fresh worktree with no plan, Opus plans from the
    task's spec.md under planner_<variant>.md, then run_plan.py executes that plan directly
    (no Haiku orchestrator) and the hidden tests score it. Row -> runs/plan_results.csv."""
    wt = make_worktree(task, "P", f"{variant}-{rep}", copy_plan=False, overlay_name="PLAN")
    shutil.copy2(ROOT / ".harness" / "CHECK_PATTERNS.md", wt / ".harness" / "CHECK_PATTERNS.md")  # untracked
    body = (BENCH / "planners" / f"planner_{variant}.md").read_text(encoding="utf-8").split("---", 2)[2].lstrip()
    (wt / "planner_prompt.md").write_text(body, encoding="utf-8")
    spec = (BENCH / "tasks" / task / "spec.md").read_text(encoding="utf-8")
    prompt = (f"Write the plan for this spec. Use slug bench-plan. This is a benchmark: plan the WHOLE spec "
              f"in this one plan (every page and route, up to 10 tasks), no later phases.\n\n{spec}")
    cmd = ["claude", "-p", prompt, "--model", "opus", "--output-format", "json",
           "--append-system-prompt-file", "planner_prompt.md",
           "--allowedTools", "Read,Grep,Glob,Write,Bash", "--dangerously-skip-permissions"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800)
    plan_s = time.time() - t0
    (wt / "planner_run.json").write_text(r.stdout, encoding="utf-8")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"is_error": True}
    plan = wt / ".harness" / "plans" / "bench-plan"
    plan_bytes = sum(f.stat().st_size for f in plan.rglob("*") if f.is_file()) if plan.exists() else 0
    lint = subprocess.run([sys.executable, ".harness/run_plan.py", "bench-plan", "--lint"], cwd=wt,
                          capture_output=True, text=True, timeout=600)
    t1 = time.time()
    ex = subprocess.run([sys.executable, ".harness/run_plan.py", "bench-plan",
                         "--no-worktree", "--no-window"], cwd=wt,
                        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10800)
    exec_s = time.time() - t1
    (wt / "runner_out.txt").write_text(ex.stdout + ex.stderr, encoding="utf-8")
    sc = score(wt, task)
    complete = plan.exists() and plan_complete(wt)
    rv = review(wt, task, "P") if (plan / "tasks.json").exists() else {"review_text": "", "review_cost_usd": 0.0}
    u = data.get("usage", {})
    row = {"task": task, "variant": variant, "rep": rep,
           "plan_cost_usd": round(data.get("total_cost_usd", 0) or 0, 4),
           "plan_out_tokens": u.get("output_tokens", 0), "plan_turns": data.get("num_turns", -1),
           "plan_s": round(plan_s, 1), "plan_bytes": plan_bytes, "lint_ok": lint.returncode == 0,
           "exec_s": round(exec_s, 1), "plan_complete": complete,
           "hidden_passed": sc["hidden_passed"], "hidden_failed": sc["hidden_failed"] if complete else max(sc["hidden_failed"], 1),
           "review_cost_usd": rv["review_cost_usd"],
           "review_flag": "CONCERNS" if "CONCERNS" in rv["review_text"] else ("CLEAN" if "CLEAN" in rv["review_text"] else "UNKNOWN")}
    csv = BENCH / "runs" / "plan_results.csv"
    if not csv.exists():
        csv.write_text(",".join(row) + "\n", encoding="utf-8")
    with open(csv, "a", encoding="utf-8") as f:
        f.write(",".join(str(v) for v in row.values()) + "\n")
    print(json.dumps(row, indent=2))
    print("worktree:", wt)
    print("runner:", (ex.stdout + ex.stderr)[-800:])


# ---------------------------------------------------------------- fast-muse experiment (arm action)
# Six arms on the same spec per task. Rows -> runs/arms.csv. See .harness/bench/RESULTS.md.
ARMS = {"A", "P", "C", "S1", "S2", "S3", "S4", "L", "H"}  # L = lean plan, free executor; H = lean plan, Haiku executor  # S4 = optional combined arm: S3 planning + S1 warm, one session
PLAN_KIND = {"A": "slim", "C": "slim", "S1": "slim", "S2": "lanes", "L": "lean", "H": "lean"}
RUNNER_FLAGS = {"C": ["--fresh"], "S1": [], "S2": ["--parallel", "3"], "S3": ["--fresh"], "S4": [],
                "L": [], "H": ["--executor", "claude", "--executor-model", "haiku"]}
LANES_ADDENDUM = """

## Parallel execution (this plan runs with `run_plan.py --parallel 3`)
- Group the work into independent LANES that can be built at the same time. Tasks in different lanes must have
  disjoint `files`; a shared file (package.json, layout, globals.css, a shared lib) belongs to exactly ONE task, and
  tasks that need it list that task in `deps`.
- Add a dep only when a task truly needs another task's output. Keep lanes short and wide, not one long chain.
- A lane task's acceptance runs ONLY its own new test file(s); no build or typecheck there, because other lanes may be
  half-written while it runs.
- End with ONE task `integrate` that depends on every other task. Its acceptance runs the full build/typecheck and the
  full test suite (each test file in its own command). Its files are whatever glue it may need to fix; keep it small.
"""
S3_PROMPT = ("You are the PLANNER for this run, not the executor: the executor rules about briefs do not apply to "
             "this step. Read SPEC.md and the planning rules in plan_draft/RULES.md. Explore the project read-only. "
             "Then write a plan for the WHOLE spec (every page and route, up to 10 tasks, no later phases) as "
             "plan_draft/plan.md and plan_draft/tasks.json, using slug bench-plan. Paths inside the plan are relative "
             "to the project root; the harness will move the plan to .harness/plans/bench-plan/ and lint it, so skip the "
             "lint step and write nowhere except plan_draft/. Do not implement anything. Finish with DONE: or BLOCKED:.")
AUDIT_PROMPT = """You audit a build plan against its spec before any code is written. Be strict but brief.

SPEC:
{spec}

PLAN.md:
{plan}

TASKS.json:
{tasks}

Check: (1) every requirement in the spec (routes, validation rules, pages, pricing, design, build) is covered by some
task's MUST bullets; (2) every task's acceptance is a real shell command that fails before the work is done (a new
test file must be run in its own command, e.g. `node --test new.ts && node --test old.ts`) and tasks touching compiled
code chain the build/typecheck; (3) each task's files list includes its own test file and everything it will edit.
Reply with ONLY a JSON object: {{"ok": true|false, "gaps": ["one line per concrete gap"]}}"""


def _claude(prompt, cwd, model, timeout, extra=()):
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", *extra]
    t0 = time.time()
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                             timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        out = ""
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = {"is_error": True, "result": out[-2000:]}
    data["_s"] = time.time() - t0
    return data


def _muse(wt, prompt, log, session=None, timeout=1800):
    """One pi call outside the runner, for S3/S4 planning. Reuses the runner's run_pi,
    so rate limits are waited out the same way. Returns the session id."""
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("run_plan_lab", ROOT / ".harness" / "run_plan.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    cwd = os.getcwd()
    os.chdir(wt)
    try:
        while True:
            code, _, sid = rp.run_pi("", str(log) + ".part", timeout, session=session, raw_prompt=prompt)
            if code != 75:
                break
            rp.wait_for_quota(str(log) + ".part")
    finally:
        os.chdir(cwd)
    part = Path(str(log) + ".part")
    with open(log, "a", encoding="utf-8") as f:
        f.write(part.read_text(encoding="utf-8", errors="replace"))
    part.unlink()
    return sid or session


def _planner_body():
    body = (ROOT / ".claude" / "agents" / "planner.md").read_text(encoding="utf-8")
    return body.split("---", 2)[2].lstrip() if body.startswith("---") else body


def opus_plan(task, rep, kind):
    """One Opus planning run per (task, rep, kind), cached, so A/C/S1 build from the SAME plan.
    Every arm that uses it is charged its full cost and minutes."""
    cache = BENCH / "runs" / task / "_plans" / f"{kind}-{rep}"
    meta = cache / "meta.json"
    if meta.exists():
        return cache, json.loads(meta.read_text(encoding="utf-8"))
    wt = make_worktree(task, "plan", f"{kind}-{rep}", copy_plan=False, overlay_name="PLAN")
    (wt / "planner_prompt.md").write_text(_planner_body() + (LANES_ADDENDUM if kind == "lanes" else ""),
                                          encoding="utf-8")
    spec = (BENCH / "tasks" / task / "spec.md").read_text(encoding="utf-8")
    prompt = (f"Write the plan for this spec. Use slug bench-plan. This is a benchmark: plan the WHOLE spec in this one "
              f"plan (every page and route, up to 10 tasks), no later phases.\n\n{spec}")
    data = _claude(prompt, wt, "opus", 1800, ["--append-system-prompt-file", "planner_prompt.md",
                                               "--allowedTools", "Read,Grep,Glob,Write,Bash"])
    (wt / "planner_run.json").write_text(json.dumps(data), encoding="utf-8")
    src = wt / ".harness" / "plans" / "bench-plan"
    cache.mkdir(parents=True, exist_ok=True)
    for name in ("plan.md", "tasks.json"):
        if (src / name).exists():
            shutil.copy2(src / name, cache / name)
    if (src / "checks").exists():
        shutil.copytree(src / "checks", cache / "checks", dirs_exist_ok=True)
    info = {"usd": round(data.get("total_cost_usd", 0) or 0, 4), "min": round(data["_s"] / 60, 2),
            "turns": data.get("num_turns", -1), "ok": (cache / "tasks.json").exists()}
    meta.write_text(json.dumps(info), encoding="utf-8")
    return cache, info


def muse_plan(wt, task):
    """S3: Muse drafts the plan, a Haiku auditor checks it, Muse revises once; lint, Muse fixes once."""
    t0, usd = time.time(), 0.0
    draft = wt / "plan_draft"
    draft.mkdir(exist_ok=True)
    (draft / "RULES.md").write_text(_planner_body(), encoding="utf-8")
    log = wt / "muse_plan.log"
    sid = _muse(wt, S3_PROMPT, log)
    if (draft / "plan.md").exists() and (draft / "tasks.json").exists():
        audit = _claude(AUDIT_PROMPT.format(spec=(wt / "SPEC.md").read_text(encoding="utf-8"),
                                            plan=(draft / "plan.md").read_text(encoding="utf-8"),
                                            tasks=(draft / "tasks.json").read_text(encoding="utf-8")),
                        wt, "haiku", 600, ["--allowedTools", "Read"])
        usd += audit.get("total_cost_usd", 0) or 0
        text = audit.get("result", "")
        (wt / "audit_result.txt").write_text(text, encoding="utf-8")
        if '"ok": true' not in text.replace("'", '"').lower():
            (draft / "AUDIT.md").write_text(text, encoding="utf-8")
            sid = _muse(wt, "The plan auditor found gaps, listed in plan_draft/AUDIT.md. Revise plan_draft/plan.md "
                            "and plan_draft/tasks.json to close every real gap. Write nowhere else. Finish with DONE:.",
                        log, sid)
    plan = wt / ".harness" / "plans" / "bench-plan"
    lint_rc = 1
    for attempt in range(2):
        plan.mkdir(parents=True, exist_ok=True)
        for name in ("plan.md", "tasks.json"):
            if (draft / name).exists():
                shutil.copy2(draft / name, plan / name)
        if not (plan / "tasks.json").exists():
            break
        lint = subprocess.run([sys.executable, ".harness/run_plan.py", "bench-plan", "--lint"], cwd=wt,
                              capture_output=True, text=True, timeout=900)
        lint_rc = lint.returncode
        if lint_rc == 0 or attempt:
            break
        (draft / "LINT.md").write_text(lint.stdout + lint.stderr, encoding="utf-8")
        sid = _muse(wt, "`run_plan.py --lint` rejected the plan; its output is in plan_draft/LINT.md. Fix "
                        "plan_draft/plan.md and plan_draft/tasks.json (only there). Finish with DONE:.", log, sid)
    shutil.rmtree(draft, ignore_errors=True)
    for f in (plan / "items", plan / "logs"):
        shutil.rmtree(f, ignore_errors=True)
    return {"usd": round(usd, 4), "min": round((time.time() - t0) / 60, 2), "lint_ok": lint_rc == 0, "session": sid}


def _files_now(wt):
    skip = ("node_modules", ".next", "__pycache__", ".pytest_cache", ".git", "_hidden_tests")
    return {str(p.relative_to(wt)).replace("\\", "/"): p.stat().st_mtime_ns for p in wt.rglob("*")
            if p.is_file() and not any(part in skip for part in p.relative_to(wt).parts)}


def run_arm(task, arm, rep):
    import os
    label = os.environ.get("HARNESS_ARM_LABEL", arm)  # e.g. S1-bunny: same strategy, other executor model
    row = {"task": task, "arm": label, "rep": rep, "plan_usd": 0.0, "build_usd": 0.0, "review_usd": 0.0,
           "total_usd": 0.0, "plan_min": 0.0, "build_min": 0.0, "wall_min": 0.0, "hidden_passed": 0,
           "hidden_failed": 0, "retries": 0, "rate_limit_waits": 0, "plan_complete": True, "note": ""}
    copy_plan = arm in PLAN_KIND
    if copy_plan:
        cache, info = opus_plan(task, rep, PLAN_KIND[arm])
        row["plan_usd"], row["plan_min"] = info["usd"], info["min"]
    wt = make_worktree(task, label, rep, copy_plan=False, overlay_name="PS" if arm == "P" else
                       ("A" if arm == "A" else "PLAN"))
    shutil.copy2(BENCH / "tasks" / task / "spec.md", wt / "SPEC.md")
    plan = wt / ".harness" / "plans" / "bench-plan"
    if copy_plan:
        shutil.copytree(cache, plan, dirs_exist_ok=True, ignore=shutil.ignore_patterns("meta.json"))
    subprocess.run(["git", "init", "-q"], cwd=wt)  # the runner's files guard needs a repo, as in real use
    with open(wt / ".gitignore", "a", encoding="utf-8") as gi:  # what the ufoz installer appends in real projects
        gi.write("\n__pycache__/\n.pytest_cache/\n.harness/plans/*/logs/\n.harness/metrics.jsonl\n")
    before = _files_now(wt)

    if arm not in ("A", "P", "H"):  # start every free-model arm on a live quota; waits inside the run still count
        import importlib.util
        import os
        spec = importlib.util.spec_from_file_location("run_plan_lab", ROOT / ".harness" / "run_plan.py")
        rp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rp)
        cwd = os.getcwd()
        os.chdir(wt)
        try:
            if not rp.quota_ok(timeout=150):
                rp.wait_for_quota(str(wt / "quota_gate.log"))
        finally:
            os.chdir(cwd)
    flags = list(RUNNER_FLAGS.get(arm, []))
    if arm in ("S3", "S4"):
        info = muse_plan(wt, task)
        if arm == "S4" and info.get("session"):
            flags += ["--session", info["session"]]  # build in the same session that planned
        row["plan_usd"], row["plan_min"] = info["usd"], info["min"]
        if not info["lint_ok"]:
            row["note"] += "muse plan failed lint; "
    t0 = time.time()
    if arm in ("A", "P"):
        data = _claude("Read CLAUDE.md and follow it.", wt, "sonnet", 5400)
        (wt / "claude_run.json").write_text(json.dumps(data), encoding="utf-8")
        row["build_usd"] = round(data.get("total_cost_usd", 0) or 0, 4)
        if data.get("is_error"):
            row["note"] += "build session error; "
    else:
        r = subprocess.run([sys.executable, ".harness/run_plan.py", "bench-plan",
                            "--no-worktree", "--no-window", *flags], cwd=wt,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10800)
        (wt / "runner_out.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
        row["plan_complete"] = plan_complete(wt)
    row["build_min"] = round((time.time() - t0) / 60, 2)

    metrics = wt / ".harness" / "metrics.jsonl"
    if metrics.exists():
        for line in metrics.read_text(encoding="utf-8").splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            row["retries"] += m.get("attempts", 1) - 1
            row["build_usd"] += (m.get("tokens") or {}).get("cost", 0) or 0  # executor's own cost ($0 free, >0 Haiku)
        row["build_usd"] = round(row["build_usd"], 4)
    import re
    for lg in list((plan / "logs").glob("*.log")) + [wt / "muse_plan.log"]:
        if lg.exists():
            row["rate_limit_waits"] += len(re.findall(r"rate.?limit|too many requests|\b429\b",
                                                      lg.read_text(encoding="utf-8", errors="replace"), re.I))

    sc = score(wt, task)
    row["hidden_passed"] = sc["hidden_passed"]
    row["hidden_failed"] = sc["hidden_failed"] if row["plan_complete"] else max(sc["hidden_failed"], 1)
    after = _files_now(wt)
    changed = {f for f in after if before.get(f) != after[f]} - {"SPEC.md", "runner_out.txt", "claude_run.json"}
    changed = {f for f in changed if not f.startswith((".harness/", "muse_plan.log", "audit_result.txt"))}
    rv = review(wt, task, arm, files=None if (plan / "tasks.json").exists() else changed)
    row["review_usd"] = rv["review_cost_usd"]
    row["total_usd"] = round(row["plan_usd"] + row["build_usd"] + row["review_usd"], 4)
    row["wall_min"] = round(row["plan_min"] + row["build_min"], 2)
    csv = BENCH / "runs" / "arms.csv"
    if not csv.exists():
        csv.write_text(",".join(row) + "\n", encoding="utf-8")
    with open(csv, "a", encoding="utf-8") as f:
        f.write(",".join(str(v).replace(",", ";") for v in row.values()) + "\n")
    print(json.dumps(row, indent=2))
    print("worktree:", wt)
    if sc["hidden_failed"]:
        print(sc["pytest_tail"][-1200:])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "arm":
        ap = argparse.ArgumentParser()
        ap.add_argument("action")
        ap.add_argument("task")
        ap.add_argument("arm", choices=sorted(ARMS))
        ap.add_argument("--rep", type=int, default=1)
        a = ap.parse_args()
        run_arm(a.task, a.arm, a.rep)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        ap = argparse.ArgumentParser()
        ap.add_argument("action")
        ap.add_argument("task")
        ap.add_argument("variant", choices=["full", "slim"])
        ap.add_argument("--rep", type=int, default=1)
        a = ap.parse_args()
        run_planner_arm(a.task, a.variant, a.rep)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["run"])
    ap.add_argument("task")
    ap.add_argument("arm", choices=["A", "C", "D"])  # B (haiku->opencode) dropped: unreliable,
    # self-reported success it didn't do, 3 distinct ways across 3 runs. C is cheaper anyway.
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()

    wt = make_worktree(args.task, args.arm, args.rep)
    before = snapshot(wt)
    result = run_claude(wt, args.arm)
    after = snapshot(wt)
    sc = score(wt, args.task)
    sc["diff_stat"] = diff_stat(before, after)
    # only arm C actually drives run_plan.py / writes report.md; arm A implements
    # directly and is never expected to produce those, so the check doesn't apply
    complete = plan_complete(wt) if args.arm in ("C", "D") else True
    if not complete:
        # a partial run (e.g. stopped mid-plan) does not get to keep a hidden-test
        # pass just because the tests it did happen to satisfy didn't need the
        # missing task
        sc["hidden_failed"] = max(sc["hidden_failed"], 1)

    # run on BOTH arms, not gated by run_plan.py's own --review (arm A never
    # calls run_plan.py at all) — see review()'s docstring
    rv = review(wt, args.task, args.arm)
    review_flag = "CONCERNS" if "CONCERNS" in rv["review_text"] else (
        "CLEAN" if "CLEAN" in rv["review_text"] else "UNKNOWN")

    row = {
        "task": args.task, "arm": args.arm, "rep": args.rep,
        "cost_usd": round(result.get("total_cost_usd", 0), 4),
        "wall_s": round(result.get("_wall_s", 0), 1),
        "turns": result.get("num_turns", -1),
        "hidden_passed": sc["hidden_passed"], "hidden_failed": sc["hidden_failed"],
        "plan_complete": complete,
        "is_error": result.get("is_error", True),
        "review_cost_usd": rv["review_cost_usd"],
        "review_flag": review_flag,
    }
    append_csv(row)
    print(json.dumps(row, indent=2))
    print("worktree:", wt)
    print(sc["diff_stat"])
    if sc["hidden_failed"]:
        print(sc["pytest_tail"])
    if not complete:
        print("INCOMPLETE PLAN: not every task has RESULT: pass in its report.md")
    print("review:", wt / "REVIEW.md")


if __name__ == "__main__":
    main()
