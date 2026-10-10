"""Tests for the harness-suite matrix/report plumbing (no executor, no network)."""
import csv
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = REPO_ROOT / "bench" / "suite"
if str(SUITE_DIR) not in sys.path:
    sys.path.insert(0, str(SUITE_DIR))

import report  # noqa: E402
import suite  # noqa: E402
from report import load_rows  # noqa: E402
from suite import build_matrix, preflight_executor  # noqa: E402


# ----------------------------------------------------------------- unsupported
def test_parallel_unsupported_for_non_thread_safe_executors():
    rows = build_matrix(["small"], ["parallel"], ["cline", "cline-acp"], reps=1)
    assert [r["status"] for r in rows] == ["unsupported", "unsupported"]


def test_llama_unsupported_for_multi_and_parallel():
    rows = build_matrix(["small"], ["serial", "parallel", "multi", "window"], ["llama"], reps=1)
    by_mode = {r["mode"]: r["status"] for r in rows}
    assert by_mode["parallel"] == "unsupported"
    assert by_mode["multi"] == "unsupported"
    assert by_mode["serial"] == "pending"
    assert by_mode["window"] == "pending"


def test_window_only_small_is_supported():
    rows = build_matrix(["small", "medium", "large"], ["window"], ["pi"], reps=1)
    by_size = {r["size"]: r["status"] for r in rows}
    assert by_size == {"small": "pending", "medium": "unsupported", "large": "unsupported"}


def test_matrix_shape_slugs_and_order_idx():
    sizes, modes, executors, reps = suite.SIZES, ["serial"], suite.EXECUTORS, 3
    rows = build_matrix(sizes, modes, executors, reps, seed=0)
    assert len(rows) == len(sizes) * len(modes) * len(executors) * reps
    assert {r["slug"] for r in rows} == {
        f"suite-{s}-serial-{e}-r{n}" for s in sizes for e in executors for n in range(1, reps + 1)
    }
    assert sorted(r["order_idx"] for r in rows) == list(range(len(rows)))
    assert all(r["seed"] == 0 for r in rows)
    assert [r["slug"] for r in rows] == [r["slug"] for r in
                                        build_matrix(sizes, modes, executors, reps, seed=0)]


def test_build_matrix_never_marks_skipped():
    rows = build_matrix(suite.SIZES, suite.MODES, suite.EXECUTORS, reps=1)
    assert {r["status"] for r in rows} <= {"pending", "unsupported"}


# ------------------------------------------------------------------- preflight
def test_preflight_executor_true_for_local_executors():
    for name in ("pi", "opencode", "cline", "cline-acp", "claude"):
        assert preflight_executor(name) is True


def test_preflight_llama_false_when_unreachable(monkeypatch):
    monkeypatch.setenv("HARNESS_LLAMA_URL", "http://127.0.0.1:9/nope")

    def _boom(*_a, **_k):
        raise OSError("unreachable")

    monkeypatch.setattr(suite.urllib.request, "urlopen", _boom)
    assert preflight_executor("llama") is False


# ---------------------------------------------------------------------- resume
def _fake_cells_module(calls):
    mod = types.ModuleType("cells")

    def run_cell(cell, repo_root, cell_timeout=1800, keep=False):
        calls.append(cell["slug"])
        return dict(cell, status="pass")

    def cleanup_cell(cell, repo_root):
        return None

    mod.run_cell = run_cell
    mod.cleanup_cell = cleanup_cell
    mod.prepare_cell = lambda cell, repo_root: repo_root
    return mod


def _write_results_csv(path, slugs):
    # resume keys on the cell slug, so the fake CSV carries it alongside the real columns
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["slug"] + suite.COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for slug in slugs:
            row = {col: "" for col in suite.COLUMNS}
            row.update({"slug": slug, "size": "small", "mode": "serial",
                        "executor": "pi", "rep": 1, "status": "pass"})
            writer.writerow(row)


@pytest.fixture
def resume_env(tmp_path, monkeypatch):
    """suite.main wired to a temp results.csv and a stub cells module.

    Yields (csv_path, calls, prior) where `prior` is the dict of rows suite reads back
    as the already-present results.csv content.
    """
    csv_path = tmp_path / "results.csv"
    calls = []
    prior = {}
    monkeypatch.setitem(sys.modules, "cells", _fake_cells_module(calls))
    monkeypatch.setattr(suite, "RESULTS_CSV", csv_path)
    monkeypatch.setattr(suite, "load_existing_rows", lambda *a, **k: prior)
    monkeypatch.setattr(suite, "load_existing_slugs", lambda *a, **k: set(prior))
    monkeypatch.setattr(suite, "cumulative_cost", lambda *a, **k: 0.0)
    return csv_path, calls, prior


def test_resume_skips_slug_already_in_results(resume_env):
    csv_path, calls, prior = resume_env
    _write_results_csv(csv_path, ["suite-small-serial-pi-r1"])
    with open(csv_path, newline="", encoding="utf-8") as fh:
        prior.update({row["slug"]: row for row in csv.DictReader(fh)})
    assert suite.main(["--sizes", "small", "--modes", "serial",
                       "--executors", "pi", "--reps", "2"]) == 0
    assert calls == ["suite-small-serial-pi-r2"]


def test_force_reruns_slug_already_in_results(resume_env):
    csv_path, calls, prior = resume_env
    _write_results_csv(csv_path, ["suite-small-serial-pi-r1"])
    with open(csv_path, newline="", encoding="utf-8") as fh:
        prior.update({row["slug"]: row for row in csv.DictReader(fh)})
    assert suite.main(["--sizes", "small", "--modes", "serial", "--executors", "pi",
                       "--reps", "1", "--force"]) == 0
    assert calls == ["suite-small-serial-pi-r1"]


# ------------------------------------------------------------------ multi batching
class _RecordingCells:
    """Stub cells module: records runs, returns a multi list or raises on demand."""

    def __init__(self, fail_on=None):
        self.runs = []
        self.cleanups = []
        self.fail_on = fail_on or {}

    def run_cell(self, cell, repo_root, cell_timeout=1800, keep=False):
        self.runs.append(cell["slug"])
        if cell["slug"] in self.fail_on:
            raise RuntimeError(self.fail_on[cell["slug"]])
        if cell["mode"] == "multi":
            return [dict(cell, size=size, slug=f"suite-{size}-multi-{cell['executor']}"
                                           f"-r{cell['rep']}", status="pass", cost="0.1")
                    for size in suite.SIZES]
        return dict(cell, status="pass", cost="0.1")

    def cleanup_cell(self, cell, repo_root):
        self.cleanups.append(cell["slug"])

    def prepare_cell(self, cell, repo_root):
        return repo_root


def _multi_env(tmp_path, monkeypatch, fake):
    csv_path = tmp_path / "results.csv"
    monkeypatch.setitem(sys.modules, "cells", fake)
    monkeypatch.setattr(suite, "RESULTS_CSV", csv_path)
    monkeypatch.setattr(suite, "load_existing_rows", lambda *a, **k: {})
    monkeypatch.setattr(suite, "load_existing_slugs", lambda *a, **k: set())
    monkeypatch.setattr(suite, "cumulative_cost", lambda *a, **k: 0.0)
    return csv_path


def test_multi_once_runs_one_batch_per_executor_rep(tmp_path, monkeypatch):
    fake = _RecordingCells()
    _multi_env(tmp_path, monkeypatch, fake)
    assert suite.main(["--sizes", "small", "--modes", "multi", "--executors", "pi",
                       "--reps", "2"]) == 0
    assert fake.runs == ["suite-small-multi-pi-r1", "suite-small-multi-pi-r2"]
    # _run_multi already cleans each size: main must not clean the pair again
    assert fake.cleanups == []


def test_multi_list_return_writes_a_row_per_size(tmp_path, monkeypatch):
    csv_path = _multi_env(tmp_path, monkeypatch, _RecordingCells())
    suite.main(["--sizes", "small", "--modes", "multi", "--executors", "pi", "--reps", "1"])
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["slug"] for r in rows] == [f"suite-{s}-multi-pi-r1" for s in suite.SIZES]


def test_multi_resume_skips_pair_when_all_sizes_present(tmp_path, monkeypatch):
    fake = _RecordingCells()
    csv_path = _multi_env(tmp_path, monkeypatch, fake)
    _write_results_csv(csv_path, [f"suite-{s}-multi-pi-r1" for s in suite.SIZES])
    prior = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        prior.update({r["slug"]: r for r in csv.DictReader(fh)})
    monkeypatch.setattr(suite, "load_existing_rows", lambda *a, **k: prior)
    monkeypatch.setattr(suite, "load_existing_slugs", lambda *a, **k: set(prior))
    suite.main(["--sizes", "small", "--modes", "multi", "--executors", "pi", "--reps", "1"])
    assert fake.runs == []


def test_rows_persist_when_a_later_cell_raises(tmp_path, monkeypatch):
    fake = _RecordingCells(fail_on={"suite-small-serial-pi-r2": "boom"})
    csv_path = _multi_env(tmp_path, monkeypatch, fake)
    with pytest.raises(RuntimeError):
        suite.main(["--sizes", "small", "--modes", "serial", "--executors", "pi",
                    "--reps", "2"])
    with open(csv_path, newline="", encoding="utf-8") as fh:
        slugs = [r["slug"] for r in csv.DictReader(fh)]
    assert "suite-small-serial-pi-r1" in slugs
    assert "suite-small-serial-pi-r2" not in slugs


# --------------------------------------------------------- multi survivor timeout
def test_multi_timeout_maps_survivors_only(tmp_path, monkeypatch):
    import cells as cells_mod  # noqa: PLC0415 (stubbed launch, no real executor)

    class _Proc:
        def __init__(self, alive):
            self.alive = alive

        def poll(self):
            return None if self.alive else 0

        def wait(self, timeout=None):
            self.alive = False
            return 0

    monkeypatch.setattr(cells_mod, "prepare_cell", lambda cell, repo_root: tmp_path)
    monkeypatch.setattr(cells_mod, "_stop_tree", lambda proc: setattr(proc, "alive", False))
    monkeypatch.setattr(cells_mod, "cleanup_cell", lambda cell, repo_root: None)
    monkeypatch.setattr(cells_mod, "_metrics", lambda *a, **k: {k2: 0 for k2 in
                                                              cells_mod.METRIC_FIELDS})
    monkeypatch.setattr(cells_mod, "_harness_sha", lambda *a, **k: "abc123")
    monkeypatch.setattr(cells_mod.subprocess, "Popen",
                        lambda *a, **k: _Proc(alive=True))

    cell = {"size": "small", "mode": "multi", "executor": "pi", "rep": 1,
            "slug": "suite-small-multi-pi-r1", "order_idx": 0, "seed": 0, "status": "pending"}
    rows = cells_mod._run_multi(cell, tmp_path, cell_timeout=0.05)
    assert [r["status"] for r in rows] == ["timeout", "timeout", "timeout"]
    assert all(r["batch_wall_s"] for r in rows)


# ------------------------------------------------------------------ csv round trip
def test_columns_lists_agree():
    assert suite.COLUMNS == report.COLUMNS


def test_csv_round_trip(tmp_path):
    rows = []
    for rep, status in ((1, "pass"), (2, "fail")):
        row = {col: "" for col in suite.COLUMNS}
        row.update({
            "ts": "2026-09-28T10:00:00", "size": "small", "mode": "serial",
            "executor": "pi", "rep": str(rep), "status": status, "wall_s": "12.5",
            "tests_passed": "3", "tests_total": "3", "tasks_passed": "2",
            "tasks_total": "2", "attempts": "2", "input": "10", "output": "20",
            "reasoning": "5", "cache_read": "0", "cost": "0.25", "tampered": "false",
            "seed": "0", "order_idx": str(rep - 1),
        })
        rows.append(row)
    path = tmp_path / "results.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=suite.COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    assert load_rows(path) == rows


def test_load_rows_missing_and_empty(tmp_path):
    assert load_rows(tmp_path / "nope.csv") == []
    empty = tmp_path / "empty.csv"
    empty.write_text(",".join(suite.COLUMNS) + "\n", encoding="utf-8")
    assert load_rows(empty) == []


def test_build_report_on_one_row():
    text = report.build_report([{"executor": "pi", "size": "small", "mode": "serial",
                                 "status": "pass", "wall_s": "1.0", "cost": "0"}])
    assert "pi" in text


# ------------------------------------------------------------- cleanup retry / stale branch
def _git_out(text="", returncode=0):
    return types.SimpleNamespace(stdout=text, stderr="", returncode=returncode)


def test_cleanup_retry_on_failing_worktree_remove(tmp_path):
    import cells  # noqa: PLC0415 (real module; every git call is mocked)

    calls = []
    slept = []

    def fake_git(*args, cwd=None):
        argv = list(args)
        calls.append(argv)
        if argv[:3] == ["worktree", "remove", "--force"]:
            attempts = len([c for c in calls if c[:3] == ["worktree", "remove", "--force"]])
            return _git_out("error: locked", returncode=1 if attempts < 3 else "")
        if argv[:2] == ["rev-parse", "--verify"]:
            return _git_out("", returncode=1)
        return _git_out("")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(cells, "_git", fake_git)
    monkey.setattr(cells, "_remove_leftover", lambda path: None)
    try:
        cells.cleanup_cell({"slug": "suite-small-serial-pi-r1"}, tmp_path,
                           sleep_fn=slept.append)
    finally:
        monkey.undo()

    removes = [c for c in calls if c[:3] == ["worktree", "remove", "--force"]]
    assert len(removes) == 3
    assert slept == [1, 1]


def test_cleanup_stale_branch_warns_when_branch_survives(tmp_path, capsys):
    import cells  # noqa: PLC0415

    calls = []

    def fake_git(*args, cwd=None):
        argv = list(args)
        calls.append(argv)
        if argv[:2] == ["branch", "-D"]:
            return _git_out("", returncode=1)
        if argv[:2] == ["rev-parse", "--verify"]:
            return _git_out("abc123\n")
        return _git_out("")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(cells, "_git", fake_git)
    monkey.setattr(cells, "_remove_leftover", lambda path: None)
    try:
        cells.cleanup_cell({"slug": "suite-small-serial-pi-r1"}, tmp_path, sleep_fn=lambda s: None)
    finally:
        monkey.undo()
    out = capsys.readouterr().out
    assert "harness/suite-small-serial-pi-r1" in out


def test_prepare_cell_deletes_unused_branch_stale_branch(tmp_path):
    import cells  # noqa: PLC0415

    (tmp_path / "bench" / "suite" / "fixtures" / "small" / "seed").mkdir(parents=True)
    calls = []

    def fake_git(*args, cwd=None):
        argv = list(args)
        calls.append(argv)
        if argv[:2] == ["rev-parse", "--verify"]:
            return _git_out("abc123\n")
        if argv[:2] == ["worktree", "list"]:
            return _git_out("worktree /other\nHEAD abc\n")
        return _git_out("")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(cells, "_git", fake_git)
    monkey.setattr(cells, "worktree", types.SimpleNamespace(
        ensure=lambda slug, exclude=(), orphan=False: str(tmp_path / "wt")))
    try:
        cells.prepare_cell({"slug": "suite-small-serial-pi-r1", "size": "small"}, tmp_path)
    finally:
        monkey.undo()

    assert ["branch", "-D", "harness/suite-small-serial-pi-r1"] in calls


def test_prepare_cell_stale_branch_keeps_checked_out(tmp_path):
    import cells  # noqa: PLC0415

    (tmp_path / "bench" / "suite" / "fixtures" / "small" / "seed").mkdir(parents=True)
    calls = []

    def fake_git(*args, cwd=None):
        argv = list(args)
        calls.append(argv)
        if argv[:2] == ["rev-parse", "--verify"]:
            return _git_out("abc123\n")
        if argv[:2] == ["worktree", "list"]:
            return _git_out(
                "worktree /other\nHEAD abc\nbranch refs/heads/harness/suite-small-serial-pi-r1\n")
        return _git_out("")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(cells, "_git", fake_git)
    monkey.setattr(cells, "worktree", types.SimpleNamespace(
        ensure=lambda slug, exclude=(), orphan=False: str(tmp_path / "wt")))
    try:
        cells.prepare_cell({"slug": "suite-small-serial-pi-r1", "size": "small"}, tmp_path)
    finally:
        monkey.undo()

    assert not [c for c in calls if c[:2] == ["branch", "-D"]]


def test_prepare_cell_stale_branch_skipped_for_non_cell_slug(tmp_path):
    import cells  # noqa: PLC0415

    (tmp_path / "bench" / "suite" / "fixtures" / "small" / "seed").mkdir(parents=True)
    calls = []

    def fake_git(*args, cwd=None):
        argv = list(args)
        calls.append(argv)
        return _git_out("abc123\n")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(cells, "_git", fake_git)
    monkey.setattr(cells, "worktree", types.SimpleNamespace(
        ensure=lambda slug, exclude=(), orphan=False: str(tmp_path / "wt")))
    try:
        cells.prepare_cell({"slug": "suite-fixes", "size": "small"}, tmp_path)
    finally:
        monkey.undo()

    assert not [c for c in calls if c[:2] == ["branch", "-D"]]


# ------------------------------------------------------------- poll_until (wall clock)
def test_poll_until_returns_true_after_machine_sleep():
    import cells  # noqa: PLC0415

    class FakeProc:
        def __init__(self):
            self.polls = 0

        def poll(self):
            self.polls += 1
            return None

    ticks = iter([0.0, 10_000.0])  # the clock jumps past the deadline between polls
    assert cells._poll_until(FakeProc(), 100.0, clock=lambda: next(ticks),
                             sleep_fn=lambda s: None) is True


def test_poll_until_returns_false_when_process_exits():
    import cells  # noqa: PLC0415

    class FakeProc:
        def __init__(self):
            self.polls = 0

        def poll(self):
            self.polls += 1
            return 0 if self.polls > 2 else None

    sleeps = []
    assert cells._poll_until(FakeProc(), 100.0, clock=lambda: 0.0,
                             sleep_fn=sleeps.append) is False
    assert sleeps == [1, 1]


# ------------------------------------------------------------- preserve failed logs
def test_preserve_failed_copies_items_and_logs(tmp_path):
    import cells  # noqa: PLC0415 (real module, tmp layout only)

    slug = "suite-small-serial-pi-r1"
    src = tmp_path / ".worktrees" / slug / ".harness" / "plans" / slug
    (src / "items").mkdir(parents=True)
    (src / "logs").mkdir(parents=True)
    (src / "items" / "T1.report.md").write_text("report body", encoding="utf-8")
    (src / "logs" / "T1.pi.log").write_text("pi output", encoding="utf-8")

    cells._preserve_failed({"slug": slug}, tmp_path)

    dst = tmp_path / "bench" / "suite" / "failed" / slug
    assert (dst / "items" / "T1.report.md").read_text(encoding="utf-8") == "report body"
    assert (dst / "logs" / "T1.pi.log").read_text(encoding="utf-8") == "pi output"


# ----------------------------------------------------------- report.main guard
def _report_paths(monkeypatch, tmp_path):
    md = tmp_path / "RESULTS.md"
    md.write_text("# keep me\n", encoding="utf-8")
    monkeypatch.setattr(report, "RESULTS_CSV", tmp_path / "results.csv")
    monkeypatch.setattr(report, "RESULTS_MD", md)
    return md


@pytest.mark.parametrize("argv", [["--help"], ["--bogus"]])
def test_report_main_bad_or_help_args_never_write(monkeypatch, tmp_path, argv):
    md = _report_paths(monkeypatch, tmp_path)
    with pytest.raises(SystemExit):
        report.main(argv)
    assert md.read_text(encoding="utf-8") == "# keep me\n"


def test_report_main_keeps_existing_md_when_no_rows(monkeypatch, tmp_path):
    md = _report_paths(monkeypatch, tmp_path)
    assert report.main([]) == 1
    assert md.read_text(encoding="utf-8") == "# keep me\n"


# ------------------------------------------------------------- bench-trust
def test_writer_migrates_old_header(tmp_path):
    csv_path = tmp_path / "results.csv"
    csv_path.write_text("slug,ts\na,1\n", encoding="utf-8")

    writer = suite._ResultWriter(csv_path)
    writer.write({"slug": "b", "ts": "2"})

    with open(csv_path, newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert header == suite.CSV_FIELDS
    assert rows[0]["slug"] == "a" and rows[0]["ts"] == "1" and rows[0]["run_id"] == ""
    assert rows[1]["slug"] == "b" and rows[1]["run_id"] == writer.run_id


def test_latest_per_cell_and_newest_sha():
    base = {"size": "small", "mode": "serial", "executor": "claude", "rep": "1",
            "wall_s": "1", "cost": "1", "model": "claude-x"}
    rows = [
        dict(base, status="fail", harness_sha="A"),
        dict(base, status="pass", harness_sha="A"),
        dict(base, rep="2", status="harness_fail", harness_sha="B"),
        dict(base, rep="3", status="pass", harness_sha="B"),
    ]
    latest = report.latest_per_cell(rows)
    assert len(latest) == 3
    assert latest[0]["status"] == "pass" and latest[0]["harness_sha"] == "A"
    newest = report.newest_sha_rows(latest)
    assert {r["harness_sha"] for r in newest} == {"B"}
    assert report.newest_sha_rows([]) == []


def test_harness_fail_excluded_from_rates():
    base = {"size": "small", "mode": "serial", "executor": "pi", "rep": "1",
            "wall_s": "1", "cost": "0", "model": "m", "harness_sha": "A"}
    rows = [dict(base, status="pass"),
            dict(base, rep="2", status="harness_fail"),
            dict(base, rep="3", status="infra_error")]
    graded = report._graded(rows)
    assert [r["status"] for r in graded] == ["pass"]
    text = report.build_report(rows, all_shas=True)
    assert "1 counted" in text and "1 harness_fail excluded" in text


def test_apply_window_verdict():
    import cells  # noqa: PLC0415 (real module, pure helper)

    row = {"mode": "window", "status": "pass", "window_opened": "true", "watch_ok": "false"}
    cells._apply_window_verdict(row)
    assert row["status"] == "harness_fail"

    row = {"mode": "window", "status": "pass", "window_opened": "false", "watch_ok": "true"}
    cells._apply_window_verdict(row)
    assert row["status"] == "harness_fail"

    row = {"mode": "window", "status": "pass", "window_opened": "true", "watch_ok": "true"}
    cells._apply_window_verdict(row)
    assert row["status"] == "pass"

    row = {"mode": "serial", "status": "fail", "window_opened": "false", "watch_ok": "false"}
    cells._apply_window_verdict(row)
    assert row["status"] == "fail"


def test_runs_agree():
    import check_fixtures  # noqa: PLC0415

    assert check_fixtures.runs_agree([{"pytest": 0, "vitest": 0}, {"pytest": 0, "vitest": 0}])
    assert not check_fixtures.runs_agree([{"pytest": 0}, {"pytest": 1}])
    assert check_fixtures.runs_agree([])


def test_seed_checks_for(tmp_path):
    import check_fixtures  # noqa: PLC0415

    py_dir = tmp_path / "py"
    py_dir.mkdir()
    (py_dir / "test_x.py").write_text("", encoding="utf-8")
    assert [label for label, _ in check_fixtures.seed_checks_for(py_dir)] == ["pytest"]

    ts_dir = tmp_path / "ts"
    ts_dir.mkdir()
    (ts_dir / "a.test.ts").write_text("", encoding="utf-8")
    assert [label for label, _ in check_fixtures.seed_checks_for(ts_dir)] == ["vitest"]

    empty = tmp_path / "empty"
    empty.mkdir()
    assert check_fixtures.seed_checks_for(empty) == []


# ----------------------------------------------------------------- isolated projects
def _run_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_kit(root):
    _write(root / "index.js",
           "const fs=require('fs');const i=process.argv.indexOf('--dir');"
           "fs.writeFileSync(process.argv[i+1]+'/HARNESS.txt','kit');")
    return root, "fake1234"


def test_make_project_commits(tmp_path, monkeypatch):
    import cells
    monkeypatch.setattr(cells, "TEMP_ROOT", tmp_path / "ufoz-bench")
    cell = {"slug": "suite-small-serial-pi-r97", "size": "small", "mode": "serial",
            "executor": "pi", "rep": 97}
    project = cells.make_project(cell, kit=_fake_kit(tmp_path / "kit"))
    try:
        assert _run_git(project, "log", "--format=%s").stdout.split() == ["harness", "seed"]
        assert (project / "HARNESS.txt").is_file()
        assert cell["project"] and cell["seed_commit"]
    finally:
        cells.cleanup_project(cell)
    assert not project.exists()


def test_plan_cache_hit_once(tmp_path, monkeypatch):
    import cells
    monkeypatch.setattr(cells, "TEMP_ROOT", tmp_path / "ufoz-bench")
    monkeypatch.setattr(cells, "PLAN_CACHE", tmp_path / "plan_cache")
    calls = []

    def runner(cmd, cwd=None, **kw):
        calls.append(cmd)
        slug = cmd[2]
        plan_dir = Path(cwd) / ".harness" / "plans" / slug
        _write(plan_dir / "plan.md", "# Plan")
        _write(plan_dir / "tasks.json", json.dumps({"slug": slug, "tasks": []}))
        _write(plan_dir / "planner.json", json.dumps({"cost": 0.7}))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    costs = []
    for rep in (95, 96):
        cell = {"slug": f"suite-small-serial-pi-r{rep}", "size": "small", "mode": "serial",
                "executor": "pi", "rep": rep, "plan_source": "planner",
                "planner": "claude", "planner_model": "sonnet"}
        project = cells.make_project(cell, kit=_fake_kit(tmp_path / f"kit{rep}"))
        try:
            costs.append(cells.plan_for_project(cell, project, kit_hash="fake1234",
                                                runner=runner))
        finally:
            cells.cleanup_project(cell)
    assert costs == [0.7, 0.0]
    assert len(calls) == 1


def test_tampered_git_flags(tmp_path):
    import cells
    pat = cells.TAMPER_PATTERNS[0]

    def fresh(name):
        d = tmp_path / name
        d.mkdir()
        _run_git(d, "init", "-q", "-b", "main")
        _run_git(d, "config", "user.email", "a@b.c")
        _run_git(d, "config", "user.name", "x")
        _write(d / "package.json", "{}")
        _write(d / "app.py", "x = 1\n")
        _run_git(d, "add", "-A")
        _run_git(d, "commit", "-qm", "seed")
        return d, _run_git(d, "rev-parse", "HEAD").stdout.strip()

    cases = {
        "sensitive_seed_edited": (lambda d: _write(d / "package.json", '{"a":1}'), True),
        "harness_dir_ignored": (lambda d: _write(d / ".harness" / "n.md", pat), False),
        "added_test_file": (lambda d: _write(d / "test_new.py", "def test_a(): pass\n"), True),
        "suppression_added": (lambda d: _write(d / "app.py", "x = 1\n# " + pat + "\n"), True),
        "plain_edit": (lambda d: _write(d / "app.py", "x = 2\n"), False),
    }
    for name, (mutate, expect) in cases.items():
        d, seed = fresh(name)
        mutate(d)
        assert cells._tampered_git(d, seed, seed, set()) is expect, name


def test_report_regressions():
    row = dict(size="small", mode="serial", executor="pi", rep="1", status="fail",
               regression_passed="1", regression_total="2", plan_cost="0.5", kit_hash="ab12")
    text = report.build_report([row])
    assert "| regressions |" in text
    assert "Planner cost (not billed to executors): $0.50" in text
    assert "Kit hash: ab12" in text
    grid = [line for line in text.splitlines() if line.startswith("| pi | small | serial |")]
    assert grid and grid[0].endswith("| 1 |")
    old = report.build_report([dict(size="small", mode="serial", executor="pi", rep="1",
                                    status="pass")])
    assert "Planner cost" in old


def test_plan_cost_reads_the_planners_nested_cost(tmp_path):
    import json
    import sys
    sys.path.insert(0, "bench/suite")
    import cells
    assert cells._plan_cost(tmp_path) == 0.0
    (tmp_path / "planner.json").write_text(json.dumps({"tokens": {"cost": 0.1234}}), encoding="utf-8")
    assert cells._plan_cost(tmp_path) == 0.1234
    (tmp_path / "planner.json").write_text(json.dumps({"cost": 0.5}), encoding="utf-8")
    assert cells._plan_cost(tmp_path) == 0.5


# ------------------------------------------------------------- task registry
def test_discover_tasks_legacy_and_toml(tmp_path, monkeypatch):
    import tasks
    (tmp_path / "plain").mkdir()
    (tmp_path / "_hidden").mkdir()
    (tmp_path / "withtoml" / "plan_project").mkdir(parents=True)
    (tmp_path / "withtoml" / "task.toml").write_text(
        'capability = "bug-fix-prose"\nlang = "python"\nlicence = "MIT"\n', encoding="utf-8")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "task.toml").write_text("capability = [", encoding="utf-8")
    monkeypatch.setattr(tasks, "FIXTURES", tmp_path)
    with pytest.raises(ValueError, match="task.toml"):
        tasks.discover_tasks()
    (tmp_path / "bad" / "task.toml").unlink()
    found = tasks.discover_tasks()
    assert set(found) == {"plain", "withtoml", "bad"}
    assert found["plain"]["capability"] == "multi-file-feature"
    assert found["plain"]["has_plan_project"] is False
    assert found["withtoml"]["capability"] == "bug-fix-prose"
    assert found["withtoml"]["lang"] == "python"
    assert found["withtoml"]["has_plan_project"] is True


def test_parse_arms_and_slugs():
    import tasks
    assert tasks.parse_arms("pi:a/b,claude") == [("pi", "a/b"), ("claude", "")]
    assert tasks.model_slug("opencode/Muse Spark-1.3") == "opencode-muse-spark-1-3"
    assert tasks.cell_slug("small", "serial", "pi", "", 1) == "suite-small-serial-pi-r1"
    assert tasks.cell_slug("small", "serial", "pi", "opencode/x-free", 2) \
        == "suite-small-serial-pi-opencode-x-free-r2"
    rows = build_matrix(["small"], ["serial"], [("pi", "m/x"), "claude"], reps=1)
    assert {r["slug"] for r in rows} == {"suite-small-serial-pi-m-x-r1", "suite-small-serial-claude-r1"}
    assert {r["model"] for r in rows} == {"m/x", ""}


def test_plan_args_model_wins_over_env(monkeypatch):
    import cells
    monkeypatch.setenv("HARNESS_EXECUTOR_MODEL", "env/model")
    cell = {"slug": "s", "executor": "pi", "mode": "serial"}
    args = cells._plan_args(dict(cell, model="cell/model"), Path("."))
    assert args[args.index("--executor") + 1] == "pi:cell/model"
    args = cells._plan_args(cell, Path("."))
    assert args[args.index("--executor") + 1] == "pi:env/model"
    assert cells.is_cell_slug("suite-small-serial-pi-cell-model-r1")
    assert not cells.is_cell_slug("suite-fixes")


def test_planner_forced_without_plan_project(tmp_path, monkeypatch, capsys):
    import cells
    meta = {"capability": "multi-file-feature", "has_plan_project": False}
    monkeypatch.setattr(suite, "TASKS", {"x": dict(meta, id="x")})
    monkeypatch.setattr(suite, "SIZES", ["x"])
    seen = []
    real = suite.build_matrix

    def spy(*a, **kw):
        seen.extend(real(*a, **kw))
        return seen

    monkeypatch.setattr(suite, "build_matrix", spy)
    assert suite.main(["--dry", "--tasks", "x", "--modes", "serial", "--executors", "pi",
                       "--reps", "1"]) == 0
    assert [c["plan_source"] for c in seen] == ["planner"]
    with pytest.raises(cells.ProjectError, match="use --plan-source planner"):
        cells.plan_for_project({"size": "nosuch", "slug": "s"}, tmp_path)


def test_report_first_try_and_capability():
    base = {c: "" for c in report.COLUMNS}
    rows = [
        dict(base, size="t", mode="serial", executor="pi", model="m1", rep="1", status="pass",
             attempts="1", tasks_total="1", capability="bug-fix-prose"),
        dict(base, size="t", mode="serial", executor="pi", model="m1", rep="2", status="pass",
             attempts="2", tasks_total="1", capability="bug-fix-prose"),
        dict(base, size="t", mode="serial", executor="claude", model="claude", rep="1",
             status="pass", attempts="1", tasks_total="1"),
    ]
    assert report.first_try(rows[0]) and not report.first_try(rows[1])
    assert not report.first_try(dict(rows[0], attempts=""))
    assert report.arm_label(rows[0]) == "pi:m1" and report.arm_label(rows[2]) == "claude"
    out = report.build_report(rows)
    assert "## Per capability" in out and "| bug-fix-prose | pi:m1 | 2 | 50% | 100% |" in out
    assert "| ? | claude | 1 | 100% |" in out


def test_short_slug_keeps_cell_shape_and_stays_short():
    import sys
    sys.path.insert(0, "bench/suite")
    import cells
    import tasks
    long = tasks.cell_slug("fix-from-prose", "serial", "opencode", "opencode/muse-spark-1.3-contributor-free", 1)
    cell = {"slug": long, "size": "fix-from-prose", "mode": "serial", "executor": "opencode", "rep": 1}
    short = cells._short_slug(cell)
    assert len(short) <= 48 and cells.is_cell_slug(short)
    assert short == cells._short_slug(cell) and short != cells._short_slug({**cell, "slug": long + "x"})
    small = {"slug": "suite-small-serial-pi-r1", "size": "small", "mode": "serial", "executor": "pi", "rep": 1}
    assert cells._short_slug(small) == "suite-small-serial-pi-r1"


def test_rewrite_slug_points_a_cached_plan_at_the_new_cell(tmp_path):
    import sys
    sys.path.insert(0, "bench/suite")
    import cells
    (tmp_path / "checks").mkdir()
    (tmp_path / "plan.md").write_text("write .harness/plans/OLD/SUMMARY.md", encoding="utf-8")
    (tmp_path / "tasks.json").write_text('{"slug": "OLD", "acceptance": ".harness/plans/OLD/SUMMARY.md"}', encoding="utf-8")
    (tmp_path / "checks" / "check_t1.py").write_text("P = '.harness/plans/OLD'", encoding="utf-8")
    cells._rewrite_slug(tmp_path, "OLD", "NEW")
    for name in ("plan.md", "tasks.json", "checks/check_t1.py"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "NEW" in text and "OLD" not in text
