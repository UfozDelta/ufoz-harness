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
