"""Acceptance check for T4. Run from project root: python .harness/plans/bench-plan/checks/check_t4.py"""
import os
import re

path = os.path.join("storefront", "lib", "cart-context.tsx")
assert os.path.isfile(path), f"missing file: {path}"
src = open(path, encoding="utf-8").read()

assert src.lstrip().startswith(('"use client"', "'use client'")), \
    "cart-context.tsx must start with the 'use client' directive"

for needle in ("lego_cart", "localStorage", "createContext", "useEffect", "useState",
               "addItem", "removeItem", "clearCart", "itemCount", "total"):
    assert needle in src, f"cart-context.tsx missing {needle}"

for fn in ("CartProvider", "useCart"):
    assert re.search(rf"export\s+function\s+{fn}\s*[(<]", src) or \
        re.search(rf"export\s+const\s+{fn}\s*[:=]", src), f"cart-context.tsx missing export {fn}"

assert "products" in src, "cart-context.tsx must import product data to compute the total"
assert "throw new Error" in src, "useCart must throw when used outside CartProvider"

print("CART OK")
