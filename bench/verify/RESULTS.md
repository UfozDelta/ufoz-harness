# verify-bench results

Cells recorded: 27

## Combinations

| orchestrator | planner | executor | pass | fail | other | rules_ok | plan_ok | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pi | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | pi | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | pi | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | claude | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | pi | claude | 1 | 0 | 0 | 0 | 1 | 1 |
| opencode | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | claude | claude | 1 | 0 | 0 | 0 | 1 | 1 |
| opencode | pi | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | claude | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | claude | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | opencode | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | opencode | opencode | 1 | 0 | 0 | 1 | 1 | 1 |
| claude | claude | pi | 1 | 0 | 0 | 1 | 1 | 1 |
| opencode | opencode | claude | 1 | 0 | 0 | 1 | 1 | 1 |
| pi | pi | claude | 1 | 0 | 0 | 1 | 1 | 1 |

## Totals

- pass: 27
- fail: 0
- other (skipped/infra_error/timeout): 0
- total: 27
- rules_ok: 25
- plan_ok: 27
