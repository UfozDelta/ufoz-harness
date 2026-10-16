import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner import skills  # noqa: E402
from runner.executors import pi  # noqa: E402


def test_one_dir_under_three_names_yields_one_skill_arg(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "shared").mkdir(parents=True)
    (root / "shared" / "SKILL.md").write_text("# shared\n", encoding="utf-8")

    listing = tmp_path / "skills.txt"
    listing.write_text("shared\n./shared\nshared/\n", encoding="utf-8")

    monkeypatch.setattr(skills, "LIST_FILE", listing)
    monkeypatch.setattr(skills, "default_roots", lambda: [root])
    monkeypatch.setenv("HARNESS_SKILLS", "1")

    resolved = skills.resolve(skills.load_list(), skills.default_roots())

    assert len(resolved) == 1
    assert pi._skill_args().count("--skill") == 1
