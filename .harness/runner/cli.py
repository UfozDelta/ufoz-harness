"""Command line: 18 flags, one of several executors behind them (`--executor backend:model`)."""
import argparse
import os
import sys
import time
from pathlib import Path

from . import check, land, pending, planner, scheduler, skills, status, watch, worktree
from .executors import get, REGISTRY
from .lint import lint
from .plan import PLANS_ROOT, Plan
from .report import record_plan_event
from .reviewer import run_reviewer
from .stats import print_stats
from .task_runner import State, TaskRunner

_ACTIVE_RUN_LOCK = None


def _acquire_run_lock(path):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid = path.read_text(encoding="utf-8").strip()
        except OSError:
            pid = "?"
        print(f"ERROR another run is in progress for {path.parent.name} (pid {pid}, {path}); delete it if that process is gone")
        sys.exit(1)
    with os.fdopen(fd, "w", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))


def build_parser():
    ap = argparse.ArgumentParser(allow_abbrev=False)  # old `--relock` must not mean `--relock-only`
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--review", nargs="?", const="", default=None, metavar="claude[:MODEL]",
                    help="After a fresh full pass, run one cheap review pass against reviewer.md's "
                         "checklist and write <plan>/REVIEW.md. Only claude; bare = sonnet. Put the "
                         "slug before --review.")
    ap.add_argument("--no-worktree", action="store_true",
                    help="Run in place. Default: the plan runs in its own git worktree "
                         ".worktrees/<slug> (branch harness/<slug>), so several plans can run at "
                         "once; HARNESS_WORKTREE=0 also opts out.")
    ap.add_argument("--status", action="store_true",
                    help="Show task states, the first failure's tail and the next command; runs nothing.")
    ap.add_argument("--no-window", action="store_true",
                    help="Do not open the shared terminal window that watches the output "
                         "(default on; HARNESS_WINDOW=0 also opts out).")
    ap.add_argument("--relock-only", action="store_true",
                    help="Re-record plan.lock.json (here, and in the plan's worktree if there is "
                         "one) after you edited tasks.json or a check script; run nothing.")
    ap.add_argument("--land", action="store_true",
                    help="The user's command, not ours: merge the worktree's branch into this "
                         "tree with --ff-only, copy its plan records, remove the worktree and branch.")
    ap.add_argument("--yes", action="store_true",
                    help="With --land: skip the interactive-terminal requirement (CI). Without it "
                         "--land refuses when stdin is not a terminal, e.g. under an agent's Bash tool.")
    ap.add_argument("--lint", action="store_true",
                     help="Validate the plan and run every check on the untouched tree; run nothing else.")
    ap.add_argument("--stats", action="store_true", help="Print executor time/token totals per plan.")
    ap.add_argument("--pending", action="store_true",
                    help="List plan worktrees not landed yet; run nothing.")
    ap.add_argument("--fresh", action="store_true",
                     help="A fresh pi session per task (the old default). Warm is faster on the bench.")
    ap.add_argument("--session",
                     help="ignored with --fresh or --parallel > 1: continue this existing "
                          "session (e.g. the one that wrote the plan).")
    ap.add_argument("--parallel", type=int, default=1,
                     help="Run up to N tasks at once (deps passed, no shared files).")
    ap.add_argument("--executor", default="pi", metavar="BACKEND[:MODEL]",
                    help="Who writes the code, optionally with a model (claude:sonnet). Backends: pi, "
                         "claude (`claude -p`), opencode (its HTTP server), cline (Cline CLI, no warm "
                         "session), cline-acp (Cline over ACP, one warm process per plan), llama (pi "
                         "driving a local llama.cpp router: HARNESS_LLAMA_URL/HARNESS_LLAMA_MODEL), "
                         "agent (agent:haiku: the main session spawns @claude-executor; run this "
                         "command once to prepare the worktree, again to grade it).")
    ap.add_argument("--plan", metavar="SPEC.md",
                    help="Plan <slug> from this spec file with the planner backend, lint the "
                         "plan, and run no tasks.")
    ap.add_argument("--planner", default=os.environ.get("HARNESS_PLANNER", "pi"), metavar="BACKEND[:MODEL]",
                    help="Who writes the plan for --plan: pi, opencode, claude, cline or cline-acp, "
                         "optionally with a model (claude:sonnet; else HARNESS_PLANNER_MODEL).")
    return ap


def interactive():
    """True when stdin is a real terminal. isatty() alone is wrong on Windows: the NUL device
    reports True, so there stdin must be a console (GetConsoleMode succeeds only on one)."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    if sys.platform != "win32":
        return True
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
    return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(ctypes.c_ulong())))


def use_worktree(args):
    """On unless --no-worktree or HARNESS_WORKTREE=0."""
    return not args.no_worktree and os.environ.get("HARNESS_WORKTREE") != "0"


def use_window(args):
    """On unless --no-window or HARNESS_WINDOW=0."""
    return not args.no_window and os.environ.get("HARNESS_WINDOW") != "0"


def parse_backend(spec, valid):
    """'backend' or 'backend:model' -> (backend, model or None); exits on an unknown backend."""
    backend, _, model = spec.partition(":")
    if backend not in valid:
        raise SystemExit(f"unknown backend {backend!r}: use one of {', '.join(valid)}")
    return backend, model or None


def relock_only(slug):
    """Lock the grader without running anything. The worktree copy gets the edited plan
    first, and is locked from inside the worktree: lock keys are cwd-relative paths."""
    Plan(slug, PLANS_ROOT).lock_grader(True)
    print(f"relocked: {Path(PLANS_ROOT) / slug}")
    wt = worktree.path_for(slug)
    if (wt / ".harness" / "plans" / slug).is_dir():
        home = Path.cwd()
        worktree.sync_plan(slug, wt.resolve(), home)
        os.chdir(wt)
        try:
            Plan(slug, PLANS_ROOT).lock_grader(True)
        finally:
            os.chdir(home)
        print(f"relocked: {wt / '.harness' / 'plans' / slug}")
    return 0


def main(argv=None):
    global _ACTIVE_RUN_LOCK
    ap = build_parser()
    args = ap.parse_args(argv)
    args.executor, args.executor_model = parse_backend(args.executor, (*REGISTRY, "agent"))
    args.planner, args.planner_model = parse_backend(
        args.planner, ("pi", "opencode", "claude", "cline", "cline-acp"))
    args.planner_model = args.planner_model or os.environ.get("HARNESS_PLANNER_MODEL")
    args.review_model = None
    if args.review is not None:
        args.review_model = parse_backend(args.review or "claude", ("claude",))[1] or "sonnet"
    if args.session and (args.fresh or args.parallel > 1):
        print("--session is ignored with --fresh or --parallel > 1; drop one of them")
        return 1
    try:
        code = _run(ap, args)
    finally:
        if _ACTIVE_RUN_LOCK is not None:
            _ACTIVE_RUN_LOCK.unlink(missing_ok=True)
            _ACTIVE_RUN_LOCK = None
    return code or 0


def _agent(args):
    """`--executor agent[:model]`: the main session spawns @claude-executor, so the runner only
    brackets it. First call: make the worktree and print the handoff. Second call: grade it."""
    if not use_worktree(args):
        print("--executor agent needs the worktree: drop --no-worktree / HARNESS_WORKTREE=0")
        return 1
    wt = worktree.path_for(args.slug)
    if not (Path(PLANS_ROOT) / args.slug / check.BASELINE).is_file() or not wt.is_dir():
        if check.prepare(args.slug):
            return 1
        print(f"handoff: spawn claude-executor (Agent tool, no isolation, run_in_background true) "
              f"with slug {args.slug}, path {wt.resolve()}, model {args.executor_model or 'haiku'}; "
              f"then rerun this command to grade it")
        return 0
    return check.check(args.slug, str(wt))


def _info(ap, args, metrics):
    """Commands that print, lock or grade and never run a task. Returns an exit code, or None
    when the run goes on."""
    if args.stats:
        print_stats(metrics)
        return 0
    if args.pending:
        return pending.pending()
    if not args.slug:
        ap.error("slug is required")
    if args.land and not args.yes and not interactive():
        print("--land is your command: run it in a terminal, or pass --yes")
        return 1
    if args.land:
        return land.land(args.slug)
    if args.relock_only:
        return relock_only(args.slug)
    if args.status:
        print(status.render(args.slug, watch.watch_dir(args.slug)))
        return 0
    if args.plan:
        plan_dir = Path(PLANS_ROOT) / args.slug
        result = planner.run_planner(args.slug, args.plan, PLANS_ROOT, args.planner,
                                     args.planner_model)
        if result["lint_ok"]:
            record_plan_event(metrics, args.slug, "created", backend=args.planner or "pi")
        print(f"plan: {plan_dir}")
        return 0 if result["lint_ok"] else 1
    return None


def _enter_worktree(args):
    """The default run moves into the plan's worktree. Before the plan dir and the run lock are
    touched: inside, everything is relative to the worktree copy of the tree."""
    global _ACTIVE_RUN_LOCK
    if not (use_worktree(args) and not args.lint):
        return
    if not worktree.in_git_repo():
        print("not a git repo: running in place")
        return
    main = Path.cwd()
    target = worktree.ensure(args.slug)
    os.chdir(target)
    # the run lock comes first: a second run of the same slug exits before anything
    # is copied over.
    (Path(PLANS_ROOT) / args.slug).mkdir(parents=True, exist_ok=True)
    run_lock = Path(PLANS_ROOT) / args.slug / "run.lock"
    _acquire_run_lock(run_lock)
    _ACTIVE_RUN_LOCK = run_lock
    worktree.sync_plan(args.slug, target, main)


def _execute(plan, args, metrics):
    """Run the plan's tasks through the executor, then the optional review. Returns the exit code."""
    tasks = plan.tasks
    plan.prepare()
    plan.lock_grader(False)

    # the curated skills are decided from the plan's files, before the executor reads the env
    skills.apply_default([t.raw for t in tasks], os.environ)
    chosen = skills.chosen_dirs()
    print(f"skills: on ({len(chosen)})" if skills.enabled() else "skills: off")
    # only when the flag is given: claude keeps its own sonnet default, cline falls back to
    # HARNESS_MODEL, pi/opencode to their model lists
    opts = {"model": args.executor_model} if args.executor_model else {}
    run_started = time.time()
    record_plan_event(metrics, args.slug, "run_start", executor=args.executor)
    with get(args.executor, **opts) as executor:
        runner = TaskRunner(plan, args, executor, State())
        result = scheduler.run_all(plan, args, runner)

    summary, failed = result.summary, result.failed
    if runner.state.unattributed:
        summary.insert(0, f"UNATTRIBUTED STRAYS (no task's trace wrote them; review by hand): "
                          f"{sorted(runner.state.unattributed)}")
        failed = True
    if result.ran_any:
        record_plan_event(metrics, args.slug, "run_end", executor=args.executor,
                          result=("fail" if failed else "pass"),
                          duration_s=round(time.time() - run_started, 1),
                          tasks_done=len(result.done))
    _review(plan, args, metrics, result, failed, summary)

    print("\n".join(summary[:20]) if summary else "nothing to run (all tasks already passed)")
    return 1 if failed else 0


def _review(plan, args, metrics, result, failed, summary):
    """--review: one cheap pass after a fresh full run; its line goes into the summary."""
    tasks = plan.tasks
    fresh_full_pass = (not failed and not args.only and result.ran_any
                        and result.done == {t.id for t in tasks}
                        and result.already_done != {t.id for t in tasks})
    if args.review is not None and fresh_full_pass:
        all_files = {f for t in tasks for f in t.get("files", [])}
        run_reviewer(plan.dir, all_files, metrics, args.slug, model=args.review_model)
        summary.append(f"review: {plan.dir / 'REVIEW.md'}")
    elif args.review is not None:
        summary.append("review: skipped (not a fresh full pass)")


def _run(ap, args):
    global _ACTIVE_RUN_LOCK
    metrics = Path(PLANS_ROOT).parent / "metrics.jsonl"
    code = _info(ap, args, metrics)
    if code is not None:
        return code
    if args.executor == "agent" and not args.lint:
        return _agent(args)
    # Before anything is spawned (no plan dir, no run lock, no session): an executor that
    # cannot take concurrent turns must never start half a parallel run.
    if args.parallel > 1 and args.executor != "agent" and not REGISTRY[args.executor].thread_safe:
        print(f"--executor {args.executor} does not support --parallel > 1 (single shared session)")
        return 1
    _enter_worktree(args)
    plan = Plan(args.slug, PLANS_ROOT)
    if not args.lint:
        if _ACTIVE_RUN_LOCK is None:
            _acquire_run_lock(plan.run_lock)
            _ACTIVE_RUN_LOCK = plan.run_lock
        if use_window(args) and os.name == "nt":
            watch.open_window(args.slug)
    if args.lint:
        # red-first only means something before the first attempt (same rule as the run loop)
        attempted = {t.id for t in plan.tasks
                     if any(f"RESULT: {r}" in plan.report_text(t.id) for r in ("pass", "fail", "running"))}
        return lint(plan.dir, [t.raw for t in plan.tasks], attempted)
    return _execute(plan, args, metrics)
