from inventory import Inventory, Item, list_items


def make_inv():
    inv = Inventory()
    inv.add(Item("S-3", "bolt", 10, 0.5))
    inv.add(Item("S-1", "Anvil", 2, 99.0))
    inv.add(Item("S-2", "crate", 10, 12.25))
    return inv


def test_items_keep_insertion_order():
    assert [item.sku for item in make_inv().items()] == ["S-3", "S-1", "S-2"]


def test_list_items_without_arguments_is_insertion_order():
    assert [item.sku for item in list_items(make_inv())] == ["S-3", "S-1", "S-2"]


def test_items_returns_a_copy():
    inv = make_inv()
    inv.items().clear()
    assert len(inv.items()) == 3
