import json
from pathlib import Path

import pytest

import appcfg
from appcfg import cli, config, jobs, server

ROOT = Path(__file__).resolve().parent


def write(tmp_path, data):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_load_config_merges_file_over_defaults(tmp_path):
    path = write(tmp_path, {"port": 9000})
    assert config.load_config(path, {"port": 8080, "debug": False}) == {"port": 9000, "debug": False}


def test_load_config_missing_file_returns_defaults(tmp_path):
    assert config.load_config(str(tmp_path / "none.json"), {"a": 1}) == {"a": 1}


def test_load_config_does_not_mutate_defaults(tmp_path):
    defaults = {"a": 1}
    config.load_config(write(tmp_path, {"a": 2}), defaults)
    assert defaults == {"a": 1}


def test_load_config_bad_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValueError):
        config.load_config(str(bad))


def test_load_config_exported_from_package():
    assert appcfg.load_config is config.load_config


def test_old_name_removed_from_package():
    assert not hasattr(appcfg, "load_cfg")
    assert not hasattr(config, "load_cfg")


def test_old_name_absent_from_package_sources():
    for path in sorted((ROOT / "appcfg").glob("*.py")):
        assert "load_cfg" not in path.read_text(encoding="utf-8"), path.name


def test_docs_use_new_name_only():
    for path in (ROOT / "docs" / "usage.md", ROOT / "README.md"):
        text = path.read_text(encoding="utf-8")
        assert "load_cfg" not in text, path.name
        assert "load_config" in text, path.name


def test_callers_still_work(tmp_path):
    path = write(tmp_path, {"port": 9000})
    assert cli.run([path])["port"] == 9000
    assert server.server_settings(path)["port"] == 9000
    assert jobs.job_settings(write(tmp_path, {"workers": 7}))["workers"] == 7
