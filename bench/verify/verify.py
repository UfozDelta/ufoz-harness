"""verify-bench: run the 3x3x3 orchestrator x planner x executor matrix over one fixture.

`--dry` prints the matrix and exits; every other invocation runs one cell at a time,
appending a row to `bench/verify/results.csv` as soon as it finishes. The planning step
is either a headless orchestrator command (non-deterministic) or, with `--plan-via
runner`, `run_plan.py <slug> --plan SPEC.md --planner P[:m]` (the deterministic fallback).
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backends  # noqa: E402  (also puts bench/suite on sys.path)

RESULTS = REPO_ROOT / "bench" / "verify" / "results.csv"
FIXTURES = REPO_ROOT / "bench" / "suite" / "fixtures"


def _cells():
    """The suite helpers are a heavy import: keep them out of `--dry`."""
    import cells as cells_mod  # noqa: E402

    return cells_mod


def _arms(text):
    """A comma list of `backend` or `backend:model` entries. `build_matrix` takes either."""
    arms = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        arms.append(tuple(part.split(":", 1)) if ":" in part else part)
    return arms


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="verify.py",
                                 description="orchestrator x planner x executor verification matrix")
    ap.add_argument("--dry", action="store_true", help="print the matrix and exit, run nothing")
    ap.add_argument("--orchestrators", help="comma list of orchestrator[:model] (default: all)")
    ap.add_argument("--planners", help="comma list of planner[:model] (default: all)")
    ap.add_argument("--executors", help="comma list of executor[:model] (default: all)")
    ap.add_argument("--only", help="comma list of cell slugs; run only those")
    ap.add_argument("--reps", type=int, default=1, help="repetitions per cell (default 1)")
    ap.add_argument("--seed", type=int, default=0, help="matrix shuffle seed (default 0)")
    ap.add_argument("--task", default="small", help="fixture to run (default small)")
    ap.add_argument("--max-cost", type=float, default=None,
                    help="stop once cumulative plan+exec cost reaches this")
    ap.add_argument("--plan-via", choices=["headless", "runner"], default="headless",
                    help="who plans: the orchestrator (default) or run_plan.py's planner")
    ap.add_argument("--cell-timeout", type=int, default=1800, help="per-phase timeout seconds")
    ap.add_argument("--keep", action="store_true", help="keep the temp project after each cell")
    ap.add_argument("--force", action="store_true", help="rerun slugs already in results.csv")
    return ap.parse_args(argv)


def _matrix(args):
    orchestrators = _arms(args.orchestrators) or list(backends.ORCHESTRATORS)
    planners = _arms(args.planners) or list(backends.PLANNERS)
    executors = _arms(args.executors) or list(backends.EXECUTORS)
    cells = backends.build_matrix(orchestrators, planners, executors, args.reps,
                                  seed=args.seed)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        cells = [c for c in cells if c["slug"] in wanted]
    return cells


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _write_log(plan_dir, name, text):
    path = Path(plan_dir) / "logs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _run_cmd(cmd, cwd, timeout):
    """Returns (returncode, combined output, timed_out). A timeout never raises."""
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                              timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), False
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        return None, out, True


def _rules_check(phase, backend, log_text, project, slug):
    ok, offending = backends.check_rules(phase, backend, log_text, project)
    if not ok:
        backends.RULES_FAILURES.parent.mkdir(parents=True, exist_ok=True)
        with open(backends.RULES_FAILURES, "a", encoding="utf-8") as fh:
            fh.write(f"{slug}: {offending}\n")
    return ok


def _plan_brief(cell, project):
    """The whole headless prompt: the spec plus where the plan must land."""
    slug = cell["slug"]
    plan_dir = Path(project) / ".harness" / "plans" / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    spec = FIXTURES / cell["size"] / "spec.md"
    return (f"Plan the work described by the spec below. Write the plan to "
            f".harness/plans/{slug}/plan.md and its tasks to "
            f".harness/plans/{slug}/tasks.json (the plan slug is {slug}).\n\n"
            f"{_read_text(spec)}")


def run_cell(cell, args, repo_root=REPO_ROOT):
    cells = _cells()
    slug = cell["slug"]
    cell["size"] = args.task
    row = {field: "" for field in backends.CSV_FIELDS}
    row.update({"slug": slug, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "orchestrator": cell["orchestrator"], "planner": cell["planner"],
                "executor": cell["executor"], "rep": cell["rep"],
                "model": cell["model"], "seed": cell["seed"]})
    started = time.time()
    project = None
    plan_backend = cell["planner"] if args.plan_via == "runner" else cell["orchestrator"]

    def finish(status):
        row["status"] = status
        row["wall_s"] = round(time.time() - started, 1)
        return row

    needed = [(cell["planner"], cell["planner_model"]),
              (cell["executor"], cell["executor_model"])]
    if args.plan_via != "runner":
        needed.insert(0, (cell["orchestrator"], cell["orchestrator_model"]))
    for backend, model in needed:
        if not backends.preflight(backend, model):
            return finish("skipped")

    try:
        project = cells.make_project(cell, repo_root)
        plan_dir = project / ".harness" / "plans" / slug

        if args.plan_via == "runner":
            cell["plan_source"] = "planner"
            try:
                row["plan_cost"] = cells.plan_for_project(
                    cell, project, repo_root, kit_hash=cell.get("kit_hash", ""))
            except Exception as exc:
                _write_log(plan_dir, "plan.log", f"plan error: {exc}\n")
                return finish("fail")
        else:
            cmd = backends.orchestrator_command(cell["orchestrator"],
                                                cell["orchestrator_model"],
                                                _plan_brief(cell, project))
            code, output, timed_out = _run_cmd(cmd, project, args.cell_timeout)
            _write_log(plan_dir, "plan.log", output)
            if timed_out:
                return finish("timeout")
            if not ((plan_dir / "plan.md").is_file() and (plan_dir / "tasks.json").is_file()):
                return finish("fail")
            cells.commit_plan(cell, project)

        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--lint"], project,
            args.cell_timeout)
        _write_log(plan_dir, "lint.log", output)
        if timed_out:
            return finish("timeout")
        row["plan_ok"] = "true" if code == 0 else "false"
        if code != 0:
            return finish("fail")

        spec = (f"{cell['executor']}:{cell['executor_model']}"
                if cell["executor_model"] else cell["executor"])
        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--executor", spec, "--no-window"],
            project, args.cell_timeout)
        _write_log(plan_dir, "exec.log", output)
        if timed_out:
            return finish("timeout")

        # --land removes the worktree and its metrics, so read the totals before it
        metrics = cells._metrics(slug, project / ".worktrees" / slug, project)

        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--land"], project,
            args.cell_timeout)
        _write_log(plan_dir, "land.log", output)
        if timed_out:
            return finish("timeout")
        if code != 0:
            return finish("fail")

        scored = cells.score_project(cell, project, repo_root)
        scored.update({k: metrics[k] for k in ("tasks_passed", "tasks_total", "cost")})
        for key in ("tasks_passed", "tasks_total", "harness_sha", "tampered",
                    "regression_passed", "regression_total", "tests_passed", "tests_total"):
            row[key] = scored.get(key, row.get(key, ""))
        row["exec_cost"] = scored.get("cost", "")
        status = scored.get("status", "fail")

        plan_text = _read_text(plan_dir / "logs" / "plan.log")
        exec_text = _read_text(plan_dir / "logs" / "exec.log")
        rules_ok = _rules_check("plan", plan_backend, plan_text, project, slug)
        rules_ok = _rules_check("exec", cell["executor"], exec_text, project, slug) and rules_ok
        row["rules_ok"] = "true" if rules_ok else "false"
        return finish(status)
    except Exception as exc:  # a broken cell is infra, never a crash of the matrix
        print(f"  cell error: {exc}")
        return finish("infra_error")
    finally:
        if project is not None and not args.keep:
            cells.cleanup_project(cell)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _existing_slugs(path):
    done = set()
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("slug"):
                    done.add(row["slug"])
    except OSError:
        pass
    return done


def _existing_cost(path):
    total = 0.0
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                total += _num(row.get("plan_cost")) + _num(row.get("exec_cost"))
    except OSError:
        pass
    return total


def _append_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=backends.CSV_FIELDS, extrasaction="ignore")
        if fresh:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in backends.CSV_FIELDS})
        fh.flush()


def main(argv=None):
    args = parse_args(argv)
    matrix = _matrix(args)
    if args.dry:
        for cell in matrix:
            print(f"{cell['slug']} {cell['orchestrator']}/{cell['planner']}/"
                  f"{cell['executor']} r{cell['rep']}")
        return 0

    done = set() if args.force else _existing_slugs(RESULTS)
    cumulative = _existing_cost(RESULTS) if args.max_cost is not None else 0.0
    count = 0
    for cell in matrix:
        slug = cell["slug"]
        if slug in done:
            print(f"skip (already in results.csv): {slug}")
            continue
        if args.max_cost is not None and cumulative >= args.max_cost:
            print(f"stop: cumulative cost {cumulative:.4f} >= --max-cost {args.max_cost}")
            break
        print(f"run: {slug}")
        row = run_cell(cell, args)
        _append_row(RESULTS, row)
        done.add(slug)
        count += 1
        cumulative += _num(row.get("plan_cost")) + _num(row.get("exec_cost"))
        print(f"  {row.get('status')}")
    print(f"wrote {count} row(s) to {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
