from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)


class Item(ItemCreate):
    id: int
