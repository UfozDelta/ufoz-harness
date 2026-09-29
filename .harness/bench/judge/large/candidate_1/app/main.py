from fastapi import FastAPI

from app.routers.items import router as items_router
from app.store import reset_store

app = FastAPI()

app.include_router(items_router)


@app.get("/health")
def health():
    return {"status": "ok"}
