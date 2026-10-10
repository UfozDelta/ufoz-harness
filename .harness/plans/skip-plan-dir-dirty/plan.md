# Plan: skip-plan-dir-dirty
## Goal
Clean-tree check ignores `.harness/plans/<slug>/` for the slug being run. Other dirty paths still refuse.

## Decisions
- `_dirty_paths(slug=None)`: when slug given, drop paths equal to or under `.harness/plans/<slug>` (normalize `\` to `/`, strip trailing `/`). Match on path-component boundary: slug `a` must not hide `.harness/plans/ab/`.
- `_require_clean_tree(slug=None)` passes slug through; `ensure` calls `_require_clean_tree(slug)`.
- No other callers; no signature change to `ensure`. `sync_plan` untouched.
- Check script is `checks/check_t1.py`, not in any `files` list.
Verified: only caller of both helpers is `ensure` (`grep -rn _require_clean_tree .harness`)
Verified: package import path is `.harness` on sys.path, `from runner import worktree`
Unverified: `ensure` is followed by `sync_plan` in the run flow (per requester)

## interfaces
- `_dirty_paths(slug=None) -> list[str]`
- `_require_clean_tree(slug=None)`: sys.exit on remaining dirty paths

## T1 Filter plan dir
FILES: .harness/runner/worktree.py
MUST:
- `_dirty_paths("x")` omits `.harness/plans/x/...` (untracked dir, new or modified files); keeps `.harness/plans/xy/...` and any other path.
- `_dirty_paths()` unchanged behaviour.
- `ensure` passes slug to `_require_clean_tree`; refusal message unchanged.
TEST: python .harness/plans/skip-plan-dir-dirty/checks/check_t1.py

## T2 Update HARNESS docs
FILES: .harness/HARNESS.md
MUST:
- Edit only the "Clean tree required" paragraph: say the `.harness/plans/<slug>/` dir of the slug being run is ignored by the check (no plan-add commit needed); all other dirty paths still refuse.
- Keep the `--no-worktree` sentence. Leave the file's existing uncommitted edits untouched.
TEST: python -c "t=open('.harness/HARNESS.md',encoding='utf-8').read(); assert 'plans/<slug>' in t.split('Clean tree required')[1].split('**Delegate**')[0]"

## T3 write summary
FILES: .harness/plans/skip-plan-dir-dirty/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/skip-plan-dir-dirty/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
