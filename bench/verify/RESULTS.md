# verify-bench results

Cells recorded: 27

## Combinations

| orchestrator | planner | executor | pass | fail | other | rules_ok | plan_ok | total | mean wall s | mean cost $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pi | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 | 939 | 0.145 |
| claude | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 | 205 | 0.014 |
| opencode | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 | 198 | 0.010 |
| claude | pi | claude | 1 | 0 | 0 | 1 | 1 | 1 | 178 | 0.343 |
| pi | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 438 | 0.013 |
| pi | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 | 281 | 0.011 |
| pi | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 392 | 0.009 |
| claude | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 219 | 0.010 |
| claude | claude | claude | 1 | 0 | 0 | 1 | 1 | 1 | 254 | 0.468 |
| claude | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 | 281 | 0.008 |
| opencode | pi | claude | 1 | 0 | 0 | 0 | 1 | 1 | 753 | 0.198 |
| opencode | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 | 287 | 0.008 |
| opencode | claude | claude | 1 | 0 | 0 | 0 | 1 | 1 | 367 | 0.390 |
| opencode | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 284 | 0.010 |
| opencode | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 | 419 | 0.010 |
| claude | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 152 | 0.015 |
| claude | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 | 114 | 0.437 |
| pi | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 292 | 0.012 |
| opencode | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 288 | 0.012 |
| pi | claude | claude | 1 | 0 | 0 | 1 | 1 | 1 | 168 | 0.354 |
| opencode | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 247 | 0.014 |
| pi | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 | 174 | 0.332 |
| pi | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 | 267 | 0.016 |
| claude | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 | 146 | 0.010 |
| claude | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 | 117 | 0.011 |
| opencode | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 | 178 | 0.357 |
| pi | pi | claude | 1 | 0 | 0 | 1 | 1 | 1 | 358 | 0.367 |

## Totals

- pass: 27
- fail: 0
- other (skipped/infra_error/timeout): 0
- total: 27
- rules_ok: 25
- plan_ok: 27
