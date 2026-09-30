"""worktree._exclude_worktrees / worktree._link inside a real linked worktree.

Every test builds a throwaway git repo in tmp_path (real `git`, like the task runner
tests) and chdirs into it, restoring the cwd afterwards.
"""
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import worktree  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, f"git {args} failed: {r.stderr}"
    return r


def _repo(root, ignored=()):
    """A main worktree at `root` with `ignored` dirs present and gitignored."""
    root.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", str(root), cwd=root)
    _git("config", "user.email", "t@t", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    (root / "README.md").write_text("main\n", encoding="utf-8")
    lines = [f"{d}/" for d in ignored]
    if lines:
        (root / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for d in ignored:
        (root / d).mkdir(parents=True)
        (root / d / "marker.txt").write_text(d, encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-qm", "init", cwd=root)
    return root


def _linked(main, name):
    """A linked worktree of `main` at `<main>.worktrees/<name>`."""
    wt = main.parent / (main.name + ".worktrees") / name
    _git("worktree", "add", "-q", "-b", f"wt-{name}", str(wt), cwd=main)
    return wt


@contextmanager
def _chdir(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(old)


def test_exclude_worktrees_writes_common_info_exclude_in_linked_worktree(tmp_path):
    main = _repo(tmp_path / "main")
    wt = _linked(main, "wt")
    exclude = Path(_git("rev-parse", "--path-format=absolute", "--git-path", "info/exclude",
                        cwd=wt).stdout.strip())
    if exclude.exists():
        assert ".worktrees/" not in exclude.read_text(encoding="utf-8")
    with _chdir(wt):
        worktree._exclude_worktrees()  # used to crash: no .git/info/exclude here
    assert exclude.exists()
    assert ".worktrees/" in exclude.read_text(encoding="utf-8")
    # the linked worktree's own git file was not used as the exclude location
    assert not (wt / ".git" / "info" / "exclude").exists()


def test_link_sources_shared_dir_from_main_worktree(tmp_path):
    main = _repo(tmp_path / "main", ignored=("node_modules",))
    wt = _linked(main, "wt")
    assert not (wt / "node_modules").exists()
    with _chdir(wt):
        worktree._link("node_modules", wt)
    linked = wt / "node_modules"
    assert linked.exists()
    assert (linked / "marker.txt").read_text(encoding="utf-8") == "node_modules"
    if os.name == "nt":  # mklink /J junction points back at the main tree's dir
        assert os.path.realpath(linked) == os.path.realpath(main / "node_modules")


def test_link_keeps_existing_target_dir(tmp_path):
    main = _repo(tmp_path / "main", ignored=("node_modules",))
    wt = _linked(main, "wt")
    keep = wt / "node_modules"
    keep.mkdir()
    (keep / "keep.txt").write_text("mine\n", encoding="utf-8")
    with _chdir(wt):
        worktree._link("node_modules", wt)  # must not delete or replace the target
    assert (keep / "keep.txt").read_text(encoding="utf-8") == "mine\n"
