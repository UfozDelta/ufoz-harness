# skip-plan-dir-dirty

The clean-tree guard now ignores `.harness/plans/<slug>/` for the slug being run, so a
plan's own dir needs no commit before its worktree starts. Other dirty paths still refuse.

Files: `.harness/runner/worktree.py`, `.harness/HARNESS.md`.

Wiring: `_dirty_paths(slug=None)` drops paths equal to/under `.harness/plans/<slug>`
(`\` normalized, trailing `/` stripped, component-boundary match, so `x` does not hide
`xy`; with a slug it uses `git status -uall`). `_require_clean_tree(slug=None)` forwards
it; `ensure` passes `slug`. BUILD: pass