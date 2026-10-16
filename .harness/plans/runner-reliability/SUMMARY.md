# runner-reliability

1. Detached grandchildren survived a kill: ctypes kill-on-close job helpers in `procs.py`
   (`create_job`/`assign_job`/`register_job`); `stop_process_tree` kills the registered job,
   else `taskkill /F /T`, then polls `pid_alive`. `pi.py` assigns a job after Popen.
2. A hung command outran the deadline: `pi.py` shrinks the wait slice and re-checks the
   deadline around every wait; `task_runner._bounded_run` watchdog returns
   `ExecResult(EXIT_TIMEOUT)` and calls `executor.stop()` on overrun.
3. `skills.resolve` dedupes by resolved path: one dir, one `--skill`.
