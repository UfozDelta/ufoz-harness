"""Hidden acceptance test, not shown to any arm. Run from the worktree root:
python -m pytest .harness/bench/tasks/large/hidden_tests/test_hidden.py -q

Covers PUT/DELETE/filters plus a regression check on the pre-existing
endpoints, per .harness/bench/tasks/large/plan/plan.md's decisions.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    reset_store()


def _create(name="a", price=1.0):
    return client.post("/items", json={"name": name, "price": price}).json()


# --- regression: pre-existing endpoints still work after the router split ---

def test_health_still_works():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_get_and_post_still_work():
    created = _create("widget", 3.5)
    assert created["id"] == 1 and created["name"] == "widget"
    assert client.get("/items").json() == [created]


# --- PUT ---

def test_put_replaces_and_keeps_id_and_position():
    a = _create("a", 1)
    b = _create("b", 2)
    r = client.put(f"/items/{a['id']}", json={"name": "a2", "price": 9})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["id"] == a["id"] and updated["name"] == "a2" and updated["price"] == 9
    listed = client.get("/items").json()
    assert [i["id"] for i in listed] == [a["id"], b["id"]]  # position unchanged


def test_put_missing_404():
    r = client.put("/items/999", json={"name": "x", "price": 1})
    assert r.status_code == 404 and "detail" in r.json()


def test_put_invalid_body_422():
    a = _create()
    r = client.put(f"/items/{a['id']}", json={"name": "", "price": -1})
    assert r.status_code == 422


# --- DELETE ---

def test_delete_removes_item_204():
    a = _create()
    r = client.delete(f"/items/{a['id']}")
    assert r.status_code == 204
    assert client.get(f"/items/{a['id']}").status_code == 404
    assert client.get("/items").json() == []


def test_delete_missing_404():
    r = client.delete("/items/999")
    assert r.status_code == 404


def test_ids_not_reused_after_delete():
    a = _create()
    client.delete(f"/items/{a['id']}")
    b = _create()
    assert b["id"] == a["id"] + 1


# --- filters ---

def test_filter_min_price():
    _create("cheap", 1)
    _create("mid", 5)
    _create("pricey", 10)
    names = {i["name"] for i in client.get("/items", params={"min_price": 5}).json()}
    assert names == {"mid", "pricey"}


def test_filter_max_price():
    _create("cheap", 1)
    _create("pricey", 10)
    names = {i["name"] for i in client.get("/items", params={"max_price": 5}).json()}
    assert names == {"cheap"}


def test_filter_name_contains_case_insensitive():
    _create("Widget", 1)
    _create("gadget", 1)
    _create("thing", 1)
    names = {i["name"] for i in client.get("/items", params={"name_contains": "GET"}).json()}
    assert names == {"Widget", "gadget"}


def test_filter_combined_and_no_match_is_empty_list():
    _create("widget", 1)
    _create("widget", 100)
    r = client.get("/items", params={"min_price": 5, "max_price": 50, "name_contains": "widget"})
    assert r.status_code == 200 and r.json() == []


def test_filter_min_greater_than_max_is_empty_not_error():
    _create("a", 5)
    r = client.get("/items", params={"min_price": 10, "max_price": 1})
    assert r.status_code == 200 and r.json() == []


def test_filter_invalid_price_422():
    r = client.get("/items", params={"min_price": "not-a-number"})
    assert r.status_code == 422


def test_store_isolated_between_tests():
    assert client.get("/items").json() == []
