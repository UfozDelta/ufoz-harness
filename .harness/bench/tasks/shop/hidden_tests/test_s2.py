from conftest import call

CATALOG = [
    ("wireless-earbuds", "Wireless Earbuds", 2999, 50),
    ("phone-stand", "Adjustable Phone Stand", 1499, 100),
    ("led-strip-lights", "LED Strip Lights", 1999, 75),
    ("insulated-tumbler", "Insulated Tumbler", 2499, 60),
    ("yoga-mat", "Yoga Mat", 3499, 40),
    ("desk-organizer", "Bamboo Desk Organizer", 1799, 30),
]


def test_products_list(base):
    s, j = call(base, "GET", "/api/products")
    assert s == 200
    assert len(j["products"]) == 6
    for p, (slug, name, price, _stock) in zip(j["products"], CATALOG):
        assert p["slug"] == slug and p["name"] == name and p["priceCents"] == price


def test_products_list_ids_ascending(base):
    s, j = call(base, "GET", "/api/products")
    ids = [p["id"] for p in j["products"]]
    assert ids == sorted(ids) == list(range(1, 7))


def test_product_by_slug(base):
    s, j = call(base, "GET", "/api/products/wireless-earbuds")
    assert s == 200
    assert j["slug"] == "wireless-earbuds" and j["priceCents"] == 2999 and j["stock"] == 50
    assert "description" in j


def test_product_unknown_slug_404(base):
    s, j = call(base, "GET", "/api/products/does-not-exist")
    assert s == 404 and "error" in j


def test_catalog_page(base):
    s, html = call(base, "GET", "/products")
    assert s == 200
    assert 'data-testid="product-grid"' in html
    assert html.count('data-testid="product-card"') == 6
    assert 'data-testid="product-name"' in html
    assert "$29.99" in html  # wireless-earbuds price


def test_catalog_page_links_to_detail(base):
    s, html = call(base, "GET", "/products")
    assert 'href="/products/wireless-earbuds"' in html


def test_detail_page(base):
    s, html = call(base, "GET", "/products/yoga-mat")
    assert s == 200
    assert 'data-testid="product-detail"' in html
    assert 'data-testid="product-price"' in html and "$34.99" in html
    assert 'data-testid="product-stock"' in html
    assert 'data-testid="product-description"' in html


def test_detail_page_unknown_slug_404(base):
    s, html = call(base, "GET", "/products/nope-not-real")
    assert s == 404
    assert 'data-testid="not-found"' in html
