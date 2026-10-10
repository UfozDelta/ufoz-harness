# Plan: land-merge-fallback
## Goal
`land()` falls back to `merge --no-ff` when ff-only fails; clean abort on conflict. Copied records get committed so main tree stays clean.

## Decisions
- Keep order from 330113f: merge first, copy records after (untracked copy would abort merge).
- Fallback: `git merge --no-ff -m "land <slug>" harness/<slug>`. Only when ff-only rc != 0.
- Conflict/fail of fallback: run `git merge --abort` (ignore its rc), print "merge conflict landing <slug>; aborted, worktree kept: resolve by hand or rebase harness/<slug>" plus git stderr/stdout, return 1. Worktree and branch untouched, no records copied.
- Records: after copytree, `git add .harness/plans/<slug>` (no -f; gitignored logs/land.patch/baseline stay out), then `git commit -m "harness(<slug>): plan records" -- .harness/plans/<slug>`. Pathspec commit so unrelated staged work is not swept in. If nothing to commit (git commit rc 1 / no diff via `git diff --cached --quiet -- <path>`), skip silently. Commit fail: print warning, still return 0 (code already landed).
- Risks: merge commit/records commit need git identity in user config (tests set env). Records commit adds one commit per land. Fallback merge may still fail on dirty overlapping main tree: same abort path. Worktree has real code in main only after merge; a semantic (non-textual) conflict is not detected.
- File count message unchanged.
- Verified: land.py ff-only at line 45; records copy 52-57 (`Read .harness/runner/land.py`). Verified: tests/test_land.py exists with `_git` helper, IDENTITY env, `worktree.ensure`. Verified: report.md under items/ is not gitignored, logs/ is (`git check-ignore`).

## interfaces
`land.land(slug) -> int` unchanged (0 ok, 1 fail). No new public names.

## T1 merge fallback
FILES: .harness/runner/land.py
MUST:
- ff-only first; on failure try `merge --no-ff`; success continues to records copy.
- Fallback failure: `git merge --abort`, print message above, return 1, worktree+branch remain.
- Update module docstring to describe fallback and records commit.
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner import land; assert land.land"

## T2 commit records
FILES: .harness/runner/land.py
MUST:
- After copytree: `git add` + pathspec `git commit` of `.harness/plans/<slug>` as in Decisions.
- No-op when nothing staged; commit failure warns, returns 0.
- Main tree has no untracked/modified files afterward (`git status --porcelain` empty).
TEST: python -c "import sys; sys.path.insert(0,'.harness'); from runner import land; assert land.land"

## T3 sequence test
FILES: tests/test_land.py
MUST:
- Add `test_land_two_plans_in_sequence`: repo with 2 plans p, q; two worktrees each commit a distinct file; land p (ff), then q (fallback no-ff, main moved); both rc 0; both files in main; `git log --merges` shows one merge.
- Assert `git status --porcelain` empty after each land (records committed).
- Add `test_land_conflict_aborts`: both branches edit same file line; second land returns 1, output has "aborted", no MERGE_HEAD, worktree still listed, tree clean.
- Both new tests call `monkeypatch.setenv` for the 4 IDENTITY vars (`land()` runs `_git` with no env; merge and records commit need an identity).
- Keep existing test passing (expect it unchanged or adjusted only if records commit changes its asserts).
TEST: python -m pytest tests/test_land.py -q

## T4 write summary
FILES: .harness/plans/land-merge-fallback/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/land-merge-fallback/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
