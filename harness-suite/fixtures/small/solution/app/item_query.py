from app.models import Item


def filter_items(
    items: list[Item],
    min_price: float | None = None,
    max_price: float | None = None,
    name_contains: str | None = None,
) -> list[Item]:
    """Items matching every supplied filter, in their original order."""
    selected = list(items)
    if min_price is not None:
        selected = [item for item in selected if item.price >= min_price]
    if max_price is not None:
        selected = [item for item in selected if item.price <= max_price]
    if name_contains:
        needle = name_contains.lower()
        selected = [item for item in selected if needle in item.name.lower()]
    return selected


def count_filtered(
    items: list[Item],
    min_price: float | None = None,
    max_price: float | None = None,
    name_contains: str | None = None,
) -> int:
    """How many items match the filters, before limit/offset is applied."""
    return len(filter_items(items, min_price, max_price, name_contains))


def select_items(
    items: list[Item],
    min_price: float | None = None,
    max_price: float | None = None,
    name_contains: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Item]:
    """The page of matching items: filters first, then offset, then limit."""
    matched = filter_items(items, min_price, max_price, name_contains)
    start = max(offset, 0)
    if limit is None:
        return matched[start:]
    return matched[start:start + limit]
