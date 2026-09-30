import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_store

try:  # T2's module; the seed does not have it yet
    from app.tag_store import reset_tag_store
except ImportError:  # pragma: no cover - seed state
    def reset_tag_store() -> None:
        pass

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    reset_store()
    reset_tag_store()


def _seed_items():
    client.post("/items", json={"name": "Widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    client.post("/items", json={"name": "Big Widget", "price": 100.0})


# --- GET /items filters + pagination -------------------------------------


def test_list_items_without_params_returns_everything():
    _seed_items()
    resp = client.get("/items")
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [1, 2, 3]
    assert resp.headers["X-Total-Count"] == "3"


def test_filter_by_min_price():
    _seed_items()
    resp = client.get("/items", params={"min_price": 9.5})
    assert [item["id"] for item in resp.json()] == [1, 3]
    assert resp.headers["X-Total-Count"] == "2"


def test_filter_by_max_price():
    _seed_items()
    resp = client.get("/items", params={"max_price": 9.5})
    assert [item["id"] for item in resp.json()] == [1, 2]


def test_price_filters_combine_with_and():
    _seed_items()
    resp = client.get("/items", params={"min_price": 3.0, "max_price": 9.5})
    assert [item["id"] for item in resp.json()] == [1, 2]


def test_name_contains_is_case_insensitive_substring():
    _seed_items()
    resp = client.get("/items", params={"name_contains": "wIdG"})
    assert [item["id"] for item in resp.json()] == [1, 3]
    assert client.get("/items", params={"name_contains": "nope"}).json() == []


def test_name_contains_empty_string_matches_everything():
    _seed_items()
    resp = client.get("/items", params={"name_contains": ""})
    assert [item["id"] for item in resp.json()] == [1, 2, 3]


def test_min_price_above_max_price_is_empty_not_an_error():
    _seed_items()
    resp = client.get("/items", params={"min_price": 50, "max_price": 1})
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


def test_limit_and_offset_page_through_results():
    _seed_items()
    first = client.get("/items", params={"limit": 2})
    assert [item["id"] for item in first.json()] == [1, 2]
    assert first.headers["X-Total-Count"] == "3"
    second = client.get("/items", params={"limit": 2, "offset": 2})
    assert [item["id"] for item in second.json()] == [3]
    assert second.headers["X-Total-Count"] == "3"


def test_offset_beyond_the_end_returns_empty():
    _seed_items()
    resp = client.get("/items", params={"offset": 10})
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "3"


def test_pagination_applies_after_filters():
    _seed_items()
    resp = client.get("/items", params={"name_contains": "widget", "limit": 1, "offset": 1})
    assert [item["id"] for item in resp.json()] == [3]
    assert resp.headers["X-Total-Count"] == "2"


@pytest.mark.parametrize(
    "params",
    [
        {"min_price": -1},
        {"max_price": -1},
        {"limit": 0},
        {"offset": -1},
        {"min_price": "abc"},
    ],
)
def test_invalid_query_params_return_422(params):
    resp = client.get("/items", params=params)
    assert resp.status_code == 422


# --- /tags router + its own store -----------------------------------------


def test_create_tag():
    resp = client.post("/tags", json={"name": "urgent"})
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "name": "urgent", "item_ids": []}


@pytest.mark.parametrize("body", [{"name": ""}, {}])
def test_create_tag_rejects_bad_names(body):
    resp = client.post("/tags", json=body)
    assert resp.status_code == 422


def test_create_duplicate_tag_is_409():
    client.post("/tags", json={"name": "urgent"})
    resp = client.post("/tags", json={"name": "urgent"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Tag already exists"


def test_list_tags_is_empty_on_a_fresh_store():
    assert client.get("/tags").json() == []


def test_list_and_get_tag():
    client.post("/tags", json={"name": "urgent"})
    client.post("/tags", json={"name": "sale"})
    listed = client.get("/tags")
    assert [tag["name"] for tag in listed.json()] == ["urgent", "sale"]
    one = client.get("/tags/2")
    assert one.status_code == 200
    assert one.json()["name"] == "sale"


def test_get_missing_tag_is_404():
    resp = client.get("/tags/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Tag not found"


def test_attach_item_to_tag():
    client.post("/items", json={"name": "widget", "price": 1.0})
    client.post("/tags", json={"name": "urgent"})
    resp = client.post("/tags/1/items/1")
    assert resp.status_code == 200
    assert resp.json()["item_ids"] == [1]
    assert client.get("/tags/1").json()["item_ids"] == [1]


def test_attach_same_item_twice_is_idempotent():
    client.post("/items", json={"name": "widget", "price": 1.0})
    client.post("/tags", json={"name": "urgent"})
    client.post("/tags/1/items/1")
    resp = client.post("/tags/1/items/1")
    assert resp.status_code == 200
    assert resp.json()["item_ids"] == [1]


def test_attach_to_missing_tag_is_404():
    client.post("/items", json={"name": "widget", "price": 1.0})
    resp = client.post("/tags/99/items/1")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Tag not found"


def test_attach_missing_item_is_404():
    client.post("/tags", json={"name": "urgent"})
    resp = client.post("/tags/1/items/99")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Item not found"


def test_tag_store_is_isolated_between_tests():
    assert client.get("/tags").json() == []


def test_existing_item_endpoints_still_work_alongside_tags():
    created = client.post("/items", json={"name": "widget", "price": 2.0})
    assert created.status_code == 201
    client.post("/tags", json={"name": "urgent"})
    client.post("/tags/1/items/1")
    assert client.get("/items/1").json() == created.json()
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/items").json() == [created.json()]
