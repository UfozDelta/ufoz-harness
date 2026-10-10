# harness-suite results

Rows: 94 total, 53 latest per cell, 1 counted (0 infra_error and 0 harness_fail excluded).
Scope: harness_sha `1e94d80+ab107c` only (`--all-shas` for every revision).
Kit hash: 0425ca2a.

## Per executor x size x mode

| executor | size | mode | n | pass@1 | first_try | pass^1 | wilson95 | median wall_s | cost/task | tokens/task | regressions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude:haiku | small | serial | 1 | 0% | 0% | 0/1 (0%) | [0%, 79%] | 298.3 | - | - | 0 |

## Per capability

| capability | arm | n | first_try | pass-after-retry | wilson95 |
|---|---|---|---|---|---|
| multi-file-feature | claude:haiku | 1 | 0% | 0% | [0%, 79%] |

## Per task

| size | arm | n | first_try | pass-after-retry | wilson95 |
|---|---|---|---|---|---|
| small | claude:haiku | 1 | 0% | 0% | [0%, 79%] |

## Parallel speedup and multi overhead

| executor | size | serial wall | parallel wall | speedup | multi wall | multi overhead |
|---|---|---|---|---|---|---|
| claude | small | 298.3 | - | - | - | - |

## Cost

| executor | runs | total cost | cost/pass | notes |
|---|---|---|---|---|
| claude | 1 | $0.04 | - | haiku (paid tier) - reported separately |
| **total** | 1 | $0.04 |  |  |

Excluding `claude`: $0.00.
Planner cost (not billed to executors): $0.00.

## Harness revision delta

- `376b7a4-dirty`: 2 rows, 2 pass, $0.02 cost, median wall 283.1.
- `f9cd4c8+4119f5`: 2 rows, 2 pass, $0.00 cost, median wall 138.6.
- `f946157+e73990`: 1 rows, 1 pass, $0.00 cost, median wall 64.1.
- `f107714+036312`: 16 rows, 13 pass, $0.66 cost, median wall 40.5.
- `f107714+d27d83`: 6 rows, 6 pass, $0.78 cost, median wall 47.5.
- `1e94d80+58340a`: 1 rows, 0 pass, $0.00 cost, median wall 8.0.
- `1e94d80+653150`: 1 rows, 0 pass, $0.00 cost, median wall 8.0.
- `1e94d80+ee2870`: 19 rows, 19 pass, $2.51 cost, median wall 40.0.
- `1e94d80+9454f0`: 2 rows, 0 pass, $0.00 cost, median wall 291.9.
- `1e94d80+7cd659`: 2 rows, 0 pass, $0.33 cost, median wall 1291.8.
- `1e94d80+ab107c`: 1 rows, 0 pass, $0.04 cost, median wall 298.3.

Delta `1e94d80+7cd659` -> `1e94d80+ab107c`: pass-rate 0% -> 0%, cost -0.29 USD.

