# Spec (large: full-stack items app — FastAPI + sqlite3 behind a Next.js App Router front end)

Two halves in one work dir, eight tasks. The seed backend is a bare `FastAPI` serving `GET /health`; the seed web app is a dependency-free
App Router shell (`tsconfig.json`, `next-env.d.ts`, `vitest.config.ts`, `layout.tsx`, a static `page.tsx`, `lib/format.ts`).
T1 `backend/app/models.py` — pydantic `ItemCreate`/`ItemUpdate`/`Item`/`SearchResult`/`ItemStats` with `NAME_MAX`/`SKU_MAX` bounds and `quantity` defaulting to 0.
T2 `backend/app/store.py` — stdlib `sqlite3` only (no sqlalchemy, no ORM): `ItemStore` over a one-table `items` schema, `DuplicateSku`, `reset()`, and the `get_store()`/`reset_store()` singletons.
T3 `backend/app/items_router.py` — `APIRouter(prefix="/items")`: list, create (201, 409 on a taken sku), get/patch/delete (404 unknown id, 204 delete).
T4 `backend/app/stats.py` — `GET /search?q=` (case-insensitive substring over name or sku, echoing the raw query) and `GET /stats` (`total`, `total_quantity`, `total_value`, `avg_price`, `0.0` on an empty store).
T5 `web/lib/api-client.ts` — the `Item`/`NewItem`/`ItemStats`/`SearchResult` types plus `ApiClient`, `ApiError` and `createApiClient`, all traffic through one `fetch` helper.
T6 `web/components/ItemList.tsx` + `ItemDetail.tsx` — presentational, relative imports only, the documented `data-testid` contract.
T7 joins the four backend leaves into `create_app()` in `backend/app/main.py` and pins the OpenAPI document with `backend/tests/test_openapi.py`; T8 joins the two web leaves into an `async` `web/app/page.tsx`.
No new dependencies, no `next build`, and no edits outside the files each task owns.
