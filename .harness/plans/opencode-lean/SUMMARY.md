# opencode-lean

`HARNESS_OPENCODE_PROFILE` = default (unset) | tools | agent | noproj, each stacking on the one before.
`tools` denies todowrite, task, websearch, codesearch, list, lsp (skill stays).
`agent`+ adds a primary `executor` agent (rules + batching line) and sends `"agent": "executor"` with no
system prompt unless run() got custom rules.
`noproj` adds `OPENCODE_DISABLE_PROJECT_CONFIG=1` to the serve env.
Unknown value raises ValueError; default profile output is unchanged.

File: .harness/runner/executors/opencode.py

BUILD: pass
