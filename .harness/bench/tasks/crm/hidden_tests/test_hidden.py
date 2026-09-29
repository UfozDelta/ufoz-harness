import uuid

import pytest

from conftest import call


def client(**over):
    tag = uuid.uuid4().hex[:8]
    body = {"name": f"Parent {tag}", "email": f"p{tag}@example.com", "dob": "1985-06-15", "kids": 1}
    body.update(over)
    return body


@pytest.mark.parametrize("kids,total", [(1, 400), (2, 550), (3, 700), (10, 1750)])
def test_quote_totals(base, kids, total):
    s, j = call(base, "GET", f"/api/quote?kids={kids}")
    assert s == 200, j
    assert j == {"kids": kids, "firstKid": 350, "additionalKids": 150 * (kids - 1), "activityFee": 50, "total": total}


@pytest.mark.parametrize("q", ["0", "11", "abc", "1.5", "", "-1"])
def test_quote_invalid(base, q):
    s, j = call(base, "GET", f"/api/quote?kids={q}")
    assert s == 400, (q, j)
    assert j["field"] == "kids"


def test_create_client(base):
    b = client(kids=3, email="MiXeD.Case@Example.com".replace("MiXeD", "Mx" + uuid.uuid4().hex[:6]), name="  Ada Lovelace  ")
    s, j = call(base, "POST", "/api/clients", b)
    assert s == 201, j
    assert isinstance(j["id"], int)
    assert j["name"] == "Ada Lovelace"
    assert j["email"] == b["email"].strip().lower()
    assert j["dob"] == "1985-06-15" and j["kids"] == 3 and j["total"] == 700
    assert isinstance(j["createdAt"], str) and "T" in j["createdAt"]


@pytest.mark.parametrize("over,field", [
    ({"name": "   "}, "name"),
    ({"name": "x" * 101}, "name"),
    ({"email": "not-an-email"}, "email"),
    ({"email": "a b@c.com"}, "email"),
    ({"dob": "2999-01-01"}, "dob"),
    ({"dob": "2023-02-30"}, "dob"),
    ({"dob": "1899-12-31"}, "dob"),
    ({"dob": "15/06/1985"}, "dob"),
    ({"kids": 0}, "kids"),
    ({"kids": 11}, "kids"),
    ({"kids": 1.5}, "kids"),
    ({"kids": "2"}, "kids"),
])
def test_create_invalid_field(base, over, field):
    s, j = call(base, "POST", "/api/clients", client(**over))
    assert s == 400, (over, j)
    assert j["field"] == field and j["error"]


@pytest.mark.parametrize("missing", ["name", "email", "dob", "kids"])
def test_create_missing_field(base, missing):
    b = client()
    del b[missing]
    s, j = call(base, "POST", "/api/clients", b)
    assert s == 400 and j["field"] == missing, j


def test_first_bad_field_wins(base):
    s, j = call(base, "POST", "/api/clients", {"name": "", "email": "bad", "dob": "x", "kids": 0})
    assert s == 400 and j["field"] == "name", j


def test_non_object_body(base):
    s, _ = call(base, "POST", "/api/clients", raw=b"[1,2]")
    assert s == 400
    s, _ = call(base, "POST", "/api/clients", raw=b"not json")
    assert s == 400


def test_duplicate_email_case_insensitive(base):
    b = client()
    assert call(base, "POST", "/api/clients", b)[0] == 201
    s, j = call(base, "POST", "/api/clients", client(email=b["email"].upper()))
    assert s == 409 and j["field"] == "email", j


def test_list_newest_first_and_totals(base):
    a = call(base, "POST", "/api/clients", client(kids=1))[1]
    b = call(base, "POST", "/api/clients", client(kids=2))[1]
    s, j = call(base, "GET", "/api/clients")
    assert s == 200
    ids = [c["id"] for c in j["clients"]]
    assert ids.index(b["id"]) < ids.index(a["id"])
    assert j["count"] == len(j["clients"])
    assert j["revenue"] == sum(c["total"] for c in j["clients"])


def test_search_name_and_email(base):
    tag = uuid.uuid4().hex[:8]
    c1 = call(base, "POST", "/api/clients", client(name=f"Zed {tag}Qux"))[1]
    c2 = call(base, "POST", "/api/clients", client(email=f"{tag}zz@example.com"))[1]
    s, j = call(base, "GET", f"/api/clients?q={tag.upper()}")
    assert s == 200
    assert {c["id"] for c in j["clients"]} == {c1["id"], c2["id"]}
    assert j["count"] == 2 and j["revenue"] == c1["total"] + c2["total"]


def test_get_by_id(base):
    c = call(base, "POST", "/api/clients", client(kids=2))[1]
    s, j = call(base, "GET", f"/api/clients/{c['id']}")
    assert s == 200 and j["id"] == c["id"] and j["total"] == 550
    assert call(base, "GET", "/api/clients/999999")[0] == 404
    assert call(base, "GET", "/api/clients/abc")[0] == 404


def test_dashboard_renders_clients(base):
    c = call(base, "POST", "/api/clients", client(kids=2))[1]
    s, html = call(base, "GET", "/")
    assert s == 200
    assert 'data-testid="clients-table"' in html and 'data-testid="client-row"' in html
    assert c["name"] in html and c["email"] in html
    revenue = call(base, "GET", "/api/clients")[1]["revenue"]
    assert f'${revenue:,}' in html
    assert 'href="/intake"' in html


def test_dashboard_search(base):
    tag = uuid.uuid4().hex[:8]
    hit = call(base, "POST", "/api/clients", client(name=f"Findme {tag}"))[1]
    miss = call(base, "POST", "/api/clients", client())[1]
    s, html = call(base, "GET", f"/?q={tag}")
    assert s == 200 and hit["email"] in html and miss["email"] not in html


def test_intake_form(base):
    s, html = call(base, "GET", "/intake")
    assert s == 200
    for name in ("name", "email", "dob", "kids"):
        assert f'name="{name}"' in html, name
    assert 'type="date"' in html and 'type="number"' in html
    assert "<label" in html


def test_db_file_created(base, db_path):
    call(base, "POST", "/api/clients", client())
    assert db_path.exists() and db_path.stat().st_size > 0
