"""Application factory wiring the item and stats routers together."""

from fastapi import FastAPI

from app import items_router, stats
from app.store import get_store, reset_store

__all__ = ["app", "create_app", "get_store", "reset_store"]


def create_app() -> FastAPI:
    application = FastAPI(title="Items API", version="1.0.0")
    application.include_router(items_router.router)
    application.include_router(stats.router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
