"""Static plan validation + red-first proof on a throwaway worktree."""
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .acceptance import run_acceptance
from .plan import in_scope, uses_checks_script

# a directory entry lets the executor write anything under it: never the harness, git or deps,
# and never a directory that already holds a lot of the project
PROTECTED_DIRS = (".harness", ".git", "node_modules", ".worktrees", ".pi", ".claude")
MAX_TRACKED_UNDER_DIR = 50


HARNESS_MODULES = ("runner", "envfile", "build_map", "selftest", "run_plan")


def _shadows_harness(entry):
    """A new module outside .harness/ named like a harness module: code in its dir that
    puts .harness on sys.path and imports e.g. runner.executors gets itself instead."""
    p = Path(entry.rstrip("/"))
    if p.parts and p.parts[0] == ".harness":
        return False
    return p.stem in HARNESS_MODULES and (entry.endswith("/") or p.suffix == ".py")


def _ancestors(task, by_id):
    """Every task `task` depends on, directly or through other deps."""
    seen, pending = set(), list(task.get("deps", []))
    while pending:
        dep = pending.pop()
        if dep in seen or dep not in by_id:
            continue
        seen.add(dep)
        pending.extend(by_id[dep].get("deps", []))
    return seen


def _too_broad(entry):
    """Why a directory entry is too broad, or None."""
    rel = entry.replace("\\", "/").strip("/")
    while rel.startswith("./"):
        rel = rel[2:]
    if rel in ("", "."):
        return "the whole repo"
    if rel.split("/")[0] in PROTECTED_DIRS:
        return f"under protected {rel.split('/')[0]}/"
    r = subprocess.run(["git", "ls-files", "--", rel], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tracked = len(r.stdout.splitlines()) if r.returncode == 0 else 0
    if tracked > MAX_TRACKED_UNDER_DIR:
        return f"{tracked} tracked files under it, max {MAX_TRACKED_UNDER_DIR}"
    return None


@contextlib.contextmanager
def _worktree(plan):
    """A throwaway detached worktree of HEAD, chdir'd into; None if it cannot be made.

    red-first acceptance runs there, never in the main tree."""
    main = os.getcwd()
    tmp = wt = None
    try:
        tmp = tempfile.mkdtemp()
        wt = os.path.join(tmp, "wt")
        if subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True,
                          cwd=main).returncode != 0:
            yield None
            return
        r = subprocess.run(["git", "worktree", "add", "--detach", wt, "HEAD"],
                           capture_output=True, text=True, cwd=main)
        if r.returncode != 0:
            yield None
            return
        # the checks/ scripts a task's acceptance calls live in the plan dir: bring them along
        try:
            rel = Path(plan).resolve().relative_to(Path(main).resolve())
        except ValueError:
            rel = None
        if rel is not None:
            shutil.copytree(Path(plan), Path(wt) / rel, dirs_exist_ok=True)
        os.chdir(wt)
        try:
            yield wt
        finally:
            os.chdir(main)
    finally:
        if wt is not None:
            subprocess.run(["git", "worktree", "remove", "--force", wt],
                           capture_output=True, text=True, cwd=main)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def lint(plan, tasks, passed):
    """Static checks + red-first on every not-yet-passed task, before anything runs."""
    errs, warns, seen = [], [], set()
    plan_md = (plan / "plan.md").read_text(encoding="utf-8") if (plan / "plan.md").exists() else ""
    for d in ("items", "logs"):  # the runner writes reports/logs here; prove it can
        try:
            (plan / d).mkdir(exist_ok=True)
            probe = plan / d / ".lint-probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            errs.append(f"cannot write {d}/: {e}")
    # only a real .harness/plans/<slug> layout has a metrics.jsonl two levels up; a plan dir
    # anywhere else (e.g. a fixture's plan/) would get a stray metrics.jsonl beside it
    if plan.parent.name == "plans":
        try:
            (plan.parent.parent / "metrics.jsonl").open("a", encoding="utf-8").close()
        except OSError as e:
            errs.append(f"cannot write metrics.jsonl: {e}")
    for i, t in enumerate(tasks):
        tid = t.get("id", "?")
        errs += [f"{tid}: missing '{k}'" for k in ("id", "acceptance", "files") if k not in t]
        if "brief" in t and not (plan / t["brief"]).exists():
            errs.append(f"{tid}: brief {t['brief']} not found")
        if "brief" not in t and f"## {tid}" not in plan_md:
            errs.append(f"{tid}: no 'brief' and no '## {tid}' section in plan.md")
        errs += [f"{tid}: dep {d} is not an earlier task" for d in t.get("deps", []) if d not in seen]
        errs += [f"{tid}: {w} not found" for w in t.get("acceptance", "").split()
                 if "checks/" in w and not Path(w).exists()]
        acceptance = t.get("acceptance", "")
        if sys.platform == "win32":
            m = re.match(r"^\s*(!|test\s|rm\s)", acceptance)
            if m:
                errs.append(f"{tid}: acceptance starts with POSIX '{m.group(1).strip()}' "
                            f"which cmd.exe cannot run; use python -c")
        if re.search(r"(import\(|require\()\s*['\"][^'\"]+\.(ts|tsx|mts|cts)['\"]", acceptance):
            errs.append(f"{tid}: acceptance loads a .ts file through node; use tsc (planner rule 5)")
        files = t.get("files", [])
        errs += [f"{tid}: files entry '{f}' is a glob, list exact paths"
                 for f in files if "*" in f or "?" in f]
        errs += [f"{tid}: files entry '{f}' is a directory; directory entries must end with '/'"
                 for f in files if not f.endswith("/") and Path(f).is_dir()]
        errs += [f"{tid}: files entry '{f}' is too broad ({why})"
                 for f in files if f.endswith("/") and (why := _too_broad(f))]
        warns += [f"{tid}: files entry '{f}' shadows the harness package '{Path(f.rstrip('/')).stem}' "
                  f"(code in that dir importing it gets this file instead); rename it"
                  for f in files if _shadows_harness(f)]
        if (any(f.endswith((".ts", ".tsx")) and not f.endswith(".d.ts") for f in files)
                and "tsc" not in acceptance):
            errs.append(f"{tid}: TypeScript files but no tsc in acceptance")
        if "tsc" in acceptance:
            if "--incremental" not in acceptance:
                warns.append(f"{tid}: tsc without --incremental")
            if not any(f.endswith((".ts", ".tsx", ".mts", ".cts")) or Path(f).name == "tsconfig.json"
                       for f in files):
                warns.append(f"{tid}: tsc but no TS files")
        if (t.get("expect") is not None and not uses_checks_script(plan, acceptance)
                and not (plan / "checks").is_dir()):
            warns.append(f"{tid}: loose expect {t['expect']!r} matches any output;"
                         " add a checks/ script")
        if t.get("build_gate") is True:
            if i != len(tasks) - 1:
                errs.append(f"{tid}: build_gate must be the last task")
            if not t.get("repair_check"):
                errs.append(f"{tid}: build_gate needs repair_check")
            by_id = {task.get("id"): task for task in tasks}
            ancestors = _ancestors(t, by_id)
            if not {task.get("id") for task in tasks[:i]} <= ancestors:
                errs.append(f"{tid}: build_gate must depend on all earlier tasks")
        if tid in seen:
            errs.append(f"{tid}: duplicate id")
        seen.add(tid)
    by_id = {task.get("id"): task for task in tasks}
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            fa, fb = a.get("files", []), b.get("files", [])
            shared = {x for x in fa if in_scope(x, fb)} | {y for y in fb if in_scope(y, fa)}
            if shared and a.get("id") not in _ancestors(b, by_id):
                warns.append(f"{a.get('id')}/{b.get('id')}: share {sorted(shared)} without a dep between them")
    todo = [t for t in tasks
            if t.get("id") not in passed and "acceptance" in t
            and (t["red_first"] if "red_first" in t
                 else uses_checks_script(plan, t.get("acceptance", "")))]
    if todo:
        with _worktree(plan) as wt:
            if wt is None:
                for t in todo:
                    warns.append(f"{t.get('id')}: skipped red-first: no throwaway worktree available")
            else:
                for t in todo:
                    if run_acceptance(t["acceptance"], t.get("expect"))[0]:
                        errs.append(f"{t['id']}: acceptance already passes on the untouched tree"
                                    " (check-invalid)")
    print("\n".join([f"ERROR {e}" for e in errs] + [f"WARN {w}" for w in warns]) or "lint OK")
    return 1 if errs else 0
