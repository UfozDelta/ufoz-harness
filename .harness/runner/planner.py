"""Backend-neutral planner: a spec file in, a linted plan out, written by a pi/opencode/claude
executor running the planner contract (the rules from .claude/agents/planner.md, verbatim).

The executor may only touch the plan's own directory: any other changed path fails the
attempt. Lint failures are fed back into the same warm session (2 retries max).
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import guards
from .executors import get
from .lint import lint

PLANNER_MD = Path(".claude/agents/planner.md")
DEFAULT_BACKEND = "pi"
DEFAULT_MODEL = "opencode/space-bunny-free"
CLAUDE_MODEL = "sonnet"
# No cline entry on purpose: ClineExecutor picks its own model (the free ones are quota-capped,
# so it probes FALLBACK_MODELS). Pinning a default here handed the planner a capped model and
# bypassed that fallback.
BACKEND_MODELS = {"claude": CLAUDE_MODEL}
TIMEOUT = 1800
MAX_ATTEMPTS = 3


def _planner_body():
    """The planner contract with the YAML frontmatter stripped."""
    text = PLANNER_MD.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _, rest = text.partition("---")
        text = rest.partition("---")[2]
    return text.lstrip("\n")


def _contract(body):
    """The 'Layout' + 'Rules' sections of the contract, verbatim."""
    _, sep, rest = body.partition("## Layout")
    return f"## Layout{rest}" if sep else body


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _tasks(plan_dir):
    path = plan_dir / "tasks.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("tasks", [])
    except (ValueError, OSError):
        return []


def _out_of_scope(before, after, prefixes):
    changed = {f for f, h in (after or {}).items() if before is None or before.get(f) != h}
    changed |= set(before or {}) - set(after or {})
    return sorted(f for f in changed if not f.startswith(prefixes))


def _lint(plan_dir):
    """Run the linter, capture its output (that is the feedback the retry gets). Returns
    (ok, output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ok = not lint(plan_dir, _tasks(plan_dir), set())
    return ok, out.getvalue()


def _local_spec(plan_dir, spec_path):
    """Copy the spec into the plan dir so backends that deny reads outside the repo can
    read it. Returns the path to point PLAN_REQUEST.md at."""
    src = Path(spec_path)
    dst = plan_dir / "spec.md"
    try:
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    except OSError:
        return src
    return dst


def _build_map():
    """Keep .harness/context/REPO_MAP.md fresh: --check, and rebuild it if it is stale."""
    try:
        check = subprocess.run([sys.executable, ".harness/build_map.py", "--check"],
                               stdin=subprocess.DEVNULL, capture_output=True)
        if check.returncode == 0:
            return
        subprocess.run([sys.executable, ".harness/build_map.py"],
                       stdin=subprocess.DEVNULL, capture_output=True)
    except OSError:
        pass


def run_planner(slug, spec_path, plans_root=".harness/plans", backend=None, model=None) -> dict:
    """Plan `slug` from the spec at `spec_path`. Never raises for a normal lint failure:
    it returns the result dict (also written to <plan>/planner.json) with lint_ok False."""
    backend = backend or os.environ.get("HARNESS_PLANNER", DEFAULT_BACKEND)
    model = model or os.environ.get("HARNESS_PLANNER_MODEL")
    if model is None and backend in BACKEND_MODELS:
        model = BACKEND_MODELS[backend]
    plan_dir = Path(plans_root) / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "logs").mkdir(exist_ok=True)
    log = plan_dir / "logs" / "planner.log"
    feedback = plan_dir / "items" / "planner.feedback.md"
    local_spec = _local_spec(plan_dir, spec_path)
    request = _write(plan_dir / "PLAN_REQUEST.md",
                     f"Plan this work. The spec is at: {Path(local_spec).as_posix()}\nRead it first.\n\n{_contract(_planner_body())}")
    rules = _write(plan_dir / "planner_rules.md", _planner_body())

    _build_map()
    prefixes = (f"{plan_dir.as_posix()}/", ".harness/context/")
    before, attempts, usage, started = None, 0, {}, time.time()
    lint_ok, session = False, None
    with get(backend, model=model) as executor:
        model = getattr(executor, "model", None) or model  # the backend may resolve a fallback
        for attempt in range(MAX_ATTEMPTS):
            before = guards.snapshot()
            result = executor.run(request, log, TIMEOUT, feedback if attempt else None, session, rules=rules)
            attempts += 1
            session = result.session
            for key in ("input", "output", "reasoning", "cache_read"):
                usage[key] = usage.get(key, 0) + result.usage.get(key, 0)
            usage["cost"] = usage.get("cost", 0.0) + (result.usage.get("cost") or 0.0)
            stray = _out_of_scope(before, guards.snapshot(), prefixes)
            if stray:
                print(f"ERROR planner changed files outside the plan dir: {stray[:10]}")
                break
            lint_ok, output = _lint(plan_dir)
            if lint_ok and not ((plan_dir / "plan.md").exists() and _tasks(plan_dir)):
                lint_ok = False
                print("ERROR planner wrote no plan.md/tasks.json")
                output = "ERROR planner wrote no plan.md/tasks.json\n" + output
            if lint_ok or result.code != 0:
                break
            if attempt + 1 < MAX_ATTEMPTS:  # same warm session, the lint output as feedback
                _write(feedback, output)
                print(f"planner lint failed, retrying with feedback ({attempt + 2}/{MAX_ATTEMPTS})")

    data = {"backend": backend, "model": model, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seconds": round(time.time() - started, 1),
            "attempts": attempts, "tokens": {"input": usage.get("input", 0), "output": usage.get("output", 0),
                                             "reasoning": usage.get("reasoning", 0),
                                             "cache_read": usage.get("cache_read", 0),
                                             "cost": round(usage.get("cost", 0.0), 6)},
            "lint_ok": bool(lint_ok)}
    (plan_dir / "planner.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
