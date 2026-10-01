"""Stub: the plan's task T2 replaces this module with the real storage layer.

Typed placeholders so sibling modules can be imported before T2 runs; every
member raises ``NotImplementedError`` until then.
"""

from app.models import Item, ItemCreate, ItemUpdate


class DuplicateSku(ValueError):
    """Raised when a create would store a sku that is already taken."""


class ItemStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        raise NotImplementedError("not implemented")

    def list_items(self) -> list[Item]:
        raise NotImplementedError("not implemented")

    def get_item(self, item_id: int) -> Item | None:
        raise NotImplementedError("not implemented")

    def create_item(self, payload: ItemCreate) -> Item:
        raise NotImplementedError("not implemented")

    def update_item(self, item_id: int, payload: ItemUpdate) -> Item | None:
        raise NotImplementedError("not implemented")

    def delete_item(self, item_id: int) -> bool:
        raise NotImplementedError("not implemented")

    def reset(self) -> None:
        raise NotImplementedError("not implemented")


def get_store() -> ItemStore:
    raise NotImplementedError("not implemented")


def reset_store() -> None:
    raise NotImplementedError("not implemented")
