"""Acceptance check for T6. Run from project root: python .harness/plans/bench-plan/checks/check_t6.py"""
import os

SF = "storefront"


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8").read()


pdp = read("app", "product", "[slug]", "page.tsx")
assert "use client" not in pdp, "the PDP must stay a server component"
for needle in ("params", "notFound", "next/navigation", "AddToCartButton",
               "generateStaticParams", "<img", "export default"):
    assert needle in pdp, f"app/product/[slug]/page.tsx missing {needle}"
assert "getProduct" in pdp or "products.find" in pdp, "PDP must look the product up by slug"
assert "next/image" not in pdp, "PDP must use plain <img>, not next/image"

btn = read("components", "AddToCartButton.tsx")
assert btn.lstrip().startswith(('"use client"', "'use client'")), \
    "AddToCartButton.tsx must start with the 'use client' directive"
for needle in ("useCart", "addItem", "trackAddToCart", "onClick", "Add to Cart", "export default"):
    assert needle in btn, f"components/AddToCartButton.tsx missing {needle}"

print("PDP OK")
