import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
import envfile  # noqa: E402


def test_comments_and_blank_lines_ignored(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "\n"
        "# a comment\n"
        "   # indented comment\n"
        "\n"
        "  HARNESS_MODEL = opencode/space-bunny-free  \n",
        encoding="utf-8",
    )
    assert envfile.parse_env_file(env) == {
        "HARNESS_MODEL": "opencode/space-bunny-free"
    }


def test_malformed_lines_skipped(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "NO_EQUALS_SIGN\n"
        "=noname\n"
        "HARNESS_VARIANT=medium\n",
        encoding="utf-8",
    )
    assert envfile.parse_env_file(env) == {"HARNESS_VARIANT": "medium"}


def test_missing_file_returns_empty(tmp_path, monkeypatch):
    missing = tmp_path / "nope.env"
    assert envfile.parse_env_file(missing) == {}

    import os

    monkeypatch.delenv("HARNESS_ENVFILE_MISSING", raising=False)
    envfile.load_env(missing)
    assert "HARNESS_ENVFILE_MISSING" not in os.environ


def test_load_env_does_not_overwrite_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "HARNESS_ENVFILE_TEST=from_file\n"
        "HARNESS_ENVFILE_TEST_NEW=from_file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HARNESS_ENVFILE_TEST", "from_shell")
    monkeypatch.delenv("HARNESS_ENVFILE_TEST_NEW", raising=False)

    envfile.load_env(env)

    import os

    assert os.environ["HARNESS_ENVFILE_TEST"] == "from_shell"
    assert os.environ["HARNESS_ENVFILE_TEST_NEW"] == "from_file"
