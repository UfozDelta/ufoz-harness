"""One suite cell = one executor run of one fixture, end to end.

prepare_cell builds the worktree (via runner.worktree) and drops the fixture seed +
plan into it, run_cell drives run_plan.py and scores the result (hidden tests, tamper
diff, metrics.jsonl), cleanup_cell removes the worktree again. Nothing here touches git
state beyond `git worktree remove --force` and `git branch -D` on suite-* slugs.
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / ".harness") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / ".harness"))

from runner import worktree  # noqa: E402

SUITE_DIR = "harness-suite"
WORK_PREFIX = f"{SUITE_DIR}/work"
SIZES = ("small", "medium", "large")
# only names build_matrix makes; plans like `suite-fixes` share the prefix and must never match
CELL_SLUG = re.compile(r"^suite-(small|medium|large)-(serial|parallel|multi|window)-[a-z][a-z-]*-r\d+$")


def is_cell_slug(name):
    return bool(CELL_SLUG.match(name))

WINDOW_POLL_S = 15
TEST_TIMEOUT = 900
TAMPER_SENSITIVE = ("tsconfig.json", "package.json", "package-lock.json",
                    "vitest.config.ts", "vitest.config.js", "conftest.py", "pytest.ini",
                    "setup.cfg", "pyproject.toml")
TEST_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".test.js", ".test.jsx")
# built in pieces so this detector's own source never looks like what it hunts for
_TS = "@ts" + "-"
TAMPER_PATTERNS = (_TS + "ignore", _TS + "expect-error", "pytest.mark.skip",
                   "pytest.mark.xfail", "@pytest.mark.skip", "@pytest.mark.xfail",
                   "it.skip", "describe.skip", "test.skip", "test.todo", "xit(", "xdescribe(")
SKIP_DIRS = ("node_modules", ".git", "__pycache__", ".pytest_cache", ".next", ".check-tmp")
# executors that read HARNESS_MODEL from .harness/.env and pick the wrong model
EXECUTOR_MODELS = {"cline": "cline-free/deepseek-v4.1-flash",
                   "cline-acp": "stealth/space-bunny-alpha"}


# --------------------------------------------------------------------------- utils
@contextlib.contextmanager
def _chdir(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield Path(path)
    finally:
        os.chdir(old)


def node_tool(name):
    """Resolve a node CLI (npx, tsc, ...) so Windows finds npx.cmd: a bare "npx" in a
    subprocess list fails with CreateProcess."""
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"cells: required node tool not on PATH: {name}")
    return found


def _stop_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


def _pump(stream, sink):
    """Drain a child's stdout into `sink` on a thread, so a chatty run never fills the
    pipe while we wait on the process."""
    def reader():
        with contextlib.suppress(OSError, ValueError):
            for line in stream:
                sink.write(line)
        with contextlib.suppress(Exception):
            stream.close()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return thread


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _harness_sha(repo_root):
    sha = _git("rev-parse", "--short", "HEAD", cwd=repo_root).stdout.strip()
    dirty = _git("status", "--porcelain", ".harness", cwd=repo_root).stdout.strip()
    return f"{sha}-dirty" if dirty else sha


def _copy_tree(src, dst):
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _copy_files(src, dst):
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_dir():
            shutil.copytree(item, dst / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst / item.name)


def _preserve_failed(cell, repo_root):
    """Copy a failed cell's plan items and logs out of its worktree before cleanup
    takes the worktree away. The work dir / source tree itself is never copied."""
    repo_root = Path(repo_root)
    slug = cell["slug"]
    src_plan = repo_root / worktree.path_for(slug) / ".harness" / "plans" / slug
    dst_plan = repo_root / SUITE_DIR / "failed" / slug
    for name in ("items", "logs"):
        _copy_tree(src_plan / name, dst_plan / name)


def _plan_dir(root, slug):
    return Path(root) / ".harness" / "plans" / slug


def _work_dir(root, slug):
    return Path(root) / SUITE_DIR / "work" / slug


def _rel_to_work(token, work_rel):
    """Normalise a path mentioned in a task to a posix path relative to the work dir."""
    text = str(token).replace("\\", "/").strip().strip('"')
    for prefix in (work_rel + "/", "{work}/"):
        if prefix and text.startswith(prefix):
            text = text[len(prefix):]
    if not text or text.startswith(("/", "..")):
        return ""
    return text.strip("/")


def _task_files(slug, repo_root):
    """Work-relative posix paths a fixture task is allowed to touch (from its
    files/acceptance entries; the {work}/ prefix is stripped)."""
    tasks_json = _plan_dir(repo_root, slug) / "tasks.json"
    work_rel = f"{WORK_PREFIX}/{slug}"
    allowed = set()
    try:
        data = json.loads(tasks_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return allowed
    tasks = data.get("tasks", []) if isinstance(data, dict) else data
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        for entry in task.get("files") or []:
            if rel := _rel_to_work(entry, work_rel):
                allowed.add(rel)
        for entry in task.get("acceptance") or []:
            for token in str(entry).replace("\\", "/").split():
                token = token.strip("\"'`,;()")
                if token.startswith("-") or "/" not in token or "=" in token:
                    continue
                if rel := _rel_to_work(token, work_rel):
                    allowed.add(rel)
    return allowed


# ---------------------------------------------------------------------- prepare
def _branch_in_use(branch, repo_root):
    """True if any worktree has `branch` checked out."""
    out = _git("worktree", "list", "--porcelain", cwd=repo_root).stdout or ""
    return any(line.strip() == f"branch refs/heads/{branch}" for line in out.splitlines())


def prepare_cell(cell, repo_root=REPO_ROOT):
    """Worktree + fixture seed + templated plan. Returns the worktree path."""
    repo_root = Path(repo_root)
    slug, size = cell["slug"], cell["size"]
    fixtures = repo_root / SUITE_DIR / "fixtures" / size
    seed = fixtures / "seed"
    if not seed.is_dir():
        raise SystemExit(f"cells: missing fixture seed {seed} (build the fixture first)")

    # a crashed run can leave the branch behind; a checked-out worktree must keep it
    if is_cell_slug(slug):
        branch = f"harness/{slug}"
        exists = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}",
                      cwd=repo_root)
        if exists.returncode == 0 and exists.stdout.strip() and not _branch_in_use(
                branch, repo_root):
            _git("branch", "-D", branch, cwd=repo_root)

    with _chdir(repo_root):
        # harness-suite/ (fixtures, hidden tests, results) is left out of the snapshot, and
        # the snapshot has no parent, so neither the tree nor `git show HEAD~1:...` reaches it
        wt = Path(worktree.ensure(slug, exclude=[SUITE_DIR], orphan=True))

    # belt and braces: nothing of the suite may sit in the working tree before the seed
    suite_wt = wt / SUITE_DIR
    if suite_wt.is_dir():
        for item in suite_wt.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
    work = _work_dir(wt, slug)
    shutil.rmtree(work, ignore_errors=True)
    _copy_tree(seed, work)

    work_rel = f"{WORK_PREFIX}/{slug}"
    plan_src = fixtures / "plan"
    if plan_src.is_dir():
        for root in (wt, repo_root):
            dst = _plan_dir(root, slug)
            dst.mkdir(parents=True, exist_ok=True)
            for item in plan_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, dst / item.name)
    # the fixture plan may say "Work dir: `{work}`"; both copies get the real path
    for root in (wt, repo_root):
        plan_md = _plan_dir(root, slug) / "plan.md"
        if plan_md.is_file():
            plan_md.write_text(plan_md.read_text(encoding="utf-8").replace("{work}", work_rel),
                               encoding="utf-8")
    tasks_json = _plan_dir(wt, slug) / "tasks.json"
    if tasks_json.is_file():
        data = json.loads(tasks_json.read_text(encoding="utf-8").replace("{work}", work_rel))
        if isinstance(data, dict):
            data["slug"] = slug
        templated = json.dumps(data, indent=2) + "\n"
        tasks_json.write_text(templated, encoding="utf-8")
        # the main tree keeps a templated copy too, so sync_plan on a rerun has a source
        _plan_dir(repo_root, slug).joinpath("tasks.json").write_text(templated, encoding="utf-8")
    return wt


# ---------------------------------------------------------------------- scoring
def _pytest_counts(cwd, py_tests):
    proc = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
                           "--rootdir", str(cwd), "-q", *py_tests],
                          cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=TEST_TIMEOUT)
    out = (proc.stdout or "") + (proc.stderr or "")
    line = ""
    for candidate in reversed([ln for ln in out.strip().splitlines() if ln.strip()]):
        if re.search(r"\d+ (passed|failed|error|no tests ran)", candidate):
            line = candidate
            break
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", line)) else 0
    total = passed
    for pattern in (r"(\d+) failed", r"(\d+) error", r"(\d+) skipped", r"(\d+) xfailed"):
        if m := re.search(pattern, line):
            total += int(m.group(1))
    return passed, total


def _vitest_counts(cwd, ts_tests):
    npx = node_tool("npx")
    proc = subprocess.run([npx, "--no-install", "vitest", "run", *ts_tests], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TEST_TIMEOUT)
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = total = 0
    for line in out.splitlines():
        if not re.match(r"\s*Tests\s", line):
            continue
        if m := re.search(r"\((\d+)\)", line):
            total = int(m.group(1))
        passed = sum(int(n) for n in re.findall(r"(\d+) passed", line))
    total = max(total, passed)
    if not total:  # vitest died before printing a summary
        return 0, max(1, len(ts_tests))
    return passed, total


def _tsc_ok(cwd):
    npx = node_tool("npx")
    proc = subprocess.run([npx, "--no-install", "tsc", "--noEmit"], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TEST_TIMEOUT)
    return proc.returncode == 0


def _is_py_test(name):
    return name.endswith("_test.py") or (name.startswith("test_") and name.endswith(".py"))


def _hidden_layout(hidden):
    """Hidden test files, found recursively and grouped by where they must run.
    Returns (py, ts): py maps the test's top-level folder (None = the work root) to
    paths relative to the hidden root, ts maps the test's own folder to the same."""
    py, ts = {}, {}
    for path in sorted(Path(hidden).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(hidden)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if _is_py_test(path.name):
            top = rel.parts[0] if len(rel.parts) > 1 else None
            py.setdefault(top, []).append(rel)
        elif path.name.endswith(TEST_SUFFIXES):
            ts.setdefault(rel.parent, []).append(rel)
    return py, ts


def _vitest_root(start, work):
    """The nearest dir holding a vitest config, at or above start (never outside work)."""
    for candidate in (start, *start.parents):
        if ((candidate / "vitest.config.ts").is_file() or
                (candidate / "vitest.config.js").is_file()):
            return candidate
        if candidate == work:
            break
    return work


def _ts_dirs(work):
    """Every dir under work that holds a tsconfig.json (node_modules etc. skipped)."""
    work = Path(work)
    out = []
    for dirpath, dirnames, filenames in os.walk(work):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "tsconfig.json" in filenames:
            out.append(Path(dirpath))
    return sorted(out)


def _run_tests(work, size, repo_root):
    """Copy the hidden tests in (keeping their relative paths) and run them. Each group
    runs from its own dir: pytest from the test's top-level folder, vitest from the
    nearest dir holding a vitest config, tsc once per dir holding a tsconfig.json.
    Returns (passed, total)."""
    hidden = Path(repo_root) / SUITE_DIR / "fixtures" / size / "hidden_tests"
    work = Path(work)
    if not hidden.is_dir():
        return 0, 0
    _copy_tree(hidden, work)
    py_groups, ts_groups = _hidden_layout(hidden)
    passed = total = 0
    for top, rels in sorted(py_groups.items(), key=lambda kv: (kv[0] or "")):
        cwd = work / top if top else work
        names = [r.relative_to(top) if top else r for r in rels]
        with contextlib.suppress(subprocess.TimeoutExpired):
            got_passed, got_total = _pytest_counts(cwd, [str(n) for n in names])
            passed += got_passed
            total += got_total
    if not ts_groups:
        return passed, total
    for rel_dir, rels in sorted(ts_groups.items()):
        cwd = _vitest_root(work / rel_dir, work)
        names = [r.relative_to(cwd.relative_to(work)) for r in rels]
        try:
            ts_passed, ts_total = _vitest_counts(cwd, [str(n) for n in names])
        except SystemExit:  # no npx: the ts checks cannot pass
            ts_passed, ts_total = 0, 1
        passed += ts_passed
        total += ts_total
    try:
        ts_dirs = _ts_dirs(work)
    except OSError:
        ts_dirs = []
    for ts_dir in ts_dirs:
        try:
            ok = _tsc_ok(ts_dir)
        except (SystemExit, subprocess.TimeoutExpired):
            ok = False
        total += 1
        if ok:
            passed += 1
    return passed, total


def _looks_like_test(name):
    return (name in TAMPER_SENSITIVE or name.startswith(("test_", "conftest"))
            or name.endswith(TEST_SUFFIXES) or _is_py_test(name))


def _tampered(work, seed, allowed):
    """True when the executor touched a seed file it had no business touching, added a
    test/config file of its own, or slipped in a suppression the seed did not have.
    `allowed` holds work-relative posix paths from the cell's task files."""
    work, seed = Path(work), Path(seed)
    if not seed.is_dir():
        return False
    allowed = {str(a).replace("\\", "/").strip("/") for a in allowed or ()}
    hits = []
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(work).as_posix()
        if any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
            continue
        base = path.name
        src = seed / rel
        was = ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if src.is_file():
            try:
                was = src.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                was = ""
            if base in TAMPER_SENSITIVE and rel not in allowed and was != text:
                hits.append(rel)
        elif _looks_like_test(base) and rel not in allowed:
            hits.append(rel)
        for pat in TAMPER_PATTERNS:
            if pat in text and pat not in was:
                hits.append(rel)
                break
    if hits:
        print(f"  cells: tamper: {', '.join(sorted(set(hits))[:5])}")
    return bool(hits)


def _metrics(slug, wt, repo_root):
    """Totals for one slug from metrics.jsonl. Missing file/field -> 0, never raises."""
    out = {"attempts": 0, "seconds": 0.0, "cost": 0.0, "tasks_passed": 0, "tasks_total": 0,
           "input": 0, "output": 0, "reasoning": 0, "cache_read": 0}
    for candidate in (Path(wt) / ".harness" / "metrics.jsonl",
                      Path(repo_root) / ".harness" / "metrics.jsonl"):
        if not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("slug") != slug or "kind" in row:
                continue
            if not row.get("task"):
                continue
            out["tasks_total"] += 1
            if row.get("result") == "pass":
                out["tasks_passed"] += 1
            with contextlib.suppress(TypeError, ValueError):
                out["attempts"] += int(row.get("attempts") or 0)
            with contextlib.suppress(TypeError, ValueError):
                out["seconds"] += float(row.get("seconds") or 0.0)
            tokens = row.get("tokens") or {}
            if not isinstance(tokens, dict):
                tokens = {}
            for key in ("input", "output", "reasoning", "cache_read"):
                with contextlib.suppress(TypeError, ValueError):
                    out[key] += int(tokens.get(key) or 0)
            with contextlib.suppress(TypeError, ValueError):
                out["cost"] += float(tokens.get("cost") or row.get("cost") or 0.0)
        break
    for key in ("cost", "seconds"):
        out[key] = round(out[key], 6)
    return out


# ---------------------------------------------------------------------- window
def _window_opened(slug, timeout=WINDOW_POLL_S):
    if os.name != "nt":
        return ""
    ps = (f"$ErrorActionPreference='SilentlyContinue';"
          f"Get-CimInstance Win32_Process | Where-Object {{$_.CommandLine -like '*{slug}*' -and "
          f"$_.CommandLine -like '*--watch*'}} | Select-Object -First 1 -ExpandProperty CommandLine")
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if (proc.stdout or "").strip():
            return "true"
        time.sleep(1)
    return "false"


def _watch_ok(slug, repo_root, wt):
    """A separate headless --watch run must report a completed plan."""
    proc = subprocess.run([sys.executable, ".harness/run_plan.py", slug, "--watch", "--no-window"],
                          cwd=str(wt), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    return "true" if "done:" in ((proc.stdout or "") + (proc.stderr or "")) else "false"


# ---------------------------------------------------------------------- rows
METRIC_FIELDS = ("attempts", "input", "output", "reasoning", "cache_read", "cost",
                 "tasks_passed", "tasks_total")


def _blank(cell):
    row = dict(cell)
    row.update({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "wall_s": "", "tests_passed": "",
                "tests_total": "", "attempts": "", "input": "", "output": "",
                "reasoning": "", "cache_read": "", "cost": "", "window_opened": "",
                "watch_ok": "", "peak_worktrees": "",
                "model": os.environ.get("HARNESS_EXECUTOR_MODEL", cell["executor"]),
                "harness_sha": "", "batch_wall_s": "", "tampered": ""})
    return row


def _plan_args(cell, wt, parallel=0):
    args = [sys.executable, ".harness/run_plan.py", cell["slug"],
            "--executor", cell["executor"], "--no-worktree"]
    if model := EXECUTOR_MODELS.get(cell["executor"]):
        args += ["--executor-model", model]
    if cell["mode"] != "window":
        args.append("--no-window")
    if parallel > 1:
        args += ["--parallel", str(parallel)]
    return args


def _finish(cell, row, wt, repo_root, reports):
    """Common post-run bookkeeping: metrics first, then tamper (before the hidden tests
    land in the work dir), then the hidden tests themselves."""
    metrics = _metrics(cell["slug"], wt, repo_root)
    row.update({k: metrics[k] for k in METRIC_FIELDS})
    work = _work_dir(wt, cell["slug"])
    row["tampered"] = "true" if _tampered(
        work, Path(repo_root) / SUITE_DIR / "fixtures" / cell["size"] / "seed",
        _task_files(cell["slug"], repo_root)) else "false"
    if not reports:
        row["status"] = "infra_error"
    else:
        passed, total = _run_tests(work, cell["size"], repo_root)
        row["tests_passed"], row["tests_total"] = passed, total
        if total and passed == total and metrics["tasks_passed"] == metrics["tasks_total"]:
            row["status"] = "pass"
        else:
            row["status"] = "fail"
    row["harness_sha"] = _harness_sha(repo_root)
    return row


# ---------------------------------------------------------------------- run
def _poll_until(proc, deadline, clock=time.time, sleep_fn=time.sleep):
    """Wait for `proc`, comparing the wall clock: proc.wait(timeout=) counts sleep time
    towards the timeout it is meant to bound. True if it was still running past `deadline`."""
    while proc.poll() is None:
        if clock() >= deadline:
            return True
        sleep_fn(1)
    return False


def _run_single(cell, repo_root, cell_timeout):
    """serial / parallel / window: one run_plan process, one row."""
    row = _blank(cell)
    slug, mode = cell["slug"], cell["mode"]
    wt = prepare_cell(cell, repo_root)
    # the log lives outside the work dir: cleanup must not take it, and a run's
    # own output is never part of what gets scored
    log = Path(repo_root) / SUITE_DIR / "work" / "_logs" / f"{slug}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    args = _plan_args(cell, wt, parallel=3 if mode == "parallel" else 0)
    proc = subprocess.Popen(args, cwd=str(wt), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", stdin=subprocess.DEVNULL)
    with log.open("w", encoding="utf-8") as fh:
        thread = _pump(proc.stdout, fh)
        if mode == "window":
            row["window_opened"] = _window_opened(slug)
        t0 = time.time()
        timed_out = _poll_until(proc, t0 + cell_timeout)
        if timed_out:
            _stop_tree(proc)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=30)
        thread.join(timeout=30)
        row["wall_s"] = round(time.time() - t0, 1)
    _stop_tree(proc)
    reports = sorted(_plan_dir(wt, slug).glob("items/*.report.md"))
    if timed_out:
        row["status"] = "timeout"
        metrics = _metrics(slug, wt, repo_root)
        row.update({k: metrics[k] for k in METRIC_FIELDS})
        row["harness_sha"] = _harness_sha(repo_root)
    else:
        _finish(cell, row, wt, repo_root, reports)
    if mode == "window":
        with contextlib.suppress(Exception):
            row["watch_ok"] = _watch_ok(slug, repo_root, wt)
    return row


def _run_multi(cell, repo_root, cell_timeout, keep=False):
    """multi: the three sizes of one (executor, rep) run concurrently. One row per size."""
    log_dir = Path(repo_root) / SUITE_DIR / "work" / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    running = {}
    for size in SIZES:
        sub = dict(cell, size=size,
                   slug=f"suite-{size}-{cell['mode']}-{cell['executor']}-r{cell['rep']}")
        wt = prepare_cell(sub, repo_root)
        args = _plan_args(sub, wt)
        fh = (log_dir / f"{sub['slug']}.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(args, cwd=str(wt), stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        running[size] = (sub, wt, fh, proc)
    t0 = time.time()
    peak = 0
    deadline = t0 + cell_timeout
    timed_out = set()
    while any(p.poll() is None for _, _, _, p in running.values()):
        if time.time() >= deadline:
            timed_out = {size for size, (_, _, _, p) in running.items() if p.poll() is None}
            break
        with contextlib.suppress(OSError):
            peak = max(peak, sum(1 for p in (Path(repo_root) / ".worktrees").glob("suite-*")
                                     if is_cell_slug(p.name)))
        time.sleep(1)
    for _, _, _, proc in running.values():
        if proc.poll() is None:
            _stop_tree(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=30)
    for _, _, fh, _ in running.values():
        with contextlib.suppress(OSError):
            fh.close()
    batch_wall = round(time.time() - t0, 1)
    rows = []
    for size, (sub, wt, _, _) in running.items():
        row = _blank(sub)
        row["batch_wall_s"] = batch_wall
        row["peak_worktrees"] = peak
        reports = sorted(_plan_dir(wt, sub["slug"]).glob("items/*.report.md"))
        if size in timed_out:
            row["status"] = "timeout"
            metrics = _metrics(sub["slug"], wt, repo_root)
            row.update({k: metrics[k] for k in METRIC_FIELDS})
            row["harness_sha"] = _harness_sha(repo_root)
            rows.append(row)
        else:
            rows.append(_finish(sub, row, wt, repo_root, reports))
        if not keep:
            if row["status"] != "pass":
                _preserve_failed(sub, repo_root)
            cleanup_cell(sub, repo_root)
    return rows


def run_cell(cell, repo_root=REPO_ROOT, cell_timeout=1800, keep=False):
    """Run one cell. Returns its row (a list of rows, one per size, for mode 'multi')."""
    repo_root = Path(repo_root)
    if cell.get("mode") == "multi":
        return _run_multi(cell, repo_root, cell_timeout, keep=keep)
    try:
        row = _run_single(cell, repo_root, cell_timeout)
        result = row[0] if isinstance(row, list) else row
        if not keep and result.get("status") != "pass":
            _preserve_failed(cell, repo_root)
        return row
    finally:
        if not keep:
            cleanup_cell(cell, repo_root)


def _is_junction(path):
    if hasattr(os.path, "isjunction") and os.path.isjunction(path):
        return True
    try:
        return os.path.islink(path) or bool(os.readlink(path))
    except OSError:
        return False


def _remove_leftover(path):
    """Remove what `git worktree remove --force` left behind. Junctions (node_modules)
    are unlinked with rmdir, never followed: rmtree would delete their real target."""
    path = Path(path)
    if not path.exists():
        return
    for dirpath, dirnames, _ in os.walk(path):
        for name in list(dirnames):
            candidate = Path(dirpath) / name
            if _is_junction(candidate):
                dirnames.remove(name)
                with contextlib.suppress(OSError):
                    os.rmdir(candidate)
    shutil.rmtree(path, ignore_errors=True)


def cleanup_cell(cell, repo_root=REPO_ROOT, sleep_fn=time.sleep):
    """Drop the worktree, its branch, and this cell's plan/work dir. Never rmtree a
    worktree path directly: node_modules is a junction into the root tree."""
    repo_root = Path(repo_root)
    slug = cell["slug"]
    if not is_cell_slug(slug):  # only ever delete what the suite created
        raise ValueError(f"cleanup_cell: refusing non-suite slug {slug!r}")
    # a just-stopped agent can still hold a file open; retry before falling back
    for attempt in range(3):
        done = _git("worktree", "remove", "--force", f".worktrees/{slug}", cwd=repo_root)
        if done.returncode == 0:
            break
        if attempt < 2:
            sleep_fn(1)
    _remove_leftover(Path(repo_root) / ".worktrees" / slug)
    _git("worktree", "prune", cwd=repo_root)
    _git("branch", "-D", f"harness/{slug}", cwd=repo_root)
    still = _git("rev-parse", "--verify", "--quiet", f"refs/heads/harness/{slug}",
                 cwd=repo_root)
    if still.returncode == 0 and still.stdout.strip():
        print(f"cells: warning: branch harness/{slug} still exists after cleanup")
    plan = _plan_dir(repo_root, slug)
    if plan.is_dir() and is_cell_slug(plan.name):
        shutil.rmtree(plan, ignore_errors=True)
    work = _work_dir(repo_root, slug)
    if work.is_dir() and work.parent.name == "work":
        shutil.rmtree(work, ignore_errors=True)
