"""Build the package's kit/ folder from this repo.

Usage: python packages/ufoz-harness/export_kit.py

Copies the harness files into packages/ufoz-harness/kit/, clearing it first
so stale files never survive. Run from the repo root.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = Path(__file__).resolve().parent / "kit"

FILES = ["CLAUDE.md", "AGENTS.md", "opencode.json",
         ".claude/agents/planner.md", ".claude/agents/reviewer.md",
         ".claude/settings.json",
         ".pi/deny.json", ".pi/executor.md",
         ".pi/extensions/deny-list.ts", ".pi/extensions/deny-match.ts",
         ".opencode/package.json", ".opencode/package-lock.json",
         "skills-lock.json",
         ".harness/run_plan.py", ".harness/selftest.py", ".harness/build_map.py",
         ".harness/envfile.py", ".harness/.env.example", ".harness/MAIN.md",
         ".harness/CHECK_PATTERNS.md"]
README_SRC = Path("packages/ufoz-harness/kit_readme.md")
SKILL_DIRS = [Path(".claude/skills"), Path(".agents/skills")]
IGNORE = shutil.ignore_patterns("__pycache__", "*.test.mjs")


def fail_missing(path):
    print(f"missing: {path}", file=sys.stderr)
    sys.exit(1)


def rel_of(path):
    return path.relative_to(ROOT) if str(path).startswith(str(ROOT)) else path


def copy_file(src, dst):
    if not src.is_file():
        fail_missing(rel_of(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_skills(src_rel):
    src = ROOT / src_rel
    if not src.is_dir():
        fail_missing(src_rel)
    for entry in sorted(src.iterdir(), key=lambda p: p.name):
        if entry.name == "__pycache__" or not entry.is_dir():
            continue
        dst = KIT / src_rel / entry.name
        shutil.copytree(entry.resolve(), dst, symlinks=False, ignore=IGNORE)


def copy_runner():
    src = ROOT / ".harness/runner"
    if not src.is_dir():
        fail_missing(Path(".harness/runner"))
    for entry in sorted(src.iterdir(), key=lambda p: p.name):
        if entry.name == "__pycache__":
            continue
        if entry.is_file():
            if entry.suffix != ".py":
                continue
            copy_file(entry, KIT / ".harness/runner" / entry.name)
        elif entry.is_dir():
            for sub in sorted(entry.rglob("*.py"), key=lambda p: p.as_posix()):
                if "__pycache__" in sub.parts:
                    continue
                copy_file(sub, KIT / ".harness/runner" / sub.relative_to(src))


def export():
    shutil.rmtree(KIT, ignore_errors=True)
    KIT.mkdir(parents=True, exist_ok=True)
    for rel in FILES:
        copy_file(ROOT / rel, KIT / rel)
    for rel in SKILL_DIRS:
        copy_skills(rel)
    copy_runner()
    agent = ROOT / ".opencode/agent"
    if not agent.is_dir():
        fail_missing(Path(".opencode/agent"))
    shutil.copytree(agent, KIT / ".opencode/agent",
                    symlinks=False, ignore=IGNORE)
    readme = ROOT / README_SRC
    if not readme.is_file():
        fail_missing(README_SRC)
    copy_file(readme, KIT / ".harness/README.md")
    (KIT / ".harness/plans").mkdir(parents=True, exist_ok=True)
    (KIT / ".harness/plans/.gitkeep").write_bytes(b"")
    count = sum(1 for p in KIT.rglob("*") if p.is_file())
    print(f"kit exported: {count} files -> {KIT}")


def main():
    export()


if __name__ == "__main__":
    main()
