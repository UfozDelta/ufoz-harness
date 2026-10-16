# Plan: plan-check-gap
## Goal
The large fixture scores ~half because the plan is written from the spec alone: the planner never sees the
behaviour the hidden tests assert. Derive a readable `contract.md` from the hidden tests and feed it to the
planner. Never expose test source.

## Decisions
- `.harness/bench/bench.py` gains `CONTRACT_FILENAME = "contract.md"`, `hidden_contract(task) -> str`
  (reads `<task>/hidden_tests/*.py` with `ast`, returns the markdown text, `""` when the dir is missing),
  `ensure_contract(task) -> Path | None` (overwrites `<task>/contract.md`, `None` when the text is empty) and
  `spec_with_contract(task) -> str` (spec.md text + the contract text; contract first-class).
- Contract markdown, exactly these sections in this order, header line `# Acceptance contract`:
  `## Endpoints`, `## Status codes`, `## Query params`, `## Edge cases`. Endpoint bullets
  `- \`<METHOD> <path>\``; a purely numeric path segment is normalised to `{id}`; paths sorted, methods in
  HTTP order then alphabetical. Status-code bullets list the integers a test compares against
  `r.status_code` for that method+path. Query-param bullets name `params={...}` keys. Edge-case bullets are
  one per test, `test_foo_bar` -> `foo bar`. No source lines, no imports, no `client.` text, no assertions.
- `_local_contract(plan_dir, spec_path)` in `.harness/runner/planner.py` returns the copied path in the plan
  dir or `None`; `run_planner` adds one extra line to PLAN_REQUEST.md only when it exists:
  `Acceptance contract: <path>` + `Read it too; it is binding.`
- `contract_fingerprint(task) -> str` (new): `hashlib.sha1(hidden_contract(task).encode()).hexdigest()`, or the
  literal `"-"` when the contract text is empty.
- Wiring: `opus_plan` (incl. its cache key) and `run_planner_arm` build their prompt from
  `spec_with_contract(task)`; both call `ensure_contract(task)` before reading the spec. `opus_plan`'s cache dir
  additionally embeds `contract_fingerprint(task)`, so a changed contract can never reuse a stale plan.
  `muse_plan`, `run_arm`, `make_worktree`, `score` unchanged.
- `.gitignore` gains `.harness/bench/tasks/*/contract.md` (derived file, never tracked).
- Verified: bench imports with `sys.path.insert(0,'.harness/bench')`, `hidden_tests/test_hidden.py` uses
  `client.<verb>` + `params=` only, tests pass (`python -m pytest tests/test_staged.py -q` -> 6 passed).
  Unverified: exact markdown a first-cut `ast` walk yields. Later: `muse_plan` (S3) still spec-only.
## interfaces
Preserve: `plan_dir`, `make_worktree`, `score`, `plan_complete`, `run_planner_arm`, `opus_plan`, `muse_plan`
signatures; `run_planner(slug, spec_path, plans_root, backend, model)`.
New (public, importable): `hidden_contract`, `ensure_contract`, `spec_with_contract`, `contract_fingerprint`, `CONTRACT_FILENAME`.

## T1 extract acceptance contract
FILES: .harness/bench/bench.py, .gitignore
MUST:
- `hidden_contract` parses with `ast` only (no regex on source, no network), reads every `.py` in
  `<task>/hidden_tests/`, returns `""` for a missing dir and never raises on a bad file (skip it).
- Output is byte-identical for the same input (sorted everywhere, `\n` endings).
- Neither test source lines nor imports appear; only the section/format fixed in Decisions.
- `ensure_contract` writes UTF-8 `<task>/contract.md` with `newline="\n"`, returns the Path, `None` when empty.
- `contract_fingerprint(task)` returns the sha1 hex of the contract text, `"-"` when empty.
- Append `.harness/bench/tasks/*/contract.md` to `.gitignore`.
TEST: python -c "import sys;sys.path.insert(0,'.harness/bench');import bench;assert bench.CONTRACT_FILENAME=='contract.md';t=bench.hidden_contract('large');assert t.startswith('# Acceptance contract');assert all(s in t for s in ('## Endpoints','## Status codes','## Query params','## Edge cases','PUT /items/{id}','DELETE /items/{id}','GET /health','min_price','name_contains','204','422'));assert 'client.' not in t and 'import pytest' not in t and t==bench.hidden_contract('large');assert bench.hidden_contract('nope')=='' and bench.ensure_contract('nope') is None;assert bench.contract_fingerprint('large')!='-' and bench.contract_fingerprint('large')==bench.contract_fingerprint('large') and bench.contract_fingerprint('nope')=='-';assert '.harness/bench/tasks/*/contract.md' in open('.gitignore',encoding='utf-8').read();print('T1 ok')"

## T2 planner reads contract
FILES: .harness/runner/planner.py
MUST:
- `_local_contract(plan_dir, spec_path)` copies `<spec_dir>/contract.md` to `plan_dir/contract.md`
  (create the dir), returns it; returns `None` when absent, and swallows OSError like `_local_spec` does.
- `run_planner` calls it after `_local_spec` and adds `Acceptance contract: <posix path>` +
  `Read it too; it is binding.` to PLAN_REQUEST.md only when a contract was copied; otherwise the request is
  byte-identical to today's.
- `local_spec` still points at `spec.md`; nothing else in the request body changes.
TEST: python -c "import sys,tempfile,pathlib;sys.path.insert(0,'.harness');from runner import planner;d=pathlib.Path(tempfile.mkdtemp());(d/'spec.md').write_text('s',encoding='utf-8');pd=d/'plan'/'x';pd.mkdir(parents=True);assert planner._local_contract(pd,d/'spec.md') is None;(d/'contract.md').write_text('c',encoding='utf-8');c=planner._local_contract(pd,d/'spec.md');assert c.name=='contract.md' and c.read_text(encoding='utf-8')=='c' and pd.joinpath('spec.md').exists();print('T2 ok')"

## T3 wire contract into bench planner
FILES: .harness/bench/bench.py
MUST:
- `spec_with_contract(task)` = `ensure_contract(task)` result then the spec text; returns the plain spec text
  when no contract exists (identical bytes to today's prompt).
- `opus_plan` (incl. its cache-hit path) and `run_planner_arm` build the prompt from it; `opus_plan`'s cache
  dir embeds `contract_fingerprint(task)`; no other prompt or score() call changes.
- `muse_plan`, `run_arm`, `make_worktree`, `score` untouched.
TEST: python -c "import sys;sys.path.insert(0,'.harness/bench');import bench;assert bench.ensure_contract('large').name=='contract.md';s=bench.spec_with_contract('large');assert s.count('# Acceptance contract')==1;src=open('.harness/bench/bench.py',encoding='utf-8').read();assert src.count('spec_with_contract(task)')==3;assert 'contract_fingerprint(task)' in src;print('T3 ok')"

## T4 write summary
FILES: .harness/plans/plan-check-gap/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run the build if any and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/plan-check-gap/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"