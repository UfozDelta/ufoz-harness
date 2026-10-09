import json

import pytest

from appcfg import cli, jobs, server


def write(tmp_path, data):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_server_settings_override_defaults(tmp_path):
    settings = server.server_settings(write(tmp_path, {"port": 9000}))
    assert settings["port"] == 9000
    assert settings["host"] == "127.0.0.1"


def test_job_settings_override_defaults(tmp_path):
    settings = jobs.job_settings(write(tmp_path, {"retries": 5}))
    assert settings["retries"] == 5
    assert settings["workers"] == 4


def test_cli_reads_path_from_argv(tmp_path):
    settings = cli.run([write(tmp_path, {"verbose": True})])
    assert settings["verbose"] is True
    assert settings["port"] == 8000


def test_missing_file_gives_defaults(tmp_path):
    assert server.server_settings(str(tmp_path / "none.json"))["port"] == 8080


def test_bad_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValueError):
        jobs.job_settings(str(bad))
