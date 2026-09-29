import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import guards  # noqa: E402


def test_runner_owned_covers_runner_artifacts_only():
    plan = Path("plans/slug")
    run_lock = plan / "plan.lock.json"
    metrics = Path("metrics.jsonl")
    assert guards.runner_owned("plans/slug/plan.lock.json", run_lock, plan, metrics)
    assert guards.runner_owned("plans/slug/logs/run.log", run_lock, plan, metrics)
    assert guards.runner_owned("metrics.jsonl", run_lock, plan, metrics)
    assert guards.runner_owned("tsconfig.tsbuildinfo", run_lock, plan, metrics)
    assert guards.runner_owned("plans/slug/items/T1.report.md", run_lock, plan, metrics)
    assert guards.runner_owned("plans/slug/items/T1.feedback.md", run_lock, plan, metrics)
    assert guards.runner_owned("plans/slug/items/T1.metrics.json", run_lock, plan, metrics)
    assert guards.runner_owned("plans/slug/items/T1.repair1.md", run_lock, plan, metrics)
    # a file the executor owns
    assert not guards.runner_owned("src/app.ts", run_lock, plan, metrics)
    assert not guards.runner_owned("plans/slug/plan.md", run_lock, plan, metrics)


def test_marker_counts_counts_occurrences(tmp_path):
    marker = guards.SUPPRESSION_MARKERS[0]
    counted = tmp_path / "counted.py"
    counted.write_text(f"a = 1  {marker}\nb = 2\n", encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text("a = 1\nb = 2\n", encoding="utf-8")
    assert guards.marker_counts(counted)[marker] == 1
    assert guards.marker_counts(clean)[marker] == 0


def test_suppression_markers_reports_only_new_occurrences(tmp_path):
    marker = guards.SUPPRESSION_MARKERS[0]
    f = tmp_path / "mod.py"
    f.write_text(f"x = 0  {marker}\n", encoding="utf-8")

    baseline = {f.as_posix(): {"total": 0, "counts": dict.fromkeys(guards.SUPPRESSION_MARKERS, 0)}}
    found = guards.suppression_markers([f.as_posix()], baseline)
    assert found == [f"{f.as_posix()}: {marker}"]

    already = {f.as_posix(): {"total": 1, "counts": {**dict.fromkeys(guards.SUPPRESSION_MARKERS, 0),
                                                    marker: 1}}}
    assert guards.suppression_markers([f.as_posix()], already) == []


def test_lock_hashes_covers_tasks_and_checks(tmp_path):
    plan = tmp_path / "plans" / "slug"
    (plan / "checks").mkdir(parents=True)
    (plan / "tasks.json").write_text('{"tasks": []}', encoding="utf-8")
    (plan / "checks" / "check_t1.py").write_text("print('ok')\n", encoding="utf-8")
    (plan / "notes.md").write_text("not a grader\n", encoding="utf-8")

    hashes = guards.lock_hashes(plan)
    assert set(hashes) == {(plan / "tasks.json").as_posix(),
                           (plan / "checks" / "check_t1.py").as_posix()}
    for path, digest in hashes.items():
        assert digest == hashlib.sha256(Path(path).read_bytes()).hexdigest()
