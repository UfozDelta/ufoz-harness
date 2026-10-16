# bench-rigor summary

Comparisons now carry rep counts and confidence/spread bands; differences inside the band are labeled noise, not a win.

- suite grid: `reps` column with `low-reps` below `MIN_REPS=3`; new `rep_count`.
- delta: last two shas compared by Wilson CIs; overlap prints `pass-rate delta within noise (CIs overlap ...)`.
- speedup: `(noise)` when the seeded-bootstrap 95% CI of the serial/parallel wall ratio contains 1.0; `<2` reps stays `-`.
- speed report: `spread` + `wall_s min-max` column; `Low-rep` notes under 3 runs.
- 4 `test_rigor_*` specs added; 51 pass.
