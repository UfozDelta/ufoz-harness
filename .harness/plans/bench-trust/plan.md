# Plan: bench-trust
## Goal
Trustworthy, cheap-to-read suite results: versioned rows, one store, harness_fail class, right labels, flake gate. Do not touch .harness/runner.

## Decisions
- New COLUMNS (suite.py AND report.py, identical): existing list + `"run_id", "fixture_hash"` APPENDED at the end. CSV_FIELDS = ["slug"] + COLUMNS (unchanged form).
- cells.py: `_harness_sha(repo_root)` -> `git rev-parse --short HEAD`; if `git diff HEAD` output non-blank: `f"{sha}+{sha256(diff bytes).hexdigest()[:6]}"`; else bare sha. No `-dirty`.
- cells.py: `_fixture_hash(size, repo_root=REPO_ROOT) -> str`: sha256 over sorted (posix relpath + file bytes) of `bench/suite/fixtures/<size>`, skipping `__pycache__`, `.pytest_cache`, `node_modules`; first 8 hex; `""` if dir missing. `_blank(cell)` sets `row["fixture_hash"]=_fixture_hash(cell["size"])`.
- cells.py: `_apply_window_verdict(row)`: if `row["mode"]=="window"` and `row["status"]=="pass"` and (`str(row["window_opened"]).lower() == "false"` or `str(row["watch_ok"]).lower() == "false"`; cells.py stores these as the strings "true"/"false", "" when unset) -> `row["status"]="harness_fail"`. Called in `_run_single` right after watch_ok is set. Other statuses untouched.
- suite.py: `_ResultWriter(csv_path, run_id=None)`; `run_id` default `time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())` taken once at init; `write()` stamps `row["run_id"]` on a copy. If file exists with a header != CSV_FIELDS, `write()` first rewrites the file with the new header (old rows kept, new cols empty).
- report.py: `EXCLUDED_STATUSES={"infra_error","harness_fail"}`; `load_rows` unchanged shape (COLUMNS keys only, no slug). New `latest_per_cell(rows)`: keep last row in file order per (size,mode,executor,rep). New `newest_sha_rows(rows)`: sha = harness_sha of the last row with a non-empty one; keep rows with that sha; no sha anywhere -> return all. `build_report(rows, all_shas=False)`: dedupe, then filter unless all_shas; the delta section gets deduped but unfiltered rows. Header line shows counts of infra_error and harness_fail separately. `main` gets `--all-shas`.
- report.py labels: no "Sonnet" text. Cost notes for executor `claude` use the sorted distinct `model` values of its rows: `f"{models} (paid tier) - reported separately"`; footer line "Excluding `claude`: $X".
- bench/speed/report.py: header gets a leading `Harness` column so it matches data rows.
- check_fixtures.py: `--repeat N` (int, default 5, min 1). `runs_agree(results: list[dict[str,int]]) -> bool`: True iff every run has the same {label: code==0} map as the first. `check_size(size, repeat=5)`: after GREEN, rerun `run_all` repeat-1 times on the solution; any disagreement prints `FAIL: <size> flaky ...` and returns False (exit 1 via existing path).
- Archiving the old results CSVs is done by the main session, not a task (they are gitignored).

Verified: suite.COLUMNS==report.COLUMNS is asserted by tests (`pytest tests/test_harness_suite.py -k columns_lists_agree`). speed/report.py header lacks the harness label while rows prepend it (read file).
Unverified: cmd.exe quoting of acceptance one-liners; git diff HEAD cost on large trees.
Later: backfill run_id/fixture_hash on old rows; hash untracked files into harness_sha.

## interfaces
Preserve: `suite.build_matrix`, `load_existing_slugs/rows`, `report.load_rows`, `report.build_report(rows)` callable with 1 arg, `cells._harness_sha` monkeypatchable by tests.

## T1 cells versioning
FILES: bench/suite/cells.py
MUST: implement `_harness_sha`, `_fixture_hash`, `_apply_window_verdict` per Decisions; `_blank` sets fixture_hash; `_run_single` calls the verdict helper after watch_ok. Never raise when git/fixture missing (return "" / bare).
TEST: python -c "import sys; sys.path.insert(0,'bench/suite'); import cells; from pathlib import Path; h=cells._fixture_hash('small'); assert len(h)==8 and cells._fixture_hash('nope')==''; assert '-dirty' not in cells._harness_sha(Path('.')); r={'mode':'window','status':'pass','window_opened':'true','watch_ok':'false'}; cells._apply_window_verdict(r); assert r['status']=='harness_fail'; r={'mode':'window','status':'pass','window_opened':'true','watch_ok':'true'}; cells._apply_window_verdict(r); assert r['status']=='pass'; r={'mode':'serial','status':'fail','window_opened':False,'watch_ok':False}; cells._apply_window_verdict(r); assert r['status']=='fail'"

## T2 suite columns writer
FILES: bench/suite/suite.py
MUST: COLUMNS gets run_id, fixture_hash appended; `_ResultWriter` stamps run_id once per process and migrates an old-header file; import time if needed.
TEST: python -c "import sys,tempfile,csv; sys.path.insert(0,'bench/suite'); import suite; from pathlib import Path; assert suite.COLUMNS[-2:]==['run_id','fixture_hash']; p=Path(tempfile.mkdtemp())/'r.csv'; p.write_text('slug,ts\na,1\n'); w=suite._ResultWriter(p); w.write({'slug':'b','ts':'2'}); rows=list(csv.DictReader(open(p))); assert list(rows[0])==suite.CSV_FIELDS and rows[0]['slug']=='a' and rows[1]['run_id']==w.run_id"

## T3 suite report
FILES: bench/suite/report.py
MUST: COLUMNS match T2; add `latest_per_cell`, `newest_sha_rows`, `--all-shas`, harness_fail exclusion + count, model-based labels per Decisions; stays safe on empty input.
TEST: python -c "import sys; sys.path.insert(0,'bench/suite'); import report as r; b=dict(size='s',mode='serial',executor='claude',rep='1',wall_s='1',cost='1',model='claude-x'); rows=[dict(b,status='fail',harness_sha='A'),dict(b,status='pass',harness_sha='A'),dict(b,rep='2',status='harness_fail',harness_sha='B'),dict(b,rep='3',status='pass',harness_sha='B')]; assert len(r.latest_per_cell(rows))==3; assert {x['harness_sha'] for x in r.newest_sha_rows(r.latest_per_cell(rows))}=={'B'}; t=r.build_report(rows); assert 'Sonnet' not in t and 'claude-x' in t and 'harness_fail' in t; assert r.COLUMNS[-2:]==['run_id','fixture_hash']"

## T4 speed header
FILES: bench/speed/report.py
MUST: header row and separator gain a leading Harness column; data rows unchanged.
TEST: python -c "import sys; sys.path.insert(0,'bench/speed'); import report as r; t=r.build_report([dict(task='t',harness='pi',model='m',tests_passed='1',tests_total='1',wall_s='1')]); assert any(l.startswith('| Harness | Runs |') for l in t.splitlines()), t"

## T5 flake gate
FILES: bench/suite/check_fixtures.py
MUST: `--repeat N` default 5 per Decisions; `runs_agree`; repeat<1 clamps to 1; seed RED and first GREEN logic unchanged.
TEST: python -c "import sys,subprocess; sys.path.insert(0,'bench/suite'); import check_fixtures as c; assert c.runs_agree([{'a':0},{'a':0}]) and not c.runs_agree([{'a':0},{'a':1}]); o=subprocess.run([sys.executable,'bench/suite/check_fixtures.py','--help'],capture_output=True,text=True).stdout; assert '--repeat' in o"

## T7 tests
FILES: tests/test_harness_suite.py
MUST: append tests `test_writer_migrates_old_header`, `test_latest_per_cell_and_newest_sha`, `test_harness_fail_excluded_from_rates`, `test_apply_window_verdict`, `test_runs_agree`; follow file style; keep existing tests untouched.
TEST: python -m pytest -q tests/test_harness_suite.py -k "writer_migrates or latest_per_cell or harness_fail_excluded or apply_window_verdict or runs_agree"

## T8 write summary
FILES: .harness/plans/bench-trust/SUMMARY.md
MUST: write <= 600 chars covering what was made, which files, and how it was wired; run `python -m pytest -q tests/test_harness_suite.py` and add a line `BUILD: pass` or `BUILD: fail <first error line>` to SUMMARY.md. The build result never fails the task.
TEST: python -c "from pathlib import Path; p=Path('.harness/plans/bench-trust/SUMMARY.md'); assert p.exists() and len(p.read_text(encoding='utf-8')) <= 600"
