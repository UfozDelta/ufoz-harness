"""Curated executor skills: one list (.harness/skills.txt), on only for frontend plans,
the same for pi and opencode, each skill loaded once."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".harness"))
from runner import skills  # noqa: E402
from runner.executors import opencode as oc  # noqa: E402
from runner.executors import pi  # noqa: E402

FAKE = ("frontend-design", "animate")


@pytest.fixture
def roots(tmp_path):
    """Two search roots holding the same skill (duplicate) plus one only in the second."""
    first, second = tmp_path / "a", tmp_path / "b"
    for root, names in ((first, ["frontend-design"]), (second, ["frontend-design", "animate", "other"])):
        for n in names:
            (root / n).mkdir(parents=True)
            (root / n / "SKILL.md").write_text(f"---\nname: {n}\n---\n", encoding="utf-8")
    return [first, second]


def test_list_file_names_the_four_frontend_skills():
    names = skills.load_list()
    assert names == ["frontend-design", "emil-design-eng", "animate", "mobile-native"]


def test_load_list_ignores_blanks_and_comments(tmp_path):
    f = tmp_path / "skills.txt"
    f.write_text("# comment\nfrontend-design\n\n  animate  \n", encoding="utf-8")
    assert skills.load_list(f) == ["frontend-design", "animate"]


def test_resolve_first_root_wins_and_each_skill_once(roots):
    dirs = skills.resolve(list(FAKE), roots)
    assert dirs == [roots[0] / "frontend-design", roots[1] / "animate"]


def test_resolve_skips_missing_names(roots):
    assert skills.resolve(["nope", "animate"], roots) == [roots[1] / "animate"]


def test_default_roots_order():
    home = Path.home()
    assert skills.default_roots() == [Path(".agents/skills"), Path(".claude/skills"),
                                      home / ".agents" / "skills", home / ".claude" / "skills"]


@pytest.mark.parametrize("files,want", [
    (["app/page.tsx"], True), (["web/x.jsx"], True), (["s.css"], True), (["a.scss"], True),
    (["i.html"], True), (["c.vue"], True), (["c.svelte"], True),
    (["app/main.py", "lib/x.ts"], False), ([], False),
])
def test_plan_wants_skills(files, want):
    assert skills.plan_wants_skills([{"files": files}, {"files": ["README.md"]}]) is want


def test_apply_default_respects_an_explicit_setting():
    env = {"HARNESS_SKILLS": "0"}
    skills.apply_default([{"files": ["a.tsx"]}], env)
    assert env["HARNESS_SKILLS"] == "0"
    env = {}
    skills.apply_default([{"files": ["a.tsx"]}], env)
    assert env["HARNESS_SKILLS"] == "1"
    env = {}
    skills.apply_default([{"files": ["a.py"]}], env)
    assert env["HARNESS_SKILLS"] == "0"


def test_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("HARNESS_SKILLS", raising=False)
    assert skills.enabled() is False
    monkeypatch.setenv("HARNESS_SKILLS", "1")
    assert skills.enabled() is True


def test_pi_off_is_no_skills(monkeypatch):
    monkeypatch.setenv("HARNESS_SKILLS", "0")
    assert pi._skill_args() == ["--no-skills"]


def test_pi_on_loads_each_listed_skill_once_and_nothing_else(monkeypatch, roots):
    monkeypatch.setenv("HARNESS_SKILLS", "1")
    monkeypatch.setattr(skills, "load_list", lambda path=None: list(FAKE))
    monkeypatch.setattr(skills, "default_roots", lambda: roots)
    assert pi._skill_args() == ["--no-skills", "--skill", str(roots[0] / "frontend-design"),
                                "--skill", str(roots[1] / "animate")]


def test_opencode_on_lists_only_the_chosen_skills(monkeypatch, roots):
    monkeypatch.setenv("HARNESS_SKILLS", "1")
    monkeypatch.setattr(skills, "load_list", lambda path=None: list(FAKE))
    monkeypatch.setattr(skills, "default_roots", lambda: roots)
    cfg = oc.opencode_config([])
    assert cfg["skills"]["paths"] == [str((roots[0] / "frontend-design").resolve()),
                                      str((roots[1] / "animate").resolve())]
    assert cfg["permission"].get("skill") != "deny"


def test_opencode_off_has_no_skills(monkeypatch):
    monkeypatch.setenv("HARNESS_SKILLS", "0")
    cfg = oc.opencode_config([])
    assert "skills" not in cfg
    assert cfg["permission"]["skill"] == "deny"


def test_opencode_never_discovers_claude_or_agents_skills(tmp_path):
    env = oc._serve_env({}, tmp_path, "C:/x")
    assert env["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"
    assert env["OPENCODE_DISABLE_EXTERNAL_SKILLS"] == "1"
