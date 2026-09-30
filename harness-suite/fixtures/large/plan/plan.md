# Plan: suite-items-fullstack (backend + web items app)

Work dir: `{work}` - every path in this plan is relative to it; cd there before running anything.

Slim plan: each task brief is the `## T<n>` section of this file. Work dir is `{work}`; the backend lives
in `{work}/backend` and the web app in `{work}/web`, so every path below is relative to `{work}`.

## Goal
Grow the seeded fixture into a full-stack items app: a sqlite-backed FastAPI CRUD service with search and
stats on one side, a typed fetch client plus list/detail components and a home page on the other.

## Starting point (already exists — do not re-create)
`backend/app/__init__.py` and `backend/app/main.py` (a bare `FastAPI()` with `GET /health` only); the web
app declares no dependencies of its own: `web/package.json`, `web/tsconfig.json` (strict,
`jsx: preserve`, `noUncheckedIndexedAccess`), `web/next-env.d.ts`, `web/next.config.mjs`,
`web/vitest.config.ts` (jsdom, `@vitejs/plugin-react`, `@` alias), `web/app/layout.tsx`, a static
`web/app/page.tsx` and `web/lib/format.ts` (`pluralItems(count)`). There is no `components/` directory,
no `web/lib/api-client.ts`, no store, no models, no `backend/tests/`.

## Assumptions / Decisions (fixed — the executor must not re-decide)
- Phase 1 has six leaves with pairwise-disjoint files: no leaf may edit another leaf's file. The four
  backend leaves are still layered (`models` <- `store` <- the two routers), so the store and the two
  routers depend on the models task and the routers additionally depend on the store task; the web leaves
  import only each other and are declared below. The seed ships typed stubs for every cross-task import
  (`backend/app/models.py`, `backend/app/store.py`, `web/lib/api-client.ts`) so any module can be
  imported before its owner task runs; each stub raises `NotImplementedError` and its owning task
  replaces it wholesale.
- Persistence is stdlib `sqlite3` only — no sqlalchemy, no ORM, no migration files, no network access.
  `ItemStore.__init__(self, db_path: str = ":memory:")` opens `sqlite3.connect(db_path,
  check_same_thread=False)` (the `check_same_thread=False` part is required: FastAPI runs sync endpoints
  in a worker thread), sets `row_factory = sqlite3.Row`, and creates the table if missing.
- The table is `items(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sku TEXT NOT NULL
  UNIQUE, price REAL NOT NULL, quantity INTEGER NOT NULL DEFAULT 0)`.
- `app/store.py` exposes `class DuplicateSku(ValueError)`, `class ItemStore` with `list_items() -> list[Item]`,
  `get_item(item_id) -> Item | None`, `create_item(payload: ItemCreate) -> Item` (raises `DuplicateSku`),
  `update_item(item_id, payload: ItemUpdate) -> Item | None`, `delete_item(item_id) -> bool` and
  `reset() -> None` (empties the table and restarts ids at 1), plus the module singletons
  `get_store() -> ItemStore` and `reset_store() -> None`. `create_item`/`update_item` strip the name and
  sku; `ItemUpdate` fields that are `None` are left untouched.
- `app/items_router.py` exposes `router = APIRouter(prefix="/items", tags=["items"])` with the collection
  paths written as `""` (so the URLs are `/items`, not `/items/`): `GET ""` 200 + list, `POST ""` 201 +
  item, `GET/PATCH/DELETE "/{item_id}"`. A duplicate sku on create is `409 {"detail": "sku already
  exists"}` (declared in `responses={409: ...}` so it shows up in the OpenAPI document); any unknown id is
  `404 {"detail": "Item not found"}`; `DELETE` answers `204` with an empty body. Validation failures stay
  FastAPI's default `422`.
- `app/stats.py` exposes `router = APIRouter(tags=["stats"])` with `GET /search?q=` (a `str` query
  parameter, `default=""`, `max_length=80`, answering `{query, count, items}` where `query` echoes the raw
  parameter and the match is a case-insensitive substring of the name or the sku; a blank query matches
  everything) and `GET /stats` (answering `{total, total_quantity, total_value, avg_price}`, where
  `total_value` is `sum(price * quantity)` and `avg_price` is `total_value / total`, both rounded to two
  decimals, and `0.0` for both when the store is empty).
- `app/main.py` (T7) is replaced by a `create_app() -> FastAPI` factory titled `"Items API"` that includes
  both routers, keeps `GET /health` returning `{"status": "ok"}`, exposes the module-level `app =
  create_app()` and re-exports `get_store` / `reset_store` so tests can reset the singleton.
- Inside `web/`, imports between project files are **relative** (`../lib/api-client`), never the `@/`
  alias: the hidden specs run from the work root with their own vitest config, where `@` does not resolve.
- `web/lib/api-client.ts` exports the wire types `Item`, `NewItem` (`quantity` optional), `ItemStats`,
  `SearchResult`, `class ApiError extends Error` with a `status` field, `class ApiClient` (constructor
  `(baseUrl = "/api")` that strips trailing slashes; `request<T>(path, init?)`; `listItems`, `getItem`,
  `createItem`, `deleteItem`, `stats`, `search`) and `function createApiClient(baseUrl?)`. `request` calls
  `fetch(`${baseUrl}${path}`, init)`, throws `ApiError(response.status, ...)` for a non-`ok` response,
  resolves `undefined` for `204`, and JSON-decodes everything else. `createItem` sends
  `method: "POST"`, a `content-type: application/json` header and the JSON body; `search` URL-encodes the
  query. No `any`, no `axios`, no new dependencies.
- `web/components/ItemList.tsx` exports `ItemListProps = { items: Item[]; emptyLabel?: string }`,
  `ItemList({ items, emptyLabel = "No items yet." })` and a default export. Empty renders only
  `<p data-testid="item-empty">{emptyLabel}</p>`; otherwise a `<ul data-testid="item-list">` of
  `<li data-testid="item-row" data-sku={item.sku}>` rows, each with a `<a href={`/items/${item.id}`}>`
  showing the name and a `<span data-testid="item-qty">` showing the quantity, in the given order.
- `web/components/ItemDetail.tsx` exports `ItemDetailProps = { item: Item }`, `ItemDetail({ item })` and a
  default export: `<article data-testid="item-detail" data-id={String(item.id)}>` with
  `<h2 data-testid="item-detail-name">`, a `<dl>` holding `item-detail-sku`, `item-detail-price` and
  `item-detail-quantity` (each rendering the raw value), plus
  `<p data-testid="item-out-of-stock">Out of stock</p>` only when `quantity === 0`.
- `web/app/page.tsx` (T8) is replaced by an `async` default-exported server component that awaits
  `createApiClient().listItems()`, keeps the seeded `<h1>Items</h1>` and the `data-testid="item-count"`
  paragraph (now `pluralItems(items.length)` from `../lib/format`) and renders `<ItemList items={items} />`.
  It is not a client component: no `"use client"`, no hooks, no `useEffect`.
- `backend/tests/test_openapi.py` (T7) is a pytest module that puts `backend/` on `sys.path` from
  `Path(__file__).resolve().parents[1]` and asserts the OpenAPI contract: the paths `/health`, `/items`,
  `/items/{item_id}`, `/search`, `/stats` with the expected methods, the schemas `Item`, `ItemCreate`,
  `ItemUpdate`, `SearchResult`, `ItemStats`, the `Item`/`ItemCreate` property sets, `201` + `409` on
  `POST /items` and `204` on `DELETE /items/{item_id}`.
- No new dependencies anywhere, no `next build`, no database server, no authentication, no pagination
  beyond what is written above, and no changes to `web/tsconfig.json`, `web/vitest.config.ts`,
  `web/package.json`, `web/next-env.d.ts`, `web/lib/format.ts` or `web/app/layout.tsx`. The hidden specs
  bring their own `vitest.config.ts` at the work root; do not create a second one and do not copy a spec
  into the project.
- Acceptance commands run from the project root with `python` / `node` / `npx --no-install`; the plan
  directory is `{work}/.harness/plans/<slug>/` at execution time.

## Tasks (phase 1)
| id | title | deps | files |
|----|-------|------|-------|
| T1 | item schemas | - | backend/app/models.py |
| T2 | sqlite item store | T1 | backend/app/store.py |
| T3 | /items CRUD router | T1, T2 | backend/app/items_router.py |
| T4 | /search + /stats router | T1, T2 | backend/app/stats.py |
| T5 | typed API client | - | web/lib/api-client.ts |
| T6 | ItemList + ItemDetail | - | web/components/ItemList.tsx, web/components/ItemDetail.tsx |
| T7 | app wiring + OpenAPI contract | T1, T2, T3, T4 | backend/app/main.py, backend/tests/test_openapi.py |
| T8 | home page wiring | T5, T6 | web/app/page.tsx |

## Later phases
None planned. Optional follow-ups if requested later: a detail route `app/items/[id]/page.tsx` rendering
`ItemDetail`, an "add item" client form posting through `createItem`, and a `pytest` + `vitest` CI job.

## T1
GOAL: create `backend/app/models.py`, the pydantic schemas every other backend module shares.

CONTEXT: the seed has no models at all — `backend/app/main.py` serves `GET /health` and nothing else. This
module is imported by the store (T2) and both routers (T3, T4), so it must import nothing local; that is
why it is a leaf task of its own rather than a prerequisite of the others.

FILES (create; touch nothing else):
- `backend/app/models.py`

REQUIREMENTS:
- `NAME_MAX = 60` and `SKU_MAX = 32` module constants.
- `class ItemCreate(BaseModel)` with `name: str = Field(min_length=1, max_length=NAME_MAX)`,
  `sku: str = Field(min_length=1, max_length=SKU_MAX)`, `price: float = Field(ge=0)` and
  `quantity: int = Field(ge=0, default=0)`.
- `class ItemUpdate(BaseModel)` with `name`, `price` and `quantity`, every one of them optional
  (`default=None`, the same bounds as above) — `None` means "leave this field alone".
- `class Item(ItemCreate)` adding `id: int`.
- `class SearchResult(BaseModel)` with `query: str`, `count: int`, `items: list[Item]`.
- `class ItemStats(BaseModel)` with `total: int`, `total_quantity: int`, `total_value: float`,
  `avg_price: float`.
- Pydantic v2 style (`Field`, `model_fields`); no SQL, no FastAPI imports, no default exports.

CONSTRAINTS: touch only the listed file; no new dependencies; never run git commands that change state;
bounds are enforced by the models so the routers never re-validate by hand.

ACCEPTANCE (run from the project root; must print `MODELS OK` and exit 0):
`cd {work}/backend && python -c "from app.models import NAME_MAX, SKU_MAX, Item, ItemCreate, ItemStats, ItemUpdate, SearchResult; assert set(Item.model_fields) == {'id', 'name', 'sku', 'price', 'quantity'}; assert set(ItemCreate.model_fields) == {'name', 'sku', 'price', 'quantity'}; assert set(ItemUpdate.model_fields) == {'name', 'price', 'quantity'}; assert set(SearchResult.model_fields) == {'query', 'count', 'items'}; assert set(ItemStats.model_fields) == {'total', 'total_quantity', 'total_value', 'avg_price'}; assert issubclass(Item, ItemCreate); assert ItemCreate(name='n', sku='s', price=1.0).quantity == 0; assert ItemUpdate().model_dump(exclude_unset=True) == {}; assert ItemUpdate(name='x').model_dump()['price'] is None; assert (NAME_MAX, SKU_MAX) == (60, 32); print('MODELS OK')"`

## T2
GOAL: create `backend/app/store.py`, the sqlite3-backed storage the routers will read and write.

CONTEXT: nothing persists anything today. Use the stdlib `sqlite3` module — sqlalchemy is not installed
and must not be added. The store is a plain class plus two module singletons, with no FastAPI import, so
it can be exercised on its own. `app/models.py` comes from T1 (the seed's stub is replaced by it).

FILES (create; touch nothing else):
- `backend/app/store.py`

REQUIREMENTS:
- `SCHEMA` creating the table `items(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sku TEXT
  NOT NULL UNIQUE, price REAL NOT NULL, quantity INTEGER NOT NULL DEFAULT 0)` with `IF NOT EXISTS`.
- `class DuplicateSku(ValueError)` — raised, never returned, when a create would store a taken sku.
- `class ItemStore.__init__(self, db_path: str = ':memory:')` — `sqlite3.connect(db_path,
  check_same_thread=False)`, `row_factory = sqlite3.Row`, then apply `SCHEMA` and commit.
- `list_items() -> list[Item]` — every item ordered by id.
- `get_item(item_id: int) -> Item | None`.
- `create_item(payload: ItemCreate) -> Item` — strips `name`/`sku`, stores `price` as a float, raises
  `DuplicateSku` when the sku is taken, and returns the stored row (with its server-assigned id).
- `update_item(item_id: int, payload: ItemUpdate) -> Item | None` — `None` for an unknown id, otherwise
  applies only the fields that are not `None` and returns the new row.
- `delete_item(item_id: int) -> bool` — whether anything was removed.
- `reset() -> None` — empties the table and restarts the ids at 1.
- Module singletons `get_store() -> ItemStore` (created on first use) and `reset_store() -> None`.
- The only project import allowed is `app.models`; the table is created with `executescript` and every
  write is committed.

CONSTRAINTS: stdlib `sqlite3` only; touch only the listed file; no new dependencies; never run git
commands that change state; keep the schema in one place (the `SCHEMA` constant).

ACCEPTANCE (run from the project root; must print `STORE OK` and exit 0):
`cd {work}/backend && python -c "from app.models import ItemCreate, ItemUpdate; from app.store import DuplicateSku, ItemStore, get_store, reset_store; assert issubclass(DuplicateSku, ValueError); s = ItemStore(); assert s.list_items() == []; a = s.create_item(ItemCreate(name='  Widget  ', sku='W-1', price=9.5, quantity=4)); assert (a.id, a.name, a.sku, a.price, a.quantity) == (1, 'Widget', 'W-1', 9.5, 4); b = s.create_item(ItemCreate(name='Gadget', sku='G-2', price=3.0)); assert (b.id, b.quantity) == (2, 0); assert [i.sku for i in s.list_items()] == ['W-1', 'G-2']; assert s.get_item(1).name == 'Widget' and s.get_item(99) is None; assert s.update_item(1, ItemUpdate(price=12.0)).price == 12.0 and s.get_item(1).name == 'Widget'; assert s.update_item(1, ItemUpdate(quantity=0)).quantity == 0; assert s.update_item(99, ItemUpdate(price=1.0)) is None; assert s.delete_item(1) is True and s.delete_item(1) is False; assert s.create_item(ItemCreate(name='Fresh', sku='F-3', price=1.0)).id == 3; s.reset(); assert s.list_items() == [] and s.create_item(ItemCreate(name='Again', sku='A-1', price=1.0)).id == 1; assert get_store() is get_store(); reset_store(); print('STORE OK')"`

## T3
GOAL: create `backend/app/items_router.py`, the CRUD HTTP surface of the items service.

CONTEXT: the seed app has no routes beyond `/health` and no store. The router is standalone: it builds
routes from `app.models` and `app.store` only, so it can be mounted on a throwaway `FastAPI()` to verify.
Those two modules come from T1 and T2 (the seed's stubs are replaced by them).

FILES (create; touch nothing else):
- `backend/app/items_router.py`

REQUIREMENTS:
- `router = APIRouter(prefix="/items", tags=["items"])`, with the collection paths written as `""` so the
  URLs are exactly `/items` and `/items/{item_id}`.
- `GET ""` -> `response_model=list[Item]`, 200, the full list in id order.
- `POST ""` -> `response_model=Item`, `status_code=201`, and `responses={409: {"description": "sku already
  exists"}}`; a `DuplicateSku` from the store becomes `HTTPException(409, detail="sku already exists")`.
- `GET "/{item_id}"` -> 200 + the item, or `404` with `detail="Item not found"`.
- `PATCH "/{item_id}"` -> 200 + the updated item, or the same 404.
- `DELETE "/{item_id}"` -> `status_code=204` with an empty `Response` body, or the same 404.
- Bad payloads are not handled here: let FastAPI answer `422`. `item_id: int` is a path parameter, so a
  non-integer id is also a `422`.
- One `HTTPException` per failure; no try/except around the store beyond translating `DuplicateSku`.

CONSTRAINTS: touch only the listed file; no new dependencies; never run git commands that change state;
do not import `app.main` (that is task T7 and would be circular).

ACCEPTANCE (run from the project root; must print `ITEMS OK` and exit 0):
`cd {work}/backend && python -c "from fastapi import FastAPI; from fastapi.testclient import TestClient; from app.items_router import router; from app.store import reset_store; app = FastAPI(); app.include_router(router); c = TestClient(app); reset_store(); assert set(r.path for r in router.routes) == {'/items', '/items/{item_id}'}; assert c.get('/items').json() == []; created = c.post('/items', json={'name': 'Widget', 'sku': 'W-1', 'price': 9.5, 'quantity': 4}); assert created.status_code == 201 and created.json() == {'id': 1, 'name': 'Widget', 'sku': 'W-1', 'price': 9.5, 'quantity': 4}; assert c.get('/items/1').json() == created.json(); assert c.get('/items/99').json() == {'detail': 'Item not found'}; assert c.get('/items/abc').status_code == 422; assert c.post('/items', json={'name': 'Other', 'sku': 'W-1', 'price': 1.0}).status_code == 409; assert c.post('/items', json={'name': '', 'sku': 'X', 'price': 1.0}).status_code == 422; assert c.patch('/items/1', json={'price': 12.0}).json()['price'] == 12.0; assert c.patch('/items/1', json={'price': 12.0}).json()['name'] == 'Widget'; assert c.patch('/items/99', json={'price': 1.0}).status_code == 404; assert c.delete('/items/1').status_code == 204; assert c.get('/items').json() == []; assert c.delete('/items/1').status_code == 404; print('ITEMS OK')"`

## T4
GOAL: create `backend/app/stats.py`, the read-only search and aggregate endpoints.

CONTEXT: the service can now store and serve individual items, but nothing can find or summarise them.
Like the CRUD router this module is standalone: it reads the store and builds its own `APIRouter`.
`app/models.py` and `app/store.py` come from T1 and T2 (the seed's stubs are replaced by them).

FILES (create; touch nothing else):
- `backend/app/stats.py`

REQUIREMENTS:
- `router = APIRouter(tags=["stats"])` with no prefix.
- `GET "/search"` -> `response_model=SearchResult`; the parameter is
  `q: str = Query(default="", max_length=80)`. A blank/whitespace-only `q` matches every item; otherwise
  the (trimmed, lower-cased) query must be a substring of the item's name or sku, compared
  case-insensitively. Answer `{query, count, items}` where `query` echoes the raw parameter (not the
  trimmed one) and `count == len(items)`. Results keep the store's id order.
- `GET "/stats"` -> `response_model=ItemStats` with `total` (number of items), `total_quantity`
  (`sum(quantity)`), `total_value` (`sum(price * quantity)`) and `avg_price` (`total_value / total`).
  `total_value` and `avg_price` are rounded to two decimals; an empty store answers all four as `0`
  for the counts and `0.0` for the money fields (never a `ZeroDivisionError`).
- Only `app.models` and `app.store` may be imported; no writes, no new query parameters, no new deps.

CONSTRAINTS: touch only the listed file; no new dependencies; never run git commands that change state;
keep the endpoint bodies pure functions of the current store contents.

ACCEPTANCE (run from the project root; must print `STATS OK` and exit 0):
`cd {work}/backend && python -c "from fastapi import FastAPI; from fastapi.testclient import TestClient; from app.models import ItemCreate; from app.stats import router; from app.store import get_store, reset_store; app = FastAPI(); app.include_router(router); c = TestClient(app); reset_store(); assert c.get('/stats').json() == {'total': 0, 'total_quantity': 0, 'total_value': 0.0, 'avg_price': 0.0}; assert c.get('/search').json() == {'query': '', 'count': 0, 'items': []}; s = get_store(); s.create_item(ItemCreate(name='Big Widget', sku='A-1', price=10.0, quantity=2)); s.create_item(ItemCreate(name='gadget', sku='B-2', price=4.0, quantity=3)); found = c.get('/search', params={'q': '  wIdG '}).json(); assert found['query'] == '  wIdG ' and found['count'] == 1 and [i['sku'] for i in found['items']] == ['A-1']; assert [i['sku'] for i in c.get('/search', params={'q': 'b-2'}).json()['items']] == ['B-2']; assert c.get('/search', params={'q': 'zzz'}).json() == {'query': 'zzz', 'count': 0, 'items': []}; assert c.get('/search', params={'q': 'x' * 81}).status_code == 422; stats = c.get('/stats').json(); assert stats['total'] == 2 and stats['total_quantity'] == 5 and stats['total_value'] == 32.0 and stats['avg_price'] == 16.0; print('STATS OK')"`

## T5
GOAL: create `web/lib/api-client.ts`, the single typed way the web app talks to the backend.

CONTEXT: the web app is static and has no way to reach the API. Nothing else in `web/` may import
anything except the types declared here, so this module owns the wire format of the items service.

FILES (create; touch nothing else):
- `web/lib/api-client.ts`

REQUIREMENTS:
- `export type Item = { id: number; name: string; sku: string; price: number; quantity: number }` and
  `export type NewItem = { name: string; sku: string; price: number; quantity?: number }`.
- `export type ItemStats = { total: number; total_quantity: number; total_value: number; avg_price: number }`
  and `export type SearchResult = { query: string; count: number; items: Item[] }`.
- `export class ApiError extends Error` carrying a readonly `status: number`; `message` mentions the status.
- `export class ApiClient` with `readonly baseUrl: string`, a constructor `(baseUrl = "/api")` that drops
  trailing slashes, and:
  - `request<T>(path: string, init?: RequestInit): Promise<T>` — `fetch(`${this.baseUrl}${path}`, init)`;
    a non-`ok` response throws `new ApiError(response.status, ...)`; `204` resolves `undefined`; anything
    else resolves `(await response.json()) as T`.
  - `listItems()` -> `GET /items`; `getItem(id)` -> `GET /items/${id}`; `createItem(input: NewItem)` ->
    `POST /items` with a `content-type: application/json` header and `JSON.stringify(input)`;
    `deleteItem(id)` -> `DELETE /items/${id}`; `stats()` -> `GET /stats`; `search(query)` ->
    `GET /search?q=${encodeURIComponent(query)}`.
- `export function createApiClient(baseUrl?: string): ApiClient`.
- No `any`, no React, no `axios`, no imports at all, no default export.

CONSTRAINTS: TypeScript, `strict` mode (including `noUncheckedIndexedAccess`), touch only the listed
file; no new dependencies; never run git commands that change state; every network call goes through
`request`.

ACCEPTANCE (run from the project root; the file must typecheck cleanly, then the command must print `CLIENT OK` and exit 0; runtime behaviour is covered by the hidden vitest specs, which stub `fetch` and assert every URL, header and body):
`cd {work} && npx --no-install tsc --noEmit --strict --noUncheckedIndexedAccess --jsx react-jsx --module esnext --moduleResolution bundler --target es2022 --lib dom,dom.iterable,es2022 web/lib/api-client.ts && node --input-type=module -e "import { readFileSync } from 'node:fs'; const src = readFileSync('web/lib/api-client.ts', 'utf8'); if (/not implemented/.test(src)) throw new Error('web/lib/api-client.ts is still a stub'); for (const n of ['ApiError', 'ApiClient', 'createApiClient']) { if (!src.includes(n)) throw new Error('missing ' + n); } console.log('CLIENT OK');"`

## T6
GOAL: create `web/components/ItemList.tsx` and `web/components/ItemDetail.tsx`, the two presentational views.

CONTEXT: there is no `components/` directory and no `Item` type in the app yet — it comes from
`../lib/api-client` (task T5), imported as a *type only*. Both components are dumb: props in, markup out,
no store, no fetch, no state.

FILES (create; touch nothing else):
- `web/components/ItemList.tsx`
- `web/components/ItemDetail.tsx`

REQUIREMENTS (ItemList):
- `export type ItemListProps = { items: Item[]; emptyLabel?: string }` and
  `export function ItemList({ items, emptyLabel = "No items yet." }: ItemListProps)`.
- Empty: return `<p data-testid="item-empty">{emptyLabel}</p>` and nothing else.
- Otherwise: `<ul data-testid="item-list">` with one
  `<li key={item.id} data-testid="item-row" data-sku={item.sku}>` per item, in the given order, each
  holding a `<a href={`/items/${item.id}`}>{item.name}</a>` and a `<span data-testid="item-qty">` with
  the quantity.

REQUIREMENTS (ItemDetail):
- `export type ItemDetailProps = { item: Item }` and `export function ItemDetail({ item }: ItemDetailProps)`.
- `<article data-testid="item-detail" data-id={String(item.id)}>` containing
  `<h2 data-testid="item-detail-name">{item.name}</h2>` and a `<dl>` whose `<dd>` elements are
  `data-testid="item-detail-sku"`, `data-testid="item-detail-price"` and
  `data-testid="item-detail-quantity"`, each rendering the raw value.
- Render `<p data-testid="item-out-of-stock">Out of stock</p>` only when `item.quantity === 0`.

REQUIREMENTS (both files): `Item` is imported as a type from `../lib/api-client` (relative, not the `@`
alias); each component is exported both by name and as the default export; JSX only, no
`React.createElement`, no `import React`, no `"use client"`, no hooks, no event handlers.

CONSTRAINTS: TypeScript, `strict` mode; touch only the two listed files; no new dependencies; never run
git commands that change state; the hidden specs drive these components through
`@testing-library/react`, so the `data-testid` names above are part of the contract.

ACCEPTANCE (run from the project root; both files must typecheck cleanly, then the command must print `COMPONENTS OK` and exit 0; runtime behaviour is covered by the hidden vitest specs):
`cd {work} && npx --no-install tsc --noEmit --strict --noUncheckedIndexedAccess --jsx react-jsx --module esnext --moduleResolution bundler --target es2022 --lib dom,dom.iterable,es2022 web/components/ItemList.tsx web/components/ItemDetail.tsx && node --input-type=module -e "import { readFileSync } from 'node:fs'; for (const file of ['web/components/ItemList.tsx', 'web/components/ItemDetail.tsx']) { const src = readFileSync(file, 'utf8'); if (!/export default/.test(src)) throw new Error(file + ': needs a default export'); if (!/export function/.test(src)) throw new Error(file + ': needs a named export'); if (src.includes('@/')) throw new Error(file + ': use relative imports'); } console.log('COMPONENTS OK');"`

## T7
GOAL: wire the backend together — `backend/app/main.py` becomes a real application factory, and
`backend/tests/test_openapi.py` pins its OpenAPI contract.

CONTEXT: T1-T4 produced the models, the store and two routers; nothing includes them yet, so the seed app
still serves only `/health`. This is the only task that edits an existing backend file, and it also adds the
first backend test module. `backend/tests/` does not exist yet.

FILES (create/edit; touch nothing else):
- `backend/app/main.py` (replace the seed's bare app)
- `backend/tests/test_openapi.py` (create)

REQUIREMENTS (`main.py`):
- `def create_app() -> FastAPI` returning a `FastAPI(title="Items API", version="1.0.0")` that calls
  `include_router(items_router.router)` and `include_router(stats.router)`.
- `GET /health` still answers `{"status": "ok"}` (define it inside the factory so every app instance has
  it).
- Module-level `app = create_app()`, and re-export `get_store` and `reset_store` from `app.store` so tests
  and the runner can reset the singleton.
- `__all__ = ["app", "create_app", "get_store", "reset_store"]`.

REQUIREMENTS (`tests/test_openapi.py`):
- Put `backend/` on `sys.path` with `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` before
  importing `app.main`, so the module works no matter where pytest is started from.
- Assert `create_app().openapi()` documents the paths `/health` (get), `/items` (get, post),
  `/items/{item_id}` (get, patch, delete), `/search` (get) and `/stats` (get).
- Assert `components.schemas` contains `Item`, `ItemCreate`, `ItemUpdate`, `SearchResult`, `ItemStats`;
  that `Item` has exactly the properties `id, name, sku, price, quantity` with `id, name, sku, price`
  required (`quantity` has a default, so it is optional); that `ItemCreate` requires `name, sku, price`
  and has no `id`; and that `SearchResult` requires `query, count, items`.
- Assert `POST /items` documents both `201` and `409`, and that `DELETE /items/{item_id}` documents `204`.
- One `assert` per behaviour, function names describing the behaviour; no HTTP calls, no store writes.

CONSTRAINTS: no new dependencies (pytest, fastapi and pydantic are already available); touch only the
two listed files; never run git commands that change state; the contract test must not import the
routers directly — it goes through `create_app()`.

ACCEPTANCE (run from the project root; the contract test must pass and the command must print `OPENAPI OK` and exit 0):
`cd {work}/backend && python -m pytest -q tests/test_openapi.py && echo OPENAPI OK`

## T8
GOAL: wire the web app — the seeded static `web/app/page.tsx` becomes the async items home page.

CONTEXT: T5 added the client and T6 the list component; their output is on disk and this task is the only
place they meet. The seeded page renders `pluralItems(0)` with no data; keep the count element but feed it
the real number of items. `web/app/page.tsx` already imports `../lib/format` relatively — keep that style.

FILES (edit; touch nothing else):
- `web/app/page.tsx`

REQUIREMENTS:
- Replace the seeded default export with an `async` default-exported server component (no `"use client"`,
  no `next/headers`, no hooks, no `useEffect`).
- Inside the component: `const items = await createApiClient().listItems();` using
  `import { createApiClient } from "../lib/api-client"`.
- Render `<main>` with the existing `<h1>Items</h1>`, `<p data-testid="item-count">` showing
  `pluralItems(items.length)` from `../lib/format`, and `<ItemList items={items} />` (default import from
  `../components/ItemList`) after the count.
- The component must be awaitable with no arguments so a test can `render(await HomePage())`.

CONSTRAINTS: TypeScript, `strict` mode; relative imports only; touch only `web/app/page.tsx` (do not
"fix" `web/tsconfig.json`, `web/vitest.config.ts` or any other task's file); no new dependencies; never
run git commands that change state; the page must not swallow a client failure with a try/catch — let the
rejection propagate.

ACCEPTANCE (run from the project root; the page must typecheck cleanly, then the command must print `PAGE OK` and exit 0; rendering is covered by the hidden vitest specs):
`cd {work} && npx --no-install tsc --noEmit --strict --noUncheckedIndexedAccess --jsx preserve --module esnext --moduleResolution bundler --target es2022 --lib dom,dom.iterable,es2022 web/app/page.tsx && node --input-type=module -e "import { readFileSync } from 'node:fs'; const src = readFileSync('web/app/page.tsx', 'utf8'); for (const name of ['../lib/api-client', '../components/ItemList', '../lib/format', 'item-count', 'await']) { if (!src.includes(name)) throw new Error('missing ' + name); } if (!/export default async function/.test(src)) throw new Error('page must be an async default export'); if (src.includes('use client')) throw new Error('server component only'); console.log('PAGE OK');"`
