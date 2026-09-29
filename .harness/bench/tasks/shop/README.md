# Shop bench task

6-stage dropshipping shop. `spec.md` is the shared spec; `stages/s1.md` .. `s6.md` are the specs
builders see, one stage at a time (never the tests). Starting point: `SEED.md` points at the crm
seed (`../crm/seed`) — reuse it, don't copy it.

## Scoring a stage
`hidden_tests/conftest.py` has no `--rootdir`/path logic of its own: like the crm task, it builds
and starts `next start` using the current working directory as the app root (`npm run build` /
`npx next start` run with `cwd` = wherever pytest is invoked from). So to score, copy
`hidden_tests/conftest.py` plus the `test_sN.py` files you want into the ROOT of the built app
(next to its `package.json`), then run pytest from there:

```
cp .harness/bench/tasks/shop/hidden_tests/conftest.py <built-app>/conftest.py
cp .harness/bench/tasks/shop/hidden_tests/test_s1.py ... test_sN.py <built-app>/
cd <built-app>
python -m pytest -q conftest.py test_s1.py test_s2.py ... test_sN.py
```

Run stages 1..N together (not just test_sN.py alone) so earlier-stage contracts are re-checked for
regressions introduced by stage N's changes. All test files share one `next build` + `next start`
per session (`base` fixture is session-scoped) and one `SHOP_DB_PATH` temp DB, so tests must not
assume an empty DB — they use unique data (uuid emails) and compute expected deltas rather than
absolute totals.
