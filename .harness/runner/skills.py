"""The curated skills the executors get: one list (.harness/skills.txt), on only for
frontend plans (HARNESS_SKILLS=1), the same dirs for pi and opencode, each skill once."""
import os
from pathlib import Path

LIST_FILE = Path(".harness/skills.txt")
FRONTEND_EXT = (".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte")


def load_list(path=None):
    """The names in the list file, in order; blanks and `#` comments ignored. No file, no skills."""
    try:
        text = (path or LIST_FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def default_roots():
    """Where skills live, in the order the first hit wins: project first, then the user copies."""
    return [Path(".agents/skills"), Path(".claude/skills"),
            Path.home() / ".agents" / "skills", Path.home() / ".claude" / "skills"]


def resolve(names, roots=None):
    """One directory per name: the first root holding a SKILL.md. Missing names are skipped,
    and a name never resolves twice (the first root wins, not every root)."""
    dirs = []
    for name in names:
        for root in roots if roots is not None else default_roots():
            candidate = root / name
            if (candidate / "SKILL.md").is_file():
                dirs.append(candidate)
                break
    return dirs


def enabled():
    return os.environ.get("HARNESS_SKILLS") == "1"


def plan_wants_skills(tasks):
    """True when any task touches a frontend file: a skills list is only worth the tokens there."""
    return any(str(f).endswith(FRONTEND_EXT)
               for task in tasks for f in task.get("files", []))


def apply_default(tasks, environ):
    """Set HARNESS_SKILLS from the plan unless the caller already decided (HARNESS_SKILLS=0/1)."""
    if "HARNESS_SKILLS" not in environ:
        environ["HARNESS_SKILLS"] = "1" if plan_wants_skills(tasks) else "0"
    return environ


def chosen_dirs():
    """Looked up at call time so the list and the roots can be changed after import."""
    return resolve(load_list(), default_roots())
