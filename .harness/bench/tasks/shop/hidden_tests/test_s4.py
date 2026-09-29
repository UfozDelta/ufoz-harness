import uuid

from conftest import call


def msg(**over):
    tag = uuid.uuid4().hex[:8]
    body = {"name": f"Customer {tag}", "email": f"c{tag}@example.com", "message": f"Hello there {tag}"}
    body.update(over)
    return body


def test_contact_success(base):
    b = msg()
    s, j = call(base, "POST", "/api/contact", b)
    assert s == 201, j
    assert j["name"] == b["name"] and j["email"] == b["email"] and j["message"] == b["message"]
    assert isinstance(j["id"], int)
    assert isinstance(j["createdAt"], str) and "T" in j["createdAt"]


def test_contact_appears_in_list(base):
    b = msg()
    created = call(base, "POST", "/api/contact", b)[1]
    s, j = call(base, "GET", "/api/contact")
    assert s == 200
    ids = [m["id"] for m in j["messages"]]
    assert created["id"] in ids
    assert j["count"] == len(j["messages"])


def test_contact_newest_first(base):
    a = call(base, "POST", "/api/contact", msg())[1]
    b = call(base, "POST", "/api/contact", msg())[1]
    s, j = call(base, "GET", "/api/contact")
    ids = [m["id"] for m in j["messages"]]
    assert ids.index(b["id"]) < ids.index(a["id"])


def test_contact_missing_name(base):
    b = msg()
    del b["name"]
    s, j = call(base, "POST", "/api/contact", b)
    assert s == 400 and j["field"] == "name"


def test_contact_invalid_email(base):
    s, j = call(base, "POST", "/api/contact", msg(email="not-an-email"))
    assert s == 400 and j["field"] == "email"


def test_contact_empty_message(base):
    s, j = call(base, "POST", "/api/contact", msg(message="   "))
    assert s == 400 and j["field"] == "message"


def test_contact_message_too_long(base):
    s, j = call(base, "POST", "/api/contact", msg(message="x" * 2001))
    assert s == 400 and j["field"] == "message"


def test_contact_first_bad_field_wins(base):
    s, j = call(base, "POST", "/api/contact", {"name": "", "email": "bad", "message": ""})
    assert s == 400 and j["field"] == "name"


def test_contact_non_object_body(base):
    s, _ = call(base, "POST", "/api/contact", raw=b"not json")
    assert s == 400


def test_contact_page(base):
    s, html = call(base, "GET", "/contact")
    assert s == 200
    assert 'data-testid="contact-form"' in html
    for name in ("name", "email", "message"):
        assert f'name="{name}"' in html
