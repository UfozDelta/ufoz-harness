"""Acceptance check for T1. Run from project root: python .harness/plans/bench-plan/checks/check_t1.py"""
import os
import sys

sys.path.insert(0, os.getcwd())

from app import store
from app.models import Item

assert isinstance(store.items, list), type(store.items)

store.reset_store()
assert store.items == [], store.items
assert store.next_id() == 1
assert store.next_id() == 2
assert store.next_id() == 3

store.items.append(Item(id=1, name="widget", price=9.5))
assert len(store.items) == 1

before = store.items
store.reset_store()
assert store.items is before, "reset_store must not rebind items"
assert store.items == [], store.items
assert store.next_id() == 1

print("STORE OK")
