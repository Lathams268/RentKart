"""Additive revenue tables.

Nothing in this module changes an existing table. Every money column is stored
as an INTEGER number of paise (INR x 100). Negative ``gross`` values are
reversal entries created when a booking is refunded.
"""
from datetime import datetime

from models import db


class RevenueSetting(db.Model):
    """One JSON row holding admin-editable revenue settings."""

    __tablename__ = "revenue_setting"

    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(60), unique=True, nullable=False)
    value      = db.Column(db.Text, nullable=False, default="{}")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RevenueSetting {self.key}>"


class RevenueEntry(db.Model):
    """A single money movement in the platform revenue ledger (paise)."""

    TYPES = ("renter_fee", "owner_commission", "featured", "subscription",
             "protection", "penalty_share", "service", "ad")
    STATUSES = ("pending", "earned", "refunded")
    TYPE_LABELS = {
        "renter_fee": "Renter platform fee",
        "owner_commission": "Owner commission",
        "featured": "Featured listing",
        "subscription": "Owner Pro subscription",
        "protection": "Damage protection",
        "penalty_share": "Late/damage share",
        "service": "Extra services",
        "ad": "Sponsored banner",
    }

    id            = db.Column(db.Integer, primary_key=True)
    booking_id    = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    type          = db.Column(db.String(30), nullable=False)
    gross         = db.Column(db.Integer, nullable=False, default=0)
    gst           = db.Column(db.Integer, nullable=False, default=0)
    gateway_cost  = db.Column(db.Integer, nullable=False, default=0)
    net           = db.Column(db.Integer, nullable=False, default=0)
    status        = db.Column(db.String(12), nullable=False, default="pending")
    source_ref    = db.Column(db.String(120), nullable=True)
    note          = db.Column(db.String(300), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    earned_at     = db.Column(db.DateTime, nullable=True)

    @property
    def type_label(self):
        return self.TYPE_LABELS.get(self.type, self.type)

    @property
    def gross_rupees(self):
        return self.gross / 100.0

    @property
    def net_rupees(self):
        return self.net / 100.0

    def __repr__(self):
        return f"<RevenueEntry {self.type} {self.gross} {self.status}>"


class BookingAddon(db.Model):
    """Optional checkout extras snapshotted per booking (paise)."""

    KINDS = ("protection", "service_delivery", "service_cleaning")

    id             = db.Column(db.Integer, primary_key=True)
    booking_id     = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    kind           = db.Column(db.String(24), nullable=False)
    label          = db.Column(db.String(80), nullable=False)
    amount_paise   = db.Column(db.Integer, nullable=False, default=0)
    platform_paise = db.Column(db.Integer, nullable=False, default=0)
    owner_paise    = db.Column(db.Integer, nullable=False, default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("booking_id", "kind",
                                          name="uq_booking_addon_kind"),)

    def __repr__(self):
        return f"<BookingAddon booking={self.booking_id} {self.kind} {self.amount_paise}>"


class FeaturedListing(db.Model):
    """A paid (or Pro-free) featured window for one listing."""

    id          = db.Column(db.Integer, primary_key=True)
    item_id     = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    owner_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    weeks       = db.Column(db.Integer, nullable=False, default=1)
    price_paise = db.Column(db.Integer, nullable=False, default=0)
    free        = db.Column(db.Boolean, nullable=False, default=False)
    status      = db.Column(db.String(12), nullable=False, default="active")
    starts_at   = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at     = db.Column(db.DateTime, nullable=False)
    order_id    = db.Column(db.String(60), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self):
        return self.status == "active" and self.ends_at >= datetime.utcnow()

    @property
    def days_left(self):
        delta = self.ends_at - datetime.utcnow()
        return max(0, delta.days + (1 if delta.seconds else 0))

    def __repr__(self):
        return f"<FeaturedListing item={self.item_id} ends={self.ends_at}>"


class ProtectionClaim(db.Model):
    """A damage claim paid out under the optional protection add-on."""

    id           = db.Column(db.Integer, primary_key=True)
    booking_id   = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    amount_paise = db.Column(db.Integer, nullable=False, default=0)
    status       = db.Column(db.String(12), nullable=False, default="paid")
    note         = db.Column(db.String(300), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("booking_id", name="uq_protection_claim_booking"),)

    def __repr__(self):
        return f"<ProtectionClaim booking={self.booking_id} {self.amount_paise}>"


class BannerAd(db.Model):
    """Admin-created sponsored banner."""

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(120), nullable=False)
    sponsor     = db.Column(db.String(120), nullable=True)
    image_url   = db.Column(db.String(500), nullable=False)
    link_url    = db.Column(db.String(500), nullable=False)
    start_date  = db.Column(db.Date, nullable=False)
    end_date    = db.Column(db.Date, nullable=False)
    price_paise = db.Column(db.Integer, nullable=False, default=0)
    active      = db.Column(db.Boolean, nullable=False, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def is_live(self, today=None):
        from datetime import date
        today = today or date.today()
        return bool(self.active) and self.start_date <= today <= self.end_date

    @property
    def impressions(self):
        return BannerEvent.query.filter_by(ad_id=self.id, kind="impression").count()

    @property
    def clicks(self):
        return BannerEvent.query.filter_by(ad_id=self.id, kind="click").count()

    def __repr__(self):
        return f"<BannerAd {self.title} live={self.is_live()}>"


class BannerEvent(db.Model):
    """Impression or click counter for a banner ad."""

    id         = db.Column(db.Integer, primary_key=True)
    ad_id      = db.Column(db.Integer, db.ForeignKey("banner_ad.id"), nullable=False)
    kind       = db.Column(db.String(12), nullable=False)  # impression | click
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BannerEvent ad={self.ad_id} {self.kind}>"
