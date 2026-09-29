from app.models import Item

items: list[Item] = []
_next_id = 1


def reset_store() -> None:
    items.clear()
    global _next_id
    _next_id = 1


def next_id() -> int:
    global _next_id
    current = _next_id
    _next_id += 1
    return current
