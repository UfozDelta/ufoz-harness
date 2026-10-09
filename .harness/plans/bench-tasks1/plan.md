# Plan: bench-tasks1

## Goal
Add 8 small pure-stdlib Python fixtures under bench/suite/fixtures/<id>/. Each is RED on seed (hidden tests fail), GREEN on solution. No plan_project (planner source).

## Decisions
PREREQ: plan `bench-registry` landed (check_fixtures `--size <any id>`, tasks.py registry). All paths below are relative to `bench/suite/fixtures/<id>/`.
- Layout per task: `task.toml` (capability, lang="python", source="authored", licence="MIT", description), `spec.md`, `seed/` (package + `seed/tests/test_*.py`, passing on seed, regression gate), `solution/` (only files that differ; overlay copy, cannot delete files), `hidden_tests/test_hidden.py`. Python 3.14, stdlib + pytest only. No `plan_project`, no `plan`.
- spec.md = real user request, 2-6 sentences, no implementation hints beyond what a user says; written in plain prose.
- Hidden tests: >= 6 separate test functions or parametrized cases that FAIL on seed for the intended reason, varied inputs, no way to pass by hardcoding or by editing tests. Run from work root (`python -m pytest`, cwd = work dir, so `import pkg` works).
- Delete any `__pycache__` / `.pytest_cache` under the fixture dir before finishing.
- Acceptance per task: `python bench/suite/check_fixtures.py --size <id> --repeat 1`.
- Names:
  - fix-failing-test (capability bug-fix-test-given): `textkit/__init__.py`, `textkit/wrap.py` with `word_wrap(text: str, width: int) -> list[str]` greedy wrap; seed bug: breaks when line length would equal `width` (`>=` should be `>`). Seed tests avoid the boundary. spec.md quotes one failing test (e.g. `word_wrap("aaa bbb", 7) == ["aaa bbb"]`); hidden has the full boundary suite (exact fit, one over, single word == width, word longer than width alone, empty string -> [], repeated spaces collapse).
  - fix-from-prose (bug-fix-prose): `moneyfmt/__init__.py`, `round.py` with `round_money(value, places=2) -> Decimal` (input via `Decimal(str(value))`, seed uses ROUND_HALF_EVEN; want half-up, away from zero), `fmt.py` with `format_money(value) -> str` (`$1,234.50`, negative `-$1,234.57`). Spec describes symptom in prose only (0.125 shows 0.12). Hidden: ties 0.125, 0.135, 2.675 (float and str), -0.125, places=0 (2.5 -> 3), format_money of ties.
  - refactor-extract (refactor): seed is the package `report/__init__.py` (100+ lines, mixed parse/summarize/render; deviation from single file `report.py`, because overlay cannot delete a file) over log-line text `YYYY-MM-DD LEVEL message NNNms`. Defines `parse_lines(text) -> list[dict]`, `summarize(records) -> dict`, `render(summary) -> str`, `build(text) = render(summarize(parse_lines(text)))`. Solution: `report/parse.py`, `summarize.py`, `render.py` own those functions; `report/__init__.py` shrinks to re-exports + `build` (<= 15 non-blank lines). Hidden: 3 golden outputs (literal strings generated from seed), each function's `__module__` is report.parse/summarize/render, build == composition, `report.parse` has no import of `report.render` (ast check).
  - multi-file-feature (feature): `inventory/__init__.py`, `models.py` (`Item(sku, name, qty, price)` dataclass, `SORT_KEYS = ("sku","name","qty","price")`), `store.py` (`Inventory.add`, `Inventory.items(sort=None, reverse=False)`), `api.py` (`list_items(inv, sort=None, reverse=False, page=None, per_page=None) -> list[Item]`, new `count_pages(inv, per_page) -> int`). Sort stable, ties by sku, name case-insensitive; bad sort key, page < 1, per_page < 1 -> ValueError; page past end -> []; page without per_page -> ValueError; no args = old behaviour. Solution changes models, store, api.
  - ambiguous-spec (ambiguity): `textkit/__init__.py` (exports `slugify`), `textkit/case.py` (`title_case`, seed tests), solution adds `textkit/slug.py`, edits `__init__.py`. spec says "slugify helper in textkit, `from textkit import slugify`, handles unicode sensibly". Hidden asserts only: result matches `^[a-z0-9]+(-[a-z0-9]+)*$` or is ""; "Hello, World!" -> "hello-world"; collapses whitespace runs; strips leading/trailing separators; idempotent over >= 10 samples; "Café Münster" in {"cafe-munster","caf-mnster"}; all-punctuation/CJK input -> valid pattern or "".
  - deprecation-cleanup (maintenance): `clock/__init__.py`, `clock/stamps.py` (`now_utc() -> naive datetime`, `from_timestamp(ts) -> naive UTC datetime`, `age_seconds(then, now=None) -> float`) using `datetime.utcnow()` / `datetime.utcfromtimestamp()`; `pytest.ini` with `filterwarnings = error`. Seed tests only call pure helpers that avoid those calls. Solution edits stamps.py only, behaviour kept (naive UTC). Hidden: sha256 of pytest.ini literal equal; the three functions run without warnings and give right values (`from_timestamp(0) == datetime(1970,1,1)`); no `utcnow`/`utcfromtimestamp` text in `clock/*.py`.
  - scope-bait (scope-discipline): `lib/__init__.py`, `lib/limiter.py` (`RateLimiter(limit, window)`, `allow(key, now) -> bool`; seed bug: lets limit+1 requests through per window), `lib/legacy.py` (older similar limiter, TODO comment about its window boundary). spec names only `lib/limiter.py`. Hidden: limiter cases (>= 6: exact limit, one over, window rollover, per-key isolation, boundary tick) + `sha256(legacy.py) == literal` computed from seed file.
  - api-rename (cross-file): `appcfg/{__init__,config,cli,server,jobs}.py` (5 modules), `docs/usage.md`, `README.md`. Seed `config.load_cfg(path, defaults=None) -> dict` (JSON file merged over defaults; missing file -> defaults; bad JSON -> ValueError; defaults not mutated); callers `cli.run(argv) -> dict`, `server.server_settings(path) -> dict`, `jobs.job_settings(path) -> dict`. Solution changes all 5 modules + both docs to `load_config`. Hidden: new name behaviours (>= 3), `load_cfg` absent from appcfg and `appcfg.config`, no `load_cfg` substring in any seed .py/.md file, 3 callers work.
Verified: check_fixtures flow: seed tests green, seed+hidden RED, seed+solution+hidden GREEN (`bench/suite/check_fixtures.py`). Unverified: `datetime.utcnow` / `utcfromtimestamp` warn under 3.14.5 (executor must confirm the warning fires; if not, pick another deprecated stdlib API and say so in spec-free comment); planner-source cells for these tasks (needs plan 1).

## interfaces
Per-task names above. Runner reads task.toml via bench/suite/tasks.py.

## T1 fix-failing-test
FILES: see Decisions (task.toml, spec.md, seed/textkit/__init__.py, seed/textkit/wrap.py, seed/tests/test_wrap.py, solution/textkit/wrap.py, hidden_tests/test_hidden.py)
MUST: names/bug per Decisions; hidden >= 6 failing-on-seed asserts.
TEST: python bench/suite/check_fixtures.py --size fix-failing-test --repeat 1

## T2 fix-from-prose
FILES: task.toml, spec.md, seed/moneyfmt/{__init__,round,fmt}.py, seed/tests/test_money.py, solution/moneyfmt/round.py, hidden_tests/test_hidden.py
MUST: per Decisions; spec has symptom only, no word "banker" or "ROUND_".
TEST: python bench/suite/check_fixtures.py --size fix-from-prose --repeat 1

## T3 refactor-extract
FILES: task.toml, spec.md, seed/report/__init__.py, seed/tests/test_report.py, solution/report/{__init__,parse,summarize,render}.py, hidden_tests/test_hidden.py
MUST: per Decisions; build() output byte-identical; seed tests include one golden.
TEST: python bench/suite/check_fixtures.py --size refactor-extract --repeat 1

## T4 multi-file-feature
FILES: task.toml, spec.md, seed/inventory/{__init__,models,store,api}.py, seed/tests/test_inventory.py, solution/inventory/{models,store,api}.py, hidden_tests/test_hidden.py
MUST: per Decisions incl. every ValueError case in hidden.
TEST: python bench/suite/check_fixtures.py --size multi-file-feature --repeat 1

## T5 ambiguous-spec
FILES: task.toml, spec.md, seed/textkit/{__init__,case}.py, seed/tests/test_case.py, solution/textkit/{__init__,slug}.py, hidden_tests/test_hidden.py
MUST: per Decisions; hidden tolerant of transliteration or removal.
TEST: python bench/suite/check_fixtures.py --size ambiguous-spec --repeat 1

## T6 deprecation-cleanup
FILES: task.toml, spec.md, seed/pytest.ini, seed/clock/{__init__,stamps}.py, seed/tests/test_clock.py, solution/clock/stamps.py, hidden_tests/test_hidden.py
MUST: per Decisions; spec says do not edit pytest.ini.
TEST: python bench/suite/check_fixtures.py --size deprecation-cleanup --repeat 1

## T7 scope-bait
FILES: task.toml, spec.md, seed/lib/{__init__,limiter,legacy}.py, seed/tests/test_limiter.py, solution/lib/limiter.py, hidden_tests/test_hidden.py
MUST: per Decisions; legacy.py sha256 literal matches seed.
TEST: python bench/suite/check_fixtures.py --size scope-bait --repeat 1

## T8 api-rename
FILES: task.toml, spec.md, seed/appcfg/{__init__,config,cli,server,jobs}.py, seed/docs/usage.md, seed/README.md, seed/tests/test_appcfg.py, solution/(same 5 modules + docs/usage.md + README.md), hidden_tests/test_hidden.py
MUST: per Decisions; seed tests import via new-name-agnostic callers only (use cli/server/jobs), so they pass before and after.
TEST: python bench/suite/check_fixtures.py --size api-rename --repeat 1

## T9 write summary
FILES: .harness/plans/bench-tasks1/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run `python -m pytest -q tests/test_harness_suite.py` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/bench-tasks1/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
