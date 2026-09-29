# Plan: bench-plan (items API — router split, PUT/DELETE, filters)

## Goal
Refactor the existing in-memory items API into a router module, then add `PUT /items/{item_id}`,
`DELETE /items/{item_id}`, and optional query-param filtering on `GET /items`
(`min_price`, `max_price`, `name_contains`), with tests covering all of it.

## Starting point (already exists — do not re-create)
`app/__init__.py`, `app/models.py` (`ItemCreate`: `name` min_length=1, `price` ge=0; `Item(ItemCreate)` adds `id: int`),
`app/main.py` (FastAPI app, module-level `_items`/`_next_id`, `reset_store()`, `GET /health`, `GET /items`,
`GET /items/{item_id}` 404, `POST /items` 201/422), `tests/test_items.py`.

## Assumptions / Decisions (fixed — the executor must not re-decide)
- New module `app/store.py` owns state. Reason: `app/routers/items.py` cannot mutate `app/main.py`
  globals without a circular import. Public names in `app/store.py`: `items: list[Item]`,
  `reset_store() -> None`, `next_id() -> int`. The old private `_items` / `_next_id` in `app/main.py` go away;
  `_next_id` lives on as a private module global inside `app/store.py`.
- `app/main.py` keeps `app = FastAPI()` and `GET /health`, does `app.include_router(items_router)`,
  and re-exports `reset_store` via `from app.store import reset_store` so `from app.main import app, reset_store`
  keeps working (existing tests depend on it).
- Router: `app/routers/items.py` defines `router = APIRouter()`. No prefix, no tags. Paths stay `"/items"` and
  `"/items/{item_id}"`. `app/routers/__init__.py` is empty.
- `PUT /items/{item_id}`: body `ItemCreate`, full replace, keeps the same `id` and the same list position,
  returns the updated `Item` with status 200; 404 `{"detail": "Item not found"}` when missing; 422 on a bad body.
- `DELETE /items/{item_id}`: `status_code=204`, returns `None` (empty body); 404 when missing.
- `GET /items` filters, all optional and combinable with AND:
  - `min_price: float | None = Query(default=None, ge=0)` — keep `price >= min_price`
  - `max_price: float | None = Query(default=None, ge=0)` — keep `price <= max_price`
  - `name_contains: str | None = None` — keep items where `name_contains.lower() in item.name.lower()`
  - No matches -> `[]`. Non-numeric or negative price params -> FastAPI's default 422.
  - `min_price > max_price` is NOT an error: it returns `[]`. `name_contains=""` matches everything.
- Item ids are never reused after a DELETE (`next_id()` only counts up; `reset_store()` sets it back to 1).
- No auth, no persistence, no pagination, no PATCH, no other endpoints, no new dependencies.
- Installed: fastapi 0.115.0, uvicorn 0.32.0, pytest 9.1.1, pydantic 2.13.4, httpx 0.28.1.
- Each task writes its own pytest file under `tests/` (listed in its FILES) covering its MUSTs, including
  error cases. `tests/test_items.py` must keep passing. Acceptance commands run from the project root.

## T1 store module
FILES: app/store.py, tests/test_store.py
MUST:
- `app/store.py` has exactly `items: list[Item] = []`, private `_next_id = 1`, `reset_store()` (clears `items` in place, `_next_id = 1`), `next_id()` (returns current, then increments). Nothing else; do not touch `app/main.py` yet.
- Tests: next_id sequence 1,2,3; reset restarts at 1; reset keeps the same list object.
TEST: `python -m pytest -q tests/test_store.py`

## T2 router split + mount
FILES: app/routers/__init__.py, app/routers/items.py, app/main.py, tests/test_router_split.py
MUST:
- Move `GET /items`, `GET /items/{item_id}`, `POST /items` unchanged into `app/routers/items.py` (`router = APIRouter()`, no prefix) using `app.store`.
- `app/main.py`: keeps `app` + `GET /health`, `include_router`, `from app.store import reset_store`; old `_items`/`_next_id` gone.
- Tests: `from app.main import app, reset_store` works; routes behave as before (201, 404, 422); `app.main` has no `_items`.
TEST: `python -m pytest -q tests/test_items.py tests/test_router_split.py`

## T3 PUT + DELETE
FILES: app/routers/items.py, tests/test_put_delete.py
MUST:
- PUT: per Decisions; replace in place (same id, same list position); failed PUT mutates nothing.
- DELETE: 204 empty body; 404 when missing; ids never reused afterwards.
- Tests cover every bullet above plus 422 bodies.
TEST: `python -m pytest -q tests/test_items.py tests/test_put_delete.py`

## T4 GET /items filters
FILES: app/routers/items.py, tests/test_filters.py
MUST:
- `min_price`, `max_price`, `name_contains` per Decisions, AND-combined; min>max -> `[]`; `name_contains=""` matches all; negative/non-numeric -> 422.
- Tests cover each filter alone, combined, boundaries (inclusive), case-insensitivity, and the 422s.
TEST: `python -m pytest -q tests/test_items.py tests/test_filters.py`
