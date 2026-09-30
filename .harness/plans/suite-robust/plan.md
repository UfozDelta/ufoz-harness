# Plan: suite-robust

## Goal
Fix harness robustness bugs logged in `log.md` "## 2026-09-30 oc-speed": failed suite cells
lose their logs, cleanup can leave a stale branch, acceptance can hang on grandchild
processes, a suite cell timeout can miss a machine sleep, and the opencode executor has no
no-event watchdog.

## Decisions
Verified: `harness-suite/cells.py` has `is_cell_slug`, `prepare_cell`, `run_cell`,
`_run_single` (~L528), `_run_multi` (~L571), `cleanup_cell` (~L662), `_git` helper (~L97)
(`grep -n "def " harness-suite/cells.py`). `.harness/runner/acceptance.py` `run_acceptance`
uses `subprocess.run(shell=True, capture_output=True, timeout=timeout)` (L35).
`.harness/runner/procs.py` has `stop_process_tree(p)` (taskkill /F /T on Windows, `p.kill()`
elsewhere) and `EXIT_TIMEOUT = 124`. `.harness/runner/executors/opencode.py` `_stream`
(L251) loops `while time.monotonic() < deadline`, calling `self._drain(...)` per iteration;
`_drain` (L304) already filters events by `sessionID`. `.gitignore` L14 has
`harness-suite/.check-tmp/`. `worktree.ensure` and `cleanup_cell` both use path
`.worktrees/<slug>` for a cell's worktree (verified in both files).
Unverified: a grandchild whose parent already exited is outside `taskkill /T`'s tree; the
bounded `communicate(timeout=5)` then gives up so the run still returns.
Later: none.

## interfaces
- `cells._preserve_failed(cell, repo_root)`: new. Copies
  `.worktrees/<slug>/.harness/plans/<slug>/items/` and `/logs/` into
  `harness-suite/failed/<slug>/items/` and `/logs/` under `repo_root` (main tree),
  overwriting. No-op if the source dirs don't exist.
- `cells.cleanup_cell(cell, repo_root=REPO_ROOT, sleep_fn=time.sleep)`: `sleep_fn` param
  added for test injection; behavior otherwise unchanged from caller's view.
- `cells._poll_until(proc, deadline, clock=time.time, sleep_fn=time.sleep)`: new helper,
  returns `True` if `proc` was still running when `clock()` passed `deadline`, else `False`.
- `acceptance.run_acceptance(cmd, expect, timeout=300)`: signature and return contract
  (`(ok: bool, out_tail: str)`) unchanged.
- opencode `_stream`: env var `HARNESS_OPENCODE_IDLE_S` (default `300`), read fresh each
  call. `_drain` return dict gains key `"saw_event"` (bool: any event matched this session
  this call).

## T1 preserve failed cell logs
FILES: harness-suite/cells.py, .gitignore, tests/test_harness_suite.py
MUST:
- Add `_preserve_failed(cell, repo_root)`: reads `slug = cell["slug"]`, copies
  `.worktrees/<slug>/.harness/plans/<slug>/items/` and `.../logs/` (if present) into
  `harness-suite/failed/<slug>/items/` and `.../logs/` under `repo_root`, overwriting any
  prior copy for that slug. Never copies the whole worktree.
- In `run_cell` (single-size path) and `_run_multi` (per-size path), call
  `_preserve_failed(cell_or_sub, repo_root)` before `cleanup_cell(...)` whenever the row's
  `status` is not `"pass"` and `keep` is false.
- `.gitignore`: add `harness-suite/failed/`.
- Test `_preserve_failed` directly against a tmp dir laid out like
  `<tmp>/.worktrees/<slug>/.harness/plans/<slug>/items/x.report.md` and `.../logs/T1.pi.log`
  (no real git worktree): assert both land under
  `<tmp>/harness-suite/failed/<slug>/{items,logs}/`.
TEST: python -m pytest tests/test_harness_suite.py -k preserve_failed -q

## T2 cleanup retry and stale branch
FILES: harness-suite/cells.py, tests/test_harness_suite.py
MUST:
- `cleanup_cell(cell, repo_root=REPO_ROOT, sleep_fn=time.sleep)`: retry
  `git worktree remove --force .worktrees/<slug>` up to 3 times, calling `sleep_fn(1)`
  between attempts, before `_remove_leftover`/`worktree prune`/`branch -D`. After
  `branch -D`, verify with `git rev-parse --verify --quiet refs/heads/harness/<slug>`; if it
  still exists, `print` a warning (do not raise).
- `prepare_cell`: before `worktree.ensure(...)`, when `is_cell_slug(slug)` and
  `refs/heads/harness/<slug>` exists (`git rev-parse --verify --quiet`) and no line of
  `git worktree list --porcelain` reads `branch refs/heads/harness/<slug>`, delete the
  branch (`git branch -D`) first.
- HARD RULE: no new `shutil.rmtree`/`os.remove` call on a worktree path anywhere in this
  task; reuse `_remove_leftover` as-is.
- Tests mock `cells._git` (module-level monkeypatch) to assert: `cleanup_cell` retries on a
  failing-then-succeeding `worktree remove`; `prepare_cell`'s pre-clean branch delete fires
  only when `is_cell_slug` is true and the branch is unused, and does not fire for a
  non-cell slug.
TEST: python -m pytest tests/test_harness_suite.py -k "cleanup_retry or stale_branch" -q

## T3 acceptance tree kill on timeout
FILES: .harness/runner/acceptance.py, tests/test_acceptance.py
MUST:
- Replace `subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)` with
  `subprocess.Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, text=True,
  encoding="utf-8", errors="replace", stdin=DEVNULL, env=env)` then
  `proc.communicate(timeout=timeout)`.
- On `subprocess.TimeoutExpired`: call `procs.stop_process_tree(proc)` (import
  `from .procs import stop_process_tree`), then `proc.communicate(timeout=5)` inside a
  `contextlib.suppress(subprocess.TimeoutExpired)` to drain/release pipes, then return
  `(False, "acceptance command timed out")` (message unchanged).
- Success path keeps the existing return contract:
  `(r.returncode == 0 and (expect is None or expect in out), out[-2000:])`.
- Test (real grandchild holding the inherited stdout pipe): build
  `cmd = f'"{sys.executable}" -c "import subprocess,sys,time; subprocess.Popen([sys.executable,\'-c\',\'import time; time.sleep(30)\']); time.sleep(30)"'`;
  call `run_acceptance(cmd, None, timeout=1)`, assert it returns within 10s and the result is
  `(False, "acceptance command timed out")`. Before this task the same test hangs ~30s.
TEST: python -m pytest tests/test_acceptance.py -q

## T4 wall clock cell timeout
FILES: harness-suite/cells.py, tests/test_harness_suite.py
MUST:
- Add `_poll_until(proc, deadline, clock=time.time, sleep_fn=time.sleep)`: loop
  `while proc.poll() is None: return True if clock() >= deadline else sleep_fn(1)`; returns
  `False` once `proc.poll()` is not `None`.
- In `_run_single`, replace `proc.wait(timeout=cell_timeout)`/`except
  subprocess.TimeoutExpired` with: `deadline = time.time() + cell_timeout`;
  `timed_out = _poll_until(proc, deadline)`; on `timed_out`, keep the existing
  `_stop_tree(proc)` + bounded `proc.wait(timeout=30)` cleanup.
- Do not change `_run_multi`'s existing wall-clock loop.
- Test `_poll_until` with a fake `proc` (`.poll()` returns `None` until a counter flips) and
  a fake `clock` function whose second call already exceeds `deadline` (simulates a machine
  sleep between polls): assert it returns `True` without a real 900s wait.
TEST: python -m pytest tests/test_harness_suite.py -k poll_until -q

## T5 opencode idle watchdog
FILES: .harness/runner/executors/opencode.py, tests/test_opencode_executor.py
MUST:
- `_drain`: add `state["saw_event"] = False` at start; set it `True` right after an event
  passes the existing `sessionID` match check (before dispatching on `kind`).
- `_stream`: read `idle_timeout = float(os.environ.get("HARNESS_OPENCODE_IDLE_S", 300))`
  once per call; track wall-clock `last_event = time.time()` (not monotonic: it must fire after
  a machine sleep), updated to `time.time()` whenever `state["saw_event"]` is true. If
  `time.time() - last_event > idle_timeout`
  (checked once per loop iteration, before `time.sleep(0.05)`), call the session `/abort`
  endpoint the same way the deadline branch does (suppressing the same exceptions), set
  `code = EXIT_TIMEOUT`, and `break`.
- Do not add a per-prompt SSE reader; keep using `self._reader`/`self._events`.
- Test drives `_stream` on an `OpenCodeExecutor` instance with `self.url` set, `self._reader`
  a stub thread-like object whose `is_alive()` returns `True`, `self._connected` pre-set,
  and `self._events` starting empty (never appended to, so `saw_event` never fires); patch
  `opencode._http` to a stub (session create/prompt/abort all return `{}`/`{"id": "s1"}`);
  set `HARNESS_OPENCODE_IDLE_S=0.1` and a long `timeout`; assert `_stream` returns
  `EXIT_TIMEOUT` well before `timeout` elapses.
TEST: python -m pytest tests/test_opencode_executor.py -q

## T6 write summary
FILES: .harness/plans/suite-robust/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run
`python -m pytest tests -q` and add a line `BUILD: pass` or `BUILD: fail <first error line>`
to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/suite-robust/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
