from decimal import Decimal

import pytest

from moneyfmt import format_money
from moneyfmt.round import round_money


@pytest.mark.parametrize("value, expected", [
    ("0.125", Decimal("0.13")),
    ("0.135", Decimal("0.14")),
    (2.675, Decimal("2.68")),
    ("2.665", Decimal("2.67")),
    ("1.005", Decimal("1.01")),
    ("1234.565", Decimal("1234.57")),
])
def test_positive_half_rounds_up(value, expected):
    assert round_money(value, 2) == expected


@pytest.mark.parametrize("value, expected", [
    ("-0.125", Decimal("-0.13")),
    ("-2.665", Decimal("-2.67")),
])
def test_negative_half_rounds_away_from_zero(value, expected):
    assert round_money(value, 2) == expected


def test_half_with_zero_places_rounds_up():
    assert round_money("2.5", 0) == Decimal("3")


def test_half_with_zero_places_negative():
    assert round_money("-2.5", 0) == Decimal("-3")


def test_non_half_values_round_normally():
    assert round_money("3.5", 0) == Decimal("4")
    assert round_money("0.124", 2) == Decimal("0.12")


def test_float_input_uses_its_decimal_text():
    assert round_money(0.125, 2) == Decimal("0.13")


def test_format_money_shows_half_cent_rounded_up():
    assert format_money("0.125") == "$0.13"


def test_format_money_negative_half_cent():
    assert format_money(-0.125) == "-$0.13"


def test_format_money_thousands_with_tie():
    assert format_money("1234.565") == "$1,234.57"


def test_format_money_tie_rounds_up_to_next_dollar():
    assert format_money("99.995") == "$100.00"
