"""Static plan validation + red-first proof on the untouched tree."""
import re
from pathlib import Path

from .acceptance import run_acceptance


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
        if re.search(r"(import\(|require\()\s*['\"][^'\"]+\.(ts|tsx|mts|cts)['\"]", acceptance):
            errs.append(f"{tid}: acceptance loads a .ts file through node; use tsc (planner rule 5)")
        files = t.get("files", [])
        errs += [f"{tid}: files entry '{f}' is a glob, list exact paths"
                 for f in files if "*" in f or "?" in f]
        errs += [f"{tid}: files entry '{f}' is a directory, list exact file paths"
                 for f in files if Path(f).is_dir()]
        if (any(f.endswith((".ts", ".tsx")) and not f.endswith(".d.ts") for f in files)
                and "tsc" not in acceptance):
            errs.append(f"{tid}: TypeScript files but no tsc in acceptance")
        if "tsc" in acceptance:
            if "--incremental" not in acceptance:
                warns.append(f"{tid}: tsc without --incremental")
            if not any(f.endswith((".ts", ".tsx", ".mts", ".cts")) or Path(f).name == "tsconfig.json"
                       for f in files):
                warns.append(f"{tid}: tsc but no TS files")
        if t.get("red_first", True) is False and not t.get("red_first_reason"):
            errs.append(f"{tid}: red_first false needs a red_first_reason")
        if t.get("build_gate") is True:
            if i != len(tasks) - 1:
                errs.append(f"{tid}: build_gate must be the last task")
            if not t.get("repair_check"):
                errs.append(f"{tid}: build_gate needs repair_check")
            by_id = {task.get("id"): task for task in tasks}
            ancestors, pending = set(), list(t.get("deps", []))
            while pending:
                dep = pending.pop()
                if dep in ancestors or dep not in by_id:
                    continue
                ancestors.add(dep)
                pending.extend(by_id[dep].get("deps", []))
            if not {task.get("id") for task in tasks[:i]} <= ancestors:
                errs.append(f"{tid}: build_gate must depend on all earlier tasks")
        if tid in seen:
            errs.append(f"{tid}: duplicate id")
        seen.add(tid)
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            shared = set(a.get("files", [])) & set(b.get("files", []))
            if shared and a.get("id") not in b.get("deps", []):
                warns.append(f"{a.get('id')}/{b.get('id')}: share {sorted(shared)} without a dep between them")
    for t in tasks:
        if t.get("id") in passed or not t.get("red_first", True) or "acceptance" not in t:
            continue
        if run_acceptance(t["acceptance"], t.get("expect"))[0]:
            errs.append(f"{t['id']}: acceptance already passes on the untouched tree (check-invalid)")
    print("\n".join([f"ERROR {e}" for e in errs] + [f"WARN {w}" for w in warns]) or "lint OK")
    return 1 if errs else 0
