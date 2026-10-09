# Usage

`appcfg` reads JSON settings files.

    from appcfg.config import load_config
    settings = load_config("app.json", defaults={"port": 8000})

- `load_config(path, defaults=None)` merges the file over the defaults. A missing file returns the defaults, and invalid JSON raises `ValueError`.
- `cli.run(argv)`, `server.server_settings(path)` and `jobs.job_settings(path)` are thin wrappers around `load_config`.
