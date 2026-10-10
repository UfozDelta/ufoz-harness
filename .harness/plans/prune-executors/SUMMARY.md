# prune-executors

Removed the cold `cline` executor: deleted `.harness/runner/executors/cline.py` and its
`REGISTRY` entry (`--executor cline` / `--planner cline` are now unknown; `cline-acp` stays).
Pruned its bench arms (suite/cells/duel/tests), docs (README, ARCHITECTURE, FLOWS, mermaid,
kit), the Roles lines in HARNESS.md/MAIN.md, the duplicate `## 2026-09-29 oc-speed` log
section, and the plain-cline comments in runner/watch/planner/selftest/register.tsx.
Kept `cline_acp.py`, llama, `--session`, CLINE_MODEL and HARNESS_CLINE*.
BUILD: pass