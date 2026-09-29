"""Acceptance check for T2. Run from project root: python .harness/plans/bench-plan/checks/check_t2.py"""
import os
import re

SF = "storefront"

path = os.path.join(SF, "lib", "products.ts")
assert os.path.isfile(path), f"missing file: {path}"
src = open(path, encoding="utf-8").read()

assert "export type Product" in src or "export interface Product" in src, "Product type not exported"
for field in ("slug", "name", "price", "image", "description"):
    assert re.search(rf"\b{field}\s*:", src), f"Product field missing: {field}"

assert re.search(r"export\s+const\s+products\s*:", src), "products array not exported"

slugs = re.findall(r"slug\s*:\s*[\"'`]([a-z0-9-]+)[\"'`]", src)
assert len(slugs) >= 6, f"need at least 6 products, found {len(slugs)}: {slugs}"
assert len(set(slugs)) == len(slugs), f"duplicate slugs: {slugs}"

images = re.findall(r"image\s*:\s*[\"'`]([^\"'`]+)[\"'`]", src)
assert len(images) >= 6, f"need an image on every product, found {len(images)}"
assert all(i == "/images/placeholder.svg" for i in images), f"unexpected image paths: {set(images)}"

prices = [float(p) for p in re.findall(r"price\s*:\s*([0-9]+(?:\.[0-9]+)?)", src)]
assert len(prices) >= 6, f"need a numeric price on every product, found {len(prices)}"
assert all(0 < p < 10000 for p in prices), f"implausible prices: {prices}"

assert re.search(r"export\s+function\s+getProduct\s*\(", src), "getProduct(slug) not exported"

svg = os.path.join(SF, "public", "images", "placeholder.svg")
assert os.path.isfile(svg), f"missing file: {svg}"
svg_src = open(svg, encoding="utf-8").read()
assert "<svg" in svg_src and "</svg>" in svg_src, "placeholder.svg is not a valid SVG document"

print("PRODUCTS OK")
