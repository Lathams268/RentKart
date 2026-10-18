"""Money helpers: one place for Decimal rounding and Rupee display formatting."""
from decimal import Decimal, ROUND_HALF_UP


def q2(value) -> Decimal:
    """Round any numeric value half-up to 2 decimals, returned as Decimal."""
    return Decimal(str(value if value is not None else 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def to_float(value) -> float:
    """Round half-up to 2 decimals and return as a plain float (for DB storage)."""
    return float(q2(value))


def inr(value) -> str:
    """Format a money value for display: rupee symbol, thousands separators,
    no decimals for whole numbers and 2 decimals otherwise.

    Examples: inr(1250) -> "Rs 1,250"; inr(1250.5) -> "Rs 1,250.50".
    """
    try:
        d = q2(value)
    except Exception:
        d = Decimal("0.00")
    if d == d.to_integral_value():
        formatted = f"{int(d):,}"
    else:
        formatted = f"{d:,.2f}"
    return f"₹{formatted}"
