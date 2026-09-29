# Plan: bench-small

## Goal
A one-file FastAPI app with a single `GET /health` endpoint, plus a pytest test for it.

## Assumptions / Decisions
- File: `app/main.py` only (create `app/__init__.py` empty). Test: `tests/test_health.py`.
- `GET /health` returns `{"status": "ok"}`.
- No other endpoints, no models file needed.

## Tasks
| id | title | deps | files |
|----|-------|------|-------|
| T1 | app + /health endpoint | - | app/__init__.py, app/main.py |
| T2 | pytest for /health | T1 | tests/test_health.py |
