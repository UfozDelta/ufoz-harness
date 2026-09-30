# Plan: worktree-fixes

## Goal
Fix two bugs in .harness/runner/worktree.py: `_exclude_worktrees` crashes inside a
linked worktree; `_link` sources shared dirs from the wrong tree when run from inside
a linked worktree.

## Decisions
- Only file changed besides tests: .harness/runner/worktree.py.
- New test file: tests/test_worktree.py (pytest style, matches tests/test_task_runner.py).
- Verified (`sed -n worktree.py`): current `_exclude_worktrees` line 57 is
  `exclude = Path(".git/info/exclude")`.
- Verified fix already exists in `.worktrees/oc-speed/.harness/runner/worktree.py`:
  `exclude = Path(_git("rev-parse", "--git-path", "info/exclude").stdout.strip() or ".git/info/exclude")`.
  Port this exact line into the current worktree.py (do not touch surrounding lines).
- `_link(name, target)` currently does `src = Path(name)` (cwd-relative) then links `target/name`
  -> `src.resolve()`. Fix: resolve `src` from the main worktree root when current cwd is a linked
  worktree, falling back to cwd if resolution fails or main-tree copy is absent.
  Main worktree root = parent of `git rev-parse --path-format=absolute --git-common-dir`
  (that git-common-dir is always `<main>/.git`).
- HARD RULES for T2: never delete/replace existing target dir (keep existing early-return
  `if dst.exists(): return`); never call shutil.rmtree anywhere.
- No other files/behavior change.

## interfaces
- `_exclude_worktrees() -> None` (no args, no return) — unchanged signature.
- `_link(name: str, target: Path) -> None` — unchanged signature; only source resolution changes.
- `_git(*args, env=None)` — reuse existing helper, don't duplicate subprocess calls.

## T1 fix exclude path
FILES: .harness/runner/worktree.py
MUST:
- Replace hardcoded `Path(".git/info/exclude")` with the git-path-resolved version shown in
  Decisions, ported verbatim from `.worktrees/oc-speed/.harness/runner/worktree.py`.
- Keep rest of `_exclude_worktrees` body unchanged.
- No other lines in worktree.py touched.
TEST: python -c "import ast; ast.parse(open('.harness/runner/worktree.py',encoding='utf-8').read())"

## T2 fix link source
FILES: .harness/runner/worktree.py
MUST:
- In `_link`, resolve the source dir from the main worktree root (parent of
  `git rev-parse --path-format=absolute --git-common-dir`) when that dir exists and contains
  `name`; else fall back to current `Path(name)` (today's behavior).
- Keep `if dst.exists(): return` (never overwrite/delete existing target).
- Do not add any `shutil.rmtree` call anywhere in the file.
- `check-ignore` / `is_dir` checks still run against the resolved source path.
TEST: python -c "import ast; ast.parse(open('.harness/runner/worktree.py',encoding='utf-8').read())"

## T3 add worktree tests
FILES: tests/test_worktree.py
MUST:
- Test A (T1 behavior): in a tmp dir, `git init`, commit a file, `git worktree add` a linked
  worktree, chdir into it (restore cwd after, even on failure), call `worktree._exclude_worktrees()`;
  assert no exception raised and the resolved common `info/exclude` file contains `.worktrees/`.
- Test B (T2 behavior): build a fake main tree in tmp with `node_modules/` dir present, add a
  linked worktree from it (no `node_modules` there); chdir into the linked worktree; call
  `worktree._link("node_modules", <linked worktree path>)`; assert a link/dir now exists at
  `<linked worktree>/node_modules` and resolves back to the main tree's `node_modules`
  (Windows: junction via `mklink /J`, already handled by existing code — do not reimplement
  linking, only test the source resolution).
- Test C: pre-create an existing dir at the target path before calling `_link`; assert `_link`
  leaves it untouched (no delete/replace) and returns without raising.
- Use real `git` subprocess calls (tests already use real git per task runner conventions);
  skip test if `git` not on PATH (`pytest.importorskip` style guard or `pytest.skip`).
TEST: python -m pytest tests/test_worktree.py -q

## T4 write summary
FILES: .harness/plans/worktree-fixes/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run
`python -m pytest tests -q` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to
SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/worktree-fixes/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
