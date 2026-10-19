# Plan: verify-timeoutfix
## Goal
Fix two verify-bench bugs: the escape regex mis-parses the slug at a path boundary, and a phase timeout hangs when a grandchild process holds the output pipe.

## Decisions
- Escape regex: `_ESCAPE_CELL` captures `((?:verify|suite)-[A-Za-z0-9-]*)` so trailing `>`, `.`, `"` or `\` are not part of the slug. Comparison with `slug` stays exact and case-insensitive.
- `verify._run_cmd` uses `subprocess.Popen` + `communicate(timeout=)`; on `TimeoutExpired` it calls `cells._stop_tree(proc)` (kills the process tree; reuse it via `_cells()`), then `proc.communicate(timeout=30)` inside `contextlib.suppress(subprocess.TimeoutExpired)` to collect the partial output. Return `(None, out, True)` as before; the non-timeout return is unchanged.

## interfaces
- `_run_cmd(cmd, cwd, timeout) -> (returncode|None, output, timed_out)` unchanged.

## T1 regex
FILES: bench/verify/backends.py
MUST:
- Change only the capture group of `_ESCAPE_CELL` per Decisions.
TEST: python .harness/plans/verify-timeoutfix/checks/check_t1.py

## T2 timeout
FILES: bench/verify/verify.py
MUST:
- Rewrite `_run_cmd` per Decisions (add `import contextlib` if absent).
TEST: python .harness/plans/verify-timeoutfix/checks/check_t2.py

## T3 summary
FILES: .harness/plans/verify-timeoutfix/SUMMARY.md
MUST:
- SUMMARY.md (<= 600 chars: what, files, how wired) ending `BUILD: pass` after `python bench/verify/verify.py --dry` exits 0. Write it with a bash heredoc.
TEST: python .harness/plans/verify-timeoutfix/checks/check_t3.py
