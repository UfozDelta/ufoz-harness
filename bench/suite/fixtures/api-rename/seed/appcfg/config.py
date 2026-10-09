"""Load JSON settings files and merge them over defaults."""

import json
from pathlib import Path


def load_cfg(path, defaults=None) -> dict:
    """Return the JSON settings at path merged over defaults; defaults are not changed."""
    merged = dict(defaults or {})
    file = Path(path)
    if not file.exists():
        return merged
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"bad JSON in {file}: {exc}") from exc
    merged.update(data)
    return merged
