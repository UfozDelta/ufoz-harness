from inventory.models import Item
from inventory.store import Inventory


def list_items(inv: Inventory) -> list[Item]:
    """Return every item in the inventory, in insertion order."""
    return inv.items()
