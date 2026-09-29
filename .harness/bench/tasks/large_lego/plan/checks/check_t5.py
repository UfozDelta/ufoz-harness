"""Acceptance check for T5. Run from project root: python .harness/plans/bench-plan/checks/check_t5.py"""
import os

SF = "storefront"


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8").read()


layout = read("app", "layout.tsx")
assert "use client" not in layout, "layout.tsx must stay a server component"
for needle in ("globals.css", "AnalyticsScripts", "CartProvider", "<html", "<body", "export default"):
    assert needle in layout, f"app/layout.tsx missing {needle}"
assert "metadata" in layout, "app/layout.tsx must export metadata"

home = read("app", "page.tsx")
for needle in ("products", "next/link", "/product/", "<img", "export default"):
    assert needle in home, f"app/page.tsx missing {needle}"
assert "next/image" not in home, "app/page.tsx must use plain <img>, not next/image"

css = read("app", "globals.css")
for needle in ("body", "grid"):
    assert needle in css, f"app/globals.css missing {needle}"

print("HOME OK")
