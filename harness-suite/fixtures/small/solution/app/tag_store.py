from pydantic import BaseModel, Field


class Tag(BaseModel):
    id: int
    name: str
    item_ids: list[int] = []


_tags: list[Tag] = []
_next_id = 1


def reset_tag_store() -> None:
    _tags.clear()
    global _next_id
    _next_id = 1


def next_id() -> int:
    global _next_id
    current = _next_id
    _next_id += 1
    return current


def tags() -> list[Tag]:
    return list(_tags)


def get_tag(tag_id: int) -> Tag | None:
    for tag in _tags:
        if tag.id == tag_id:
            return tag
    return None


def find_by_name(name: str) -> Tag | None:
    for tag in _tags:
        if tag.name == name:
            return tag
    return None


def add_tag(name: str) -> Tag:
    created = Tag(id=next_id(), name=name, item_ids=[])
    _tags.append(created)
    return created


def attach_item(tag_id: int, item_id: int) -> Tag | None:
    tag = get_tag(tag_id)
    if tag is None:
        return None
    if item_id not in tag.item_ids:
        tag.item_ids.append(item_id)
    return tag
