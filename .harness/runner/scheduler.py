"""Deciding what runs when: a serial list, or a DAG that never overlaps two tasks' files."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from .plan import overlaps


@dataclass
class RunResult:
    summary: list = field(default_factory=list)
    failed: bool = False
    done: set = field(default_factory=set)
    already_done: set = field(default_factory=set)
    ran_any: bool = False


def run_all(plan, args, runner):
    """Run every not-yet-passed task (deps in order, or in parallel), stopping at the first
    failure in serial mode. Returns what the caller needs to decide on the review pass."""
    result = RunResult(done={t.id for t in plan.tasks if plan.passed(t.id)})
    result.already_done = set(result.done)
    todo = [t for t in plan.tasks
            if t.id not in result.done and not (args.only and t.id != args.only)]
    result.ran_any = bool(todo)
    done, summary = result.done, result.summary
    if args.parallel > 1 and not args.only:
        _parallel(plan, args, runner, todo, done, summary, result)
    else:
        _serial(plan, args, runner, todo, done, summary, result)
    return result


def _serial(plan, args, runner, todo, done, summary, result):
    session = args.session if args.warm else None
    for t in todo:
        missing = [d for d in t.deps if d not in done]
        if missing:
            summary.append(f"{t.id} BLOCKED: deps not passed {missing}")
            result.failed = True
            break
        ok, lines, session = runner.run(t, session if args.warm else None)
        summary += lines
        if ok:
            done.add(t.id)
        else:
            result.failed = True
            break


def _parallel(plan, args, runner, todo, done, summary, result):
    # DAG scheduler: a task starts once its deps passed and no running task shares a file
    state, pending, active = runner.state, list(todo), {}
    with ThreadPoolExecutor(args.parallel) as pool:
        while pending or active:
            for t in list(pending):
                if result.failed or len(active) >= args.parallel:
                    break
                files = t.norm_files
                if not all(d in done for d in t.deps):
                    continue
                with state.state_lock:
                    if any(overlaps(files, other) for other in state.running.values()):
                        continue
                    state.co_files[t.id] = set().union(*state.running.values()) if state.running else set()
                    for other in state.running:
                        state.co_files[other] |= files
                    state.running[t.id] = files
                pending.remove(t)
                active[t.id] = pool.submit(runner.run, t)
            if not active:
                if pending and not result.failed:
                    summary.append(f"BLOCKED: {[t['id'] for t in pending]} (deps never passed)")
                    result.failed = True
                break
            finished, _ = wait(list(active.values()), return_when=FIRST_COMPLETED)
            for tid, fut in list(active.items()):
                if fut in finished:
                    ok, lines, _ = fut.result()
                    summary += lines
                    del active[tid]
                    with state.state_lock:
                        state.running.pop(tid, None)
                    if ok:
                        done.add(tid)
                    else:
                        result.failed = True
