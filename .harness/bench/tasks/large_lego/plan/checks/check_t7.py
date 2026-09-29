"""Acceptance check for T7. Run from project root: python .harness/plans/bench-plan/checks/check_t7.py"""
import os

SF = "storefront"


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8").read()


cart = read("app", "cart", "page.tsx")
assert cart.lstrip().startswith(('"use client"', "'use client'")), \
    "app/cart/page.tsx must start with the 'use client' directive"
for needle in ("useCart", "removeItem", "/checkout", "total", "export default"):
    assert needle in cart, f"app/cart/page.tsx missing {needle}"
assert "empty" in cart.lower(), "app/cart/page.tsx needs an empty-cart state"

checkout = read("app", "checkout", "page.tsx")
assert checkout.lstrip().startswith(('"use client"', "'use client'")), \
    "app/checkout/page.tsx must start with the 'use client' directive"
for needle in ("trackPlaceOrder", "clearCart", "onSubmit", "preventDefault",
               "Place Order", "export default"):
    assert needle in checkout, f"app/checkout/page.tsx missing {needle}"
for field in ("fullName", "email", "address", "city", "postalCode", "country"):
    assert field in checkout, f"app/checkout/page.tsx missing shipping field {field}"
assert "fetch(" not in checkout, "checkout is a stub: no network calls allowed"
for banned in ("stripe", "Stripe", "paypal", "PayPal", "cardNumber"):
    assert banned not in checkout, f"checkout must not integrate a payment processor ({banned})"

print("CHECKOUT OK")
