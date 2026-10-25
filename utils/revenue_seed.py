"""Demo revenue data so the admin dashboard shows numbers in development.

The seed is idempotent and is skipped for tests and when revenue is switched off.
"""
from datetime import date, datetime, timedelta

from flask import current_app

from models import Booking, Item, db
from models_revenue import (BannerAd, BookingAddon, FeaturedListing,
                            ProtectionClaim, RevenueEntry)
from utils.revenue import gst_parts, to_paise


# (days ago, hour, type, rupees, status)
DEMO_ENTRIES = (
    (0, 9, "renter_fee", 96, "pending"),
    (0, 11, "service", 30, "pending"),
    (0, 14, "owner_commission", 145, "pending"),
    (1, 10, "renter_fee", 128, "pending"),
    (1, 16, "protection", 70, "pending"),
    (2, 12, "renter_fee", 210, "earned"),
    (2, 18, "featured", 99, "earned"),
    (3, 9, "owner_commission", 96, "earned"),
    (3, 15, "service", 60, "earned"),
    (4, 11, "renter_fee", 152, "refunded"),
    (4, 11, "owner_commission", 84, "refunded"),
    (5, 10, "subscription", 399, "earned"),
    (6, 13, "renter_fee", 240, "earned"),
    (6, 17, "protection", 120, "earned"),
    (7, 9, "owner_commission", 132, "earned"),
    (8, 12, "ad", 2500, "earned"),
    (8, 16, "renter_fee", 184, "earned"),
    (9, 10, "service", 60, "earned"),
    (10, 14, "penalty_share", 75, "earned"),
    (10, 18, "renter_fee", 320, "earned"),
    (11, 9, "featured", 199, "earned"),
    (12, 11, "owner_commission", 210, "earned"),
    (13, 15, "renter_fee", 264, "earned"),
    (14, 10, "protection", 90, "earned"),
    (15, 12, "subscription", 399, "earned"),
    (16, 9, "renter_fee", 112, "earned"),
    (16, 17, "service", 90, "earned"),
    (17, 13, "owner_commission", 156, "earned"),
    (18, 11, "renter_fee", 296, "refunded"),
    (18, 11, "protection", 80, "refunded"),
    (19, 10, "featured", 99, "earned"),
    (20, 14, "renter_fee", 344, "earned"),
    (21, 16, "penalty_share", 120, "earned"),
    (22, 9, "owner_commission", 188, "earned"),
    (23, 12, "ad", 1800, "earned"),
    (24, 15, "renter_fee", 208, "earned"),
    (25, 11, "service", 120, "earned"),
    (26, 13, "protection", 110, "earned"),
    (27, 10, "renter_fee", 136, "earned"),
    (28, 17, "owner_commission", 92, "earned"),
    (29, 12, "featured", 299, "earned"),
)


def _entry(kind, gross_paise, *, when, status, booking=None, user_id=None,
           note=None):
    gst, gateway, net = gst_parts(gross_paise)
    db.session.add(RevenueEntry(
        booking_id=booking.id if booking else None,
        user_id=user_id,
        type=kind, gross=gross_paise, gst=gst, gateway_cost=gateway, net=net,
        status=status, source_ref="demo-seed", note=note,
        created_at=when, earned_at=when if status == "earned" else None,
    ))


def seed_revenue():
    """Insert ~40 ledger rows, a live banner, one featured listing and a claim."""
    if current_app.config.get("TESTING"):
        return 0
    if not current_app.config.get("REVENUE_ENABLED", True):
        return 0
    if RevenueEntry.query.count() or BannerAd.query.count():
        return 0

    now = datetime.utcnow()
    booking = Booking.query.filter(
        Booking.status.in_(["picked_up", "returned", "completed"]),
    ).order_by(Booking.id.asc()).first()
    item = Item.query.order_by(Item.id.asc()).first()
    owner_id = item.owner_id if item else None

    for days, hour, kind, rupees, status in DEMO_ENTRIES:
        when = datetime.combine((now - timedelta(days=days)).date(),
                                datetime.min.time()) + timedelta(hours=hour)
        _entry(kind, to_paise(rupees), when=when, status=status,
               booking=booking if kind in ("renter_fee", "owner_commission",
                                           "protection", "service",
                                           "penalty_share") else None,
               user_id=owner_id, note=f"Demo {kind.replace('_', ' ')}")
        if status == "refunded":
            _entry(kind, -to_paise(rupees),
                   when=when + timedelta(minutes=5), status="refunded",
                   booking=booking if kind in ("renter_fee", "owner_commission",
                                               "protection") else None,
                   user_id=owner_id, note="Demo reversal: booking cancelled")

    # One live sponsored banner (image reuses an existing illustration).
    today = date.today()
    db.session.add(BannerAd(
        title="Festive season rentals", sponsor="RentKart Partners",
        image_url="/static/illustrations/event_items.svg",
        link_url="/browse?category=event_items",
        start_date=today - timedelta(days=3), end_date=today + timedelta(days=25),
        price_paise=to_paise(2500), active=True,
    ))

    # Give the first listing a featured window with days remaining.
    if item is not None and not FeaturedListing.query.first():
        db.session.add(FeaturedListing(
            item_id=item.id, owner_id=item.owner_id, weeks=1,
            price_paise=to_paise(99), free=False, status="active",
            starts_at=now - timedelta(days=2), ends_at=now + timedelta(days=5),
            order_id="RK-FEAT-DEMO",
        ))

    # Protection add-on + one paid claim so the net-margin card is populated.
    paid_bookings = Booking.query.filter(
        Booking.status.in_(["returned", "completed"]),
    ).order_by(Booking.id.asc()).limit(2).all()
    for booking in paid_bookings:
        if BookingAddon.query.filter_by(booking_id=booking.id,
                                        kind="protection").first():
            continue
        amount = to_paise(round(float(booking.total_rent or 0) * 0.05, 2))
        if amount <= 0:
            continue
        db.session.add(BookingAddon(
            booking_id=booking.id, kind="protection",
            label="Damage protection add-on", amount_paise=amount,
            platform_paise=amount, owner_paise=0,
        ))
        if ProtectionClaim.query.count() == 0:
            db.session.add(ProtectionClaim(
                booking_id=booking.id, user_id=booking.item.owner_id,
                amount_paise=min(amount * 2, 500000), status="paid",
                note="Demo damage claim",
            ))

    db.session.commit()
    return len(DEMO_ENTRIES)
