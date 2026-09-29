"""One task through every guard: lock, red-first, executor, acceptance, scope, build gate.

The retry loop and the repair loop differ only in which brief, which acceptance command and
which file scope they pass in, so they share a single `_attempt()`.
"""
import functools
import threading
import time
from dataclasses import dataclass, field

from . import report
from .acceptance import run_acceptance
from .guards import marker_counts, runner_owned, snapshot, suppression_markers
from .procs import EXIT_RATE_LIMIT, EXIT_TIMEOUT, TOKEN_KEYS


@dataclass
class State:
    """Shared across concurrently running tasks (--parallel)."""
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    metrics_lock: threading.Lock = field(default_factory=threading.Lock)
    running: dict = field(default_factory=dict)   # tid -> files of tasks executing right now
    co_files: dict = field(default_factory=dict)  # tid -> files owned by tasks that ran during its window


@dataclass
class _Run:
    """Per-task mutable state (one per run() call, so --parallel never shares it)."""
    tid: str
    t0: float
    usage: dict = field(default_factory=lambda: {**dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0})
    exec_s: float = 0.0
    accept_s: float = 0.0
    retry_s: float = 0.0
    repairs: int = 0
    baseline: dict = field(default_factory=dict)

    @property
    def timings(self):
        return (self.exec_s, self.accept_s, self.retry_s)


@dataclass
class Attempt:
    ok: bool
    plain_failure: bool
    code: int
    session: str | None
    out: str
    touched: list
    stray: list
    suppressed: list
    broken: list
    build_line: str | None


class TaskRunner:
    def __init__(self, plan, args, executor, state=None):
        self.plan = plan
        self.args = args
        self.executor = executor
        self.state = state or State()
        self.owned = functools.partial(runner_owned, run_lock=plan.run_lock, plan=plan.dir,
                                       metrics=plan.metrics)

    # --- small helpers -------------------------------------------------------------------

    def _timed_acceptance(self, st, command, expect):
        started = time.time()
        result = run_acceptance(command, expect)
        st.accept_s += time.time() - started
        return result

    def _add_usage(self, st, usage):
        for k in st.usage:
            st.usage[k] += usage.get(k, 0)

    def _record_metrics(self, st, result, attempts, seconds):
        report.record_metrics(self.plan, self.args, st.tid, st.usage, st.timings, st.repairs,
                              result, attempts, seconds, self.state.metrics_lock,
                              sessions=getattr(self.executor, "has_sessions", True))

    def _build_failure(self):
        summary_path = self.plan.dir / "SUMMARY.md"
        if not summary_path.exists():
            return None
        for line in summary_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("BUILD: fail"):
                return line
        return None

    def _mark_build_unverified(self):
        summary_path = self.plan.dir / "SUMMARY.md"
        if not summary_path.exists():
            return
        text = summary_path.read_text(encoding="utf-8")
        summary_path.write_text(
            text.replace(next(line for line in text.splitlines() if line.startswith("BUILD: fail")),
                         "BUILD: unverified (repair_check passed)"),
            encoding="utf-8")

    # --- the one attempt, shared by the retry and repair loops -----------------------------

    def _attempt(self, t, st, before, log, feedback, session, command, scope, bucket,
                 dynamic_scope=False, repair=False):
        """Run the executor once (waiting out rate limits), then every post-run guard.
        `bucket` is "exec" or "retry": where the executor's seconds are charged.
        `dynamic_scope` adds the files of tasks running concurrently (--parallel)."""
        plan, args = self.plan, self.args
        while True:
            started = time.time()
            res = self.executor.run(plan.brief_of(t), log.as_posix(), args.timeout, feedback, session)
            if res.code != EXIT_RATE_LIMIT:
                if bucket == "exec":
                    st.exec_s += time.time() - started
                else:
                    st.retry_s += time.time() - started
                break
            self.executor.wait_for_quota(log.as_posix())  # rate-limited: wait it out, rerun uncounted
            self._add_usage(st, res.usage)
        if args.warm:
            session = res.session or session
        self._add_usage(st, res.usage)
        code, after = res.code, snapshot()
        broken = plan.lock_broken()
        acceptance_ok, out = ((False, "not run: lock mismatch") if broken
                              else self._timed_acceptance(st, command, t.expect))
        touched = (sorted(f for f in before.keys() | after.keys() if before.get(f) != after.get(f))
                   if before is not None and after is not None else [])
        # --parallel: files of tasks that ran concurrently are theirs to touch (the scheduler
        # never overlaps two tasks' files, and each owner's own acceptance covers them)
        with self.state.state_lock:
            allowed = set(scope) | (self.state.co_files.get(t.id, set()) if dynamic_scope else set())
        stray = [f for f in touched if f not in allowed and not self.owned(f)]
        suppressed = suppression_markers([f for f in touched if not self.owned(f)], st.baseline)
        build_line = self._build_failure() if acceptance_ok and t.build_gate else None
        if repair:
            if (acceptance_ok and code == 0 and not stray and not suppressed and t.repair_check
                    and t.build_gate and build_line):
                self._mark_build_unverified()
                build_line = "BUILD: unverified (repair_check passed)"
        elif build_line:
            acceptance_ok = False
            out = f"build gate failed: {build_line}\n\nacceptance output (tail):\n{out[-1500:]}\n"
        ok = acceptance_ok and code == 0 and not stray and not suppressed
        plain_failure = (not acceptance_ok or bool(suppressed)) and not broken and not stray \
            and code != EXIT_TIMEOUT
        return Attempt(ok=ok, plain_failure=plain_failure, code=code, session=session, out=out,
                       touched=touched, stray=stray, suppressed=suppressed, broken=broken,
                       build_line=build_line)

    # --- one task -------------------------------------------------------------------------

    def run(self, t, session=None):
        """One task through every guard. Returns (ok, summary lines, session id)."""
        plan, args = self.plan, self.args
        tid = t.id
        rep = plan.report_path(tid)
        log = plan.log_path(tid, None, args.executor)
        st = _Run(tid=tid, t0=time.time())

        broken = plan.lock_broken()
        if broken:
            rep.write_text(report.lock_mismatch(broken), encoding="utf-8")
            self._record_metrics(st, "fail", 0, round(time.time() - st.t0, 1))
            return False, [f"{tid} LOCK-MISMATCH: {broken} (rerun with --relock if intended)"], session

        # red-first: a check that passes before any work proves nothing. Skipped when
        # an earlier attempt already ran the executor (fail, or "running" left by a crashed
        # runner), since the tree may be half- or fully done.
        prior = plan.report_text(tid)
        if t.red_first and "RESULT: fail" not in prior and "RESULT: running" not in prior:
            pre_ok, pre_out = self._timed_acceptance(st, t.acceptance, t.expect)
            if pre_ok:
                rep.write_text(report.check_invalid(t.acceptance, st.accept_s, pre_out), encoding="utf-8")
                self._record_metrics(st, "fail", 0, round(time.time() - st.t0, 1))
                return False, [f"{tid} CHECK-INVALID: acceptance passes before any work"], session

        feedback = plan.items / f"{tid}.feedback.md"
        listed = t.norm_files
        repair_allowed = listed | plan.prior_files(t)
        for f in repair_allowed | self.state.co_files.get(tid, set()):
            counts = marker_counts(f)
            st.baseline[f] = {"total": sum(counts.values()), "counts": counts}
        # written before the snapshot so it never counts as an out-of-scope edit
        rep.write_text(report.running(), encoding="utf-8")
        before = snapshot()

        for attempt in range(1 + max(0, args.retries)):
            if attempt:
                log = plan.log_path(tid, f"retry{attempt}", args.executor)
            got = self._attempt(t, st, before, log, feedback.as_posix() if attempt else None, session,
                                t.acceptance, listed, "retry" if attempt else "exec", dynamic_scope=True)
            session, ok = got.session, got.ok
            if ok or got.broken or got.stray or attempt >= args.retries:
                break
            if got.code == EXIT_TIMEOUT:
                session = None  # a hung session is not worth continuing; retry fresh
            feedback.write_text(report.retry_feedback(attempt, args.executor, t, got.code,
                                                      got.suppressed, got.out), encoding="utf-8")

        for repair in range(1, max(0, args.repair) + 1):
            if ok or not got.plain_failure:
                break
            st.repairs = repair
            repair_feedback = plan.items / f"{tid}.repair{repair}.md"
            repair_feedback.write_text(report.repair_feedback(repair, tid, t, got.out, got.suppressed,
                                                              repair_allowed), encoding="utf-8")
            log = plan.log_path(tid, f"repair{repair}", args.executor)
            got = self._attempt(t, st, before, log, repair_feedback.as_posix(), session,
                                t.repair_check or t.acceptance, repair_allowed, "retry", repair=True)
            session, ok = got.session, got.ok
            if got.code == EXIT_TIMEOUT:
                session = None

        result = "pass" if ok else "fail"
        seconds = round(time.time() - st.t0, 1)
        self._record_metrics(st, result, attempt + 1 + st.repairs, seconds)
        rep.write_text(report.final_report(t, result, args.executor, got.code, attempt + 1 + st.repairs,
                                           st.repairs, seconds, st.usage, st.exec_s, st.accept_s,
                                           st.retry_s, got.touched, got.stray, got.broken,
                                           got.build_line, log, got.out), encoding="utf-8")
        lines = report.summary_lines(tid, args.executor, ok, got.code, attempt + 1 + st.repairs,
                                     st.repairs, seconds, st.usage, got.stray, got.broken, log)
        return ok, lines, session
