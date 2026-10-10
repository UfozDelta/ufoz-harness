# land-drop-yes

Removed the `--land` terminal gate and the meaning of `--yes`; the main session lands itself.
`runner/cli.py`: deleted the `args.land and not args.yes and not interactive()` gate and the
`interactive()` helper, `--yes` is now a hidden no-op (`help=argparse.SUPPRESS`), `--land` help
rewritten. `run_plan.py` docstring, `tests/test_git_guard.py`, `.harness/HARNESS.md`, both READMEs,
`kit_readme.md`, `docs/bench-flow.svg` and `bench/suite/cells.py` follow. Agents stay blocked by
`git_guard.py` + `.pi/deny.json`, untouched.

BUILD: pass
