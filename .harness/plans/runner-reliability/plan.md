# Plan: runner-reliability
## Goal
Three executor-path failures fixed: detached grandchildren survive a task kill, a never-exiting
command can outrun the deadline, and one skills dir reaches pi as two `--skill` args.

## Decisions
Verified: `stop_process_tree` only runs `taskkill /F /T` and reaps nothing (`python -c "print(open('.harness/runner/procs.py').read())"`);
`run_pi` waits in 5s slices and checks the deadline only after each TimeoutExpired (`python -c "print(open('.harness/runner/executors/pi.py').read())"`);
`skills.resolve` dedupes by name and pi maps every chosen dir to one `--skill` (`python -c "print(open('.harness/runner/skills.py').read())"`);
`task_runner._attempt` calls `self.executor.run(...)` synchronously (`task_runner.py:184`) and `Executor.stop()` is a real hook (base.py:59).

- Primary kill mechanism = a real Windows **job object** (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), created and
  assigned right after Popen — NOT a post-hoc descendant snapshot. A process in a job keeps its children in
  the job, so a detached grandchild dies with the tree.
- New `procs.py` helpers: `create_job() -> int|None` (`CreateJobObjectW` + `SetInformationJobObject`),
  `assign_job(job, pid) -> bool` (`OpenProcess` + `AssignProcessToJobObject`), `close_job(job)`,
  `register_job(pid, job)` / `job_for(pid) -> int|None`, `pid_alive(pid) -> bool`.
- `stop_process_tree(p, timeout=10)` stays: if `job_for(p.pid)` exists, `TerminateJobObject` + `close_job`;
  otherwise today's `taskkill /F /T`, then poll `pid_alive` until gone or `timeout`. Call shape unchanged,
  never raises.
- ctypes only (stdlib `kernel32`); NO `wmic` (deprecated) and no `tasklist` parsing on the primary path.
  posix branch unchanged (`p.kill()`); every nt API failure degrades to the old behaviour, never an exception.
- Outer deadline: `task_runner` runs `executor.run` under a daemon-thread watchdog; on overrun it calls
  `executor.stop()` (if any) and returns a synthetic `ExecResult(code=EXIT_TIMEOUT, ...)` so the existing
  timeout branch (`task_runner.py:299`) drops the session as it already does. Bounds a backend that stalls
  for a non-subprocess reason.
- Test style, all tasks: header `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))`,
  no node/network, plain functions, nt-only steps guarded by `pytest.mark.skipif(os.name != "nt")`.

## interfaces
- `procs.stop_process_tree(p, timeout=10)` - old call shape still valid, returns None, never raises.
- `procs.create_job`, `procs.assign_job`, `procs.close_job`, `procs.register_job`, `procs.job_for`,
  `procs.pid_alive(pid) -> bool` (all new) - nt real, posix no-op/False.
- `run_pi(...) -> (code, usage, session)` - shape unchanged, EXIT_TIMEOUT 124, EXIT_RATE_LIMIT 75.
- `task_runner._attempt` result shape unchanged; a watchdog overrun yields `ExecResult(code=EXIT_TIMEOUT)`.
- `skills.resolve(names, roots=None)` - signature unchanged, result now one entry per resolved path.
- `skills.chosen_dirs`, `skills.apply_default`, `opencode` config paths: untouched.

## T1 job-object helpers
FILES: .harness/runner/procs.py, tests/test_procs.py
MUST:
- add `create_job`, `assign_job`, `close_job`, `register_job`, `job_for`, `pid_alive`; keep
  `stop_process_tree(p, timeout=10)` job-aware (terminate the registered job, else `taskkill /F /T`, then
  poll `pid_alive` until gone or `timeout`).
- nt path via ctypes only, no `wmic`/`tasklist` parsing; posix returns None/False and keeps `p.kill()`;
  already-dead pids and API failures are "dead", never a raised exception.
- new test `tests/test_procs.py::test_job_kills_detached_grandchild`: a child spawned via
  `create_job`+`assign_job`+`register_job` spawns a DETACHED_PROCESS grandchild sleeping 120s and writing
  its pid to tmp_path; after `stop_process_tree` both pids are dead within the timeout.
- no file outside FILES; no new dependency (ctypes is stdlib).
TEST: python -m pytest tests/test_procs.py -q -k detached_grandchild

## T2 job at spawn deadline
FILES: .harness/runner/executors/pi.py, tests/test_pi_executor.py
MUST: T1 landed (use `procs.create_job`/`assign_job`/`register_job`; do not redefine them).
- right after `Popen`, create+assign+register a job for `p.pid` (best effort; on any failure keep today's path).
- `run_pi` returns `(EXIT_TIMEOUT, usage, session)` at most `timeout + 5`s after Popen, whatever the pipe
  holds; the deadline is re-checked before every wait and after every TimeoutExpired; the wait slice shrinks
  to <=1s once the deadline is near, so overshoot is bounded by one slice, not a fixed 5s.
- after `stop_process_tree`: `p.kill()` inside try/except, close `p.stdout`, `t.join(1)`; the pump swallows
  ValueError/OSError on the closed pipe; `quota_ok` keeps returning False on timeout.
- new test `tests/test_pi_executor.py::test_run_pi_returns_exit_timeout_when_the_command_never_exits`: stub
  `runner.executors.pi.subprocess.Popen` (attrs pid/stdout/wait/kill/poll/returncode; wait always raises
  TimeoutExpired; stdout yields nothing then EOF), `HARNESS_PI` pointing at an existing tmp file, timeout=2.
TEST: python -m pytest tests/test_pi_executor.py -q -k never_exits

## T3 skills deduped by path
FILES: .harness/runner/skills.py, tests/test_skills.py
MUST:
- `resolve` keys on `os.path.normcase(str(Path(candidate).resolve()))`, first occurrence wins, input order
  kept, missing names still skipped, first-root-wins per name unchanged.
- one dir reached as `shared`, `./shared`, `shared/` yields exactly one entry; pi's `_skill_args` then emits
  one `--skill <dir>` per entry. No change to `--no-skills` or opencode config.
- new test `tests/test_skills.py::test_one_dir_under_three_names_yields_one_skill_arg`: tmp root with
  `shared/SKILL.md`, `LIST_FILE` monkeypatched to a tmp skills.txt holding the three spellings, `HARNESS_SKILLS=1`;
  asserts `len(skills.resolve(...)) == 1` and exactly one `--skill` in `pi._skill_args()`.
TEST: python -m pytest tests/test_skills.py -q -k one_skill_arg

## T4 outer task deadline
FILES: .harness/runner/task_runner.py, tests/test_task_runner.py
MUST:
- add `_bounded_run(...)`: run `executor.run` in a daemon thread; join for `args.timeout + 30`; on overrun
  call `executor.stop()` if present and return `ExecResult(code=EXIT_TIMEOUT, usage=zero_usage(), session=None)`.
- a normal return within the deadline is byte-for-byte unchanged; no change to retry/repair flow (the existing
  `got.code == EXIT_TIMEOUT` branch already drops the session).
- new test `tests/test_task_runner.py::test_outer_deadline_fails_a_hung_executor`: a fake executor whose `run`
  blocks past a tiny timeout+grace (monkeypatch the grace to ~0), asserts the attempt gets `EXIT_TIMEOUT` and
  `executor.stop()` was called.
TEST: python -m pytest tests/test_task_runner.py -q -k outer_deadline

## T5 write summary
FILES: .harness/plans/runner-reliability/SUMMARY.md
MUST: cover all three fixes, the files touched, and how each is wired.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/runner-reliability/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
