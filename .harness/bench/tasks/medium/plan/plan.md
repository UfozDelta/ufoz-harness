# Plan: fastapi-items

## Goal
A small FastAPI server exposing an in-memory "items" resource (GET /health, GET /items,
GET /items/{item_id}, POST /items) plus a pytest suite, in `app/` and `tests/`.

## Assumptions / Decisions (fixed — the executor must not re-decide)
- Files: `app/__init__.py` (empty), `app/models.py`, `app/main.py`, `tests/test_items.py`.
  No `tests/__init__.py` (acceptance uses `python -m pytest`, which puts the project root on `sys.path`).
- `main.py` at project root is untouched.
- Item fields: `id: int` (server-assigned, starts at 1, increments by 1), `name: str` (non-empty),
  `price: float` (>= 0).
- Models (pydantic v2): `ItemCreate(BaseModel)` with `name: str = Field(min_length=1)` and
  `price: float = Field(ge=0)`; `Item(ItemCreate)` adding `id: int`.
- Storage: module-level `_items: list[Item] = []` and `_next_id: int = 1` in `app/main.py`,
  plus a public `reset_store() -> None` that clears `_items` and sets `_next_id = 1`
  (uses `_items.clear()` and `global _next_id`, so tests never rebind module attributes).
- Endpoints:
  - `GET /health` -> `{"status": "ok"}`
  - `GET /items` -> `list[Item]` (empty list when store is empty)
  - `GET /items/{item_id}` -> `Item`, or `HTTPException(status_code=404, detail="Item not found")`
  - `POST /items` -> `status_code=201`, body `ItemCreate`, returns the created `Item`;
    invalid body yields FastAPI's default 422.
- No auth, no persistence, no CORS, no PUT/DELETE, no extra endpoints, no new dependencies.
- Installed: fastapi 0.115.0, uvicorn 0.32.0, pytest 9.1.1, pydantic 2.13.4.
  `httpx` must be installed by the main session before execution (needed by `TestClient`).
- Tests use `fastapi.testclient.TestClient` and an `autouse` fixture calling `reset_store()`
  so every test starts from an empty store.
- All acceptance commands run from the project root with `python`.

## Tasks (phase 1 — all of the work)
| id | title | deps | files |
|----|-------|------|-------|
| T1 | Pydantic models + app package | - | app/__init__.py, app/models.py |
| T2 | FastAPI app: store, /health, GET /items, GET /items/{id} | T1 | app/main.py |
| T3 | POST /items (201 + validation) | T2 | app/main.py |
| T4 | pytest suite with store-reset fixture | T3 | tests/test_items.py |

## Later phases
None. After T4 the feature is complete; optional follow-ups (run with uvicorn, pin deps in a
requirements file) are out of scope and were not requested.
