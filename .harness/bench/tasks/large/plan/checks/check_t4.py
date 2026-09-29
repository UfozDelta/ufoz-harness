"""Acceptance check for T4. Run from project root: python .harness/plans/bench-plan/checks/check_t4.py"""
import os
import sys

sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)
reset_store()

client.post("/items", json={"name": "a", "price": 1})
client.post("/items", json={"name": "b", "price": 2})
client.post("/items", json={"name": "c", "price": 3})

# PUT replaces in place, keeps id and position
r = client.put("/items/2", json={"name": "b2", "price": 20.5})
assert r.status_code == 200, (r.status_code, r.text)
assert r.json() == {"id": 2, "name": "b2", "price": 20.5}, r.json()
assert client.get("/items/2").json() == {"id": 2, "name": "b2", "price": 20.5}
assert [i["id"] for i in client.get("/items").json()] == [1, 2, 3]

# PUT 404 and 422
assert client.put("/items/999", json={"name": "x", "price": 1}).status_code == 404
assert "detail" in client.put("/items/999", json={"name": "x", "price": 1}).json()
for bad in ({"name": "", "price": 1}, {"name": "a", "price": -1}, {"price": 1}, {}):
    assert client.put("/items/1", json=bad).status_code == 422, bad
assert client.get("/items/1").json() == {"id": 1, "name": "a", "price": 1}, "failed PUT must not mutate"

# DELETE
r = client.delete("/items/2")
assert r.status_code == 204, (r.status_code, r.text)
assert r.content == b"", r.content
assert client.get("/items/2").status_code == 404
assert [i["id"] for i in client.get("/items").json()] == [1, 3]
assert client.delete("/items/2").status_code == 404
assert client.delete("/items/999").status_code == 404

# ids are not reused after delete
assert client.post("/items", json={"name": "d", "price": 4}).json()["id"] == 4

reset_store()
assert client.get("/items").json() == []
assert client.post("/items", json={"name": "e", "price": 5}).json()["id"] == 1

print("PUT DELETE OK")
