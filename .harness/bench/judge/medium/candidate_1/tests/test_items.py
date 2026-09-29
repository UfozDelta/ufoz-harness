import pytest
from fastapi.testclient import TestClient
from app.main import app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    reset_store()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_items_empty():
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == []


def test_create_item():
    response = client.post("/items", json={"name": "widget", "price": 9.5})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "widget", "price": 9.5}


def test_create_then_list():
    client.post("/items", json={"name": "widget", "price": 9.5})
    client.post("/items", json={"name": "gadget", "price": 1.0})
    response = client.get("/items")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert [item["id"] for item in body] == [1, 2]


def test_get_item():
    created = client.post("/items", json={"name": "widget", "price": 9.5})
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json() == created.json()


def test_get_missing_item_404():
    response = client.get("/items/999")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "price": 1},
        {"name": "a", "price": -1},
        {"price": 1},
        {},
    ],
)
def test_create_invalid_returns_422(payload):
    response = client.post("/items", json=payload)
    assert response.status_code == 422


def test_store_is_isolated_between_tests():
    response = client.get("/items")
    assert response.json() == []
