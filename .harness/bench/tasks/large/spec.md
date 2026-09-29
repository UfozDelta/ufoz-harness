# Spec (items API — router split, PUT/DELETE, filters)

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

