"""Read-only search and stats endpoints."""

from fastapi import APIRouter, Query

from app.models import ItemStats, SearchResult
from app.store import get_store

router = APIRouter(tags=["stats"])


@router.get("/search", response_model=SearchResult)
def search_items(q: str = Query(default="", max_length=80)) -> SearchResult:
    needle = q.strip().lower()
    matches = [
        item
        for item in get_store().list_items()
        if not needle or needle in item.name.lower() or needle in item.sku.lower()
    ]
    return SearchResult(query=q, count=len(matches), items=matches)


@router.get("/stats", response_model=ItemStats)
def item_stats() -> ItemStats:
    items = get_store().list_items()
    total = len(items)
    total_quantity = sum(item.quantity for item in items)
    total_value = round(sum(item.price * item.quantity for item in items), 2)
    avg_price = round(total_value / total, 2) if total else 0.0
    return ItemStats(
        total=total,
        total_quantity=total_quantity,
        total_value=total_value,
        avg_price=avg_price,
    )
