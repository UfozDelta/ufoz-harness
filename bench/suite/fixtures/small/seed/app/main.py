from fastapi import FastAPI, HTTPException

from app.models import Item, ItemCreate

app = FastAPI()

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
def list_items():
    return _items


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
