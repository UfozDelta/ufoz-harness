# Usage

`appcfg` reads JSON settings files.

    from appcfg.config import load_cfg
    settings = load_cfg("app.json", defaults={"port": 8000})

- `load_cfg(path, defaults=None)` merges the file over the defaults. A missing file returns the defaults, and invalid JSON raises `ValueError`.
- `cli.run(argv)`, `server.server_settings(path)` and `jobs.job_settings(path)` are thin wrappers around `load_cfg`.
