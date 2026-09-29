"""Acceptance check for T5. Run from project root: python .harness/plans/bench-plan/checks/check_t5.py"""
import os
import sys

sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)
reset_store()

client.post("/items", json={"name": "Red Widget", "price": 5})
client.post("/items", json={"name": "blue widget", "price": 15})
client.post("/items", json={"name": "Gadget", "price": 25})


def ids(**params):
    r = client.get("/items", params=params)
    assert r.status_code == 200, (r.status_code, r.text)
    return [i["id"] for i in r.json()]


assert ids() == [1, 2, 3]
assert ids(min_price=15) == [2, 3]
assert ids(max_price=15) == [1, 2]
assert ids(min_price=10, max_price=20) == [2]
assert ids(name_contains="widget") == [1, 2], "name_contains must be case-insensitive"
assert ids(name_contains="WIDGET") == [1, 2]
assert ids(name_contains="get") == [1, 2, 3]  # "widGET" x2 and "Gadget" all contain "get"
assert ids(name_contains="") == [1, 2, 3]
assert ids(name_contains="widget", min_price=10) == [2]
assert ids(name_contains="nothing") == []
assert ids(min_price=100) == []
assert ids(min_price=20, max_price=10) == []

for bad in ({"min_price": "abc"}, {"max_price": "abc"}, {"min_price": -1}, {"max_price": -5}):
    r = client.get("/items", params=bad)
    assert r.status_code == 422, (bad, r.status_code)

# other routes untouched
assert client.get("/items/3").json()["name"] == "Gadget"
assert client.put("/items/3", json={"name": "Gadget2", "price": 26}).status_code == 200
assert client.delete("/items/3").status_code == 204
assert ids() == [1, 2]

reset_store()
assert ids() == []

print("FILTERS OK")
