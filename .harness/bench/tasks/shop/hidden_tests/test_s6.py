import uuid

from conftest import call

APPROVE_CARD = {"number": "4242424242424242", "expiry": "12/30", "cvv": "123"}
DECLINE_CARD = {"number": "4000000000000002", "expiry": "12/30", "cvv": "123"}


def email():
    return f"admin{uuid.uuid4().hex[:8]}@example.com"


def checkout(base, product_id, qty, card):
    return call(base, "POST", "/api/checkout", {
        "items": [{"productId": product_id, "quantity": qty}],
        "customerEmail": email(),
        "card": card,
    })


def test_summary_shape(base):
    s, j = call(base, "GET", "/api/admin/summary")
    assert s == 200
    assert set(j.keys()) >= {"revenueCents", "orderCount", "unitsSold", "products", "recentOrders"}
    assert len(j["products"]) == 6
    assert [p["productId"] for p in j["products"]] == list(range(1, 7))


def test_approved_order_increases_totals(base):
    before = call(base, "GET", "/api/admin/summary")[1]
    s, order = checkout(base, 1, 2, APPROVE_CARD)  # 2 x 2999 = 5998
    assert s == 200
    after = call(base, "GET", "/api/admin/summary")[1]
    assert after["revenueCents"] == before["revenueCents"] + 5998
    assert after["orderCount"] == before["orderCount"] + 1
    assert after["unitsSold"] == before["unitsSold"] + 2


def test_declined_order_does_not_increase_totals(base):
    before = call(base, "GET", "/api/admin/summary")[1]
    s, order = checkout(base, 3, 1, DECLINE_CARD)
    assert s == 402
    after = call(base, "GET", "/api/admin/summary")[1]
    assert after["revenueCents"] == before["revenueCents"]
    assert after["orderCount"] == before["orderCount"]
    assert after["unitsSold"] == before["unitsSold"]


def test_declined_order_appears_in_recent_orders(base):
    s, order = checkout(base, 3, 1, DECLINE_CARD)
    assert s == 402
    j = call(base, "GET", "/api/admin/summary")[1]
    ids = [o["id"] for o in j["recentOrders"]]
    assert order["orderId"] in ids
    row = next(o for o in j["recentOrders"] if o["id"] == order["orderId"])
    assert row["status"] == "declined"


def test_product_breakdown_reflects_purchase(base):
    before = call(base, "GET", "/api/admin/summary")[1]
    before_row = next(p for p in before["products"] if p["productId"] == 4)
    s, order = checkout(base, 4, 3, APPROVE_CARD)  # 3 x 2499 = 7497
    assert s == 200
    after = call(base, "GET", "/api/admin/summary")[1]
    after_row = next(p for p in after["products"] if p["productId"] == 4)
    assert after_row["unitsSold"] == before_row["unitsSold"] + 3
    assert after_row["revenueCents"] == before_row["revenueCents"] + 7497


def test_recent_orders_newest_first(base):
    s1, a = checkout(base, 2, 1, APPROVE_CARD)
    s2, b = checkout(base, 2, 1, APPROVE_CARD)
    j = call(base, "GET", "/api/admin/summary")[1]
    ids = [o["id"] for o in j["recentOrders"]]
    assert ids.index(b["orderId"]) < ids.index(a["orderId"])


def test_admin_page_renders(base):
    checkout(base, 5, 1, APPROVE_CARD)
    s, html = call(base, "GET", "/admin")
    assert s == 200
    assert 'data-testid="admin-revenue"' in html
    assert 'data-testid="admin-order-count"' in html
    assert 'data-testid="admin-units"' in html
    assert html.count('data-testid="admin-product-row"') == 6
    assert 'data-testid="admin-order-row"' in html


def test_admin_page_revenue_matches_api(base):
    checkout(base, 6, 1, APPROVE_CARD)
    j = call(base, "GET", "/api/admin/summary")[1]
    s, html = call(base, "GET", "/admin")
    expected = f"${j['revenueCents'] / 100:,.2f}"
    assert expected in html
