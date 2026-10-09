from decimal import ROUND_HALF_EVEN, Decimal


def round_money(value, places: int = 2) -> Decimal:
    """Round a money amount to `places` decimal places."""
    quantum = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN)
