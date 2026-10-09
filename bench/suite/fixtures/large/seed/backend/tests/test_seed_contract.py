"""Contract checks for the seed backend: constants and error type only.

Never instantiates the stubbed models or store (they raise NotImplementedError).
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import NAME_MAX, SKU_MAX  # noqa: E402
from app.store import DuplicateSku  # noqa: E402


def test_name_max_is_60():
    assert NAME_MAX == 60


def test_sku_max_is_32():
    assert SKU_MAX == 32


def test_duplicate_sku_is_value_error():
    assert issubclass(DuplicateSku, ValueError)
