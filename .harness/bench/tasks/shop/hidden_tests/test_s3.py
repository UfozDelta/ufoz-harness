import uuid

from conftest import call

APPROVE_CARD = {"number": "4242424242424242", "expiry": "12/30", "cvv": "123"}
DECLINE_CARD = {"number": "4000000000000002", "expiry": "12/30", "cvv": "123"}


def email():
    return f"buyer{uuid.uuid4().hex[:8]}@example.com"


def stock_of(base, slug):
    return call(base, "GET", f"/api/products/{slug}")[1]["stock"]


def test_checkout_approved_decrements_stock(base):
    before = stock_of(base, "phone-stand")
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 2, "quantity": 1}],
        "customerEmail": email(),
        "card": APPROVE_CARD,
    })
    assert s == 200, j
    assert j["status"] == "paid" and j["totalCents"] == 1499
    assert j["payment"]["status"] == "approved" and j["payment"]["last4"] == "4242"
    assert stock_of(base, "phone-stand") == before - 1


def test_checkout_declined_does_not_decrement_stock(base):
    before = stock_of(base, "led-strip-lights")
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 3, "quantity": 1}],
        "customerEmail": email(),
        "card": DECLINE_CARD,
    })
    assert s == 402, j
    assert j["status"] == "declined" and j["payment"]["status"] == "declined"
    assert j["payment"]["last4"] == "0002"
    assert stock_of(base, "led-strip-lights") == before


def test_checkout_order_retrievable(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 1, "quantity": 2}],
        "customerEmail": email(),
        "card": APPROVE_CARD,
    })
    assert s == 200
    order_id = j["orderId"]
    s2, o = call(base, "GET", f"/api/orders/{order_id}")
    assert s2 == 200
    assert o["status"] == "paid" and o["totalCents"] == 2999 * 2
    assert o["items"] == [{"productId": 1, "quantity": 2, "priceCentsEach": 2999}]


def test_checkout_unknown_order_404(base):
    assert call(base, "GET", "/api/orders/9999999")[0] == 404
    assert call(base, "GET", "/api/orders/abc")[0] == 404


def test_checkout_empty_items(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [], "customerEmail": email(), "card": APPROVE_CARD,
    })
    assert s == 400 and j["field"] == "items"


def test_checkout_unknown_product(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 999, "quantity": 1}], "customerEmail": email(), "card": APPROVE_CARD,
    })
    assert s == 400 and j["field"] == "items"


def test_checkout_quantity_exceeds_stock(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 6, "quantity": 999999}], "customerEmail": email(), "card": APPROVE_CARD,
    })
    assert s == 400 and j["field"] == "items"


def test_checkout_invalid_email(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 1, "quantity": 1}], "customerEmail": "not-an-email", "card": APPROVE_CARD,
    })
    assert s == 400 and j["field"] == "customerEmail"


def test_checkout_bad_card_number_luhn(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 1, "quantity": 1}], "customerEmail": email(),
        "card": {"number": "4242424242424241", "expiry": "12/30", "cvv": "123"},
    })
    assert s == 400 and j["field"] == "card.number"


def test_checkout_expired_card(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 1, "quantity": 1}], "customerEmail": email(),
        "card": {"number": "4242424242424242", "expiry": "01/20", "cvv": "123"},
    })
    assert s == 400 and j["field"] == "card.expiry"


def test_checkout_bad_cvv(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [{"productId": 1, "quantity": 1}], "customerEmail": email(),
        "card": {"number": "4242424242424242", "expiry": "12/30", "cvv": "12"},
    })
    assert s == 400 and j["field"] == "card.cvv"


def test_checkout_validation_order_items_before_email(base):
    s, j = call(base, "POST", "/api/checkout", {
        "items": [], "customerEmail": "bad", "card": {"number": "bad", "expiry": "bad", "cvv": "bad"},
    })
    assert s == 400 and j["field"] == "items"
