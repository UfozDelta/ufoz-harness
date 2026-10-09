# Spec (api-rename): rename load_cfg to load_config everywhere

The public settings loader `load_cfg(path, defaults=None)` in `appcfg` has an abbreviated name that our team no longer likes, so please rename it to `load_config` with the same signature and behaviour. The name must change in the `appcfg` package, in every module that calls it (`cli`, `server`, `jobs`), and in `docs/usage.md` and `README.md`. The old name should not remain anywhere in the package or the docs. `cli.run`, `server.server_settings` and `jobs.job_settings` keep their names and results.
