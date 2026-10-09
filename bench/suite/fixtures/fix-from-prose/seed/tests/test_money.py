from decimal import Decimal

from moneyfmt import format_money, round_money


def test_round_money_drops_extra_digits():
    assert round_money("1.234", 2) == Decimal("1.23")


def test_round_money_rounds_up_above_half():
    assert round_money("1.236", 2) == Decimal("1.24")


def test_round_money_whole_units():
    assert round_money(7.9, 0) == Decimal("8")


def test_format_money_thousands_separator():
    assert format_money(1234.5) == "$1,234.50"


def test_format_money_zero():
    assert format_money(0) == "$0.00"


def test_format_money_negative():
    assert format_money(-1234.5) == "-$1,234.50"
