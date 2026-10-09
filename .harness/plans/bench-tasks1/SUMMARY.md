What: 8 pure-stdlib Python fixtures under bench/suite/fixtures/: fix-failing-test, fix-from-prose, refactor-extract, multi-file-feature, ambiguous-spec, deprecation-cleanup, scope-bait, api-rename. Each has task.toml, spec.md, seed/, solution/, hidden_tests/test_hidden.py. All 8 pass check_fixtures (seed red under hidden, green with solution).
Files: bench/suite/fixtures/<id>/** only.
Wiring: check_fixtures.py --size <id> copies seed, then hidden_tests, then solution; tasks.py discovers each dir via task.toml.
BUILD: pass
