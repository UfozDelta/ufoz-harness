"""Acceptance check for T3. Run from project root: python .harness/plans/bench-plan/checks/check_t3.py"""
import os
import re

SF = "storefront"


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8").read()


utm = read("lib", "utm.ts")
for needle in ("captureUtmParams", "getUtmParams", "sessionStorage", "utm_params",
               "utm_source", "utm_medium", "utm_campaign", "location.search"):
    assert needle in utm, f"lib/utm.ts missing {needle}"

analytics = read("lib", "analytics.ts")
for fn in ("trackPageView", "trackAddToCart", "trackPlaceOrder"):
    assert re.search(rf"export\s+function\s+{fn}\s*\(", analytics), f"lib/analytics.ts missing export {fn}"
for needle in ("fbq", "ttq", "gtag", "AddToCart", "getUtmParams"):
    assert needle in analytics, f"lib/analytics.ts missing {needle}"

scripts = read("components", "AnalyticsScripts.tsx")
assert scripts.lstrip().startswith(('"use client"', "'use client'")), \
    "AnalyticsScripts.tsx must start with the 'use client' directive"
for needle in ("next/script", "fbq", "ttq", "gtag", "googletagmanager.com/gtag/js",
               "dangerouslySetInnerHTML", "useEffect", "captureUtmParams", "trackPageView",
               "process.env.NEXT_PUBLIC_META_PIXEL_ID",
               "process.env.NEXT_PUBLIC_TIKTOK_PIXEL_ID",
               "process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID"):
    assert needle in scripts, f"components/AnalyticsScripts.tsx missing {needle}"
assert "export default" in scripts, "AnalyticsScripts.tsx must have a default export"

print("ANALYTICS OK")
