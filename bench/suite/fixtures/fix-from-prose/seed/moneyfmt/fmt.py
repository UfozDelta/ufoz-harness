from moneyfmt.round import round_money


def format_money(value) -> str:
    """Format an amount as dollars, e.g. $1,234.50 or -$1,234.57."""
    amount = round_money(value, 2)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"
