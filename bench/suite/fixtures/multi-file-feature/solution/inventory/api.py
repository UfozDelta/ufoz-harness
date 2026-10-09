import math

from inventory.models import Item
from inventory.store import Inventory


def list_items(inv: Inventory, sort: str | None = None, reverse: bool = False,
               page: int | None = None, per_page: int | None = None) -> list[Item]:
    """Return items sorted and optionally paged. With no paging arguments, returns all items."""
    items = inv.items(sort, reverse)
    if page is None and per_page is None:
        return items
    per_page = _check_per_page(per_page)
    if page is None:
        page = 1
    if page < 1:
        raise ValueError("page must be >= 1")
    start = (page - 1) * per_page
    return items[start:start + per_page]


def count_pages(inv: Inventory, per_page: int) -> int:
    """Number of pages needed to show every item, per_page items at a time."""
    per_page = _check_per_page(per_page)
    return math.ceil(len(inv.items()) / per_page)


def _check_per_page(per_page: int | None) -> int:
    if per_page is None:
        raise ValueError("per_page is required when paging")
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    return per_page
