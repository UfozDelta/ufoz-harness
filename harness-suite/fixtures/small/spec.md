# Spec (small: items API — GET /items filters + pagination, /tags router)

Two independent tasks on the in-memory items API already in the work dir.
T1: new pure module `app/item_query.py` (`filter_items`, `count_filtered`, `select_items`) plus the guarded
tags wire-in point in `app/main.py`; `GET /items` gains optional `min_price` (ge=0), `max_price` (ge=0),
`name_contains` (case-insensitive substring), `limit` (1..200) and `offset` (ge=0), all combinable with AND,
filter-then-offset-then-limit, response stays `list[Item]` and gains an `X-Total-Count` header.
T2: `app/tag_store.py` (`Tag`, `reset_tag_store`, `next_id`, `tags`, `get_tag`, `find_by_name`, `add_tag`,
`attach_item`), an empty `app/routers/__init__.py`, and `app/routers/tags.py` with `GET /tags`,
`GET /tags/{tag_id}` (404 `Tag not found`), `POST /tags` (201, 409 `Tag already exists` on a duplicate name,
422 on an empty name) and `POST /tags/{tag_id}/items/{item_id}` (404 for an unknown tag or item, idempotent
re-attach). Item existence is checked with a lazy `from app.main import _items` to avoid a circular import.
Both tasks have empty `deps` and disjoint files; `app/models.py` and `tests/test_items.py` are never edited,
and no new dependencies are allowed.
