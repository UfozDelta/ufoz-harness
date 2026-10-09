import pytest

from inventory import api, models, store


def make_inv():
    inv = store.Inventory()
    inv.add(models.Item("S-3", "bolt", 10, 0.5))
    inv.add(models.Item("S-1", "Anvil", 2, 99.0))
    inv.add(models.Item("S-2", "crate", 10, 12.25))
    inv.add(models.Item("S-4", "axle", 5, 3.0))
    return inv


def skus(items):
    return [item.sku for item in items]


@pytest.mark.parametrize("key, expected", [
    ("sku", ["S-1", "S-2", "S-3", "S-4"]),
    ("name", ["S-1", "S-4", "S-3", "S-2"]),
    ("qty", ["S-1", "S-4", "S-2", "S-3"]),
    ("price", ["S-3", "S-4", "S-2", "S-1"]),
])
def test_sort_by_each_key(key, expected):
    assert skus(api.list_items(make_inv(), sort=key)) == expected


def test_name_sort_is_case_insensitive_with_sku_tie_break():
    inv = store.Inventory()
    inv.add(models.Item("S-9", "Apple", 1, 1.0))
    inv.add(models.Item("S-2", "apple", 1, 1.0))
    inv.add(models.Item("S-5", "Banana", 1, 1.0))
    assert skus(api.list_items(inv, sort="name")) == ["S-2", "S-9", "S-5"]


def test_reverse_flips_sorted_order():
    assert skus(api.list_items(make_inv(), sort="sku", reverse=True)) == ["S-4", "S-3", "S-2", "S-1"]


def test_reverse_without_sort_flips_insertion_order():
    assert skus(api.list_items(make_inv(), reverse=True)) == ["S-4", "S-2", "S-1", "S-3"]


def test_no_arguments_keeps_insertion_order():
    assert skus(api.list_items(make_inv())) == ["S-3", "S-1", "S-2", "S-4"]


def test_unknown_sort_key_raises_in_list_items():
    with pytest.raises(ValueError):
        api.list_items(make_inv(), sort="colour")


def test_unknown_sort_key_raises_in_store():
    with pytest.raises(ValueError):
        make_inv().items(sort="colour")


def test_first_page():
    assert skus(api.list_items(make_inv(), sort="sku", page=1, per_page=3)) == ["S-1", "S-2", "S-3"]


def test_second_page_holds_remainder():
    assert skus(api.list_items(make_inv(), sort="sku", page=2, per_page=3)) == ["S-4"]


def test_page_past_end_is_empty():
    assert api.list_items(make_inv(), page=5, per_page=3) == []


def test_per_page_alone_returns_first_page():
    assert skus(api.list_items(make_inv(), sort="sku", per_page=2)) == ["S-1", "S-2"]


def test_page_without_per_page_raises():
    with pytest.raises(ValueError):
        api.list_items(make_inv(), page=1)


@pytest.mark.parametrize("kwargs", [
    {"page": 0, "per_page": 2},
    {"page": 1, "per_page": 0},
    {"per_page": -1},
])
def test_bad_page_numbers_raise(kwargs):
    with pytest.raises(ValueError):
        api.list_items(make_inv(), **kwargs)


def test_count_pages():
    inv = make_inv()
    assert api.count_pages(inv, 3) == 2
    assert api.count_pages(inv, 4) == 1
    assert api.count_pages(inv, 1) == 4


def test_count_pages_empty_inventory_is_zero():
    assert api.count_pages(store.Inventory(), 3) == 0


def test_count_pages_rejects_bad_per_page():
    with pytest.raises(ValueError):
        api.count_pages(make_inv(), 0)
