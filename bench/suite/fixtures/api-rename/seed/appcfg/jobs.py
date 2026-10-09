"""Background job settings."""

from appcfg.config import load_cfg

JOB_DEFAULTS = {"workers": 4, "retries": 3}


def job_settings(path) -> dict:
    """Return job settings from the JSON file at path, over the job defaults."""
    return load_cfg(path, JOB_DEFAULTS)
