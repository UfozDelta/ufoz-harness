# verify-bench results

Cells recorded: 27

## Combinations

| orchestrator | planner | executor | n | pass | pass % | rules_ok | plan_ok | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opencode | claude | pi | 1† | 1 | 100% | 1 | 1 | 287 | 0.008 | - | - | 0.008 |
| claude | opencode | pi | 1† | 1 | 100% | 1 | 1 | 281 | 0.008 | - | - | 0.008 |
| pi | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 392 | 0.009 | - | - | 0.009 |
| opencode | pi | opencode | 1† | 1 | 100% | 1 | 1 | 284 | 0.010 | - | - | 0.010 |
| claude | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 146 | 0.010 | - | - | 0.010 |
| opencode | pi | pi | 1† | 1 | 100% | 1 | 1 | 198 | 0.010 | - | - | 0.010 |
| claude | pi | opencode | 1† | 1 | 100% | 1 | 1 | 219 | 0.010 | - | - | 0.010 |
| opencode | opencode | pi | 1† | 1 | 100% | 1 | 1 | 419 | 0.010 | - | - | 0.010 |
| claude | claude | pi | 1† | 1 | 100% | 1 | 1 | 117 | 0.011 | - | - | 0.011 |
| pi | claude | pi | 1† | 1 | 100% | 1 | 1 | 281 | 0.011 | - | - | 0.011 |
| pi | claude | opencode | 1† | 1 | 100% | 1 | 1 | 292 | 0.012 | - | - | 0.012 |
| opencode | claude | opencode | 1† | 1 | 100% | 1 | 1 | 288 | 0.012 | - | - | 0.012 |
| pi | pi | opencode | 1† | 1 | 100% | 1 | 1 | 438 | 0.013 | - | - | 0.013 |
| claude | pi | pi | 1† | 1 | 100% | 1 | 1 | 205 | 0.014 | - | - | 0.014 |
| opencode | opencode | opencode | 1† | 1 | 100% | 1 | 1 | 247 | 0.014 | - | - | 0.014 |
| claude | claude | opencode | 1† | 1 | 100% | 1 | 1 | 152 | 0.015 | - | - | 0.015 |
| pi | opencode | pi | 1† | 1 | 100% | 1 | 1 | 267 | 0.016 | - | - | 0.016 |
| pi | pi | pi | 1† | 1 | 100% | 1 | 1 | 939 | 0.145 | - | - | 0.145 |
| opencode | pi | claude | 1† | 1 | 100% | 0 | 1 | 753 | 0.198 | - | - | 0.198 |
| pi | opencode | claude | 1† | 1 | 100% | 1 | 1 | 174 | 0.332 | - | - | 0.332 |
| claude | pi | claude | 1† | 1 | 100% | 1 | 1 | 178 | 0.343 | - | - | 0.343 |
| pi | claude | claude | 1† | 1 | 100% | 1 | 1 | 168 | 0.354 | - | - | 0.354 |
| opencode | opencode | claude | 1† | 1 | 100% | 1 | 1 | 178 | 0.357 | - | - | 0.357 |
| pi | pi | claude | 1† | 1 | 100% | 1 | 1 | 358 | 0.367 | - | - | 0.367 |
| opencode | claude | claude | 1† | 1 | 100% | 0 | 1 | 367 | 0.390 | - | - | 0.390 |
| claude | opencode | claude | 1† | 1 | 100% | 1 | 1 | 114 | 0.437 | - | - | 0.437 |
| claude | claude | claude | 1† | 1 | 100% | 1 | 1 | 254 | 0.468 | - | - | 0.468 |

† n < 3: rank provisional.

## By axis

### orchestrator

| orchestrator | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 9 | 100% | 185 ± 59 | 0.146 ± 0.205 | - | - | 0.146 |
| opencode | 9 | 100% | 336 ± 174 | 0.112 ± 0.161 | - | - | 0.112 |
| pi | 9 | 100% | 368 ± 232 | 0.140 ± 0.164 | - | - | 0.140 |

### planner

| planner | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 9 | 100% | 245 ± 81 | 0.142 ± 0.198 | - | - | 0.142 |
| opencode | 9 | 100% | 246 ± 106 | 0.133 ± 0.184 | - | - | 0.133 |
| pi | 9 | 100% | 397 ± 272 | 0.123 ± 0.148 | - | - | 0.123 |

### executor

| executor | n | pass % | mean wall s | mean cost $ | total tokens | cache hit | cost per pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 9 | 100% | 283 ± 197 | 0.361 ± 0.076 | - | - | 0.361 |
| opencode | 9 | 100% | 273 ± 98 | 0.012 ± 0.002 | - | - | 0.012 |
| pi | 9 | 100% | 333 ± 242 | 0.026 ± 0.045 | - | - | 0.026 |

## Per phase

| orchestrator | planner | executor | phase | mean wall s | mean in | mean out | mean cache_read | mean cache_write | mean cost $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pi | pi | pi | orch | - | - | - | - | - | - |
| pi | pi | pi | plan | - | - | - | - | - | - |
| pi | pi | pi | exec | - | - | - | - | - | 0.145 |
| claude | pi | pi | orch | - | - | - | - | - | - |
| claude | pi | pi | plan | - | - | - | - | - | - |
| claude | pi | pi | exec | - | - | - | - | - | 0.014 |
| opencode | pi | pi | orch | - | - | - | - | - | - |
| opencode | pi | pi | plan | - | - | - | - | - | - |
| opencode | pi | pi | exec | - | - | - | - | - | 0.010 |
| claude | pi | claude | orch | - | - | - | - | - | - |
| claude | pi | claude | plan | - | - | - | - | - | - |
| claude | pi | claude | exec | - | - | - | - | - | 0.343 |
| pi | pi | opencode | orch | - | - | - | - | - | - |
| pi | pi | opencode | plan | - | - | - | - | - | - |
| pi | pi | opencode | exec | - | - | - | - | - | 0.013 |
| pi | claude | pi | orch | - | - | - | - | - | - |
| pi | claude | pi | plan | - | - | - | - | - | - |
| pi | claude | pi | exec | - | - | - | - | - | 0.011 |
| pi | opencode | opencode | orch | - | - | - | - | - | - |
| pi | opencode | opencode | plan | - | - | - | - | - | - |
| pi | opencode | opencode | exec | - | - | - | - | - | 0.009 |
| claude | pi | opencode | orch | - | - | - | - | - | - |
| claude | pi | opencode | plan | - | - | - | - | - | - |
| claude | pi | opencode | exec | - | - | - | - | - | 0.010 |
| claude | claude | claude | orch | - | - | - | - | - | - |
| claude | claude | claude | plan | - | - | - | - | - | - |
| claude | claude | claude | exec | - | - | - | - | - | 0.468 |
| claude | opencode | pi | orch | - | - | - | - | - | - |
| claude | opencode | pi | plan | - | - | - | - | - | - |
| claude | opencode | pi | exec | - | - | - | - | - | 0.008 |
| opencode | pi | claude | orch | - | - | - | - | - | - |
| opencode | pi | claude | plan | - | - | - | - | - | - |
| opencode | pi | claude | exec | - | - | - | - | - | 0.198 |
| opencode | claude | pi | orch | - | - | - | - | - | - |
| opencode | claude | pi | plan | - | - | - | - | - | - |
| opencode | claude | pi | exec | - | - | - | - | - | 0.008 |
| opencode | claude | claude | orch | - | - | - | - | - | - |
| opencode | claude | claude | plan | - | - | - | - | - | - |
| opencode | claude | claude | exec | - | - | - | - | - | 0.390 |
| opencode | pi | opencode | orch | - | - | - | - | - | - |
| opencode | pi | opencode | plan | - | - | - | - | - | - |
| opencode | pi | opencode | exec | - | - | - | - | - | 0.010 |
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
| pi | pi | claude | orch | - | - | - | - | - | - |
| pi | pi | claude | plan | - | - | - | - | - | - |
| pi | pi | claude | exec | - | - | - | - | - | 0.367 |

## Totals

- pass: 27
- fail: 0
- other (skipped/infra_error/timeout): 0
- total: 27
- rules_ok: 25
- plan_ok: 27
