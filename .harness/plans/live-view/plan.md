# Plan: live-view

## Goal
Watch executor output live in a new Windows terminal window. Windows only for now.

## Decisions
1. Viewer follows the text logs every executor already writes (`logs/T<n>[.retryN|.repairN].<exec>.log`,
   shared line format `[toolCall NAME] ARGS` / `[tool error] TEXT` / free text / `DONE:` / `BLOCKED:`).
   No runner or executor changes. Run end = `run.lock` gone (existing file, see plan.py).
2. New module `.harness/runner/watch.py`, stdlib only. Colors = raw ANSI; call `os.system("")` once on
   Windows to enable VT.
3. `run_plan.py <slug> --watch` = viewer in this terminal, runs nothing. `--window` (or env
   `HARNESS_WINDOW=1`) = normal run + opens a new window running `--watch`.
4. Window: `wt` if on PATH, else `cmd /c start`. Always `cmd /k` inside so the window stays open.
Verified: all 6 executors write `[toolCall`/`[tool error]` lines (grep executors/*.py).
Verified: pi logs a toolCall at message_end, right before tool_execution_start, so no pi change helps.
Unverified: `wt -w new` flag behavior on older Windows Terminal builds.

## interfaces (watch.py)
- `render_line(line: str, color: bool = False) -> str | None`; color=False output exactly:
  - blank/whitespace -> None; strip trailing `\r\n`
  - `[toolCall NAME] ARGS` -> `f"  {NAME:<6} {detail}"`, detail = first present of keys
    path, command, file_path, filePath, pattern, url in json ARGS (first line only), else raw ARGS
    (ARGS may be truncated: bad json -> raw). Whole result cut to 110 chars.
  - `[tool error] TEXT` -> `"  ✖ tool error: " + TEXT`
  - starts `DONE:` -> `"  ✔ " + line`; starts `BLOCKED:` -> `"  ✖ " + line`; else `"  │ " + line`
  - color=True: same text wrapped in ANSI (name cyan, errors/BLOCKED red, DONE green, free text dim).
- `log_title(name: str) -> str`: `T4.pi.log`->`T4`, `T4.retry1.pi.log`->`T4 retry 1`,
  `T4.repair2.claude.log`->`T4 repair 2`, `planner.log`->`planner`.
- `report_line(tid: str, text: str, color: bool = False) -> str | None`: None if no RESULT line or
  `RESULT: running`. pass -> `✔ T4 pass`, else `✖ T4 <result>`; append ` · exec {int}s` from
  `exec seconds:` and ` · accept {v}s` (value as written) from `acceptance seconds:` when present.
- `watch(plan_dir: Path, poll: float = 0.5, wait_start: float = 30.0, out=None) -> int`:
  out defaults to sys.stdout; color = out.isatty(). Header `━━ harness · <slug> ━━`. Replays existing
  logs, then follows (per-file byte offset, only complete lines, files in mtime order). Prints
  `▶ <log_title> HH:MM:SS` whenever the file producing lines changes. Prints `report_line` once per
  report RESULT change. Stops when run.lock absent AND (lock was seen, or every task in tasks.json has
  a non-running report, or wait_start elapsed): final drain, then `━━ done: P/N pass ━━`, return 0.
  Ctrl+C -> return 130. Missing plan dir -> message, return 1.
- `window_command(slug: str) -> list[str]`: tail = `["cmd", "/k", sys.executable,
  ".harness/run_plan.py", slug, "--watch"]`; with `shutil.which("wt")`:
  `["wt", "-w", "new", "--title", f"harness {slug}", "-d", os.getcwd(), *tail]`,
  else `["cmd", "/c", "start", f"harness {slug}", *tail]`.
- `open_window(slug: str) -> bool`: `subprocess.Popen(window_command(slug))`, return True; OSError ->
  print `watch with: python .harness/run_plan.py <slug> --watch`, return False.

## T1 watch module
FILES: .harness/runner/watch.py
MUST: implement interfaces exactly (use module-level `import shutil, subprocess`). Stdlib only.
TEST: python .harness/plans/live-view/checks/check_t1.py

## T2 cli wiring
FILES: .harness/runner/cli.py
MUST:
- `--watch` (store_true): after the slug check, before `--plan`:
  `sys.exit(watch.watch(Path(".harness/plans") / args.slug))`.
- `--window` (store_true, help mentions HARNESS_WINDOW=1): right after `_acquire_run_lock` in a real
  run, if `args.window or os.environ.get("HARNESS_WINDOW") == "1"`: `watch.open_window(args.slug)`.
  Never for --lint/--plan/--stats/--watch.
TEST: python .harness/plans/live-view/checks/check_t2.py

## T3 docs + summary
FILES: README.md, CLAUDE.md, .harness/MAIN.md, .harness/plans/live-view/SUMMARY.md
MUST:
- README: document `--watch`, `--window`, `HARNESS_WINDOW=1` (Windows only) where other flags are listed.
- CLAUDE.md and MAIN.md step 4 (Execute): one sentence: add `--window` so the user sees executor output live.
- SUMMARY.md <= 600 chars: what, which files, how wired.
TEST: python .harness/plans/live-view/checks/check_t3.py
