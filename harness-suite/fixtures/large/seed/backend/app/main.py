"""Seed application: a health endpoint and nothing else.

The models, store, routers and the OpenAPI contract test are added by the plan's tasks.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}
