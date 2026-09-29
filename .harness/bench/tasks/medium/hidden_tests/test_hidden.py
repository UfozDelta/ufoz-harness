"""Hidden acceptance test, not shown to any arm. Run from the worktree root:
python -m pytest .harness/bench/tasks/medium/hidden_tests/test_hidden.py -q

Covers behavior beyond what the visible T4 suite checks, so an arm can't
pass just by matching the given tests verbatim.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    reset_store()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_price_zero_allowed():
    r = client.post("/items", json={"name": "free", "price": 0})
    assert r.status_code == 201, r.text


def test_negative_price_rejected():
    r = client.post("/items", json={"name": "x", "price": -0.01})
    assert r.status_code == 422


def test_empty_name_rejected():
    r = client.post("/items", json={"name": "", "price": 1})
    assert r.status_code == 422


def test_non_integer_id_is_422_or_404_not_500():
    r = client.get("/items/not-a-number")
    assert r.status_code in (404, 422), r.status_code


def test_missing_item_404_has_detail():
    r = client.get("/items/12345")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_ids_increment_and_list_order_preserved():
    a = client.post("/items", json={"name": "a", "price": 1}).json()
    b = client.post("/items", json={"name": "b", "price": 2}).json()
    assert b["id"] == a["id"] + 1
    listed = client.get("/items").json()
    assert [i["name"] for i in listed] == ["a", "b"]


def test_get_created_item_matches_post_response():
    created = client.post("/items", json={"name": "widget", "price": 3.5}).json()
    fetched = client.get(f"/items/{created['id']}").json()
    assert fetched == created


def test_store_isolated_between_tests():
    assert client.get("/items").json() == []
