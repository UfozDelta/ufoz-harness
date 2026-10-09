from inventory.models import Item


class Inventory:
    """In-memory stock list that keeps items in insertion order."""

    def __init__(self) -> None:
        self._items: list[Item] = []

    def add(self, item: Item) -> None:
        self._items.append(item)

    def items(self) -> list[Item]:
        return list(self._items)
