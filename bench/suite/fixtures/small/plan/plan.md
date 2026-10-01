# Plan: suite-small (items API — GET /items filters + pagination, /tags router)

Work dir: `{work}` - every path in this plan is relative to it; cd there before running anything.

## Goal
Add two independent features to the existing in-memory items API: query filters plus pagination on
`GET /items`, and a `/tags` router backed by its own store module. The two tasks touch disjoint files
and have no dependencies on each other.

## Starting point (already exists — do not re-create)
`app/__init__.py`, `app/models.py` (`ItemCreate`: `name` min_length=1, `price` ge=0; `Item(ItemCreate)` adds
`id: int`), `app/main.py` (FastAPI app, module-level `_items`/`_next_id`, `reset_store()`, `GET /health`,
`GET /items`, `GET /items/{item_id}` 404, `POST /items` 201/422), `tests/test_items.py`.

## Assumptions / Decisions (fixed — the executor must not re-decide)
- Task T1 owns `app/main.py`; task T2 owns only new modules. `app/main.py` therefore also carries the
  single wire-in point for the tags router: a guarded `try: from app.routers.tags import router as
  tags_router / except ImportError: tags_router = None` followed by `if tags_router is not None:
  app.include_router(tags_router)`. The guard exists because T2 runs in parallel and may not have landed
  yet; the app must import and pass its own tests on its own.
- `app/item_query.py` is pure: no FastAPI import, no globals, no store access. It takes the item list as
  its first argument. Public names: `filter_items(items, min_price=None, max_price=None, name_contains=None)
  -> list[Item]`, `count_filtered(...) -> int`, `select_items(items, min_price=None, max_price=None,
  name_contains=None, limit=None, offset=0) -> list[Item]`. Order of operations: filter, then offset, then
  limit.
- `GET /items` query params, all optional: `min_price: float | None = Query(default=None, ge=0)`,
  `max_price: float | None = Query(default=None, ge=0)`, `name_contains: str | None = None`,
  `limit: int | None = Query(default=None, ge=1, le=200)`, `offset: int = Query(default=0, ge=0)`.
  `min_price > max_price` is NOT an error (returns `[]`); `name_contains=""` matches everything; matching is
  case-insensitive substring. The response stays `list[Item]` and additionally carries an
  `X-Total-Count` header with the pre-pagination match count. No params supplied must behave exactly as
  before this plan.
- `app/tag_store.py` owns tag state. Public names: `Tag` (pydantic model: `id: int`, `name: str`,
  `item_ids: list[int]`), `reset_tag_store() -> None`, `next_id() -> int`, `tags() -> list[Tag]`,
  `get_tag(tag_id) -> Tag | None`, `find_by_name(name) -> Tag | None`, `add_tag(name) -> Tag`,
  `attach_item(tag_id, item_id) -> Tag | None`. Tag ids are never reused after a reset.
- `app/routers/tags.py` defines `router = APIRouter()` with paths `"/tags"`, `"/tags/{tag_id}"`,
  `"/tags/{tag_id}/items/{item_id}"`. No prefix, no tags. `POST /tags` is 201, and 409
  `{"detail": "Tag already exists"}` on a duplicate name, 422 on an empty/missing name. `GET /tags/{tag_id}`
  and the attach endpoint 404 with `{"detail": "Tag not found"}` for a missing tag; the attach endpoint
  404s with `{"detail": "Item not found"}` for a missing item. Attaching the same item twice is idempotent
  (still 200, `item_ids` unchanged).
- `app/routers/tags.py` checks item existence with a *lazy* `from app.main import _items` inside the helper
  function (a module-level import would be circular: `app.main` includes this router). Items keep their own
  store; tags only remember item ids.
- `app/routers/__init__.py` is empty. No new dependencies: fastapi 0.115.0, uvicorn 0.32.0, pytest 9.1.1,
  pydantic 2.13.4, httpx 0.28.1 are already installed.
- The work dir is `bench/suite/work/<slug>/`; all acceptance commands run from the project root and are
  `cd {work} && ...` (`{work}` is substituted with the work dir path by the runner; when running a command
  by hand, replace `{work}` with the current work dir). `tests/test_items.py` is never edited.

## Tasks (phase 1 — fully independent, `deps` empty for both)
| id | title | deps | files |
|----|-------|------|-------|
| T1 | GET /items filters + pagination via `app/item_query.py` | - | {work}/app/item_query.py, {work}/app/main.py |
| T2 | `/tags` router + its own store module | - | {work}/app/routers/__init__.py, {work}/app/tag_store.py, {work}/app/routers/tags.py |

## T1
GOAL: Add optional query filters (`min_price`, `max_price`, `name_contains`) and pagination (`limit`,
`offset`) to `GET /items`, with the selection logic living in a new pure module `app/item_query.py`.

CONTEXT: `GET /items` in `app/main.py` returns `_items` unchanged. Other tasks (T2) add a `/tags` router in
parallel and must not conflict with this task's files, so the tags wire-in point also lands here.

FILES (create/modify; touch nothing else):
- `{work}/app/item_query.py` (create)
- `{work}/app/main.py` (modify only the imports and the `GET /items` handler)

REQUIREMENTS:
- `app/item_query.py`: no FastAPI import, no globals, first parameter is the item list.
  - `filter_items(items, min_price=None, max_price=None, name_contains=None) -> list[Item]` — keep items with
    `price >= min_price` when given, `price <= max_price` when given, and
    `name_contains.lower() in item.name.lower()` when `name_contains` is a non-empty string. All supplied
    filters combine with AND. Original order is preserved. `name_contains=""` matches everything.
  - `count_filtered(items, min_price=None, max_price=None, name_contains=None) -> int` — number of matches
    before pagination.
  - `select_items(items, min_price=None, max_price=None, name_contains=None, limit=None, offset=0) -> list[Item]`
    — filter first, then skip `offset`, then take `limit`. `limit=None` means "no limit"; a negative `offset`
    is treated as 0; an offset past the end returns `[]`.
- `app/main.py`:
  - `GET /items` keeps `response_model=list[Item]` and gains the params
    `min_price: float | None = Query(default=None, ge=0)`, `max_price: float | None = Query(default=None, ge=0)`,
    `name_contains: str | None = None`, `limit: int | None = Query(default=None, ge=1, le=200)`,
    `offset: int = Query(default=0, ge=0)`. A non-numeric or negative value must return FastAPI's 422.
  - The handler takes a `response: Response` argument and sets the header
    `X-Total-Count` to `count_filtered(...)`; the body is `select_items(...)`.
  - Add the tags wire-in point (see Decisions): guarded `try/except ImportError` import of
    `app.routers.tags.router as tags_router`, and `app.include_router(tags_router)` when it is not `None`.
    Do not add any other import from `app.routers`.
  - `reset_store()`, `GET /health`, `GET /items/{item_id}`, `POST /items` and the module globals stay as they
    are; the tags endpoints are not implemented here.

CONSTRAINTS: match existing style (plain functions, type hints, no docstring noise); touch only the two listed
files; no new dependencies; never run git commands that change state; do not modify `app/models.py`,
`app/tag_store.py`, `app/routers/`, `app/__init__.py` or `tests/test_items.py`.

ACCEPTANCE (run from the project root; must print `FILTERS OK` and exit 0):
`cd {work} && python -c "from app.item_query import select_items, count_filtered; from app.models import Item; items = [Item(id=1, name='Widget', price=9.5), Item(id=2, name='gadget', price=3.0), Item(id=3, name='Big Widget', price=100.0)]; assert [i.id for i in select_items(items)] == [1, 2, 3]; assert [i.id for i in select_items(items, min_price=9.5)] == [1, 3]; assert [i.id for i in select_items(items, name_contains='wIdG')] == [1, 3]; assert select_items(items, limit=2)[-1].id == 2; assert [i.id for i in select_items(items, limit=2, offset=2)] == [3]; assert select_items(items, offset=99) == []; assert count_filtered(items, max_price=9.5) == 2; print('FILTERS OK')"`

## T2
GOAL: Add a `/tags` router with its own store module, so items can be labelled independently of the items
store. This task must not touch `app/main.py` — T1 owns that file and already carries the wire-in point.

CONTEXT: The seed has no `app/routers/` package and no tag state. T1 (running in parallel) adds
`app.include_router(tags_router)` to `app/main.py` behind a `try/except ImportError`, so the endpoints go live
as soon as this task's files exist — no edit to `app/main.py` is needed or allowed here.

FILES (create; touch nothing else):
- `{work}/app/routers/__init__.py` (create, empty)
- `{work}/app/tag_store.py` (create)
- `{work}/app/routers/tags.py` (create)

REQUIREMENTS:
- `app/tag_store.py` holds all tag state in module globals (`_tags: list[Tag]`, `_next_id = 1`) and imports
  only `pydantic` and `app.models`. Public names: `Tag` (`id: int`, `name: str`, `item_ids: list[int]`),
  `reset_tag_store() -> None` (clears the list, sets the counter back to 1, never rebinds the list),
  `next_id() -> int` (returns the current counter, then increments it), `tags() -> list[Tag]`,
  `get_tag(tag_id) -> Tag | None`, `find_by_name(name) -> Tag | None` (exact, case-sensitive match),
  `add_tag(name) -> Tag` (appends a tag with `item_ids == []`), and
  `attach_item(tag_id, item_id) -> Tag | None` (returns `None` for an unknown tag; appends `item_id` only if
  it is not already attached).
- `app/routers/tags.py` defines `router = APIRouter()` (no prefix, no tags) with exactly these routes:
  - `GET /tags`, `response_model=list[Tag]` — all tags in creation order.
  - `GET /tags/{tag_id}`, `response_model=Tag` — 404 `{"detail": "Tag not found"}` when missing.
  - `POST /tags`, `response_model=Tag`, `status_code=201` — body model `TagCreate` with
    `name: str = Field(min_length=1)`; 409 `{"detail": "Tag already exists"}` when the name already exists.
  - `POST /tags/{tag_id}/items/{item_id}`, `response_model=Tag` — 404 `Tag not found` for an unknown tag,
    404 `{"detail": "Item not found"}` for an unknown item, otherwise the updated tag (idempotent re-attach).
- Item existence is checked with a lazy `from app.main import _items` **inside a helper function** in
  `app/routers/tags.py` (a module-level import would be circular because `app.main` includes this router).
  Do not import any other name from `app.main` and do not move item state.
- No new dependencies, no persistence, no `DELETE /tags`, no auth, no tags on the `Item` model.

CONSTRAINTS: match existing style (plain functions, type hints, no docstring noise); touch only the three listed
files; no new dependencies; never run git commands that change state; do not modify `app/main.py`,
`app/models.py`, `app/item_query.py`, `app/__init__.py` or `tests/test_items.py`.

ACCEPTANCE (run from the project root; must print `TAGS OK` and exit 0):
`cd {work} && python -c "from app.tag_store import add_tag, attach_item, find_by_name, get_tag, reset_tag_store, tags; from app.routers.tags import router; paths = {getattr(r, 'path', '') for r in router.routes}; assert {'/tags', '/tags/{tag_id}', '/tags/{tag_id}/items/{item_id}'} <= paths, paths; reset_tag_store(); tag = add_tag('urgent'); assert (tag.id, tag.name, tag.item_ids) == (1, 'urgent', []); assert attach_item(1, 7).item_ids == [7]; assert attach_item(1, 7).item_ids == [7]; assert get_tag(99) is None; assert find_by_name('urgent').id == 1; assert [t.name for t in tags()] == ['urgent']; reset_tag_store(); assert tags() == []; print('TAGS OK')"`

## Later phases
None planned.
