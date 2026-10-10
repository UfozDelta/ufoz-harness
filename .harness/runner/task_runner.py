"""One task through every guard: lock, red-first, executor, acceptance, scope, build gate.

The retry loop and the repair loop differ only in which brief, which acceptance command and
which file scope they pass in, so they share a single `_attempt()`.
"""
import functools
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field

from . import report
from .acceptance import run_acceptance
from .guards import (GIT_MOVED, attribute, git_state, marker_counts, runner_owned, snapshot,
                     suppression_markers, written_paths)
from .plan import in_scope
from .procs import EXIT_RATE_LIMIT, EXIT_TIMEOUT, TOKEN_KEYS
from .worktree import IDENTITY

RETRIES = 1  # reruns with the failure attached, per task
REPAIRS = 1  # repair passes after the retries


def commit_task(slug, tid, title, files):
    """Commit the given files after a task passes. Returns the new commit sha, or None
    if there was nothing to commit. Uses the harness identity in the git environment."""
    if not files:
        return None

    # Stage only the files listed in the task
    add_res = subprocess.run(["git", "add", "-A", "--", *files], capture_output=True, check=False)
    if add_res.returncode != 0:
        return None

    # Check if there's anything staged
    check_res = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True,
                               text=True, check=False)
    if not check_res.stdout.strip():
        return None  # nothing to commit

    # Build the commit message based on HARNESS_COMMIT_STYLE
    style = os.environ.get("HARNESS_COMMIT_STYLE", "full")
    if style == "short":
        message = f"{tid}: {title}"
    else:
        # default to "full" for any unrecognized value
        message = f"harness({slug}): {tid} {title}"

    # Commit with the harness identity
    env = dict(os.environ, **IDENTITY)
    commit_res = subprocess.run(["git", "commit", "-m", message], capture_output=True,
                                text=True, env=env, check=False)
    if commit_res.returncode != 0:
        return None

    # Get the sha of the new commit
    sha_res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=False)
    return sha_res.stdout.strip() if sha_res.returncode == 0 else None


@dataclass
class State:
    """Shared across concurrently running tasks (--parallel)."""
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    metrics_lock: threading.Lock = field(default_factory=threading.Lock)
    running: dict = field(default_factory=dict)   # tid -> files of tasks executing right now
    co_files: dict = field(default_factory=dict)  # tid -> files owned by tasks that ran during its window
    unattributed: set = field(default_factory=set)  # --parallel strays no task's trace wrote


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
    git0: tuple | None = None

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
    unattributed: list = field(default_factory=list)


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
            quota_ok = self.executor.wait_for_quota(log.as_posix())
            self._add_usage(st, res.usage)
            if not quota_ok:
                break
        if not args.fresh:
            # "" means the executor rotated the session; None means it had none to give
            session = res.session if res.session is not None else session
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
        stray = [f for f in touched if not in_scope(f, allowed) and not self.owned(f)]
        unattributed = []
        if stray and getattr(args, "parallel", 1) > 1:
            # a stray fails only the task whose own trace wrote it; the rest (a concurrent
            # task's, or a bash side effect) is reported once for the run instead of failing
            # every task that happened to be running
            stray, unattributed = attribute(stray, written_paths(plan.logs.glob(f"{t.id}.*log")))
            with self.state.state_lock:
                self.state.unattributed.update(unattributed)
        if st.git0 is not None and git_state() != st.git0:
            stray.append(GIT_MOVED)
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
                       build_line=build_line, unattributed=unattributed)

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
            return False, [f"{tid} LOCK-MISMATCH: {broken} (rerun with --relock-only if intended)"], session

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
        # written before the snapshot so it never counts as an out-of-scope edit
        rep.write_text(report.running(), encoding="utf-8")
        before = snapshot()
        st.git0 = git_state()
        # suppression baseline: every existing file the task may touch (directory entries
        # expand to the files under them)
        scope = repair_allowed | self.state.co_files.get(tid, set())
        for f in (f for f in before if in_scope(f, scope)) if before is not None else scope:
            counts = marker_counts(f)
            st.baseline[f] = {"total": sum(counts.values()), "counts": counts}

        for attempt in range(1 + RETRIES):
            if attempt:
                log = plan.log_path(tid, f"retry{attempt}", args.executor)
            got = self._attempt(t, st, before, log, feedback.as_posix() if attempt else None, session,
                                t.acceptance, listed, "retry" if attempt else "exec", dynamic_scope=True)
            session, ok = got.session, got.ok
            if ok or got.broken or got.stray or attempt >= RETRIES:
                break
            if got.code == EXIT_TIMEOUT:
                session = None  # a hung session is not worth continuing; retry fresh
            feedback.write_text(report.retry_feedback(attempt, args.executor, t, got.code,
                                                      got.suppressed, got.out), encoding="utf-8")

        for repair in range(1, REPAIRS + 1):
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

        # commit passing task with its files
        if ok:
            sha = commit_task(plan.slug, tid, t.get("title", ""), list(t.norm_files))
            if sha:
                lines[0] = f"{lines[0]} [{sha[:7]}]"

        if got.unattributed:
            lines.append(f"{tid} note: strays not in its trace (not failing it): {got.unattributed}")
        return ok, lines, session
