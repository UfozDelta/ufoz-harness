# skills-list

Curated executor skills: one list in `.harness/skills.txt` (frontend-design, emil-design-eng,
animate, pick-ui-library, mobile-native), on only for plans touching a frontend file
(`HARNESS_SKILLS`, defaulted from the plan in cli.py), each skill loaded once and the same for
both executors. New `.harness/runner/skills.py` holds the list, roots, resolve and the switch.
pi passes `--no-skills` plus one `--skill` per chosen dir; opencode disables auto-discovery and
sets config `skills.paths`, or denies `skill` when off.

BUILD: pass
