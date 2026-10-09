"""Command-line entry point: the first argument is the settings file path."""

from appcfg.config import load_cfg

CLI_DEFAULTS = {"verbose": False, "port": 8000}


def run(argv: list[str]) -> dict:
    """Return the settings for argv; with no arguments, read app.json."""
    path = argv[0] if argv else "app.json"
    return load_cfg(path, CLI_DEFAULTS)
