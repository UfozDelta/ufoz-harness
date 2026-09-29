import uuid

from conftest import call

APPROVE_CARD = {"number": "4242424242424242", "expiry": "12/30", "cvv": "123"}
DECLINE_CARD = {"number": "4000000000000002", "expiry": "12/30", "cvv": "123"}


def email():
    return f"cart{uuid.uuid4().hex[:8]}@example.com"


def new_cart(base):
    return call(base, "POST", "/api/cart", {})[1]["cartId"]


def stock_of(base, slug):
    return call(base, "GET", f"/api/products/{slug}")[1]["stock"]


def test_create_cart_empty(base):
    s, j = call(base, "POST", "/api/cart", {})
    assert s == 201
    assert j["items"] == [] and j["subtotalCents"] == 0


def test_add_item(base):
    cart_id = new_cart(base)
    s, j = call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 2, "quantity": 2})
    assert s == 200, j
    assert len(j["items"]) == 1
    item = j["items"][0]
    assert item["productId"] == 2 and item["quantity"] == 2
    assert j["subtotalCents"] == 1499 * 2


def test_add_item_merges_quantity(base):
    cart_id = new_cart(base)
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 4, "quantity": 1})
    s, j = call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 4, "quantity": 2})
    assert s == 200
    assert j["items"][0]["quantity"] == 3


def test_add_item_unknown_product(base):
    cart_id = new_cart(base)
    s, j = call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 999, "quantity": 1})
    assert s == 400 and j["field"] == "productId"


def test_add_item_bad_quantity(base):
    cart_id = new_cart(base)
    s, j = call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 1, "quantity": 0})
    assert s == 400 and j["field"] == "quantity"


def test_add_item_exceeds_stock(base):
    cart_id = new_cart(base)
    s, j = call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 6, "quantity": 999999})
    assert s == 400 and j["field"] == "quantity"


def test_update_and_remove_item(base):
    cart_id = new_cart(base)
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 3, "quantity": 1})
    s, j = call(base, "PATCH", f"/api/cart/{cart_id}/items/3", {"quantity": 5})
    assert s == 200 and j["items"][0]["quantity"] == 5
    s2, j2 = call(base, "DELETE", f"/api/cart/{cart_id}/items/3")
    assert s2 == 200 and j2["items"] == []


def test_unknown_cart_404(base):
    assert call(base, "GET", "/api/cart/9999999")[0] == 404
    assert call(base, "POST", "/api/cart/9999999/items", {"productId": 1, "quantity": 1})[0] == 404


def test_shipping_rule(base):
    cart_id = new_cart(base)
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 2, "quantity": 1})  # 1499 cents
    s, j = call(base, "GET", f"/api/cart/{cart_id}")
    assert j["subtotalCents"] < 5000 and j["shippingCents"] == 500
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 5, "quantity": 1})  # +3499 = 4998
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 1, "quantity": 1})  # +2999 = 7997
    s2, j2 = call(base, "GET", f"/api/cart/{cart_id}")
    assert j2["subtotalCents"] >= 5000 and j2["shippingCents"] == 0


def test_checkout_approved_clears_cart_and_decrements_stock(base):
    before = stock_of(base, "phone-stand")
    cart_id = new_cart(base)
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 2, "quantity": 1})
    s, j = call(base, "POST", f"/api/cart/{cart_id}/checkout", {"customerEmail": email(), "card": APPROVE_CARD})
    assert s == 200, j
    assert j["status"] == "paid"
    assert stock_of(base, "phone-stand") == before - 1
    s2, j2 = call(base, "GET", f"/api/cart/{cart_id}")
    assert j2["items"] == []


def test_checkout_declined_keeps_cart_and_stock(base):
    before = stock_of(base, "led-strip-lights")
    cart_id = new_cart(base)
    call(base, "POST", f"/api/cart/{cart_id}/items", {"productId": 3, "quantity": 1})
    s, j = call(base, "POST", f"/api/cart/{cart_id}/checkout", {"customerEmail": email(), "card": DECLINE_CARD})
    assert s == 402
    assert stock_of(base, "led-strip-lights") == before
    s2, j2 = call(base, "GET", f"/api/cart/{cart_id}")
    assert len(j2["items"]) == 1


def test_checkout_empty_cart(base):
    cart_id = new_cart(base)
    s, j = call(base, "POST", f"/api/cart/{cart_id}/checkout", {"customerEmail": email(), "card": APPROVE_CARD})
    assert s == 400 and j["field"] == "items"


def test_cart_page(base):
    s, html = call(base, "GET", "/cart")
    assert s == 200
    assert 'data-testid="cart-page"' in html
