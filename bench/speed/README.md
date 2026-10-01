# Harness speed test

Runs identical Python tasks through opencode and pi and compares pass rate, wall
time, and usage. Each run is clean, outside this repository, and seeded equally.
Layout: during a run, `r<rep>/work/` contains only the seed; `r<rep>/` contains
opencode/pi logs, stderr, pytest output, and the opencode XDG config directory.
Hidden tests are copied into `work/_hidden_tests/` only after the harness exits.
Fairness: both use `opencode/space-bunny-free` and `medium` thinking by default,
alternate order, and receive identical prompts with closed stdin. OpenCode uses
`--pure` and an empty config home; pi disables sessions and context extensions.

## Run

```sh
python bench/speed/duel.py
python bench/speed/duel.py --tasks small,medium --reps 3
python bench/speed/duel.py --dry
```

Override defaults with `--model`, `--thinking`, `--timeout`, `--out`, `--pi`, and
`--csv`; use `--harness opencode` or `--harness pi` to select one. Use `--pi-ext PATH`
to load a pi extension for benchmark runs.
## Report

Each run prints task, harness, repetition, wall time, and passed/total tests.
Share the appended `bench/speed/results.csv` when reporting. Event logs,
stderr, and pytest output remain under the run directory.
