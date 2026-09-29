"""Acceptance check for T1. Run from project root: python .harness/plans/bench-plan/checks/check_t1.py"""
import pydantic

from app.models import Item, ItemCreate

assert Item(id=1, name="a", price=1.5).id == 1
assert Item(id=1, name="a", price=1.5).name == "a"
ItemCreate(name="a", price=0)

for bad in ({"name": "", "price": 1}, {"name": "a", "price": -1}, {"name": "a"}):
    try:
        ItemCreate(**bad)
    except pydantic.ValidationError:
        continue
    raise SystemExit(f"expected ValidationError for {bad}")

print("MODELS OK")
