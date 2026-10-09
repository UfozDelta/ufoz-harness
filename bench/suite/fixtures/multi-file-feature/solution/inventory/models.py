from dataclasses import dataclass

SORT_KEYS = ("sku", "name", "qty", "price")


@dataclass
class Item:
    sku: str
    name: str
    qty: int
    price: float
