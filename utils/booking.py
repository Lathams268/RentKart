"""Booking helpers – pricing, availability and blocked-date calculations.

All money is calculated here (server-side only) using Decimal, rounded half-up.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from utils.money import q2


def _whole(value) -> Decimal:
    """Round half-up to a whole rupee (delivery charge / late fee per day)."""
    return Decimal(str(value if value is not None else 0)).quantize(
        Decimal("1"), rounding="ROUND_HALF_UP"
    )


def _cfg(key, default=None):
    """Read a config value: app config first (test overrides), then config module."""
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            val = current_app.config.get(key, None)
            if val is not None:
                return val
    except Exception:
        pass
    import config
    return getattr(config, key, default)


def calculate_days(start: date, end: date) -> int:
    """Inclusive day count. Same day = 1 day."""
    return max((end - start).days + 1, 1)


def effective_price(item) -> float:
    """Return the per-day price after the item's discount_percent is applied.

    Whole rupees (half-up). With no discount (None/0) the original price is
    returned unchanged so old rows behave exactly as before.
    """
    base = Decimal(str(getattr(item, "price_per_day", None) or 0))
    try:
        disc = int(getattr(item, "discount_percent", None) or 0)
    except (TypeError, ValueError):
        disc = 0
    disc = max(0, min(90, disc))
    if disc <= 0:
        return float(base)
    val = (base * Decimal(100 - disc) / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return float(val)


def calculate_price(item, start: date, end: date, user=None,
                    delivery_method: str = "pickup") -> dict:
    """Return the full pricing breakdown dict for a booking.

    This is the single source of truth for money on the site. Values are Decimals
    rounded half-up to 2 decimals. The browser never decides any amount.
    """
    dm = "delivery" if (delivery_method or "").lower() == "delivery" else "pickup"

    days = calculate_days(start, end)
    price_per_day = q2(effective_price(item))
    price_original = q2(item.price_per_day or 0)
    rent = q2(price_per_day * days)

    # Deposit after the trust discount (same rule as before: deposit * multiplier)
    deposit_original = q2(item.deposit or 0)
    if user is not None:
        from utils.trust import get_user_trust
        multiplier = Decimal(str(get_user_trust(user)["multiplier"]))
    else:
        multiplier = Decimal("1")
    deposit = q2(deposit_original * multiplier)
    trust_discount = q2(deposit_original - deposit)

    # Delivery charge: 0 for pickup; only if the item offers delivery (whole rupees)
    if dm == "delivery" and getattr(item, "delivery_available", False):
        delivery_charge = _whole(item.delivery_charge or 0)
    else:
        dm = "pickup"
        delivery_charge = Decimal("0")

    # Platform fee charged to the renter (% of rent, clamped between min and max)
    percent = Decimal(str(_cfg("RENTER_FEE_PERCENT", 0) or 0))
    fee_min = q2(_cfg("RENTER_FEE_MIN", 0) or 0)
    fee_max = q2(_cfg("RENTER_FEE_MAX", 50) or 0)
    if percent <= 0:
        platform_fee = q2(0)
    else:
        raw = q2(rent * percent / Decimal("100"))
        platform_fee = min(max(raw, fee_min), fee_max)

    total_payable = q2(rent + deposit + delivery_charge + platform_fee)
    refundable_amount = deposit
    non_refundable_amount = q2(rent + delivery_charge + platform_fee)

    # Transparency only – NOT added to the total
    possible_later_charges = []
    late_fee = _whole(getattr(item, "late_fee_per_day", 0) or 0)
    if late_fee > 0:
        possible_later_charges.append({
            "type": "late_fee", "label": "Late fee per day",
            "amount": float(late_fee), "of_deposit_percent": None,
        })
    import config as _config
    for lvl, info in _config.DAMAGE_LEVELS.items():
        if lvl == "none":
            continue
        pct = Decimal(str(info.get("percent", 0)))
        if pct <= 0:
            continue
        possible_later_charges.append({
            "type": "damage", "level": lvl, "label": info.get("label", lvl),
            "of_deposit_percent": float(pct),
            "amount": float(q2(deposit_original * pct / Decimal("100"))),
        })

    return {
        "days": days,
        "price_per_day": float(price_per_day),
        "price_original": float(price_original),
        "rent": float(rent),
        "total_rent": float(rent),          # alias kept for booking column compatibility
        "deposit_original": float(deposit_original),
        "deposit": float(deposit),
        "trust_discount": float(trust_discount),
        "delivery_method": dm,
        "delivery_charge": float(delivery_charge),
        "platform_fee": float(platform_fee),
        "total_payable": float(total_payable),
        "refundable_amount": float(refundable_amount),
        "non_refundable_amount": float(non_refundable_amount),
        "possible_later_charges": possible_later_charges,
    }


# Booking columns that a pricing dict can be snapshotted into (splat-safe).
BOOKING_PRICING_FIELDS = {
    "days", "total_rent", "deposit", "total_payable",
    "delivery_method", "delivery_charge", "platform_fee",
    "price_per_day", "price_original",
}


def booking_snapshot(pricing: dict) -> dict:
    """Filter a calculate_price dict to only Booking-column keys (safe for **)."""
    return {k: v for k, v in pricing.items() if k in BOOKING_PRICING_FIELDS}


def generate_order_id() -> str:
    """Return a unique order id like RK-YYYYMMDD-XXXXXX (random A-Z0-9)."""
    import secrets
    import string
    from datetime import datetime
    prefix = str(_cfg("ORDER_PREFIX", "RK"))
    datepart = datetime.utcnow().strftime("%Y%m%d")
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{prefix}-{datepart}-{suffix}"


def payment_expiry():
    """Return the datetime a pending payment expires (now + PENDING_PAYMENT_MINUTES)."""
    from datetime import datetime, timedelta
    minutes = int(_cfg("PENDING_PAYMENT_MINUTES", 15) or 15)
    return datetime.utcnow() + timedelta(minutes=minutes)


def is_available(item, start: date, end: date) -> bool:
    """False if any approved/picked_up booking overlaps the requested range.

    A pending_payment booking does NOT block the dates.
    """
    from models import Booking
    overlap = Booking.query.filter(
        Booking.item_id == item.id,
        Booking.status.in_(["approved", "picked_up"]),
        Booking.start_date <= end,
        Booking.end_date >= start,
    ).first()
    return overlap is None


def get_blocked_dates(item) -> list[str]:
    """Return list of ISO-formatted date strings blocked by active bookings."""
    from models import Booking
    bookings = Booking.query.filter(
        Booking.item_id == item.id,
        Booking.status.in_(["approved", "picked_up"]),
    ).all()
    blocked = set()
    for b in bookings:
        d = b.start_date
        while d <= b.end_date:
            blocked.add(d.isoformat())
            d += timedelta(days=1)
    return sorted(blocked)
