"""Server settings."""

from appcfg.config import load_cfg

SERVER_DEFAULTS = {"host": "127.0.0.1", "port": 8080, "workers": 2}


def server_settings(path) -> dict:
    """Return server settings from the JSON file at path, over the server defaults."""
    return load_cfg(path, SERVER_DEFAULTS)
