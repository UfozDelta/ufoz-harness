"""verify-bench: run the 3x3x3 orchestrator x planner x executor matrix over one fixture.

`--dry` prints the matrix and exits; every other invocation runs one cell at a time,
appending a row to `bench/verify/results.csv` as soon as it finishes. The planning step
is either a headless orchestrator command (non-deterministic) or, with `--plan-via
runner`, `run_plan.py <slug> --plan SPEC.md --planner P[:m]` (the deterministic fallback).
"""
import argparse
import contextlib
import csv
import json
import os
import shutil
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
    # headless: the orchestrator plans, so the planner axis is unused; one arm unless asked
    planners = _arms(args.planners) or (list(backends.PLANNERS) if args.plan_via == "runner" else ["pi"])
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
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL)
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, (out or "") + (err or ""), False
    except subprocess.TimeoutExpired:
        # Kill the whole tree: a grandchild still holding the pipe would block communicate.
        _cells()._stop_tree(proc)
        out, err = "", ""
        with contextlib.suppress(subprocess.TimeoutExpired):
            out, err = proc.communicate(timeout=30)
        return None, (out or "") + (err or ""), True


def _record_failure(slug, text):
    backends.RULES_FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with open(backends.RULES_FAILURES, "a", encoding="utf-8") as fh:
        fh.write(f"{slug}: {text}\n")


def _rules_check(phase, backend, log_text, project, slug):
    ok, offending = backends.check_rules(phase, backend, log_text, project)
    if not ok:
        _record_failure(slug, offending)
    return ok


def _escape_check(log_text, slug):
    """True when the log shows no escape out of this cell's directory or into hidden tests."""
    ok, offending = backends.check_escape(log_text, slug)
    if not ok:
        _record_failure(slug, f"escape: {offending}")
    return ok


def _wipe_stale(cells, slug):
    """Delete other verify- cells' projects from the shared temp root, so a cell cannot read them.
    `_kit`, `_specs` and `suite-` dirs are left alone (suite runs share the root)."""
    root = Path(cells.TEMP_ROOT)
    if not root.is_dir():
        return
    for path in root.iterdir():
        if path.is_dir() and path.name.startswith("verify-") and path.name != slug:
            shutil.rmtree(path, ignore_errors=True)


def _plan_brief(cell, project):
    """The whole headless prompt: the spec plus where the plan must land."""
    slug = cell["slug"]
    plan_dir = Path(project) / ".harness" / "plans" / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    spec = FIXTURES / cell["size"] / "spec.md"
    return (f"Plan the work described by the spec below. Work only inside the current "
            f"directory and never read paths outside it. Do not read anything under .pi/. "
            f"Write the plan to "
            f".harness/plans/{slug}/plan.md and its tasks to "
            f".harness/plans/{slug}/tasks.json (the plan slug is {slug}).\n\n"
            f"{_read_text(spec)}")


def _cell(value):
    """A CSV cell. None means the backend did not report it: blank, never 0."""
    return "" if value is None else value


def _fill_phase(row, phase, data):
    for field in backends.PHASE_FIELDS:
        row[f"{phase}_{field}"] = _cell(data.get(field))


def _planner_phase(plan_dir):
    """(phase usage, attempts) from the runner's planner.json; None when there is none (cached plan)."""
    path = Path(plan_dir) / "planner.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    tokens = data.get("tokens") or {}
    usage = dict.fromkeys(backends.USAGE_FIELDS)
    for field, key in (("in", "input"), ("out", "output"), ("reason", "reasoning"),
                       ("cache_read", "cache_read"), ("cache_write", "cache_write"),
                       ("cost", "cost")):
        usage[field] = tokens.get(key)
    return {"wall_s": data.get("seconds"), **usage}, data.get("attempts")


def _exec_usage(slug, wt):
    """Executor usage for one slug, read from the worktree before --land. Token totals come
    from metrics.jsonl rows (a key no row carries stays None); tool calls are the `[toolCall`
    lines in the executor's pi logs."""
    usage = dict.fromkeys(backends.USAGE_FIELDS, None)
    usage["attempts"] = 0
    keys = (("in", "input"), ("out", "output"), ("reason", "reasoning"),
            ("cache_read", "cache_read"), ("cache_write", "cache_write"), ("cost", "cost"))
    for line in _read_text(Path(wt) / ".harness" / "metrics.jsonl").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("slug") != slug or "kind" in row or not row.get("task"):
            continue
        tokens = row.get("tokens")
        if not isinstance(tokens, dict):
            continue
        usage["attempts"] += int(row.get("attempts") or 0)
        for field, key in keys:
            if tokens.get(key) is not None:
                usage[field] = (usage[field] or 0) + tokens[key]
    logs = sorted((Path(wt) / ".harness" / "plans" / slug / "logs").glob("T*.pi.log"))
    if logs:
        usage["tool_calls"] = sum(_read_text(path).count("[toolCall") for path in logs)
    return usage


def _write_usage(repo_root, slug, phases):
    """Per-phase usage of one cell as bench/verify/usage/<slug>__<stamp>.json; returns its repo-relative path."""
    path = Path(repo_root) / "bench" / "verify" / "usage" / f"{slug}__{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(phases, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(repo_root).as_posix()


def _score_reason(scored):
    """Why a scored cell did not pass, as a short code; "" when it passed."""
    status = scored.get("status")
    if status == "pass":
        return ""
    if status == "infra_error":
        return "no_reports"
    if _num(scored.get("tasks_passed")) < _num(scored.get("tasks_total")):
        return "tasks_failed"
    if _num(scored.get("tests_passed")) < _num(scored.get("tests_total")):
        return "tests_failed"
    if _num(scored.get("regression_passed")) < _num(scored.get("regression_total")):
        return "regression_failed"
    return "tests_failed"  # all counts met but no tests counted: the scorer needs total > 0


def _save_logs(repo_root, slug, src, sub, stamp):
    """Copy a plan dir to bench/verify/logs/<slug>__<stamp>/<sub>. A failed copy is skipped, never raised."""
    dest = Path(repo_root) / "bench" / "verify" / "logs" / f"{slug}__{stamp}" / sub
    try:
        shutil.copytree(src, dest, dirs_exist_ok=True)
    except OSError:
        pass


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
    stamp = time.strftime("%Y%m%d-%H%M%S")
    wt_saved = False  # the worktree's plan dir is copied before --land removes it
    project = None
    phases = {}  # phase name -> usage dict, written to bench/verify/usage/ by finish()
    plan_backend = cell["planner"] if args.plan_via == "runner" else cell["orchestrator"]

    def finish(status, reason=""):
        row["status"] = status
        row["fail_reason"] = reason
        row["wall_s"] = round(time.time() - started, 1)
        if phases:
            row["usage_json"] = _write_usage(repo_root, slug, phases)
        return row

    needed = [(cell["planner"], cell["planner_model"]),
              (cell["executor"], cell["executor_model"])]
    if args.plan_via != "runner":
        needed.insert(0, (cell["orchestrator"], cell["orchestrator_model"]))
    for backend, model in needed:
        if not backends.preflight(backend, model):
            return finish("skipped", "skipped_preflight")

    try:
        _wipe_stale(cells, slug)
        project = cells.make_project(cell, repo_root)
        plan_dir = project / ".harness" / "plans" / slug

        if args.plan_via == "runner":
            cell["plan_source"] = "planner"
            try:
                cost = cells.plan_for_project(
                    cell, project, repo_root, kit_hash=cell.get("kit_hash", ""))
            except Exception as exc:
                _write_log(plan_dir, "plan.log", f"plan error: {exc}\n")
                return finish("fail", "plan_error")
            # a cached plan runs no planner: cost 0, no planner.json, so its plan columns stay blank
            row["plan_cached"] = "false" if cost else "true"
            row["plan_cost"] = cost if cost else ""
            planned = _planner_phase(plan_dir) if cost else None
            if planned:
                phases["plan"] = planned[0]
                _fill_phase(row, "plan", planned[0])
                row["plan_attempts"] = _cell(planned[1])
        else:
            cmd = backends.orchestrator_command(cell["orchestrator"],
                                                cell["orchestrator_model"],
                                                _plan_brief(cell, project))
            if cell["orchestrator"] == "opencode":  # else it plans in the repo it was last attached to
                cmd += ["--dir", str(project), "--model", cell["orchestrator_model"]]
            orch_started = time.time()
            code, output, timed_out = _run_cmd(cmd, project, args.cell_timeout)
            orch_wall = time.time() - orch_started
            _write_log(plan_dir, "plan.raw.jsonl", output)
            usage, rendered = backends.parse_stream(cell["orchestrator"], output)
            _write_log(plan_dir, "plan.log", rendered)
            phases["orch"] = {"wall_s": round(orch_wall, 1), **usage}
            _fill_phase(row, "orch", phases["orch"])
            row["orch_cost"] = _cell(usage["cost"])
            row["orch_turns"] = _cell(usage["turns"])
            if not _escape_check(output, slug):
                return finish("fail", "escaped_cwd")
            if timed_out:
                return finish("timeout", "timeout_orch")
            if not ((plan_dir / "plan.md").is_file() and (plan_dir / "tasks.json").is_file()):
                return finish("fail", "no_plan_files")
            cells.commit_plan(cell, project)

        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--lint"], project,
            args.cell_timeout)
        _write_log(plan_dir, "lint.log", output)
        if timed_out:
            return finish("timeout", "timeout_lint")
        row["plan_ok"] = "true" if code == 0 else "false"
        if code != 0:
            return finish("fail", "lint_failed")

        spec = (f"{cell['executor']}:{cell['executor_model']}"
                if cell["executor_model"] else cell["executor"])
        exec_started = time.time()
        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--executor", spec, "--no-window"],
            project, args.cell_timeout)
        exec_wall = time.time() - exec_started
        _write_log(plan_dir, "exec.log", output)
        if timed_out:
            return finish("timeout", "timeout_exec")

        # --land removes the worktree and its metrics, so read the totals before it
        wt = project / ".worktrees" / slug
        metrics = cells._metrics(slug, wt, project)
        exec_usage = _exec_usage(slug, wt)
        if cell["executor"] == "claude":  # claude folds cache writes into `in`: not reported
            exec_usage["cache_write"] = None
        phases["exec"] = {"wall_s": round(exec_wall, 1), **exec_usage}
        _fill_phase(row, "exec", phases["exec"])
        row["exec_attempts"] = _cell(exec_usage["attempts"])

        _save_logs(repo_root, slug, wt / ".harness" / "plans" / slug, "wt", stamp)
        wt_saved = True
        code, output, timed_out = _run_cmd(
            [sys.executable, ".harness/run_plan.py", slug, "--land"], project,
            args.cell_timeout)
        _write_log(plan_dir, "land.log", output)
        if timed_out:
            return finish("timeout", "timeout_land")
        if code != 0:
            return finish("fail", "land_failed")

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
        plan_escape_ok = _escape_check(plan_text, slug)
        escape_ok = _escape_check(exec_text, slug) and plan_escape_ok
        row["rules_ok"] = "true" if rules_ok and escape_ok else "false"
        if not escape_ok and status == "pass":
            return finish("fail", "escaped_cwd")
        return finish(status, _score_reason(scored))
    except Exception as exc:  # a broken cell is infra, never a crash of the matrix
        print(f"  cell error: {exc}")
        return finish("infra_error", "cell_exception")
    finally:
        if project is not None:
            if not wt_saved:  # the cell stopped before land: the worktree still holds its logs
                _save_logs(repo_root, slug, project / ".worktrees" / slug / ".harness" / "plans" / slug,
                           "wt", stamp)
            _save_logs(repo_root, slug, project / ".harness" / "plans" / slug, "project", stamp)
            row["logs_dir"] = f"bench/verify/logs/{slug}__{stamp}"
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
                total += (_num(row.get("orch_cost")) + _num(row.get("plan_cost"))
                          + _num(row.get("exec_cost")))
    except OSError:
        pass
    return total


def migrate_csv(path):
    """Rewrite a results.csv under an older header to `backends.CSV_FIELDS`: old values kept,
    new columns blank. Temp file then rename, so the old file survives a crash."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames == backends.CSV_FIELDS:
            return
        rows = list(reader)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=backends.CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _append_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    migrate_csv(path)
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
