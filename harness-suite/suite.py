"""harness-suite: capability matrix over every executor x size x mode x rep.

Dry-run friendly by default: `--dry` builds the matrix, prints it and exits 0
without touching a runner, a worktree or the network.
"""
import argparse
import csv
import os
import random
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / ".harness") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / ".harness"))

from runner.executors import REGISTRY  # noqa: E402

SIZES = ["small", "medium", "large"]
MODES = ["serial", "parallel", "multi", "window"]
EXECUTORS = ["pi", "opencode", "cline", "cline-acp", "llama", "claude"]

# Final results.csv column order.
COLUMNS = [
    "ts", "size", "mode", "executor", "rep", "status", "wall_s",
    "tests_passed", "tests_total", "tasks_passed", "tasks_total", "attempts",
    "input", "output", "reasoning", "cache_read", "cost",
    "window_opened", "watch_ok", "peak_worktrees", "model", "harness_sha",
    "batch_wall_s", "tampered", "seed", "order_idx",
]

# results.csv is written with the resume key in front of the reported columns:
# the slug column is what load_existing_rows()/load_existing_slugs() key on.
CSV_FIELDS = ["slug"] + COLUMNS

RESULTS_CSV = REPO_ROOT / "harness-suite" / "results.csv"


def _thread_safe(executor: str) -> bool:
    """True unless the executor class opts out of parallel task execution."""
    return bool(getattr(REGISTRY[executor], "thread_safe", True))


def build_matrix(sizes, modes, executors, reps, seed=0):
    """All (size, mode, executor, rep) cells, shuffled deterministically."""
    cells = []
    for size in sizes:
        for mode in modes:
            for executor in executors:
                for rep in range(1, reps + 1):
                    unsupported = (
                        (mode == "parallel" and not _thread_safe(executor))
                        or (mode in ("multi", "parallel") and executor == "llama")
                        or (mode == "window" and size != "small")
                    )
                    cells.append({
                        "size": size,
                        "mode": mode,
                        "executor": executor,
                        "rep": rep,
                        "slug": f"suite-{size}-{mode}-{executor}-r{rep}",
                        "status": "unsupported" if unsupported else "pending",
                        "order_idx": 0,
                        "seed": seed,
                    })
    random.Random(seed).shuffle(cells)
    for idx, cell in enumerate(cells):
        cell["order_idx"] = idx
    return cells


def preflight_executor(name):
    """Cheap sanity check before spending a cell on an executor. Best effort."""
    if name == "llama":
        url = os.environ.get("HARNESS_LLAMA_URL") or "http://127.0.0.1:8080"
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except Exception:
            return False
    return True


def load_existing_slugs(csv_path=RESULTS_CSV):
    """Slugs that already have a row in results.csv (resume)."""
    done = set()
    if not Path(csv_path).exists():
        return done
    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                slug = row.get("slug")
                if slug:
                    done.add(slug)
    except OSError:
        return done
    return done


def load_existing_rows(csv_path=RESULTS_CSV):
    """Every prior row keyed by slug (used by --rerun-infra)."""
    rows = {}
    if not Path(csv_path).exists():
        return rows
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("slug"):
                rows[row["slug"]] = row
    return rows


def cumulative_cost(csv_path=RESULTS_CSV):
    total = 0.0
    rows = load_existing_rows(csv_path)
    for row in rows.values():
        try:
            total += float(row.get("cost") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _multi_slugs(cell):
    """The three per-size slugs one (executor, rep) multi batch produces."""
    return [f"suite-{size}-{cell['mode']}-{cell['executor']}-r{cell['rep']}"
            for size in SIZES]


class _ResultWriter:
    """Append rows to results.csv the moment they exist, so a crash mid-matrix keeps
    every finished row and a resume skips them."""

    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self.rows = 0

    def write(self, row):
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        with open(self.csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if fresh:
                writer.writeheader()
            writer.writerow(row)
            fh.flush()
        self.rows += 1


def _csv_list(value, allowed, label):
    if not value:
        return list(allowed)
    items = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in items if v not in allowed]
    if unknown:
        raise SystemExit(f"unknown {label}: {', '.join(unknown)} (choose from {', '.join(allowed)})")
    return items


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="suite.py", description="executor capability suite")
    ap.add_argument("--executors", help=f"comma list from {','.join(EXECUTORS)} (default: all)")
    ap.add_argument("--sizes", help=f"comma list from {','.join(SIZES)} (default: all)")
    ap.add_argument("--modes", help=f"comma list from {','.join(MODES)} (default: all)")
    ap.add_argument("--reps", type=int, default=3, help="repetitions per cell (default 3)")
    ap.add_argument("--seed", type=int, default=0, help="matrix shuffle seed (default 0)")
    ap.add_argument("--dry", action="store_true", help="print the matrix and exit, run nothing")
    ap.add_argument("--keep", action="store_true", help="keep worktrees/work dirs after each cell")
    ap.add_argument("--force", action="store_true", help="rerun cells already present in results.csv")
    ap.add_argument("--cell-timeout", type=int, default=1800, help="hard per-cell timeout seconds")
    ap.add_argument("--max-cost", type=float, default=None, help="stop once cumulative cost exceeds this")
    ap.add_argument("--rerun-infra", action="store_true", help="rerun only rows whose status is infra_error")
    ap.add_argument("--cleanup", action="store_true",
                    help="remove leftover suite worktrees/branches/work dirs, then exit")
    return ap.parse_args(argv)


def _leftover_slugs(repo_root=REPO_ROOT):
    """Slugs of leftover suite worktrees (.worktrees/suite-*) and branches
    (harness/suite-*), from both sources, sorted."""
    repo_root = Path(repo_root)
    sys.path.insert(0, str(repo_root / "harness-suite"))
    import cells as cells_mod  # noqa: WPS433 (heavy import, only here)
    slugs = set()
    worktrees = repo_root / ".worktrees"
    if worktrees.is_dir():
        for item in worktrees.iterdir():
            if item.is_dir() and cells_mod.is_cell_slug(item.name):
                slugs.add(item.name)
    try:
        proc = subprocess.run(["git", "branch", "--list", "harness/suite-*"],
                              cwd=str(repo_root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        for line in proc.stdout.splitlines():
            name = line.strip().lstrip("* ").strip()
            if name.startswith("harness/") and cells_mod.is_cell_slug(name[len("harness/"):]):
                slugs.add(name[len("harness/"):])
    except OSError:
        pass
    return sorted(slugs)


def run_cleanup(repo_root=REPO_ROOT):
    """Clean every leftover suite cell. Runs nothing else."""
    sys.path.insert(0, str(Path(repo_root) / "harness-suite"))
    import cells as cells_mod  # noqa: WPS433 (heavy import, only here)

    slugs = _leftover_slugs(repo_root)
    for slug in slugs:
        print(f"cleanup: {slug}")
        cells_mod.cleanup_cell({"slug": slug}, repo_root)
    print(f"cleaned {len(slugs)} leftover suite cell(s)")
    return 0


def main(argv=None):
    args = parse_args(argv)
    if args.cleanup:
        return run_cleanup(REPO_ROOT)
    sizes = _csv_list(args.sizes, SIZES, "sizes")
    modes = _csv_list(args.modes, MODES, "modes")
    executors = _csv_list(args.executors, EXECUTORS, "executors")
    reps = max(1, args.reps)

    cells = build_matrix(sizes, modes, executors, reps, seed=args.seed)

    if args.dry:
        planned = [c for c in cells if c["status"] != "unsupported"]
        # "multi" is not a run_plan mode: it batches the other sizes per (executor, rep),
        # so the headline grid counts the run_plan modes and the batch rows follow it.
        core_modes = [m for m in modes if m != "multi"]
        core_cells = [c for c in cells if c["mode"] != "multi"]
        multi_cells = [c for c in cells if c["mode"] == "multi"]
        print(f"{len(sizes)} sizes x {len(core_modes)} modes x {len(executors)} executors x {reps} reps"
              f" = {len(core_cells)} cells, seed {args.seed}")
        if multi_cells:
            print(f"plus {len(multi_cells)} multi rows, batched per executor+rep at run time"
                  f" ({len(cells)} rows total)")
        for cell in cells:
            mark = " [UNSUPPORTED]" if cell["status"] == "unsupported" else ""
            print(f"  {cell['order_idx']:>3}  {cell['slug']:<34} {cell['status']}{mark}")
        print(f"estimated real (non-unsupported) runs: {len(planned)}")
        return 0

    sys.path.insert(0, str(REPO_ROOT / "harness-suite"))
    import cells as cells_mod  # noqa: WPS433 (heavy import, only for real runs)

    prior = load_existing_rows()
    if args.rerun_infra:
        infra = {slug for slug, row in prior.items() if row.get("status") == "infra_error"}
        cells = [c for c in cells if c["slug"] in infra]

    done = set() if args.force else set(prior)
    spent = cumulative_cost()
    writer = _ResultWriter(RESULTS_CSV)
    multi_done = set()
    for cell in sorted(cells, key=lambda c: c["order_idx"]):
        if cell["status"] == "unsupported":
            writer.write(dict(cell, status="unsupported"))
            continue
        if cell["slug"] in done:
            print(f"skip (already in results.csv): {cell['slug']}")
            continue
        if cell["mode"] == "multi":
            # one batch per (executor, rep): the first multi cell runs it, the other
            # two slugs come back as extra rows and are then skipped as done.
            pair = (cell["executor"], cell["rep"])
            if pair in multi_done:
                continue
            slugs = _multi_slugs(cell)
            if not args.force and all(slug in done for slug in slugs):
                print(f"skip (multi batch already in results.csv): {slugs[0]}")
                multi_done.add(pair)
                done.update(slugs)
                continue
            multi_done.add(pair)
        if args.max_cost is not None and spent >= args.max_cost:
            print(f"stopping: cumulative cost {spent:.2f} >= --max-cost {args.max_cost}")
            break
        if not preflight_executor(cell["executor"]):
            print(f"skip (preflight failed): {cell['slug']}")
            writer.write(dict(cell, status="skipped"))
            continue
        print(f"run: {cell['slug']}")
        result = cells_mod.run_cell(cell, REPO_ROOT, cell_timeout=args.cell_timeout,
                                    keep=args.keep)
        rows = result if isinstance(result, list) else [result]
        for row in rows:
            writer.write(row)
            try:
                spent += float(row.get("cost") or 0.0)
            except (TypeError, ValueError):
                pass
            if row.get("slug"):
                done.add(row["slug"])
        if cell["mode"] != "multi" and not args.keep:
            cells_mod.cleanup_cell(cell, REPO_ROOT)

    print(f"wrote {writer.rows} rows to {RESULTS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
