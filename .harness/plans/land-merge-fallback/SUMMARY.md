# land-merge-fallback

`land()` in `.harness/runner/land.py` no longer only fast-forwards: it tries
`merge --ff-only harness/<slug>` and falls back to `merge --no-ff -m "land <slug>"`.
On conflict it runs `merge --abort`, prints "merge conflict landing <slug>;
aborted, worktree kept: ..." plus git output, and returns 1, keeping the worktree
and branch. After the merge, copied plan records are staged and committed with a
pathspec commit, skipped when nothing is staged; a commit failure only warns.
`tests/test_land.py` covers the sequence (ff then no-ff) and the conflict abort.

BUILD: pass