"""Command line: the same flags as always, one of several executors behind them."""
import argparse
import os
import sys
import time
from pathlib import Path

from . import check, land, pending, planner, scheduler, skills, status, watch, worktree
from .executors import get, REGISTRY
from .lint import lint
from .plan import Plan
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
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--review", action="store_true",
                     help="After a fresh full pass, run one cheap (sonnet) review pass "
                          "against reviewer.md's checklist and write <plan>/REVIEW.md.")
    ap.add_argument("--worktree", action=argparse.BooleanOptionalAction, default=None,
                    help="Run the plan in its own git worktree .worktrees/<slug> (branch "
                         "harness/<slug>, based on the current tree), so several plans can run "
                         "at once. Default; --no-worktree to run in place, or HARNESS_WORKTREE=0.")
    ap.add_argument("--watch", action="store_true",
                    help="Watch this plan's executor output live in this terminal; run nothing.")
    ap.add_argument("--status", action="store_true",
                    help="Show task states, the first failure's tail and the next command; runs nothing.")
    ap.add_argument("--window", action=argparse.BooleanOptionalAction, default=None,
                    help="Run as usual, but also open a shared terminal window with a tab "
                         "watching the output. Default; --no-window, or HARNESS_WINDOW=0.")
    ap.add_argument("--relock", action="store_true",
                     help="Re-record plan.lock.json after you (not the executor) edited "
                          "tasks.json or a check script.")
    ap.add_argument("--relock-only", action="store_true",
                    help="Re-record plan.lock.json (here, and in the plan's worktree if there is "
                         "one) after you edited tasks.json or a check script; run nothing.")
    ap.add_argument("--check", metavar="DIR", nargs="?", const="",
                    help="Grade work done outside the runner in the git worktree DIR (default: the plan's "
                         "worktree; plan files from this tree): grader lock, file scope, each task's "
                         "acceptance run in DIR. Runs nothing else.")
    ap.add_argument("--prepare", action="store_true",
                    help="Create the plan's worktree and print its path; run nothing; for executors "
                         "that edit outside the runner.")
    ap.add_argument("--land", action="store_true",
                    help="The user's command, not ours: merge the worktree's branch into this "
                         "tree with --ff-only, copy its plan records, remove the worktree and branch.")
    ap.add_argument("--yes", action="store_true",
                    help="With --land: skip the interactive-terminal requirement (CI). Without it "
                         "--land refuses when stdin is not a terminal, e.g. under an agent's Bash tool.")
    ap.add_argument("--from", dest="from_dir", metavar="DIR",
                    help="With --land: land a git worktree DIR made outside the runner (e.g. a "
                         "Claude subagent worktree) after --check passes; only plan-listed files.")
    ap.add_argument("--lint", action="store_true",
                     help="Validate the plan and run every check on the untouched tree; run nothing else.")
    ap.add_argument("--retries", type=int, default=1,
                     help="Reruns of the (free) executor with the failure output attached, per task.")
    ap.add_argument("--repair", type=int, default=1,
                     help="Repair passes after retries, with the failing task's and earlier tasks' files in scope.")
    ap.add_argument("--stats", action="store_true", help="Print executor time/token totals per plan.")
    ap.add_argument("--pending", action="store_true",
                    help="List plan worktrees not landed yet; run nothing.")
    ap.add_argument("--fresh", action="store_true",
                     help="A fresh pi session per task (the old default). Warm is faster on the bench.")
    ap.add_argument("--executor-model", default=None,
                     help="Model override for --executor claude/pi/opencode/cline/llama "
                          "(each has its own default; for bench comparisons only).")
    ap.add_argument("--session",
                     help="ignored with --fresh or --parallel > 1: continue this existing "
                          "session (e.g. the one that wrote the plan).")
    ap.add_argument("--parallel", type=int, default=1,
                     help="Run up to N tasks at once (deps passed, no shared files).")
    ap.add_argument("--executor", choices=("pi", "claude", "opencode", "cline", "cline-acp", "llama"),
                    default="pi",
                    help="Who writes the code. claude = `claude -p` (sonnet), opencode = its HTTP server, "
                         "cline = the Cline CLI (free model, no warm session), cline-acp = the Cline CLI "
                         "over ACP (one warm process per plan, free model), llama = pi driving a local "
                         "llama.cpp router (`HARNESS_LLAMA_URL`/`HARNESS_LLAMA_MODEL`); for A/B cost "
                         "comparisons.")
    ap.add_argument("--plan", metavar="SPEC.md",
                    help="Plan <slug> from this spec file with the planner backend, lint the "
                         "plan, and run no tasks.")
    ap.add_argument("--planner", choices=("pi", "opencode", "claude", "cline", "cline-acp"),
                    default=os.environ.get("HARNESS_PLANNER", "pi"),
                    help="Who writes the plan for --plan.")
    ap.add_argument("--planner-model", default=os.environ.get("HARNESS_PLANNER_MODEL"),
                    help="Model for --planner (default: sonnet for claude, else the pi/opencode default).")
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
    """Explicit flag wins, else HARNESS_WORKTREE != "0" (unset means on)."""
    if args.worktree is not None:
        return args.worktree
    return os.environ.get("HARNESS_WORKTREE") != "0"


def use_window(args):
    """Explicit flag wins, else HARNESS_WINDOW != "0" (unset or 1 means on)."""
    if args.window is not None:
        return args.window
    return os.environ.get("HARNESS_WINDOW") != "0"


def watch_dir(slug):
    """The plan dir --watch follows: inside the worktree when there is one, else here."""
    in_worktree = worktree.path_for(slug) / ".harness" / "plans" / slug
    return in_worktree if in_worktree.is_dir() else Path(".harness/plans") / slug


def relock_only(slug):
    """Lock the grader without running anything. The worktree copy gets the edited plan
    first, and is locked from inside the worktree: lock keys are cwd-relative paths."""
    Plan(slug, ".harness/plans").lock_grader(True)
    print(f"relocked: {Path('.harness/plans') / slug}")
    wt = worktree.path_for(slug)
    if (wt / ".harness" / "plans" / slug).is_dir():
        home = Path.cwd()
        worktree.sync_plan(slug, wt.resolve(), home)
        os.chdir(wt)
        try:
            Plan(slug, ".harness/plans").lock_grader(True)
        finally:
            os.chdir(home)
        print(f"relocked: {wt / '.harness' / 'plans' / slug}")
    return 0


def prepare(slug):
    if not worktree.in_git_repo():
        print("not a git repo")
        return 1
    main = Path.cwd()
    target = worktree.ensure(slug)
    worktree.sync_plan(slug, target, main)
    check.write_baseline(slug)
    print(f"worktree: {target}")
    return 0


def main(argv=None):
    global _ACTIVE_RUN_LOCK
    ap = build_parser()
    args = ap.parse_args(argv)
    args.warm = not args.fresh
    if args.session and (args.fresh or args.parallel > 1):
        print("--session is ignored with --fresh or --parallel > 1; drop one of them")
        sys.exit(1)
    try:
        return _run(ap, args)
    finally:
        if _ACTIVE_RUN_LOCK is not None:
            _ACTIVE_RUN_LOCK.unlink(missing_ok=True)
            _ACTIVE_RUN_LOCK = None


def _run(ap, args):
    global _ACTIVE_RUN_LOCK
    metrics = Path(".harness/plans").parent / "metrics.jsonl"
    if args.stats:
        print_stats(metrics)
        return
    if args.pending:
        return pending.pending()
    if not args.slug:
        ap.error("slug is required")
    if args.from_dir and not args.land:
        ap.error("--from requires --land")
    if args.land and not args.yes and not interactive():
        print("--land is your command: run it in a terminal, or pass --yes")
        sys.exit(1)
    if args.land:
        if args.from_dir:
            sys.exit(land.land_from(args.slug, args.from_dir))
        sys.exit(land.land(args.slug))
    if args.relock_only:
        sys.exit(relock_only(args.slug))
    if args.prepare:
        sys.exit(prepare(args.slug))
    if args.check is not None:
        sys.exit(check.check(args.slug, args.check or str(worktree.path_for(args.slug))))
    if args.watch:
        sys.exit(watch.watch(watch_dir(args.slug)))
    if args.status:
        print(status.render(args.slug, watch_dir(args.slug)))
        return
    if args.plan:
        plan_dir = Path(".harness/plans") / args.slug
        result = planner.run_planner(args.slug, args.plan, ".harness/plans", args.planner,
                                     args.planner_model)
        if result["lint_ok"]:
            record_plan_event(metrics, args.slug, "created", backend=args.planner or "pi")
        print(f"plan: {plan_dir}")
        sys.exit(0 if result["lint_ok"] else 1)
    # Before anything is spawned (no plan dir, no run lock, no session): an executor that
    # cannot take concurrent turns must never start half a parallel run.
    if args.parallel > 1 and not REGISTRY[args.executor].thread_safe:
        print(f"--executor {args.executor} does not support --parallel > 1 (single shared session)")
        sys.exit(1)
    if use_worktree(args) and not args.lint:
        # before the plan dir and the run lock are touched: inside, everything is relative
        # to the worktree copy of the tree.
        if worktree.in_git_repo():
            main = Path.cwd()
            target = worktree.ensure(args.slug)
            os.chdir(target)
            # the run lock comes first: a second run of the same slug exits before anything
            # is copied over.
            (Path(".harness/plans") / args.slug).mkdir(parents=True, exist_ok=True)
            run_lock = Path(".harness/plans") / args.slug / "run.lock"
            _acquire_run_lock(run_lock)
            _ACTIVE_RUN_LOCK = run_lock
            worktree.sync_plan(args.slug, target, main)
        else:
            print("not a git repo: running in place")
    plan = Plan(args.slug, ".harness/plans")
    if not args.lint:
        if _ACTIVE_RUN_LOCK is None:
            _acquire_run_lock(plan.run_lock)
            _ACTIVE_RUN_LOCK = plan.run_lock
        if use_window(args) and os.name == "nt":
            watch.open_window(args.slug)
    tasks = plan.tasks
    if args.lint:
        # red-first only means something before the first attempt (same rule as the run loop)
        attempted = {t.id for t in tasks
                     if any(f"RESULT: {r}" in plan.report_text(t.id) for r in ("pass", "fail", "running"))}
        sys.exit(lint(plan.dir, [t.raw for t in tasks], attempted))
    plan.prepare()
    plan.lock_grader(args.relock)

    # only when the flag is given: claude keeps its own sonnet default, cline falls back to
    # HARNESS_MODEL, pi/opencode to their model lists
    # the curated skills are decided from the plan's files, before the executor reads the env
    skills.apply_default([t.raw for t in tasks], os.environ)
    chosen = skills.chosen_dirs()
    print(f"skills: on ({len(chosen)})" if skills.enabled() else "skills: off")
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
    fresh_full_pass = (not failed and not args.only and result.ran_any
                        and result.done == {t.id for t in tasks}
                        and result.already_done != {t.id for t in tasks})
    if args.review and fresh_full_pass:
        all_files = {f for t in tasks for f in t.get("files", [])}
        run_reviewer(plan.dir, all_files, metrics, args.slug)
        summary.append(f"review: {plan.dir / 'REVIEW.md'}")
    elif args.review:
        summary.append("review: skipped (not a fresh full pass)")

    print("\n".join(summary[:20]) if summary else "nothing to run (all tasks already passed)")
    sys.exit(1 if failed else 0)
