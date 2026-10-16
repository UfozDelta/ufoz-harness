"""verify-bench backends: the 3x3x3 orchestrator x planner x executor axes.

Pure data + command builders + the rule-role isolation check. Nothing here runs a
cell; `verify.py` is the only entry point. `preflight` deliberately imports the
suite lazily so `--dry` never pays for the executor registry / task discovery.
"""
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_DIR = REPO_ROOT / "bench" / "suite"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SUITE_DIR) not in sys.path:
    sys.path.insert(0, str(SUITE_DIR))

# The three axes of the matrix. Every combination is one cell (27 at reps 1).
ORCHESTRATORS = ["claude", "pi", "opencode"]
PLANNERS = ["claude", "pi", "opencode"]
EXECUTORS = ["claude", "pi", "opencode"]

# One model per backend, used when an arm is named without an explicit `:model`.
DEFAULT_MODELS = {
    "claude": "sonnet",
    "pi": "opencode/deepseek-v4.1-flash",
    "opencode": "opencode/deepseek-v4.1-flash",
}

# The orchestrator/planner "main" rules file, per backend.
MAIN_RULES = {
    "claude": "CLAUDE.md",
    "pi": "AGENTS.md",
    "opencode": "AGENTS.md",
}
# The single file the executor agent must follow.
EXECUTOR_RULES = ".pi/executor.md"

# Final results.csv column order; the resume slug goes in front of these.
COLUMNS = [
    "ts", "orchestrator", "planner", "executor", "rep", "status", "rules_ok",
    "plan_ok", "wall_s", "tasks_passed", "tasks_total", "plan_cost", "exec_cost",
    "harness_sha", "model", "seed",
]
CSV_FIELDS = ["slug"] + COLUMNS

RULES_FAILURES = REPO_ROOT / "bench" / "verify" / "rules_failures.log"


def _split_arm(arm):
    """An axis entry is either a backend name or an (backend, model) tuple."""
    if isinstance(arm, str):
        return arm, ""
    name, model = arm
    return name, model


def cell_slug(orchestrator, planner, executor, rep):
    return f"verify-{orchestrator}-{planner}-{executor}-r{rep}"


def build_matrix(orchestrators, planners, executors, reps, seed=0):
    """All (orchestrator, planner, executor, rep) cells, shuffled deterministically.

    Each cell carries the resolved per-role models; `model` mirrors the executor's
    model because that is what the executor arm actually spends.
    """
    cells = []
    for orch in orchestrators:
        o_name, o_model = _split_arm(orch)
        for plan in planners:
            p_name, p_model = _split_arm(plan)
            for exe in executors:
                e_name, e_model = _split_arm(exe)
                for rep in range(1, reps + 1):
                    cells.append({
                        "orchestrator": o_name,
                        "planner": p_name,
                        "executor": e_name,
                        "orchestrator_model": o_model or DEFAULT_MODELS.get(o_name, ""),
                        "planner_model": p_model or DEFAULT_MODELS.get(p_name, ""),
                        "executor_model": e_model or DEFAULT_MODELS.get(e_name, ""),
                        "model": e_model or DEFAULT_MODELS.get(e_name, ""),
                        "rep": rep,
                        "slug": cell_slug(o_name, p_name, e_name, rep),
                        "status": "pending",
                        "seed": seed,
                    })
    random.Random(seed).shuffle(cells)
    return cells


def orchestrator_command(backend, model, brief):
    """The fixed headless command that lets an orchestrator write the plan.

    `brief` is the whole prompt (spec + instructions); `model` may be "" for the
    opencode arm, whose fixed command does not take a model flag.
    """
    if backend == "claude":
        return ["claude", "-p", brief, "--allowedTools", "Bash,Read,Write,Edit",
                "--model", model]
    if backend == "pi":
        launcher = Path.home() / ".pi" / "agent" / "bin" / "pi-launcher.js"
        return ["node", str(launcher), "-p", brief, "--model", model]
    if backend == "opencode":
        return ["opencode", "run", "--agent", "orchestrator", brief]
    raise ValueError(f"unknown orchestrator backend: {backend!r}")


def preflight(backend, model=None):
    """True when the backend looks reachable. Lazily wraps suite.preflight_executor
    so importing backends does not pull in the executor registry."""
    from suite import preflight_executor  # noqa: E402  (lazy on purpose)

    return bool(preflight_executor(backend, model))


def check_rules(phase, backend, log_text, project):
    """Rule-role isolation for one phase of one cell.

    The main rules file must look like an orchestrator file ("think before coding",
    no executor marker); `.pi/executor.md` must look like an executor file. A plan
    log that names the executor file, or an exec log that names `AGENTS.md`, is a
    leak. Returns (ok, offending_line); offending_line is "" when ok. The caller
    (verify.py) owns appending `<slug>: <line>` to rules_failures.log, since only it
    knows the slug.
    """
    project = Path(project)
    main_name = MAIN_RULES.get(backend, "AGENTS.md")
    main_path = project / main_name
    if not main_path.is_file():
        return False, f"missing {main_name}"
    main_text = main_path.read_text(encoding="utf-8", errors="replace").lower()
    if "think before coding" not in main_text:
        return False, f"{main_name}: missing 'think before coding'"
    if "you are the implementer" in main_text:
        return False, f"{main_name}: contains executor marker"

    executor_path = project / EXECUTOR_RULES
    if not executor_path.is_file():
        return False, f"missing {EXECUTOR_RULES}"
    executor_text = executor_path.read_text(encoding="utf-8", errors="replace").lower()
    if "you are the implementer" not in executor_text:
        return False, f"{EXECUTOR_RULES}: missing 'you are the implementer'"

    phase = (phase or "").lower()
    forbidden = EXECUTOR_RULES if phase == "plan" else ("AGENTS.md" if phase == "exec" else "")
    if forbidden:
        for raw in (log_text or "").splitlines():
            if forbidden in raw:
                return False, raw.strip()
    return True, ""
