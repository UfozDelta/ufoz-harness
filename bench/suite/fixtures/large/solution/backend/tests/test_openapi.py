"""Contract test: the OpenAPI document must describe every promised route and schema."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402

EXPECTED_OPERATIONS = {
    "/health": {"get"},
    "/items": {"get", "post"},
    "/items/{item_id}": {"get", "patch", "delete"},
    "/search": {"get"},
    "/stats": {"get"},
}

EXPECTED_SCHEMAS = {"Item", "ItemCreate", "ItemUpdate", "SearchResult", "ItemStats"}


def _schema() -> dict:
    return create_app().openapi()


def test_every_route_is_documented():
    paths = _schema()["paths"]
    assert EXPECTED_OPERATIONS.keys() <= paths.keys()


def test_every_operation_is_documented():
    paths = _schema()["paths"]
    for path, methods in EXPECTED_OPERATIONS.items():
        assert methods <= set(paths[path]), path


def test_schemas_are_published():
    schemas = _schema()["components"]["schemas"]
    assert EXPECTED_SCHEMAS <= schemas.keys()


def test_item_schema_properties():
    item = _schema()["components"]["schemas"]["Item"]
    assert set(item["properties"]) == {"id", "name", "sku", "price", "quantity"}
    # quantity carries a default, so it is optional in the wire format
    assert set(item["required"]) == {"id", "name", "sku", "price"}


def test_item_create_schema_has_no_id():
    create = _schema()["components"]["schemas"]["ItemCreate"]
    assert set(create["required"]) == {"name", "sku", "price"}
    assert "id" not in create["properties"]


def test_search_result_wraps_a_list_of_items():
    result = _schema()["components"]["schemas"]["SearchResult"]
    assert set(result["required"]) == {"query", "count", "items"}


def test_post_items_documents_201_and_409():
    responses = _schema()["paths"]["/items"]["post"]["responses"]
    assert "201" in responses
    assert "409" in responses


def test_delete_item_documents_204():
    responses = _schema()["paths"]["/items/{item_id}"]["delete"]["responses"]
    assert "204" in responses
