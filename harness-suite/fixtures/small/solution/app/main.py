from fastapi import FastAPI, HTTPException, Query, Response

from app.item_query import count_filtered, select_items
from app.models import Item, ItemCreate

try:  # the tags router lands in a parallel task; keep this import optional
    from app.routers.tags import router as tags_router
except ImportError:  # pragma: no cover - tags router not written yet
    tags_router = None

app = FastAPI()

if tags_router is not None:
    app.include_router(tags_router)

_items: list[Item] = []
_next_id = 1


def reset_store() -> None:
    _items.clear()
    global _next_id
    _next_id = 1


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items", response_model=list[Item])
def list_items(
    response: Response,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    name_contains: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    response.headers["X-Total-Count"] = str(
        count_filtered(_items, min_price, max_price, name_contains)
    )
    return select_items(_items, min_price, max_price, name_contains, limit, offset)


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    for item in _items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/items", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    global _next_id
    created = Item(id=_next_id, **item.model_dump())
    _next_id += 1
    _items.append(created)
    return created
