"""sqlite3-backed item storage (stdlib sqlite3 only, no ORM)."""

import sqlite3

from app.models import Item, ItemCreate, ItemUpdate

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0
)
"""


class DuplicateSku(ValueError):
    """Raised when a create would store a sku that is already taken."""


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        sku=row["sku"],
        price=row["price"],
        quantity=row["quantity"],
    )


class ItemStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def list_items(self) -> list[Item]:
        rows = self._conn.execute("SELECT * FROM items ORDER BY id").fetchall()
        return [_row_to_item(row) for row in rows]

    def get_item(self, item_id: int) -> Item | None:
        row = self._conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return None if row is None else _row_to_item(row)

    def create_item(self, payload: ItemCreate) -> Item:
        if self._find_by_sku(payload.sku) is not None:
            raise DuplicateSku(payload.sku)
        cursor = self._conn.execute(
            "INSERT INTO items (name, sku, price, quantity) VALUES (?, ?, ?, ?)",
            (payload.name.strip(), payload.sku.strip(), float(payload.price), payload.quantity),
        )
        self._conn.commit()
        created = self.get_item(int(cursor.lastrowid or 0))
        if created is None:  # pragma: no cover - the row was just inserted
            raise RuntimeError("inserted row vanished")
        return created

    def update_item(self, item_id: int, payload: ItemUpdate) -> Item | None:
        if self.get_item(item_id) is None:
            return None
        fields: dict[str, object] = {}
        if payload.name is not None:
            fields["name"] = payload.name.strip()
        if payload.price is not None:
            fields["price"] = float(payload.price)
        if payload.quantity is not None:
            fields["quantity"] = payload.quantity
        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields)
            self._conn.execute(
                f"UPDATE items SET {assignments} WHERE id = ?", (*fields.values(), item_id)
            )
            self._conn.commit()
        return self.get_item(item_id)

    def delete_item(self, item_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def reset(self) -> None:
        self._conn.execute("DELETE FROM items")
        self._conn.execute("DELETE FROM sqlite_sequence WHERE name = 'items'")
        self._conn.commit()

    def _find_by_sku(self, sku: str) -> Item | None:
        row = self._conn.execute(
            "SELECT * FROM items WHERE sku = ?", (sku.strip(),)
        ).fetchone()
        return None if row is None else _row_to_item(row)


_store: ItemStore | None = None


def get_store() -> ItemStore:
    global _store
    if _store is None:
        _store = ItemStore()
    return _store


def reset_store() -> None:
    get_store().reset()
