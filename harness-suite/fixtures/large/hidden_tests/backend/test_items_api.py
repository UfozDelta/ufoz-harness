"""Hidden backend tests for the large fixture: the items API built by the eight tasks."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402
from app.store import reset_store  # noqa: E402

client = TestClient(create_app())


@pytest.fixture(autouse=True)
def _reset():
    reset_store()


def _item(**overrides):
    payload = {"name": "Widget", "sku": "W-1", "price": 9.5, "quantity": 4}
    payload.update(overrides)
    return payload


# --- POST /items ---------------------------------------------------------


def test_create_item_returns_201_and_the_stored_item():
    resp = client.post("/items", json=_item())
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "name": "Widget", "sku": "W-1", "price": 9.5, "quantity": 4}


def test_ids_increment_from_one():
    first = client.post("/items", json=_item(sku="A")).json()
    second = client.post("/items", json=_item(sku="B")).json()
    assert (first["id"], second["id"]) == (1, 2)


def test_names_and_skus_are_trimmed():
    body = client.post("/items", json=_item(name="  Padded  ", sku="  W-9  ")).json()
    assert body["name"] == "Padded"
    assert body["sku"] == "W-9"


def test_quantity_defaults_to_zero():
    body = client.post("/items", json={"name": "Bare", "sku": "B-1", "price": 1.0}).json()
    assert body["quantity"] == 0


def test_duplicate_sku_is_409():
    client.post("/items", json=_item())
    resp = client.post("/items", json=_item(name="Other"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == "sku already exists"
    assert len(client.get("/items").json()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "sku": "S", "price": 1.0},
        {"name": "n", "sku": "", "price": 1.0},
        {"name": "n", "sku": "S", "price": -1},
        {"name": "n", "sku": "S", "price": 1.0, "quantity": -2},
        {"name": "x" * 61, "sku": "S", "price": 1.0},
        {"sku": "S", "price": 1.0},
        {},
    ],
)
def test_invalid_payloads_are_422(body):
    assert client.post("/items", json=body).status_code == 422


# --- GET /items and GET /items/{id} --------------------------------------


def test_list_is_empty_on_a_fresh_store():
    assert client.get("/items").json() == []


def test_list_keeps_insertion_order():
    client.post("/items", json=_item(sku="A"))
    client.post("/items", json=_item(sku="B"))
    assert [item["sku"] for item in client.get("/items").json()] == ["A", "B"]


def test_get_item_round_trips_a_created_item():
    created = client.post("/items", json=_item()).json()
    assert client.get(f"/items/{created['id']}").json() == created


def test_get_missing_item_is_404():
    resp = client.get("/items/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Item not found"


def test_get_item_rejects_a_non_integer_id():
    assert client.get("/items/abc").status_code == 422


# --- PATCH /items/{id} ---------------------------------------------------


def test_patch_updates_only_the_given_fields():
    client.post("/items", json=_item())
    resp = client.patch("/items/1", json={"price": 12.0})
    assert resp.status_code == 200
    assert resp.json()["price"] == 12.0
    assert resp.json()["name"] == "Widget"
    assert resp.json()["quantity"] == 4


def test_patch_can_zero_the_quantity():
    client.post("/items", json=_item())
    assert client.patch("/items/1", json={"quantity": 0}).json()["quantity"] == 0


def test_patch_missing_item_is_404():
    assert client.patch("/items/99", json={"price": 1.0}).status_code == 404


@pytest.mark.parametrize("body", [{"name": ""}, {"price": -1}, {"quantity": -1}])
def test_patch_rejects_invalid_values(body):
    client.post("/items", json=_item())
    assert client.patch("/items/1", json=body).status_code == 422


# --- DELETE /items/{id} --------------------------------------------------


def test_delete_answers_204_and_removes_the_item():
    client.post("/items", json=_item())
    resp = client.delete("/items/1")
    assert resp.status_code == 204
    assert resp.content == b""
    assert client.get("/items").json() == []


def test_delete_twice_is_404_the_second_time():
    client.post("/items", json=_item())
    assert client.delete("/items/1").status_code == 204
    assert client.delete("/items/1").status_code == 404


# --- GET /search ---------------------------------------------------------


def test_search_without_a_query_returns_everything():
    client.post("/items", json=_item(sku="A"))
    client.post("/items", json=_item(sku="B"))
    body = client.get("/search").json()
    assert body["count"] == 2
    assert [item["sku"] for item in body["items"]] == ["A", "B"]


def test_search_matches_names_case_insensitively():
    client.post("/items", json=_item(name="Big Widget", sku="A"))
    client.post("/items", json=_item(name="gadget", sku="B"))
    body = client.get("/search", params={"q": "wIdG"}).json()
    assert body["query"] == "wIdG"
    assert [item["sku"] for item in body["items"]] == ["A"]


def test_search_matches_skus_too():
    client.post("/items", json=_item(name="Widget", sku="ABC-1"))
    assert [item["sku"] for item in client.get("/search", params={"q": "abc"}).json()["items"]] == [
        "ABC-1"
    ]


def test_search_with_no_match_is_empty_not_an_error():
    client.post("/items", json=_item())
    body = client.get("/search", params={"q": "nope"}).json()
    assert body == {"query": "nope", "count": 0, "items": []}


def test_search_trims_the_query():
    client.post("/items", json=_item(name="Widget"))
    assert client.get("/search", params={"q": "  wid  "}).json()["count"] == 1


def test_overlong_search_query_is_422():
    assert client.get("/search", params={"q": "x" * 81}).status_code == 422


# --- GET /stats ----------------------------------------------------------


def test_stats_on_an_empty_store():
    assert client.get("/stats").json() == {
        "total": 0,
        "total_quantity": 0,
        "total_value": 0.0,
        "avg_price": 0.0,
    }


def test_stats_sums_quantities_and_value():
    client.post("/items", json=_item(price=10.0, quantity=2))
    client.post("/items", json=_item(sku="B", price=4.0, quantity=3))
    body = client.get("/stats").json()
    assert body["total"] == 2
    assert body["total_quantity"] == 5
    assert body["total_value"] == pytest.approx(32.0)
    assert body["avg_price"] == pytest.approx(16.0)


def test_stats_ignore_deleted_items():
    client.post("/items", json=_item(price=10.0, quantity=2))
    client.delete("/items/1")
    assert client.get("/stats").json()["total"] == 0


# --- store isolation + health -------------------------------------------


def test_store_is_isolated_between_tests():
    assert client.get("/items").json() == []


def test_health_survives_the_wiring():
    assert client.get("/health").json() == {"status": "ok"}
