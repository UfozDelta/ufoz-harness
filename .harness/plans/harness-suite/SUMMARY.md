# harness-suite

`harness-suite/suite.py` builds the size x mode x executor x rep matrix (build_matrix, preflight_executor).
Non-dry main(): per pending cell in order_idx order, preflight, `cells.run_cell(cell, REPO_ROOT,
cell_timeout, keep)`, then `cells.cleanup_cell` unless `--keep`; each row is appended to results.csv
(slug + COLUMNS, header once). Resume skips known slugs, `--force` overrides, `--rerun-infra` reruns
infra_error, `--max-cost` stops early. Fixtures live in harness-suite/fixtures/ (check_fixtures.py: seed
RED, solution GREEN); report.py writes RESULTS.md.
BUILD: pass
