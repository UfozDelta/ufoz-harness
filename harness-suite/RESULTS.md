# harness-suite results

Rows: 40 total, 40 counted (0 infra_error excluded).

## Per executor x size x mode

| executor | size | mode | n | pass@1 | pass^1 | wilson95 | median wall_s | cost/task | tokens/task |
|---|---|---|---|---|---|---|---|---|---|
| claude | large | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.662 | 1956886 |
| claude | large | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 284.4 | $0.763 | 2356660 |
| claude | large | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| claude | medium | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.374 | 1159660 |
| claude | medium | parallel | 1 | 100% | 1/1 (100%) | [21%, 100%] | 93.7 | $0.617 | 1068624 |
| claude | small | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.435 | 856786 |
| cline | large | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 9048422 |
| cline | large | parallel | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline | large | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 2059.1 | $0.000 | 8496684 |
| cline | large | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline | medium | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 2096248 |
| cline | medium | parallel | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline | small | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 1080735 |
| cline | small | parallel | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline | small | window | 1 | 100% | 1/1 (100%) | [21%, 100%] | 204.6 | $0.000 | 2355637 |
| cline-acp | large | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 17158732 |
| cline-acp | large | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline-acp | medium | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 3007318 |
| cline-acp | medium | parallel | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline-acp | medium | serial | 1 | 0% | 0/1 (0%) | [0%, 79%] | 582.2 | - | - |
| cline-acp | medium | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| cline-acp | small | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 513121 |
| cline-acp | small | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 149.1 | $0.000 | 565636 |
| opencode | large | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 1029097 |
| opencode | large | parallel | 1 | 100% | 1/1 (100%) | [21%, 100%] | 378.0 | $0.000 | 1329035 |
| opencode | large | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 448.1 | $0.000 | 962441 |
| opencode | medium | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 371036 |
| opencode | medium | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| opencode | small | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 384247 |
| opencode | small | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 482.8 | $0.000 | 377205 |
| pi | large | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 460681 |
| pi | large | parallel | 1 | 100% | 1/1 (100%) | [21%, 100%] | 154.5 | $0.000 | 505831 |
| pi | large | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| pi | medium | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 167815 |
| pi | medium | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 216.7 | $0.000 | 156922 |
| pi | medium | window | 1 | 0% | 0/1 (0%) | [0%, 79%] | - | - | - |
| pi | small | multi | 1 | 100% | 1/1 (100%) | [21%, 100%] | - | $0.000 | 107825 |
| pi | small | parallel | 1 | 100% | 1/1 (100%) | [21%, 100%] | 40.4 | $0.000 | 108584 |
| pi | small | serial | 1 | 100% | 1/1 (100%) | [21%, 100%] | 123.7 | $0.000 | 111383 |
| pi | small | window | 1 | 100% | 1/1 (100%) | [21%, 100%] | 75.3 | $0.000 | 115257 |

## Parallel speedup and multi overhead

| executor | size | serial wall | parallel wall | speedup | multi wall | multi overhead |
|---|---|---|---|---|---|---|
| claude | large | 284.4 | - | - | 327.6 | +15% |
| claude | medium | - | 93.7 | - | 327.6 | - |
| claude | small | - | - | - | 327.6 | - |
| cline | large | 2059.1 | - | - | 949.7 | -54% |
| cline | medium | - | - | - | 949.7 | - |
| cline | small | - | - | - | 949.7 | - |
| cline-acp | large | - | - | - | 919.7 | - |
| cline-acp | medium | 582.2 | - | - | 919.7 | +58% |
| cline-acp | small | 149.1 | - | - | 919.7 | +517% |
| opencode | large | 448.1 | 378.0 | 1.19x | 676.4 | +51% |
| opencode | medium | - | - | - | 676.4 | - |
| opencode | small | 482.8 | - | - | 676.4 | +40% |
| pi | large | - | 154.5 | - | 226.4 | - |
| pi | medium | 216.7 | - | - | 226.4 | +4% |
| pi | small | 123.7 | 40.4 | 3.06x | 226.4 | +83% |

## Cost

| executor | runs | total cost | cost/pass | notes |
|---|---|---|---|---|
| claude | 6 | $2.85 | $0.570 | Sonnet (paid-tier model) - reported separately |
| cline | 9 | $0.00 | $0.000 |  |
| cline-acp | 8 | $0.00 | $0.000 |  |
| opencode | 7 | $0.00 | $0.000 |  |
| pi | 10 | $0.00 | $0.000 |  |
| **total** | 40 | $2.85 |  |  |

Excluding Sonnet (`claude`): $0.00.

## Harness revision delta

- `5030d80-dirty`: 29 rows, 28 pass, $2.85 cost, median wall 210.6.
- `unknown`: 11 rows, 0 pass, $0.00 cost, median wall -.

Delta `5030d80-dirty` -> `unknown`: pass-rate 97% -> 0%, cost -2.85 USD.

