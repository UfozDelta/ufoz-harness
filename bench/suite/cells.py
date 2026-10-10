"""One suite cell = one executor run of one fixture, end to end.

prepare_cell builds the worktree (via runner.worktree) and drops the fixture seed +
plan into it, run_cell drives run_plan.py and scores the result (hidden tests, tamper
diff, metrics.jsonl), cleanup_cell removes the worktree again. Nothing here touches git
state beyond `git worktree remove --force` and `git branch -D` on suite-* slugs.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / ".harness") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / ".harness"))

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner import worktree  # noqa: E402
from tasks import cell_slug  # noqa: E402

os.environ.setdefault("HARNESS_QUOTA_MAX_WAIT", "180")

SUITE_DIR = "bench/suite"
WORK_PREFIX = f"{SUITE_DIR}/work"
TEMP_ROOT = Path(tempfile.gettempdir()) / "ufoz-bench"
PLAN_CACHE = Path(REPO_ROOT) / "bench/suite/plan_cache"
SIZES = ("small", "medium", "large")
# only names build_matrix makes; plans like `suite-fixes` share the prefix and must never match
CELL_SLUG = re.compile(r"^suite-[a-z0-9][a-z0-9-]*-(serial|parallel|multi|window)-[a-z][a-z0-9-]*-r\d+$")


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
KIT_DIRS = (".claude", ".harness", ".worktrees", ".opencode", ".pi", ".agents")
FIXTURE_SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}
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
    diff = _git("diff", "HEAD", cwd=repo_root).stdout
    if diff.strip():
        return f"{sha}+{hashlib.sha256(diff.encode('utf-8', 'replace')).hexdigest()[:6]}"
    return sha


def _fixture_hash(size, repo_root=REPO_ROOT):
    root = Path(repo_root) / SUITE_DIR / "fixtures" / size
    if not root.is_dir():
        return ""
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file()
                   and not (set(p.relative_to(root).parts) & FIXTURE_SKIP_DIRS))
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


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
        # bench/suite/ (fixtures, hidden tests, results) is left out of the snapshot, and
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
    """Every dir under work that holds a tsconfig.json (node_modules etc. skipped, and the
    installed kit's own dirs: its skills carry tsconfigs that are not the project's)."""
    work = Path(work)
    out = []
    skip = SKIP_DIRS + KIT_DIRS
    for dirpath, dirnames, filenames in os.walk(work):
        dirnames[:] = [d for d in dirnames if d not in skip]
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


def _regression_counts(project, size, repo_root):
    """Pristine seed tests restored over the landed tree and counted like the hidden ones,
    so a landed change that breaks an existing test scores lower."""
    seed = Path(repo_root) / SUITE_DIR / "fixtures" / size / "seed"
    if not seed.is_dir():
        return 0, 0
    project = Path(project)
    py_groups, ts_groups = _hidden_layout(seed)
    for rels in (*py_groups.values(), *ts_groups.values()):
        for rel in rels:
            (project / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(seed / rel, project / rel)
    passed = total = 0
    py_names = [str(rel) for rels in py_groups.values() for rel in rels]
    if py_names:
        with contextlib.suppress(subprocess.TimeoutExpired):
            passed, total = _pytest_counts(project, py_names)
    for rel_dir, rels in sorted(ts_groups.items()):
        cwd = _vitest_root(project / rel_dir, project)
        names = [r.relative_to(cwd.relative_to(project)) for r in rels]
        try:
            ts_passed, ts_total = _vitest_counts(cwd, [str(n) for n in names])
        except SystemExit:  # no npx: the ts checks cannot pass
            ts_passed, ts_total = 0, 1
        passed += ts_passed
        total += ts_total
    return passed, total


TAMPER_EXCLUDES = (".harness", ".claude", ".pi", ".opencode", ".agents", "CLAUDE.md",
                   "AGENTS.md", "opencode.json", "skills-lock.json", ".gitignore")


def _tamper_change(kind, rel, allowed):
    name = Path(rel).name
    if kind == "A":
        return _looks_like_test(name) and rel not in allowed
    return name in TAMPER_SENSITIVE and rel not in allowed


def _tampered_git(project, seed_commit, base_commit, allowed):
    """Git-based tamper check on the landed tree: changes against the seed (tracked and
    untracked), plus suppressions added since the plan commit. Harness/agent dirs are out."""
    project = Path(project)
    allowed = {str(a).replace("\\", "/").strip("/") for a in allowed or ()}
    scope = ["--", ".", *(f":(exclude){p}" for p in TAMPER_EXCLUDES)]
    hits = []
    for line in _git("diff", "--name-status", seed_commit, *scope, cwd=project).stdout.splitlines():
        status, *paths = line.split("\t")
        if status[:1] in ("R", "C"):
            changes = [("D", paths[0]), ("A", paths[1])]
        else:
            changes = [(status[:1], paths[0])]
        hits += [rel for kind, rel in changes if _tamper_change(kind, rel, allowed)]
    for rel in _git("ls-files", "--others", "--exclude-standard", *scope,
                    cwd=project).stdout.splitlines():
        path = project / rel
        text = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
        if _tamper_change("A", rel, allowed) or any(pat in text for pat in TAMPER_PATTERNS):
            hits.append(rel)
    current = ""
    for line in _git("diff", "-U0", base_commit, *scope, cwd=project).stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and any(pat in line for pat in TAMPER_PATTERNS):
            hits.append(current)
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
          f"$_.CommandLine -like '*runner*watch.py*'}} | Select-Object -First 1 -ExpandProperty CommandLine")
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
    """A separate headless watch.py run must report a completed plan."""
    proc = subprocess.run([sys.executable, ".harness/runner/watch.py", slug],
                          cwd=str(wt), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    return "true" if "done:" in ((proc.stdout or "") + (proc.stderr or "")) else "false"


# ---------------------------------------------------------------------- rows
METRIC_FIELDS = ("attempts", "input", "output", "reasoning", "cache_read", "cost",
                 "tasks_passed", "tasks_total")


def _junk_status(row):
    """If status is timeout, or fail with wall_s < 20, and input+output tokens are 0/blank, set status to infra_error."""
    status = row.get("status")
    input_tokens = row.get("input", 0)
    output_tokens = row.get("output", 0)
    wall_s = row.get("wall_s", 0)

    # Normalize wall_s to a number for comparison (empty string becomes 0)
    try:
        wall_s_num = float(wall_s) if wall_s else 0
    except (TypeError, ValueError):
        wall_s_num = 0

    # Check if input/output tokens are 0 or blank
    tokens_zero = (
        (input_tokens == 0 or input_tokens == "") and
        (output_tokens == 0 or output_tokens == "")
    )

    if tokens_zero:
        if status == "timeout" and wall_s_num > 0:
            row["status"] = "infra_error"
        elif status == "fail" and wall_s_num < 20:
            row["status"] = "infra_error"


def _blank(cell):
    row = dict(cell)
    row.update({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "wall_s": "", "tests_passed": "",
                "tests_total": "", "attempts": "", "input": "", "output": "",
                "reasoning": "", "cache_read": "", "cost": "", "window_opened": "",
                "watch_ok": "", "peak_worktrees": "",
                "model": (cell.get("model") or os.environ.get("HARNESS_EXECUTOR_MODEL")
                          or EXECUTOR_MODELS.get(cell["executor"]) or cell["executor"]),
                "harness_sha": "", "batch_wall_s": "", "tampered": "",
                "fixture_hash": _fixture_hash(cell["size"]),
                "plan_source": cell.get("plan_source", "fixture"),
                "planner": cell.get("planner", ""), "plan_cost": "",
                "regression_passed": "", "regression_total": "",
                "kit_hash": cell.get("kit_hash", "")})
    return row


def _apply_window_verdict(row):
    """A window cell passes only if the window opened and the headless watch saw the plan finish."""
    if row.get("mode") != "window" or row.get("status") != "pass":
        return
    if str(row.get("window_opened", "")).lower() == "false" or \
            str(row.get("watch_ok", "")).lower() == "false":
        row["status"] = "harness_fail"


def _plan_args(cell, wt, parallel=0, isolated=False):
    spec = cell["executor"]
    if model := (cell.get("model") or os.environ.get("HARNESS_EXECUTOR_MODEL")
                 or EXECUTOR_MODELS.get(cell["executor"])):
        spec += f":{model}"
    args = [sys.executable, ".harness/run_plan.py", cell["slug"], "--executor", spec]
    if not isolated:
        args.append("--no-worktree")
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
        _apply_window_verdict(row)
    _junk_status(row)
    return row


def _run_multi(cell, repo_root, cell_timeout, keep=False):
    """multi: the three sizes of one (executor, rep) run concurrently. One row per size."""
    log_dir = Path(repo_root) / SUITE_DIR / "work" / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    running = {}
    for size in SIZES:
        sub = dict(cell, size=size,
                   slug=cell_slug(size, cell["mode"], cell["executor"], cell.get("model", ""),
                                  cell["rep"]))
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
        else:
            _finish(sub, row, wt, repo_root, reports)
        _junk_status(row)
        rows.append(row)
        if not keep:
            if row["status"] != "pass":
                _preserve_failed(sub, repo_root)
            cleanup_cell(sub, repo_root)
    return rows


def _score_project(cell, row, project, repo_root, reports):
    slug, size = cell["slug"], cell["size"]
    tampered = _tampered_git(project, cell["seed_commit"], cell["base_commit"],
                             _task_files(slug, project))
    row["tampered"] = "true" if tampered else "false"
    if not reports:
        row["status"] = "infra_error"
        return
    row["regression_passed"], row["regression_total"] = _regression_counts(project, size, repo_root)
    passed, total = _run_tests(project, size, repo_root)
    row["tests_passed"], row["tests_total"] = passed, total
    ok = (total and passed == total and row["tasks_passed"] == row["tasks_total"]
          and row["regression_passed"] == row["regression_total"])
    row["status"] = "pass" if ok else "fail"


def _run_project(cell, repo_root, cell_timeout):
    """Isolated path: a temp git project with the kit installed and the plan committed,
    run_plan inside it, then --land and score the landed tree. A project failure is an
    infra_error and runs no executor."""
    row = _blank(cell)
    slug, mode = cell["slug"], cell["mode"]
    try:
        project = make_project(cell, repo_root)
        row["kit_hash"] = cell["kit_hash"]
        row["plan_cost"] = plan_for_project(cell, project, repo_root, kit_hash=cell["kit_hash"])
    except ProjectError as exc:
        print(f"  cells: project error: {exc}")
        row["status"] = "infra_error"
        return row
    wt = project / ".worktrees" / slug
    log = Path(repo_root) / SUITE_DIR / "work" / "_logs" / f"{slug}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    args = _plan_args(cell, project, parallel=3 if mode == "parallel" else 0, isolated=True)
    proc = subprocess.Popen(args, cwd=str(project), stdout=subprocess.PIPE,
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
    metrics = _metrics(slug, wt, project)
    row.update({k: metrics[k] for k in METRIC_FIELDS})
    if timed_out:
        row["status"] = "timeout"
    else:
        landed = subprocess.run([sys.executable, ".harness/run_plan.py", slug, "--land"],
                                cwd=str(project), capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if landed.returncode != 0:
            row["status"] = "harness_fail"
        else:
            _score_project(cell, row, project, repo_root, reports)
    row["harness_sha"] = _harness_sha(repo_root)
    if mode == "window":
        with contextlib.suppress(Exception):
            row["watch_ok"] = _watch_ok(slug, repo_root, wt)
        _apply_window_verdict(row)
    _junk_status(row)
    return row


def _preserve_project(cell, repo_root):
    src = Path(cell["project"]) / ".worktrees" / cell["slug"] / ".harness" / "plans" / cell["slug"]
    dst = Path(repo_root) / SUITE_DIR / "failed" / cell["slug"]
    for name in ("items", "logs"):
        _copy_tree(src / name, dst / name)


MAX_FS_SLUG = 40


def _short_slug(cell):
    """The slug itself when short; else suite-<task>-<mode>-<exec>-<hash>-r<rep>, still a cell slug."""
    slug = cell["slug"]
    if len(slug) <= MAX_FS_SLUG:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:6]
    task = cell["size"][:12].rstrip("-")
    return f"suite-{task}-{cell['mode']}-{cell['executor']}-{digest}-r{cell['rep']}"


def run_cell(cell, repo_root=REPO_ROOT, cell_timeout=1800, keep=False):
    """Run one cell in its own temp project. Returns its row (a list of rows for legacy multi)."""
    repo_root = Path(repo_root)
    if cell.get("legacy"):
        return _run_legacy_cell(cell, repo_root, cell_timeout, keep)
    if cell.get("mode") == "multi":
        print("  cells: mode multi still runs on the legacy lab worktree path")
        return _run_multi(cell, repo_root, cell_timeout, keep=keep)
    # The real slug stays the results key; the filesystem (project dir, worktree, branch, plan
    # dir) uses a short one, because Windows paths + the kit's deep skill dirs overflow 260 chars
    # once a model name is in the slug.
    orig_slug = cell["slug"]
    cell = {**cell, "slug": _short_slug(cell)}
    try:
        row = _run_project(cell, repo_root, cell_timeout)
        row["slug"] = orig_slug
        if not keep and row.get("status") != "pass" and cell.get("project"):
            _preserve_project(cell, repo_root)
        return row
    finally:
        if not keep:
            cleanup_project(cell)


def _run_legacy_cell(cell, repo_root, cell_timeout=1800, keep=False):
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


class ProjectError(Exception):
    pass


_KIT_CACHE = {}


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


def ensure_kit(repo_root=REPO_ROOT):
    repo_root = Path(repo_root)
    key = str(repo_root)
    if key in _KIT_CACHE:
        return _KIT_CACHE[key]
    pkg = repo_root / "packages" / "ufoz-harness"
    root = TEMP_ROOT / "_kit"
    kit = root / "kit"
    try:
        root.mkdir(parents=True, exist_ok=True)
        for name in ("index.js", "package.json"):
            shutil.copy2(pkg / name, root / name)
    except OSError as exc:
        raise ProjectError(f"kit copy failed: {exc}") from exc
    done = subprocess.run([sys.executable, str(pkg / "export_kit.py"), "--kit-dir", str(kit)],
                          cwd=str(repo_root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise ProjectError(f"kit export failed: {done.stderr.strip()[-300:]}")
    _KIT_CACHE[key] = (root, _tree_hash(kit))
    return _KIT_CACHE[key]


def node_modules_cache(size, repo_root=REPO_ROOT):
    seed = Path(repo_root) / SUITE_DIR / "fixtures" / size / "seed"
    base = seed / "web" if size == "large" else seed
    lock = base / "package-lock.json"
    if not lock.is_file():
        return None
    key = hashlib.sha256(lock.read_bytes()).hexdigest()[:12]
    cache = TEMP_ROOT / "_nm" / key
    if not (cache / "node_modules").is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / "package.json", cache / "package.json")
        shutil.copy2(lock, cache / "package-lock.json")
        done = subprocess.run([node_tool("npm"), "ci"], cwd=str(cache), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if done.returncode != 0:
            shutil.rmtree(cache / "node_modules", ignore_errors=True)
            raise ProjectError(f"npm ci failed: {done.stderr.strip()[-300:]}")
    return cache / "node_modules"


def _must_git(project, *args):
    done = _git(*args, cwd=project)
    if done.returncode != 0:
        raise ProjectError(f"git {args[0]} failed: {done.stderr.strip()[-300:]}")
    return done.stdout.strip()


def _link_dir(link, target):
    try:
        if os.name == "nt":
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                  capture_output=True, text=True)
            if done.returncode != 0:
                raise ProjectError(f"mklink failed: {done.stderr.strip()}")
        else:
            os.symlink(target, link, target_is_directory=True)
    except OSError as exc:
        raise ProjectError(f"link failed: {exc}") from exc


def _clear_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _wipe(path):
    _remove_leftover(path)
    if path.exists():
        shutil.rmtree(path, onerror=_clear_readonly)


def make_project(cell, repo_root=REPO_ROOT, kit=None):
    repo_root = Path(repo_root)
    size, slug = cell["size"], cell["slug"]
    kit_root, kit_hash = kit or ensure_kit(repo_root)
    seed = repo_root / SUITE_DIR / "fixtures" / size / "seed"
    if not seed.is_dir():
        raise ProjectError(f"missing fixture seed {seed}")
    project = TEMP_ROOT / slug.removeprefix("suite-")
    _wipe(project)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed, project)
    (project / ".gitignore").write_text("node_modules/\n.next/\n__pycache__/\n", encoding="utf-8")
    _must_git(project, "init", "-b", "main")
    _must_git(project, "config", "user.name", "ufoz-bench")
    _must_git(project, "config", "user.email", "bench@localhost")
    _must_git(project, "config", "commit.gpgsign", "false")
    _must_git(project, "add", "-A")
    _must_git(project, "commit", "-q", "-m", "seed")
    cell["seed_commit"] = _must_git(project, "rev-parse", "HEAD")
    done = subprocess.run([node_tool("node"), str(kit_root / "index.js"), "--yes", "--dir", str(project)],
                          cwd=str(project), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise ProjectError(f"kit install failed: {done.stderr.strip()[-300:]}")
    _must_git(project, "add", "-A")
    _must_git(project, "commit", "-q", "--allow-empty", "-m", "harness")
    cache = node_modules_cache(size, repo_root)
    if cache is not None:
        where = project / "web" if size == "large" else project
        _link_dir(where / "node_modules", cache)
    cell["project"] = str(project)
    cell["kit_hash"] = kit_hash
    return project


def cleanup_project(cell):
    project = cell.get("project")
    if not project:
        return
    path = Path(project)
    if TEMP_ROOT not in path.parents:
        raise ValueError(f"cleanup_project: refusing path outside {TEMP_ROOT}: {path}")
    _wipe(path)


def _rewrite_slug(plan_dir, old, new):
    """A cached plan carries the slug of the cell that generated it in its paths and acceptance
    commands (SUMMARY.md path, log paths); point them at this cell's plan dir."""
    plan_dir = Path(plan_dir)
    files = [plan_dir / "plan.md", plan_dir / "tasks.json", *sorted((plan_dir / "checks").glob("*.py"))]
    for path in files:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if old in text:
                path.write_text(text.replace(old, new), encoding="utf-8")


def _retag_plan(plan_dir, slug):
    path = plan_dir / "tasks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["slug"] = slug
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _plan_cost(plan_dir):
    path = plan_dir / "planner.json"
    if not path.is_file():
        return 0.0
    data = json.loads(path.read_text(encoding="utf-8"))
    # the planner nests it: {"tokens": {..., "cost": x}}
    return float((data.get("tokens") or {}).get("cost", data.get("cost", 0.0)))


def _planner_plan(cell, project, repo_root, kit_hash, runner):
    size, slug = cell["size"], cell["slug"]
    model = cell.get("planner_model")
    spec = repo_root / SUITE_DIR / "fixtures" / size / "spec.md"
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:8]
    # no kit hash in the key: a harness edit must not re-roll the plan, or arms stop sharing one
    key = f"{size}-{cell['planner']}-{model or 'default'}-{sha}"
    cache = PLAN_CACHE / key
    dst = project / ".harness" / "plans" / slug
    if (cache / "meta.json").is_file():
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("plan.md", "tasks.json"):
            shutil.copy2(cache / name, dst / name)
        _copy_tree(cache / "checks", dst / "checks")
        old = json.loads((cache / "meta.json").read_text(encoding="utf-8")).get("slug")
        if old and old != slug:
            _rewrite_slug(dst, old, slug)
        _retag_plan(dst, slug)
        return 0.0

    spec_copy = TEMP_ROOT / "_specs" / f"{size}-{sha}.md"
    spec_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spec, spec_copy)
    cmd = [sys.executable, ".harness/run_plan.py", slug, "--plan", str(spec_copy),
           "--planner", f"{cell['planner']}:{model}" if model else cell["planner"]]
    try:
        done = runner(cmd, cwd=str(project), timeout=1800, capture_output=True, text=True,
                      encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        raise ProjectError(f"planner timed out: {exc}") from exc
    if done.returncode != 0 or not (dst / "plan.md").is_file() \
            or not (dst / "tasks.json").is_file():
        raise ProjectError(f"planner produced no plan (rc {done.returncode})")
    _retag_plan(dst, slug)
    cost = _plan_cost(dst)
    cache.mkdir(parents=True, exist_ok=True)
    for name in ("plan.md", "tasks.json"):
        shutil.copy2(dst / name, cache / name)
    _copy_tree(dst / "checks", cache / "checks")
    (cache / "meta.json").write_text(json.dumps({"cost": cost, "slug": slug}), encoding="utf-8")
    return cost


def plan_for_project(cell, project, repo_root=REPO_ROOT, kit_hash="", runner=subprocess.run):
    repo_root, project = Path(repo_root), Path(project)
    size, slug = cell["size"], cell["slug"]
    dst = project / ".harness" / "plans" / slug
    if cell.get("plan_source", "fixture") == "planner":
        cost = _planner_plan(cell, project, repo_root, kit_hash, runner)
    else:
        src = repo_root / SUITE_DIR / "fixtures" / size / "plan_project"
        if not src.is_dir():
            raise ProjectError(f"missing fixture plan {src}; use --plan-source planner")
        _copy_files(src, dst)
        _retag_plan(dst, slug)
        cost = 0.0
    _must_git(project, "add", "-A")
    _must_git(project, "commit", "-q", "--allow-empty", "-m", "plan")
    cell["base_commit"] = _must_git(project, "rev-parse", "HEAD")
    return cost
