"""Minimal stdlib-only loader for the optional `.harness/.env` file.

Format: plain `KEY=value` lines, `#` comments, blank lines ignored. No quoting,
no nesting. A real environment variable already set in the shell always wins
over the same key in the file.
"""

import os
from pathlib import Path

DEFAULT_ENV_PATH = Path(__file__).resolve().parent / ".env"


def parse_env_file(path):
    """Return a dict of KEY=value pairs from `path` ({} if it doesn't exist)."""
    path = Path(path)
    if not path.is_file():
        return {}

    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def load_env(path=None):
    """Apply `.harness/.env` (or `path`) into os.environ without overwriting."""
    for key, value in parse_env_file(path or DEFAULT_ENV_PATH).items():
        os.environ.setdefault(key, value)
