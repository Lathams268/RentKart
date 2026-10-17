"""Booking helpers – pricing, availability and blocked-date calculations."""
from datetime import date, timedelta


def calculate_days(start: date, end: date) -> int:
    """Inclusive day count. Same day = 1 day."""
    return max((end - start).days + 1, 1)


def calculate_price(item, start: date, end: date) -> dict:
    """Return pricing breakdown dict for a booking."""
    days = calculate_days(start, end)
    total_rent = days * item.price_per_day
    deposit = item.deposit or 0
    return {
        "days": days,
        "total_rent": total_rent,
        "deposit": deposit,
        "total_payable": total_rent + deposit,
    }


def is_available(item, start: date, end: date) -> bool:
    """False if any approved/picked_up booking overlaps the requested range."""
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
