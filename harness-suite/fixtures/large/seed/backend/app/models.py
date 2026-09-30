"""Stub: the plan's task T1 replaces this module with the real schemas.

Typed placeholders so sibling modules can be imported before T1 runs; every
constructor raises ``NotImplementedError`` until then.
"""

from pydantic import BaseModel

NAME_MAX = 60
SKU_MAX = 32


class _NotImplemented(BaseModel):
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("not implemented")


class ItemCreate(_NotImplemented):
    name: str
    sku: str
    price: float
    quantity: int


class ItemUpdate(_NotImplemented):
    name: str | None
    price: float | None
    quantity: int | None


class Item(ItemCreate):
    id: int


class SearchResult(_NotImplemented):
    query: str
    count: int
    items: list[Item]


class ItemStats(_NotImplemented):
    total: int
    total_quantity: int
    total_value: float
    avg_price: float
