import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    reset_store()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_items_empty():
    resp = client.get("/items")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_item():
    resp = client.post("/items", json={"name": "widget", "price": 9.5})
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "name": "widget", "price": 9.5}


def test_create_then_list():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    resp = client.get("/items")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert [item["id"] for item in items] == [1, 2]


def test_get_item():
    create_resp = client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.get("/items/1")
    assert resp.status_code == 200
    assert resp.json() == create_resp.json()


def test_get_missing_item_404():
    resp = client.get("/items/999")
    assert resp.status_code == 404
    assert "detail" in resp.json()


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "price": 1},
        {"name": "a", "price": -1},
        {"price": 1},
        {},
    ],
)
def test_create_invalid_returns_422(body):
    resp = client.post("/items", json=body)
    assert resp.status_code == 422


def test_store_is_isolated_between_tests():
    resp = client.get("/items")
    assert resp.json() == []


def test_put_replaces_item():
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.put("/items/1", json={"name": "gadget", "price": 3.0})
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "name": "gadget", "price": 3.0}


def test_put_keeps_list_position():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    resp = client.put("/items/1", json={"name": "updated", "price": 1.0})
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "name": "updated", "price": 1.0}
    resp = client.get("/items")
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 1, "name": "updated", "price": 1.0},
        {"id": 2, "name": "gadget", "price": 3.0},
    ]


def test_put_missing_item_404():
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.put("/items/999", json={"name": "widget", "price": 9.5})
    assert resp.status_code == 404
    assert "detail" in resp.json()


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "price": 1},
        {"name": "a", "price": -1},
        {"price": 1},
        {},
    ],
)
def test_put_invalid_returns_422(body):
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.put("/items/1", json=body)
    assert resp.status_code == 422


def test_delete_removes_item():
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.delete("/items/1")
    assert resp.status_code == 204
    assert resp.content == b""
    resp = client.get("/items/1")
    assert resp.status_code == 404
    assert "detail" in resp.json()
    resp = client.get("/items")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_missing_item_404():
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.delete("/items/999")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_delete_does_not_reuse_ids():
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.delete("/items/1")
    assert resp.status_code == 204
    assert resp.content == b""
    resp = client.post("/items", json={"name": "gadget", "price": 3.0})
    assert resp.status_code == 201
    assert resp.json() == {"id": 2, "name": "gadget", "price": 3.0}


def test_filter_min_price():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    client.post("/items", json={"name": "thing", "price": 15.0})
    resp = client.get("/items", params={"min_price": 5})
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 1, "name": "widget", "price": 9.5},
        {"id": 3, "name": "thing", "price": 15.0},
    ]


def test_filter_max_price():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    client.post("/items", json={"name": "thing", "price": 15.0})
    resp = client.get("/items", params={"max_price": 10})
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": 1, "name": "widget", "price": 9.5},
        {"id": 2, "name": "gadget", "price": 3.0},
    ]


def test_filter_name_contains_case_insensitive():
    client.post("/items", json={"name": "Widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    resp = client.get("/items", params={"name_contains": "widget"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "name": "Widget", "price": 9.5}]
    resp = client.get("/items", params={"name_contains": "WIDGET"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "name": "Widget", "price": 9.5}]


def test_filters_combined():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    client.post("/items", json={"name": "widget pro", "price": 20.0})
    resp = client.get(
        "/items",
        params={"min_price": 5, "max_price": 10, "name_contains": "widget"},
    )
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "name": "widget", "price": 9.5}]


def test_filter_no_matches_returns_empty():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 3.0})
    resp = client.get("/items", params={"min_price": 1000})
    assert resp.status_code == 200
    assert resp.json() == []
    resp = client.get("/items", params={"min_price": 10, "max_price": 5})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"min_price": "abc"},
        {"max_price": "abc"},
        {"min_price": -1},
    ],
)
def test_filter_invalid_query_returns_422(params):
    client.post("/items", json={"name": "widget", "price": 9.5})
    resp = client.get("/items", params=params)
    assert resp.status_code == 422
