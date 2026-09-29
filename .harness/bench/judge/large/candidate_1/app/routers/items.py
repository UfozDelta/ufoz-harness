from fastapi import APIRouter, HTTPException, Query

from app import store
from app.models import Item, ItemCreate

router = APIRouter()


@router.get("/items", response_model=list[Item])
def list_items(
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    name_contains: str | None = None,
):
    result = store.items
    if min_price is not None:
        result = [item for item in result if item.price >= min_price]
    if max_price is not None:
        result = [item for item in result if item.price <= max_price]
    if name_contains is not None:
        result = [item for item in result if name_contains.lower() in item.name.lower()]
    return result


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    for item in store.items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("/items", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    created = Item(id=store.next_id(), **item.model_dump())
    store.items.append(created)
    return created


@router.put("/items/{item_id}", response_model=Item)
def replace_item(item_id: int, item: ItemCreate):
    for index, existing in enumerate(store.items):
        if existing.id == item_id:
            replaced = Item(id=item_id, **item.model_dump())
            store.items[index] = replaced
            return replaced
    raise HTTPException(status_code=404, detail="Item not found")


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    for index, existing in enumerate(store.items):
        if existing.id == item_id:
            del store.items[index]
            return None
    raise HTTPException(status_code=404, detail="Item not found")
