# map-skip-worktrees
Decisions: add ".worktrees" to SKIP_DIRS in .harness/build_map.py; regenerate REPO_MAP.md.

## T1
FILES: .harness/build_map.py, .harness/context/REPO_MAP.md
MUST: ".worktrees" in SKIP_DIRS; run `python .harness/build_map.py`.
TEST: map has no .worktrees/ lines.

## T2
FILES: .harness/plans/map-skip-worktrees/SUMMARY.md
MUST: SUMMARY.md <= 600 chars.
TEST: build_map --check passes.
