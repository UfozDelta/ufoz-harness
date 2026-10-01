"""Tests for the harness-suite matrix/report plumbing (no executor, no network)."""
import csv
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
