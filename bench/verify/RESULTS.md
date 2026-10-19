# verify-bench results

Cells recorded: 45

## Combinations

| orchestrator | planner | executor | n | pass | pass % | rules_ok | plan_ok | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opencode | claude | pi | 1† | 1 | 100% | 1 | 1 | 287 | 0.008 | - | - | 0.008 |
| claude | opencode | pi | 1† | 1 | 100% | 1 | 1 | 281 | 0.008 | - | - | 0.008 |
| pi | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 392 | 0.009 | - | - | 0.009 |
| claude | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 146 | 0.010 | - | - | 0.010 |
| opencode | opencode | pi | 1† | 1 | 100% | 1 | 1 | 419 | 0.010 | - | - | 0.010 |
| opencode | pi | pi | 3 | 3 | 100% | 3 | 3 | 481 ± 156 | 0.011 ± 0.001 | 704445 | 95.5% | 0.011 |
| claude | claude | pi | 1† | 1 | 100% | 1 | 1 | 117 | 0.011 | - | - | 0.011 |
| pi | claude | pi | 1† | 1 | 100% | 1 | 1 | 281 | 0.011 | - | - | 0.011 |
| pi | claude | opencode | 1† | 1 | 100% | 1 | 1 | 292 | 0.012 | - | - | 0.012 |
| opencode | claude | opencode | 1† | 1 | 100% | 1 | 1 | 288 | 0.012 | - | - | 0.012 |
| opencode | pi | opencode | 3 | 3 | 100% | 3 | 3 | 410 ± 144 | 0.013 ± 0.003 | 759083 | 94.5% | 0.013 |
| opencode | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 247 | 0.014 | - | - | 0.014 |
| claude | claude | opencode | 1† | 1 | 100% | 1 | 1 | 152 | 0.015 | - | - | 0.015 |
| pi | opencode | pi | 1† | 1 | 100% | 1 | 1 | 267 | 0.016 | - | - | 0.016 |
| pi | pi | pi | 3 | 3 | 100% | 3 | 3 | 222 ± 57 | 0.071 ± 0.011 | 3297235 | 94.3% | 0.071 |
| pi | pi | opencode | 3 | 3 | 100% | 3 | 3 | 354 ± 34 | 0.076 ± 0.020 | 4044106 | 95.4% | 0.076 |
| claude | pi | pi | 3 | 3 | 100% | 3 | 3 | 175 ± 29 | 0.303 ± 0.044 | 1595218 | 88.9% | 0.303 |
| pi | opencode | claude | 1† | 1 | 100% | 1 | 1 | 174 | 0.332 | - | - | 0.332 |
| claude | pi | opencode | 3 | 3 | 100% | 3 | 3 | 210 ± 30 | 0.333 ± 0.065 | 1899778 | 90.5% | 0.333 |
| pi | claude | claude | 1† | 1 | 100% | 1 | 1 | 168 | 0.354 | - | - | 0.354 |
| opencode | opencode | claude | 1† | 1 | 100% | 1 | 1 | 178 | 0.357 | - | - | 0.357 |
| opencode | pi | claude | 3 | 3 | 100% | 3 | 3 | 493 ± 155 | 0.364 ± 0.124 | 796687 | 91.1% | 0.364 |
| opencode | claude | claude | 1† | 1 | 100% | 0 | 1 | 367 | 0.390 | - | - | 0.390 |
| pi | pi | claude | 3 | 3 | 100% | 2 | 3 | 341 ± 162 | 0.395 ± 0.037 | 2660805 | 91.3% | 0.395 |
| claude | opencode | claude | 1† | 1 | 100% | 1 | 1 | 114 | 0.437 | - | - | 0.437 |
| claude | claude | claude | 1† | 1 | 100% | 1 | 1 | 254 | 0.468 | - | - | 0.468 |
| claude | pi | claude | 3 | 3 | 100% | 3 | 3 | 216 ± 44 | 0.562 ± 0.033 | 1758157 | 89.3% | 0.562 |

† n < 3: rank provisional.

## By axis

### orchestrator

| orchestrator | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 15 | 100% | 191 ± 52 | 0.303 ± 0.208 | 5253153 | 89.6% | 0.303 |
| opencode | 15 | 100% | 396 ± 142 | 0.130 ± 0.180 | 2260215 | 93.6% | 0.130 |
| pi | 15 | 100% | 288 ± 98 | 0.157 ± 0.162 | 10002146 | 94.0% | 0.157 |

### planner

| planner | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 9 | 100% | 245 ± 81 | 0.142 ± 0.198 | - | - | 0.142 |
| opencode | 9 | 100% | 246 ± 106 | 0.133 ± 0.184 | - | - | 0.133 |
| pi | 27 | 100% | 323 ± 147 | 0.236 ± 0.196 | 17515514 | 92.6% | 0.236 |

### executor

| executor | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 15 | 100% | 294 ± 154 | 0.420 ± 0.095 | 5215649 | 90.6% | 0.420 |
| opencode | 15 | 100% | 296 ± 111 | 0.089 ± 0.131 | 6702967 | 93.9% | 0.089 |
| pi | 15 | 100% | 286 ± 138 | 0.081 ± 0.118 | 5596898 | 92.9% | 0.081 |

## Per phase

| orchestrator | planner | executor | phase | mean wall s | mean in | mean out | mean cache_read | mean cache_write | mean cost $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pi | pi | pi | orch | 156.2 ± 49.9 | 46366 ± 9367 | 34244 ± 8230 | 841283 ± 426924 | 0 ± 0 | 0.060 ± 0.011 |
| pi | pi | pi | plan | - | - | - | - | - | - |
| pi | pi | pi | exec | 49.6 ± 8.4 | 12679 ± 5491 | 5031 ± 982 | 132030 ± 65479 | 0 ± 0 | 0.011 ± 0.001 |
| claude | pi | pi | orch | 71.2 ± 4.7 | 15 ± 2 | 8653 ± 1862 | 319819 ± 66733 | 43285 ± 4150 | 0.292 ± 0.041 |
| claude | pi | pi | plan | - | - | - | - | - | - |
| claude | pi | pi | exec | 80.1 ± 14.3 | 14304 ± 6141 | 4754 ± 994 | 140011 ± 36559 | 0 ± 0 | 0.011 ± 0.003 |
| opencode | pi | pi | orch | 385.0 ± 166.4 | - | - | - | - | - |
| opencode | pi | pi | plan | - | - | - | - | - | - |
| opencode | pi | pi | exec | 67.7 ± 11.3 | 10245 ± 2139 | 5330 ± 184 | 217728 ± 26796 | 0 ± 0 | 0.011 ± 0.001 |
| claude | pi | claude | orch | 92.6 ± 42.8 | 14 ± 3 | 9288 ± 3711 | 302426 ± 103970 | 43735 ± 6784 | 0.298 ± 0.075 |
| claude | pi | claude | plan | - | - | - | - | - | - |
| claude | pi | claude | exec | 93.3 ± 6.5 | 17490 ± 1051 | 4104 ± 734 | 208921 ± 85996 | - | 0.264 ± 0.096 |
| pi | pi | opencode | orch | 176.0 ± 38.7 | 44784 ± 6664 | 36918 ± 15910 | 1052435 ± 573230 | 0 ± 0 | 0.064 ± 0.021 |
| pi | pi | opencode | plan | - | - | - | - | - | - |
| pi | pi | opencode | exec | 147.2 ± 19.8 | 14216 ± 2103 | 3969 ± 72 | 168678 ± 41039 | 0 ± 0 | 0.012 ± 0.001 |
| pi | claude | pi | orch | - | - | - | - | - | - |
| pi | claude | pi | plan | - | - | - | - | - | - |
| pi | claude | pi | exec | - | - | - | - | - | 0.011 |
| pi | opencode | opencode | orch | - | - | - | - | - | - |
| pi | opencode | opencode | plan | - | - | - | - | - | - |
| pi | opencode | opencode | exec | - | - | - | - | - | 0.009 |
| claude | pi | opencode | orch | 81.5 ± 24.5 | 17 ± 2 | 9548 ± 3856 | 396208 ± 77383 | 46732 ± 4802 | 0.322 ± 0.064 |
| claude | pi | opencode | plan | - | - | - | - | - | - |
| claude | pi | opencode | exec | 104.0 ± 16.9 | 12113 ± 4567 | 3731 ± 422 | 163427 ± 15575 | 0 ± 0 | 0.011 ± 0.002 |
| claude | claude | claude | orch | - | - | - | - | - | - |
| claude | claude | claude | plan | - | - | - | - | - | - |
| claude | claude | claude | exec | - | - | - | - | - | 0.468 |
| claude | opencode | pi | orch | - | - | - | - | - | - |
| claude | opencode | pi | plan | - | - | - | - | - | - |
| claude | opencode | pi | exec | - | - | - | - | - | 0.008 |
| opencode | pi | claude | orch | 383.8 ± 125.1 | - | - | - | - | - |
| opencode | pi | claude | plan | - | - | - | - | - | - |
| opencode | pi | claude | exec | 88.6 ± 32.0 | 23158 ± 5471 | 4530 ± 1210 | 237790 ± 71098 | - | 0.364 ± 0.124 |
| opencode | claude | pi | orch | - | - | - | - | - | - |
| opencode | claude | pi | plan | - | - | - | - | - | - |
| opencode | claude | pi | exec | - | - | - | - | - | 0.008 |
| opencode | claude | claude | orch | - | - | - | - | - | - |
| opencode | claude | claude | plan | - | - | - | - | - | - |
| opencode | claude | claude | exec | - | - | - | - | - | 0.390 |
| opencode | pi | opencode | orch | 268.0 ± 49.4 | - | - | - | - | - |
| opencode | pi | opencode | plan | - | - | - | - | - | - |
| opencode | pi | opencode | exec | 121.6 ± 88.2 | 13531 ± 5032 | 4304 ± 536 | 232998 ± 90502 | 0 ± 0 | 0.013 ± 0.003 |
| opencode | opencode | pi | orch | - | - | - | - | - | - |
| opencode | opencode | pi | plan | - | - | - | - | - | - |
| opencode | opencode | pi | exec | - | - | - | - | - | 0.010 |
| claude | claude | opencode | orch | - | - | - | - | - | - |
| claude | claude | opencode | plan | - | - | - | - | - | - |
| claude | claude | opencode | exec | - | - | - | - | - | 0.015 |
| claude | opencode | claude | orch | - | - | - | - | - | - |
| claude | opencode | claude | plan | - | - | - | - | - | - |
| claude | opencode | claude | exec | - | - | - | - | - | 0.437 |
| pi | claude | opencode | orch | - | - | - | - | - | - |
| pi | claude | opencode | plan | - | - | - | - | - | - |
| pi | claude | opencode | exec | - | - | - | - | - | 0.012 |
| opencode | claude | opencode | orch | - | - | - | - | - | - |
| opencode | claude | opencode | plan | - | - | - | - | - | - |
| opencode | claude | opencode | exec | - | - | - | - | - | 0.012 |
| pi | claude | claude | orch | - | - | - | - | - | - |
| pi | claude | claude | plan | - | - | - | - | - | - |
| pi | claude | claude | exec | - | - | - | - | - | 0.354 |
| opencode | opencode | opencode | orch | - | - | - | - | - | - |
| opencode | opencode | opencode | plan | - | - | - | - | - | - |
| opencode | opencode | opencode | exec | - | - | - | - | - | 0.014 |
| pi | opencode | claude | orch | - | - | - | - | - | - |
| pi | opencode | claude | plan | - | - | - | - | - | - |
| pi | opencode | claude | exec | - | - | - | - | - | 0.332 |
| pi | opencode | pi | orch | - | - | - | - | - | - |
| pi | opencode | pi | plan | - | - | - | - | - | - |
| pi | opencode | pi | exec | - | - | - | - | - | 0.016 |
| claude | opencode | opencode | orch | - | - | - | - | - | - |
| claude | opencode | opencode | plan | - | - | - | - | - | - |
| claude | opencode | opencode | exec | - | - | - | - | - | 0.010 |
| claude | claude | pi | orch | - | - | - | - | - | - |
| claude | claude | pi | plan | - | - | - | - | - | - |
| claude | claude | pi | exec | - | - | - | - | - | 0.011 |
| opencode | opencode | claude | orch | - | - | - | - | - | - |
| opencode | opencode | claude | plan | - | - | - | - | - | - |
| opencode | opencode | claude | exec | - | - | - | - | - | 0.357 |
| pi | pi | claude | orch | 182.8 ± 96.2 | 53903 ± 17999 | 27730 ± 3929 | 513288 ± 69857 | 0 ± 0 | 0.053 ± 0.010 |
| pi | pi | claude | plan | - | - | - | - | - | - |
| pi | pi | claude | exec | 110.4 ± 54.5 | 18396 ± 1672 | 3739 ± 675 | 249019 ± 25144 | - | 0.342 ± 0.041 |

## Totals

- pass: 45
- fail: 0
- other (skipped/infra_error/timeout): 0
- total: 45
- rules_ok: 43
- plan_ok: 45
