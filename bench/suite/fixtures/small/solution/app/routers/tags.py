from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import tag_store
from app.tag_store import Tag

router = APIRouter()


class TagCreate(BaseModel):
    name: str = Field(min_length=1)


def _item_exists(item_id: int) -> bool:
    # imported lazily: app.main includes this router, so a module-level import
    # of app.main here would be circular
    from app.main import _items

    return any(item.id == item_id for item in _items)


@router.get("/tags", response_model=list[Tag])
def list_tags():
    return tag_store.tags()


@router.get("/tags/{tag_id}", response_model=Tag)
def get_tag(tag_id: int):
    tag = tag_store.get_tag(tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.post("/tags", response_model=Tag, status_code=201)
def create_tag(body: TagCreate):
    if tag_store.find_by_name(body.name) is not None:
        raise HTTPException(status_code=409, detail="Tag already exists")
    return tag_store.add_tag(body.name)


@router.post("/tags/{tag_id}/items/{item_id}", response_model=Tag)
def attach_item(tag_id: int, item_id: int):
    if tag_store.get_tag(tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    if not _item_exists(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return tag_store.attach_item(tag_id, item_id)
