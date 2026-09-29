"""Hidden acceptance test, not shown to any arm. Run from the worktree root:
python -m pytest .harness/bench/tasks/large_lego/hidden_tests/test_hidden.py -q

"Did it actually get built and wired up" checks for the Lego storefront, per
.harness/bench/tasks/large_lego/plan/plan.md. No browser, no dev server: the
plan's last task (T8) runs `npm run build`, so this test reads the source tree
and asserts the build output it left behind exists. It never builds itself
(the scorer's timeout is too tight for that).
"""
import json
import os
import re

import pytest

SF = "storefront"
SKIP_DIRS = {"node_modules", ".next", ".git"}


def read(*parts):
    path = os.path.join(SF, *parts)
    assert os.path.isfile(path), f"missing file: {path}"
    return open(path, encoding="utf-8", errors="replace").read()


def all_source():
    """Every source file under storefront/, minus deps and build output."""
    chunks = []
    for root, dirs, files in os.walk(SF):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith((".ts", ".tsx", ".js", ".mjs", ".css", ".json", ".local")):
                with open(os.path.join(root, name), encoding="utf-8", errors="replace") as f:
                    chunks.append(f.read())
    return "\n".join(chunks)


@pytest.fixture(scope="module")
def source():
    return all_source()


# --- the app exists ---

@pytest.mark.parametrize("rel", [
    "package.json",
    "tsconfig.json",
    "app/layout.tsx",
    "app/page.tsx",
    "app/product/[slug]/page.tsx",
    "app/cart/page.tsx",
    "app/checkout/page.tsx",
])
def test_key_file_exists(rel):
    assert os.path.isfile(os.path.join(SF, *rel.split("/"))), f"missing {SF}/{rel}"


def test_next_is_the_framework():
    pkg = json.loads(read("package.json"))
    assert "next" in pkg.get("dependencies", {}), pkg.get("dependencies")
    assert "next build" in pkg.get("scripts", {}).get("build", "")


def test_production_build_output_present():
    assert os.path.isfile(os.path.join(SF, ".next", "BUILD_ID")), \
        "storefront/.next/BUILD_ID missing: `npm run build` was never run (or the output was deleted)"


# --- static product catalog ---

def test_six_hardcoded_products(source):
    slugs = re.findall(r"slug\s*:\s*[\"'`]([a-z0-9-]+)[\"'`]", source)
    assert len(set(slugs)) >= 6, f"expected >= 6 hardcoded products, found {sorted(set(slugs))}"
    assert re.search(r"price\s*:\s*[0-9]", source), "products need numeric prices"
    assert re.search(r"description\s*:\s*[\"'`]", source), "products need descriptions"


def test_no_backend_or_payment_integration(source):
    for banned in ("stripe", "paypal", "@stripe/", "braintree"):
        assert banned not in source.lower(), f"no payment integration expected, found {banned}"


# --- ads instrumentation ---

@pytest.mark.parametrize("env_var", [
    "NEXT_PUBLIC_META_PIXEL_ID",
    "NEXT_PUBLIC_TIKTOK_PIXEL_ID",
    "NEXT_PUBLIC_GA_MEASUREMENT_ID",
])
def test_pixel_env_var_referenced(source, env_var):
    assert f"process.env.{env_var}" in source, f"{env_var} is never read from the environment"


@pytest.mark.parametrize("snippet", ["fbq", "ttq", "gtag"])
def test_pixel_snippet_present(source, snippet):
    assert snippet in source, f"no {snippet} snippet found anywhere in {SF}/"


def test_google_tag_loader_url(source):
    assert "googletagmanager.com/gtag/js" in source, "gtag loader script URL missing"


def test_pageview_fires(source):
    assert "PageView" in source or "page_view" in source, "no PageView event wired up"


def test_add_to_cart_event(source):
    assert "AddToCart" in source or "add_to_cart" in source, "no AddToCart event wired up"


def test_place_order_event(source):
    assert any(k in source for k in ("PlaceAnOrder", "Purchase", "purchase")), \
        "no place-order / purchase conversion event wired up"


# --- utm capture ---

def test_utm_params_captured_into_session_storage(source):
    assert "utm_source" in source, "utm_source never read"
    assert "sessionStorage" in source, "UTM params must persist in sessionStorage"
    assert "location.search" in source or "URLSearchParams" in source, \
        "UTM params must come from the landing URL query string"


# --- cart is client-side only ---

def test_cart_persisted_client_side(source):
    assert "localStorage" in source, "cart must be client-side (localStorage)"


def test_checkout_collects_shipping_and_has_cta():
    checkout = read("app", "checkout", "page.tsx")
    assert "Place Order" in checkout, "checkout needs a 'Place Order' button"
    hits = sum(1 for f in ("address", "city", "postal", "country", "name", "email")
               if f.lower() in checkout.lower())
    assert hits >= 4, "checkout must collect shipping info"
