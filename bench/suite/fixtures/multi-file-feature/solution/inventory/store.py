from inventory.models import SORT_KEYS, Item


class Inventory:
    """In-memory stock list; items() can sort and reverse the result."""

    def __init__(self) -> None:
        self._items: list[Item] = []

    def add(self, item: Item) -> None:
        self._items.append(item)

    def items(self, sort: str | None = None, reverse: bool = False) -> list[Item]:
        if sort is None:
            result = list(self._items)
        else:
            if sort not in SORT_KEYS:
                raise ValueError(f"unknown sort key: {sort!r}")
            result = sorted(self._items, key=lambda item: (_sort_value(item, sort), item.sku))
        if reverse:
            result.reverse()
        return result


def _sort_value(item: Item, key: str):
    if key == "name":
        return item.name.casefold()
    return getattr(item, key)
