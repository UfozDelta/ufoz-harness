"""Every string the runner writes: items/<id>.report.md, the feedback briefs handed to the
executor, and the metrics.jsonl rows."""
import json
import time
from pathlib import Path

from .acceptance import parse_errors
from .guards import SUPPRESSION_MARKERS
from .stats import write_task_metrics


def marker_sentence():
    """The no-suppression rule for repair prompts, spelled from the guard's own list so
    the prompt cannot drift from what the guard actually hunts for."""
    markers = list(SUPPRESSION_MARKERS)
    return f"no {', '.join(markers[:-1])}, or {markers[-1]}"


def running():
    return f"RESULT: running\nstarted: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"


def lock_mismatch(broken):
    return (f"RESULT: lock-mismatch\nchanged since lock: {broken}\n"
            "If you made this edit on purpose, rerun with --relock-only.\n"
            "exec seconds: 0.0\nacceptance seconds: 0.0\nretry seconds: 0.0\n")


def check_invalid(acceptance, accept_s, pre_out):
    return (f"RESULT: check-invalid\nacceptance: {acceptance}\n"
            "Acceptance passed BEFORE the executor ran, so it cannot prove the task.\n"
            "Tighten the check, or set \"red_first\": false with a \"red_first_reason\".\n"
            f"exec seconds: 0.0\nacceptance seconds: {round(accept_s, 1)}\nretry seconds: 0.0\n\n"
            f"acceptance output (tail):\n{pre_out}\n")


def retry_feedback(attempt, executor, t, code, suppressed, out):
    errors = parse_errors(out)
    return (("The previous attempt timed out with no result; check what exists and finish the task.\n"
             if code == 124 else "") +
            f"Attempt {attempt + 1} failed. {executor} exit: {code}\n"
            f"acceptance: {t.acceptance}\n"
            + (f"suppression guard:\n" + "\n".join(suppressed) + "\n" if suppressed else "")
            + f"\nacceptance output (tail):\n{out[-1500:]}\n"
            + (f"errors:\n" + "\n".join(errors) + "\n" if errors else ""))


def repair_feedback(repair, tid, t, out, suppressed, repair_allowed):
    errors = parse_errors(out)
    return (f"Repair pass {repair} for {tid}.\n"
            f"fix the root cause; {marker_sentence()}; do not delete features or checks.\n"
            f"acceptance: {t.acceptance}\n"
            + (f"repair_check: {t.repair_check}\n" if t.repair_check else "")
            + (f"suppression guard:\n" + "\n".join(suppressed) + "\n" if suppressed else "")
            + f"acceptance output (tail):\n{out[-1500:]}\n"
            + (f"errors:\n" + "\n".join(errors) + "\n" if errors else "")
            + f"allowed files:\n" + "\n".join(sorted(repair_allowed)) + "\n")


def final_report(t, result, executor, code, attempts, repairs, seconds, usage, exec_s, accept_s,
                 retry_s, touched, stray, broken, build_line, log, out):
    return (f"RESULT: {result}\n"
            f"{executor} exit: {code}\n"
            f"attempts: {attempts}\n"
            f"repairs: {repairs}\n"
            f"seconds: {seconds}\n"
            f"exec seconds: {round(exec_s, 1)}\n"
            f"acceptance seconds: {round(accept_s, 1)}\n"
            f"retry seconds: {round(retry_s, 1)}\n"
            f"executor tokens: {usage}\n"
            f"acceptance: {t.acceptance}\n"
            f"files touched: {touched or 'n/a (not a git repo)'}\n"
            f"out-of-scope files: {stray or 'none'}\n"
            f"lock: {('CHANGED ' + str(broken)) if broken else 'ok'}\n"
            + (f"{build_line}\n" if build_line else "")
            + f"log: {log.as_posix()}\n\n"
            f"acceptance output (tail):\n{out}\n")


def summary_lines(tid, executor, ok, code, attempts, repairs, seconds, usage, stray, broken, log):
    result = "pass" if ok else "fail"
    lines = [f"{tid} {'REPAIRED' if ok and repairs else result.upper()} ({executor} exit {code}, attempts {attempts}, "
             f"{seconds}s, {usage['input'] + usage['output']} tokens)"
             + (f" out-of-scope: {stray}" if stray else "")
             + (f" lock changed: {broken}" if broken else "")]
    if not ok:
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-4:]
        lines += [f"  log: {log.as_posix()}"] + [f"  | {ln}" for ln in tail]
    return lines


def record_metrics(plan, args, tid, usage, timings, repairs, result, attempts, seconds, lock=None,
                   sessions=True):
    """Per-task timing/token record, plus the shared metrics.jsonl row. `sessions` is the
    executor's capability: without it --warm is really fresh, and the row must not claim warm."""
    exec_s, accept_s, retry_s = timings
    row = {"slug": args.slug, "task": tid, "result": result, "attempts": attempts, "repairs": repairs,
           "exec_s": round(exec_s, 1), "accept_s": round(accept_s, 1),
           "retry_s": round(retry_s, 1), "tokens": usage}
    write_task_metrics(plan.dir, tid, row)
    with (lock or _NullLock()), plan.metrics.open("a", encoding="utf-8") as mf:
        mf.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "slug": args.slug, "task": tid,
                             "executor": args.executor, "result": result, "attempts": attempts, "repairs": repairs, "seconds": seconds,
                             "exec_s": row["exec_s"], "accept_s": row["accept_s"], "retry_s": row["retry_s"],
                             "mode": ("parallel" if args.parallel > 1
                                      else ("warm" if args.warm and sessions else "fresh")),
                             "tokens": usage}) + "\n")


def record_plan_event(metrics_path, slug, event, **extra):
    """One plan-lifecycle row in metrics.jsonl: when the plan was created, when a run started
    and how it ended. Same shape as the review rows, no task/result/token keys."""
    with Path(metrics_path).open("a", encoding="utf-8") as mf:
        mf.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "slug": slug,
                             "kind": "plan_event", "event": event, **extra}) + "\n")


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
