"""CRUD router for /items."""

from fastapi import APIRouter, HTTPException, Response

from app.models import Item, ItemCreate, ItemUpdate
from app.store import DuplicateSku, get_store

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[Item])
def list_items() -> list[Item]:
    return get_store().list_items()


@router.post("", response_model=Item, status_code=201,
             responses={409: {"description": "sku already exists"}})
def create_item(payload: ItemCreate) -> Item:
    try:
        return get_store().create_item(payload)
    except DuplicateSku:
        raise HTTPException(status_code=409, detail="sku already exists")


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    item = get_store().get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=Item)
def update_item(item_id: int, payload: ItemUpdate) -> Item:
    item = get_store().update_item(item_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int) -> Response:
    if not get_store().delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(status_code=204)
