# Plan: skills-list

## Goal
Executors (pi and opencode) get a curated skill list, only for frontend plans, each skill once.

## Decisions
- `.harness/skills.txt`: one skill name per line, `#` comments allowed. Content, in order:
  frontend-design, emil-design-eng, animate, pick-ui-library, mobile-native.
- New module `.harness/runner/skills.py` (the check imports these exact names):
  - `LIST_FILE = Path(".harness/skills.txt")`; `FRONTEND_EXT = (".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte")`.
  - `load_list(path=None) -> list[str]` (default LIST_FILE; missing file -> []).
  - `default_roots() -> list[Path]`: `Path(".agents/skills")`, `Path(".claude/skills")`,
    `Path.home()/".agents"/"skills"`, `Path.home()/".claude"/"skills"` (in that order).
  - `resolve(names, roots=None) -> list[Path]`: for each name in order, the first `root/name` holding a
    `SKILL.md`; missing names skipped; no name twice.
  - `enabled() -> bool`: `os.environ.get("HARNESS_SKILLS") == "1"`.
  - `plan_wants_skills(tasks) -> bool`: any task (dict with "files") has a file ending in FRONTEND_EXT.
  - `apply_default(tasks, environ)`: if "HARNESS_SKILLS" not in environ, set it to "1"/"0" by plan_wants_skills.
  - `chosen_dirs() -> list[Path]`: `resolve(load_list(), default_roots())` (look both up at call time, so tests can patch them).
- `cli.py`: right before the executor is created, `skills.apply_default([t.raw for t in plan.tasks], os.environ)`
  and print `skills: on (<n>)` or `skills: off`.
- pi (`executors/pi.py` `_skill_args`): off -> `["--no-skills"]`; on -> `["--no-skills"]` + `["--skill", str(d)]` per
  chosen dir. Verified: `--no-skills --skill X` loads only X. Remove the old HARNESS_PI_SKILLS switch.
- opencode (`executors/opencode.py`): `_serve_env` always adds `OPENCODE_DISABLE_CLAUDE_CODE=1` and
  `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` (no auto-discovery). `opencode_config`: on -> top-level
  `"skills": {"paths": [str(d.resolve()) for d in chosen dirs]}`; off -> permission `"skill": "deny"`, no `skills` key.
  Verified in the binary: config `skills.paths` is honoured.
- Existing opencode profile code (`HARNESS_OPENCODE_PROFILE`) stays as is.

## T1 skills module, list, wiring
FILES: .harness/skills.txt, .harness/runner/skills.py, .harness/runner/cli.py, .harness/runner/executors/pi.py, .harness/runner/executors/opencode.py
MUST: everything in Decisions; defaults for non-frontend plans = no skills for both executors.
TEST: python -m pytest .harness/plans/skills-list/checks/test_skills.py -q && python -m pytest tests -q

## T2 write summary
FILES: .harness/plans/skills-list/SUMMARY.md
MUST: <= 600 chars: what changed, which files. Add `BUILD: pass` if `python -m pytest tests -q` passes, else `BUILD: fail <first error>`.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/skills-list/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
