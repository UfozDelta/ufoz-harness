"""Pydantic schemas shared by the store and the routers."""

from pydantic import BaseModel, Field

NAME_MAX = 60
SKU_MAX = 32


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    sku: str = Field(min_length=1, max_length=SKU_MAX)
    price: float = Field(ge=0)
    quantity: int = Field(ge=0, default=0)


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX)
    price: float | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=0)


class Item(ItemCreate):
    id: int


class SearchResult(BaseModel):
    query: str
    count: int
    items: list[Item]


class ItemStats(BaseModel):
    total: int
    total_quantity: int
    total_value: float
    avg_price: float
