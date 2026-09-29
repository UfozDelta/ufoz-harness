# live-view

Watch executor output live in a new Windows terminal window.

- `.harness/runner/watch.py`: new stdlib module. `render_line`/`log_title`/`report_line` format the
  logs; `watch()` replays then follows each log by byte offset and stops when `run.lock` is gone;
  `window_command`/`open_window` launch a new terminal (`wt`, else `cmd /c start`).
- `.harness/runner/cli.py`: `--watch` is the viewer only (runs nothing); `--window` (or
  `HARNESS_WINDOW=1`) opens the window right after the run lock is taken.
- README runner flags + the execute step in CLAUDE.md / .harness/MAIN.md.
