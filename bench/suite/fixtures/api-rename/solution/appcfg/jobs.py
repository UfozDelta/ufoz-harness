"""Background job settings."""

from appcfg.config import load_config

JOB_DEFAULTS = {"workers": 4, "retries": 3}


def job_settings(path) -> dict:
    """Return job settings from the JSON file at path, over the job defaults."""
    return load_config(path, JOB_DEFAULTS)
