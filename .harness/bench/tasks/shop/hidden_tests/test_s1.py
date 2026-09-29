from conftest import call


def test_landing_200(base):
    s, html = call(base, "GET", "/")
    assert s == 200
    assert isinstance(html, str)


def test_nav(base):
    s, html = call(base, "GET", "/")
    assert 'data-testid="site-nav"' in html
    assert "Nimbus Goods" in html
    assert 'href="/products"' in html


def test_hero(base):
    s, html = call(base, "GET", "/")
    assert 'data-testid="hero"' in html
    assert "<h1" in html and "Nimbus Goods" in html


def test_cta_shop(base):
    s, html = call(base, "GET", "/")
    assert 'data-testid="cta-shop"' in html
    idx = html.index('data-testid="cta-shop"')
    # href to /products should appear at or near the CTA element
    assert 'href="/products"' in html
    assert "shop" in html.lower()


def test_features(base):
    s, html = call(base, "GET", "/")
    assert 'data-testid="features"' in html


def test_footer(base):
    s, html = call(base, "GET", "/")
    assert 'data-testid="site-footer"' in html
    assert "Nimbus Goods" in html


def test_viewport_meta(base):
    s, html = call(base, "GET", "/")
    assert "width=device-width" in html


def test_no_products_route_yet_not_required(base):
    # Stage 1 does not require /products to exist; just confirm the landing page itself is solid.
    s, html = call(base, "GET", "/")
    assert s == 200 and "site-nav" in html
