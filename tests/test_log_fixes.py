"""Fixes for the open items in log.md (lint deps/shadowing/metrics probe, suppression
literals, --relock-only, suite worktrees without the fixtures or main history)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import cli, guards, worktree  # noqa: E402
from runner import lint as lint_mod  # noqa: E402

RED = 'python -c "raise SystemExit(1)"'


def _lint(plan_dir, tasks, capsys):
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.md").write_text("".join(f"## {t['id']}\n" for t in tasks), encoding="utf-8")
    code = lint_mod.lint(plan_dir, tasks, passed=set())
    return code, capsys.readouterr().out


def test_shared_files_ordered_through_a_dep_chain_do_not_warn(tmp_path, capsys):
    tasks = [{"id": "T1", "files": ["a.py"], "acceptance": RED},
             {"id": "T2", "deps": ["T1"], "files": ["b.py"], "acceptance": RED},
             {"id": "T3", "deps": ["T2"], "files": ["a.py"], "acceptance": RED}]
    code, out = _lint(tmp_path / "plans" / "slug", tasks, capsys)
    assert code == 0 and "share" not in out, out


def test_shared_files_without_any_dep_path_still_warn(tmp_path, capsys):
    tasks = [{"id": "T1", "files": ["a.py"], "acceptance": RED},
             {"id": "T2", "files": ["a.py"], "acceptance": RED}]
    code, out = _lint(tmp_path / "plans" / "slug", tasks, capsys)
    assert "T1/T2: share" in out


def test_module_shadowing_a_harness_package_warns(tmp_path, capsys):
    tasks = [{"id": "T1", "files": ["suite/runner.py"], "acceptance": RED}]
    code, out = _lint(tmp_path / "plans" / "slug", tasks, capsys)
    assert "shadows" in out and "runner" in out


def test_lint_outside_a_plans_dir_does_not_write_metrics(tmp_path, capsys):
    # a fixture plan (fixtures/medium/plan) used to get fixtures/metrics.jsonl
    plan_dir = tmp_path / "fixtures" / "medium" / "plan"
    _lint(plan_dir, [{"id": "T1", "files": ["a.py"], "acceptance": RED}], capsys)
    assert not (tmp_path / "fixtures" / "metrics.jsonl").exists()


def test_markers_inside_string_literals_are_not_suppressions(tmp_path):
    f = tmp_path / "x.ts"
    f.write_text('const NEEDLES = ["@ts-ignore", \'eslint-disable\'];\n'
                 "// @ts-ignore\n"
                 "let y = 1; /* eslint-disable */\n", encoding="utf-8")
    counts = guards.marker_counts(f)
    assert counts["@ts-ignore"] == 1
    assert counts["eslint-disable"] == 1


def test_a_stray_quote_cannot_hide_a_real_suppression(tmp_path):
    f = tmp_path / "x.ts"
    f.write_text("/* it's */ // @ts-ignore 'x'\n", encoding="utf-8")
    assert guards.marker_counts(f)["@ts-ignore"] == 1


def test_relock_only_writes_the_lock_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan_dir = tmp_path / ".harness" / "plans" / "slug"
    plan_dir.mkdir(parents=True)
    (plan_dir / "tasks.json").write_text(json.dumps({"tasks": [
        {"id": "T1", "files": ["a.py"], "acceptance": RED}]}), encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["slug", "--relock-only"])
    assert exit_info.value.code == 0
    lock = json.loads((plan_dir / "plan.lock.json").read_text(encoding="utf-8"))
    assert ".harness/plans/slug/tasks.json" in lock
    assert not (plan_dir / "items" / "T1.report.md").exists()


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_worktree_can_exclude_paths_and_drop_main_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "keep.txt").write_text("k\n", encoding="utf-8")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "hidden.py").write_text("answer = 42\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    wt = worktree.ensure("cell", exclude=["secret"], orphan=True)
    assert (wt / "keep.txt").is_file()
    assert not (wt / "secret").exists()
    assert _git(wt, "rev-list", "--count", "HEAD").stdout.strip() == "1"  # no parent to git show
    assert _git(wt, "status", "--porcelain").stdout.strip() == ""  # nothing shows up as deleted
