"""SQLAlchemy models for RentKart."""
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """A rental marketplace user (buyer or seller)."""
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(120), nullable=False)
    phone           = db.Column(db.String(15), unique=True, nullable=False)
    village_or_city = db.Column(db.String(120), nullable=False)
    lat             = db.Column(db.Float, nullable=True)
    lng             = db.Column(db.Float, nullable=True)
    shop_name        = db.Column(db.String(120), nullable=True)
    shop_description = db.Column(db.Text, nullable=True)
    shop_slug        = db.Column(db.String(120), unique=True, nullable=True)
    shop_logo        = db.Column(db.String(300), nullable=True)
    shop_theme_color = db.Column(db.String(50), nullable=True)
    is_admin         = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("Item", backref="owner", lazy=True)
    bookings_as_renter = db.relationship("Booking", backref="renter",
                                         foreign_keys="Booking.renter_id", lazy=True)
    addresses = db.relationship("Address", backref="user", lazy=True,
                                order_by="Address.is_default.desc(), Address.created_at.desc()")
    subscriptions = db.relationship("Subscription", backref="user", lazy=True,
                                    order_by="Subscription.created_at.desc()")

    def current_plan(self) -> str:
        """Return the active plan key or 'free' if expired/none."""
        from datetime import date
        today = date.today()
        for sub in self.subscriptions:
            if sub.status in ("active", "cancelled") and sub.end_date >= today:
                return sub.plan
        return "free"

    def active_subscription(self):
        """Return the current active/cancelled unexpired Subscription object, if any."""
        from datetime import date
        today = date.today()
        for sub in self.subscriptions:
            if sub.status in ("active", "cancelled") and sub.end_date >= today:
                return sub
        return None

    @property
    def owner_review_stats(self) -> dict:
        """Calculate average rating and review count received by this user as owner."""
        reviews = self.reviews_received
        if not reviews:
            return {"avg": 0.0, "count": 0}
        avg = sum(r.rating for r in reviews) / len(reviews)
        return {"avg": round(avg, 1), "count": len(reviews)}

    @property
    def total_successful_rentals(self) -> int:
        """Count total returned/completed rentals for this owner's items."""
        count = 0
        for item in self.items:
            count += sum(1 for b in item.bookings if b.status == "returned")
        return count

    def __repr__(self):
        return f"<User {self.name} ({self.phone})>"


class Address(db.Model):
    """A saved delivery address belonging to a user (Stage 1)."""
    LABELS = ("Home", "Work", "Other")

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    label       = db.Column(db.String(20),  nullable=False, default="Home")
    full_name   = db.Column(db.String(120), nullable=False)
    phone       = db.Column(db.String(15),  nullable=False)
    house_no    = db.Column(db.String(120), nullable=False)
    building    = db.Column(db.String(120), nullable=True)
    street      = db.Column(db.String(120), nullable=False)
    landmark    = db.Column(db.String(120), nullable=True)
    city        = db.Column(db.String(120), nullable=False)
    district    = db.Column(db.String(120), nullable=True)
    state       = db.Column(db.String(120), nullable=False)
    pincode     = db.Column(db.String(6),   nullable=False)
    is_default  = db.Column(db.Boolean, nullable=False, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Address {self.id} user={self.user_id} {self.label}>"


class Item(db.Model):
    """A rentable item listed on the marketplace."""
    id               = db.Column(db.Integer, primary_key=True)
    owner_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category         = db.Column(db.String(50), nullable=False)
    title            = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.Text, nullable=True)
    price_per_day    = db.Column(db.Float, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=True, default=0)  # 0-90, applied to price_per_day
    deposit          = db.Column(db.Float, nullable=True, default=0)
    late_fee_per_day = db.Column(db.Float, nullable=True, default=0)
    lat              = db.Column(db.Float, nullable=True)
    lng              = db.Column(db.Float, nullable=True)
    image            = db.Column(db.String(300), nullable=True)
    attributes       = db.Column(db.Text, nullable=True, default="{}")  # JSON
    is_available     = db.Column(db.Boolean, default=True)
    delivery_available = db.Column(db.Boolean, nullable=True, default=False)
    delivery_charge  = db.Column(db.Float, nullable=True, default=0)
    cod_available    = db.Column(db.Boolean, nullable=True, default=True)
    purchase_price   = db.Column(db.Integer, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("Booking", backref="item", lazy=True)

    # --- helpers for the JSON attributes column ---
    def get_attributes(self) -> dict:
        """Deserialise the JSON attributes string."""
        try:
            return json.loads(self.attributes) if self.attributes else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_attributes(self, data: dict):
        """Serialise a dict into the JSON attributes column."""
        self.attributes = json.dumps(data)

    @property
    def review_stats(self) -> dict:
        """Calculate average rating and review count for this item."""
        reviews = [b.review for b in self.bookings if b.review is not None]
        if not reviews:
            return {"avg": 0.0, "count": 0}
        avg = sum(r.rating for r in reviews) / len(reviews)
        return {"avg": round(avg, 1), "count": len(reviews)}

    def __repr__(self):
        return f"<Item {self.title}>"


class Booking(db.Model):
    """A rental booking linking a renter to an item for a date range."""
    STATUSES = ("pending_payment", "requested", "approved", "picked_up", "returned", "rejected", "cancelled")
    PAYMENT_METHODS = ("upi", "gpay", "phonepe", "debit_card", "credit_card", "cash")
    PAYMENT_STATUSES = ("pending", "paid", "pay_on_pickup", "refunded", "paid_demo")

    id               = db.Column(db.Integer, primary_key=True)
    item_id          = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    renter_id        = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_date       = db.Column(db.Date, nullable=False)
    end_date         = db.Column(db.Date, nullable=False)
    days             = db.Column(db.Integer, nullable=False)
    price_per_day    = db.Column(db.Float, nullable=True)   # effective per-day price used for this booking
    price_original   = db.Column(db.Float, nullable=True)   # undiscounted original per-day price snapshot
    total_rent       = db.Column(db.Float, nullable=False)
    deposit          = db.Column(db.Float, nullable=False, default=0)
    total_payable    = db.Column(db.Float, nullable=False)
    status           = db.Column(db.String(20), nullable=False, default="requested")
    payment_method   = db.Column(db.String(20), nullable=True)
    payment_status   = db.Column(db.String(20), nullable=False, default="pending")
    commission_percent = db.Column(db.Float, nullable=False, default=10.0)
    delivery_method    = db.Column(db.String(10), nullable=True, default="pickup")
    delivery_charge    = db.Column(db.Float, nullable=True, default=0)
    platform_fee       = db.Column(db.Float, nullable=True, default=0)
    order_id           = db.Column(db.String(40), nullable=True, unique=True)
    payment_expires_at = db.Column(db.DateTime, nullable=True)
    razorpay_order_id  = db.Column(db.String(120), nullable=True)
    # ----- Shipping address snapshot (Stage 2). Copied from the Address at
    #       checkout so later edits to a saved address never change old bookings. -----
    address_id      = db.Column(db.Integer, db.ForeignKey("address.id"), nullable=True)
    ship_full_name  = db.Column(db.String(120), nullable=True)
    ship_phone      = db.Column(db.String(15),  nullable=True)
    ship_house_no   = db.Column(db.String(120), nullable=True)
    ship_building   = db.Column(db.String(120), nullable=True)
    ship_street     = db.Column(db.String(120), nullable=True)
    ship_landmark   = db.Column(db.String(120), nullable=True)
    ship_city       = db.Column(db.String(120), nullable=True)
    ship_district   = db.Column(db.String(120), nullable=True)
    ship_state      = db.Column(db.String(120), nullable=True)
    ship_pincode    = db.Column(db.String(6),   nullable=True)
    handover_note    = db.Column(db.Text, nullable=True)
    handover_photo   = db.Column(db.String(300), nullable=True)
    trustshield      = db.Column(db.Boolean, nullable=True, default=False)  # TrustShield damage-protection booking
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    return_record    = db.relationship("ReturnRecord", backref="booking", uselist=False, lazy=True)
    review           = db.relationship("Review", backref="booking", uselist=False, lazy=True)
    payments         = db.relationship("Payment", backref="booking", lazy=True,
                                       order_by="Payment.attempt_no")

    def __repr__(self):
        return f"<Booking {self.id} {self.status}>"


class Payment(db.Model):
    """A gateway payment attempt for a booking. Card details are NEVER stored."""
    STATUSES = ("created", "paid", "failed", "refunded")

    id                 = db.Column(db.Integer, primary_key=True)
    booking_id         = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    order_id           = db.Column(db.String(40), nullable=True)
    attempt_no         = db.Column(db.Integer, nullable=False, default=1)
    method             = db.Column(db.String(20), nullable=True)
    amount             = db.Column(db.Float, nullable=False, default=0)
    status             = db.Column(db.String(20), nullable=False, default="created")
    provider           = db.Column(db.String(20), nullable=False, default="mock")
    provider_payment_id = db.Column(db.String(120), nullable=True)
    failure_reason     = db.Column(db.Text, nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at            = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Payment booking={self.booking_id} attempt={self.attempt_no} status={self.status}>"


class ReturnRecord(db.Model):
    """Snapshot record of an item return and financial settlement."""
    id                  = db.Column(db.Integer, primary_key=True)
    booking_id          = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    actual_return_date  = db.Column(db.Date, nullable=False)
    late_days           = db.Column(db.Integer, nullable=False, default=0)
    late_fee_per_day    = db.Column(db.Float, nullable=False, default=0)
    late_penalty        = db.Column(db.Float, nullable=False, default=0)
    damage_level        = db.Column(db.String(20), nullable=False, default="none")
    damage_percent      = db.Column(db.Float, nullable=False, default=0)
    damage_deduction    = db.Column(db.Float, nullable=False, default=0)
    deposit_held        = db.Column(db.Float, nullable=False, default=0)
    total_deductions    = db.Column(db.Float, nullable=False, default=0)
    refund_amount       = db.Column(db.Float, nullable=False, default=0)
    extra_due           = db.Column(db.Float, nullable=False, default=0)
    platform_fee        = db.Column(db.Float, nullable=False, default=0.0)
    owner_earning       = db.Column(db.Float, nullable=False, default=0.0)
    return_note         = db.Column(db.Text, nullable=True)
    return_photo        = db.Column(db.String(300), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReturnRecord booking={self.booking_id} refund={self.refund_amount} extra={self.extra_due}>"


class Review(db.Model):
    """A rental review left by a renter for a completed booking."""
    id          = db.Column(db.Integer, primary_key=True)
    booking_id  = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating      = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment     = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer    = db.relationship("User", foreign_keys=[reviewer_id], backref="reviews_given", lazy=True)
    owner       = db.relationship("User", foreign_keys=[owner_id], backref="reviews_received", lazy=True)

    def __repr__(self):
        return f"<Review booking={self.booking_id} rating={self.rating}>"


class Subscription(db.Model):
    """Subscription record per purchase doubling as payment history."""
    STATUSES = ("active", "expired", "cancelled")
    CYCLES = ("monthly", "yearly")

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plan           = db.Column(db.String(20), nullable=False)  # free, pro, business
    billing_cycle  = db.Column(db.String(20), nullable=False, default="monthly")  # monthly, yearly
    status         = db.Column(db.String(20), nullable=False, default="active")  # active, expired, cancelled
    start_date     = db.Column(db.Date, nullable=False)
    end_date       = db.Column(db.Date, nullable=False)
    amount_paid    = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(20), nullable=False, default="upi")  # upi, card (demo)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def days_left(self) -> int:
        from datetime import date
        return max(0, (self.end_date - date.today()).days)

    def __repr__(self):
        return f"<Subscription user={self.user_id} plan={self.plan} status={self.status} end={self.end_date}>"


class Feedback(db.Model):
    """Feedback submitted by guests or registered users."""
    TYPES = ("bug", "suggestion", "complaint", "praise", "other")
    STATUSES = ("new", "reviewed", "resolved")

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    type                = db.Column(db.String(20), nullable=False)
    rating              = db.Column(db.Integer, nullable=True)  # 1-5 optional
    message             = db.Column(db.Text, nullable=False)
    page_url            = db.Column(db.String(500), nullable=True)
    related_item_id     = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)
    related_booking_id  = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True)
    status              = db.Column(db.String(20), nullable=False, default="new")
    admin_reply         = db.Column(db.Text, nullable=True)
    reply_seen          = db.Column(db.Boolean, nullable=False, default=True)
    ip_address          = db.Column(db.String(50), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    user            = db.relationship("User", foreign_keys=[user_id], backref="feedbacks", lazy=True)
    related_item    = db.relationship("Item", foreign_keys=[related_item_id], lazy=True)
    related_booking = db.relationship("Booking", foreign_keys=[related_booking_id], lazy=True)

    def __repr__(self):
        return f"<Feedback {self.id} type={self.type} status={self.status}>"


# ==========================================================================
# RentKart TrustShield models (all NEW, additive).
# ==========================================================================
class ConditionReport(db.Model):
    """A photo/video + checklist condition report for a booking phase."""
    PHASES = ("handover", "return")
    STATUSES = ("draft", "submitted", "confirmed", "mismatch", "reviewed")

    id             = db.Column(db.Integer, primary_key=True)
    booking_id     = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    item_id        = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    phase          = db.Column(db.String(12), nullable=False, default="handover")
    status         = db.Column(db.String(16), nullable=False, default="draft")
    created_by     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    confirmed_by   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    note           = db.Column(db.Text, nullable=True)
    checklist      = db.Column(db.Text, nullable=True, default="[]")   # JSON list of {item, ok}
    accessories    = db.Column(db.Text, nullable=True, default="[]")   # JSON list of strings
    angles         = db.Column(db.Text, nullable=True, default="[]")   # JSON list of angle names captured
    return_date    = db.Column(db.Date, nullable=True)
    mismatch_reason = db.Column(db.Text, nullable=True)
    confirmed_at   = db.Column(db.DateTime, nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship("Booking", backref=db.backref("condition_reports", lazy=True))
    files   = db.relationship("EvidenceFile", backref="report", lazy=True,
                              foreign_keys="EvidenceFile.report_id")

    def _jload(self, col, default):
        try:
            return json.loads(col) if col else default
        except (json.JSONDecodeError, TypeError):
            return default

    def get_checklist(self):
        return self._jload(self.checklist, [])

    def set_checklist(self, data):
        self.checklist = json.dumps(data)

    def get_accessories(self):
        return self._jload(self.accessories, [])

    def set_accessories(self, data):
        self.accessories = json.dumps(data)

    def get_angles(self):
        return self._jload(self.angles, [])

    def set_angles(self, data):
        self.angles = json.dumps(data)

    def __repr__(self):
        return f"<ConditionReport {self.id} booking={self.booking_id} {self.phase} {self.status}>"


class EvidenceFile(db.Model):
    """A PRIVATE uploaded photo/video stored under instance/evidence (uuid name)."""
    KINDS = ("photo", "video", "quote", "dispute", "damage", "overlay")

    id             = db.Column(db.Integer, primary_key=True)
    report_id      = db.Column(db.Integer, db.ForeignKey("condition_report.id"), nullable=True)
    booking_id     = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True)
    item_id        = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)
    damage_record_id = db.Column(db.Integer, db.ForeignKey("damage_record.id"), nullable=True)
    dispute_id     = db.Column(db.Integer, db.ForeignKey("dispute.id"), nullable=True)
    kind           = db.Column(db.String(12), nullable=False, default="photo")
    angle          = db.Column(db.String(40), nullable=True)
    stored_name    = db.Column(db.String(300), nullable=False)   # uuid.ext, no path
    original_name  = db.Column(db.String(300), nullable=True)
    mime           = db.Column(db.String(80), nullable=True)
    size_bytes     = db.Column(db.Integer, nullable=True, default=0)
    exif_stripped  = db.Column(db.Boolean, nullable=True, default=False)
    uploaded_by    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<EvidenceFile {self.id} {self.kind} {self.stored_name}>"


class DamageRecord(db.Model):
    """Damage history for an ITEM across ALL rentals."""
    STATUSES = ("existing", "new_proposed", "verified", "dismissed", "repaired")

    id            = db.Column(db.Integer, primary_key=True)
    item_id       = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    booking_id    = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True)
    damage_type   = db.Column(db.String(40), nullable=True)
    area          = db.Column(db.String(120), nullable=True)
    angle         = db.Column(db.String(40), nullable=True)
    description   = db.Column(db.Text, nullable=True)
    status        = db.Column(db.String(16), nullable=False, default="existing")
    source_phase  = db.Column(db.String(12), nullable=True)   # handover | return
    reported_by   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    attributed_renter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    amount        = db.Column(db.Float, nullable=True, default=0)  # verified amount (whole rupees)
    repaired_at   = db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship("Item", backref=db.backref("damage_records", lazy=True))

    def __repr__(self):
        return f"<DamageRecord {self.id} item={self.item_id} {self.status}>"


class DamageCase(db.Model):
    """A proposed damage case raised after return comparison."""
    STATUSES = ("awaiting_customer", "partially_accepted", "disputed",
                "resolved", "admin_review", "closed")

    id                = db.Column(db.Integer, primary_key=True)
    booking_id        = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    item_id           = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    created_by        = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    status            = db.Column(db.String(20), nullable=False, default="awaiting_customer")
    proposed_total    = db.Column(db.Float, nullable=False, default=0)
    verified_total    = db.Column(db.Float, nullable=False, default=0)
    review_deadline   = db.Column(db.DateTime, nullable=True)
    finalized         = db.Column(db.Boolean, nullable=False, default=False)
    return_record_id  = db.Column(db.Integer, db.ForeignKey("return_record.id"), nullable=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship("Booking", backref=db.backref("damage_cases", lazy=True))
    claims  = db.relationship("DamageClaimItem", backref="case", lazy=True,
                              order_by="DamageClaimItem.id")
    dispute = db.relationship("Dispute", backref="case", uselist=False, lazy=True)

    def __repr__(self):
        return f"<DamageCase {self.id} booking={self.booking_id} {self.status}>"


class DamageClaimItem(db.Model):
    """One claimed damage line inside a case, priced from TS_DAMAGE_RULES."""
    STATUSES = ("proposed", "accepted", "disputed", "upheld", "reduced", "rejected")

    id               = db.Column(db.Integer, primary_key=True)
    case_id          = db.Column(db.Integer, db.ForeignKey("damage_case.id"), nullable=False)
    damage_record_id = db.Column(db.Integer, db.ForeignKey("damage_record.id"), nullable=True)
    rule_key         = db.Column(db.String(40), nullable=True)
    label            = db.Column(db.String(120), nullable=True)
    severity         = db.Column(db.String(12), nullable=True)
    min_amount       = db.Column(db.Integer, nullable=True, default=0)
    max_amount       = db.Column(db.Integer, nullable=True, default=0)
    proposed_amount  = db.Column(db.Float, nullable=False, default=0)
    verified_amount  = db.Column(db.Float, nullable=False, default=0)
    percent_of_deposit = db.Column(db.Float, nullable=True)  # for 'lost'
    requires_quote   = db.Column(db.Boolean, nullable=False, default=False)
    quote_file_id    = db.Column(db.Integer, db.ForeignKey("evidence_file.id"), nullable=True)
    admin_approved   = db.Column(db.Boolean, nullable=False, default=False)
    status           = db.Column(db.String(16), nullable=False, default="proposed")
    decided_by       = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    note             = db.Column(db.Text, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DamageClaimItem {self.id} {self.rule_key} {self.status}>"


class Dispute(db.Model):
    """One dispute per case raised by the renter."""
    STATUSES = ("open", "resolved")

    id              = db.Column(db.Integer, primary_key=True)
    case_id         = db.Column(db.Integer, db.ForeignKey("damage_case.id"), unique=True, nullable=False)
    raised_by       = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reason          = db.Column(db.String(40), nullable=False)
    comment         = db.Column(db.Text, nullable=False)
    disputed_claim_ids = db.Column(db.Text, nullable=True, default="[]")  # JSON list
    status          = db.Column(db.String(12), nullable=False, default="open")
    resolution_note = db.Column(db.Text, nullable=True)
    resolved_by     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    resolved_at     = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    files = db.relationship("DisputeFile", backref="dispute", lazy=True)

    def get_claim_ids(self):
        try:
            return json.loads(self.disputed_claim_ids) if self.disputed_claim_ids else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_claim_ids(self, ids):
        self.disputed_claim_ids = json.dumps(list(ids))

    def __repr__(self):
        return f"<Dispute {self.id} case={self.case_id} {self.status}>"


class DisputeFile(db.Model):
    """Counter-evidence attached to a dispute (stored privately)."""
    id            = db.Column(db.Integer, primary_key=True)
    dispute_id    = db.Column(db.Integer, db.ForeignKey("dispute.id"), nullable=False)
    stored_name   = db.Column(db.String(300), nullable=False)
    kind          = db.Column(db.String(12), nullable=False, default="photo")
    original_name = db.Column(db.String(300), nullable=True)
    size_bytes    = db.Column(db.Integer, nullable=True, default=0)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DisputeFile {self.id} dispute={self.dispute_id}>"


class ComparisonResult(db.Model):
    """SUGGESTION-ONLY per-angle comparison output (never a charge)."""
    id                  = db.Column(db.Integer, primary_key=True)
    booking_id          = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    handover_report_id  = db.Column(db.Integer, db.ForeignKey("condition_report.id"), nullable=True)
    return_report_id    = db.Column(db.Integer, db.ForeignKey("condition_report.id"), nullable=True)
    angle               = db.Column(db.String(40), nullable=True)
    similarity          = db.Column(db.Float, nullable=True, default=1.0)
    confidence          = db.Column(db.String(12), nullable=True, default="high")
    regions_json        = db.Column(db.Text, nullable=True, default="[]")
    overlay_stored_name = db.Column(db.String(300), nullable=True)
    needs_manual        = db.Column(db.Boolean, nullable=False, default=False)
    matched_existing    = db.Column(db.Boolean, nullable=False, default=False)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)

    def get_regions(self):
        try:
            return json.loads(self.regions_json) if self.regions_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_regions(self, regions):
        self.regions_json = json.dumps(regions)

    def __repr__(self):
        return f"<ComparisonResult {self.id} angle={self.angle} sim={self.similarity}>"


# --------------------------------------------------------------------------
# TrustShield opt-in for NEW bookings (additive ORM hook; does not touch any
# existing function). Old rows already in the DB keep trustshield = 0/False.
# --------------------------------------------------------------------------
def _ts_enabled_flag() -> bool:
    """Read TRUSTSHIELD_ENABLED: app config first (test override), else module."""
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            val = current_app.config.get("TRUSTSHIELD_ENABLED", None)
            if val is not None:
                return bool(val)
    except Exception:
        pass
    import config as _config
    return bool(getattr(_config, "TRUSTSHIELD_ENABLED", False))


from sqlalchemy import event as _ts_event


@_ts_event.listens_for(Booking, "before_insert")
def _ts_new_booking_default(mapper, connection, target):
    """New bookings opt into TrustShield when the feature is enabled."""
    try:
        target.trustshield = _ts_enabled_flag()
    except Exception:
        target.trustshield = False


class PricingRule(db.Model):
    """Bulk-listing shop pricing rule (additive feature, Stage 1).

    A rule sets default price_per_day / deposit / late_fee_per_day for a
    category. When match_field/match_value are empty the rule is the category
    DEFAULT; otherwise it is a SPECIFIC rule (e.g. category=books,
    match_field=genre, match_value="Comedy / Humor").
    """
    id               = db.Column(db.Integer, primary_key=True)
    owner_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category         = db.Column(db.String(50), nullable=False)
    match_field      = db.Column(db.String(60), nullable=True)   # None => default rule
    match_value      = db.Column(db.String(120), nullable=True)
    price_per_day    = db.Column(db.Float, nullable=True, default=0)
    deposit          = db.Column(db.Float, nullable=True, default=0)
    late_fee_per_day = db.Column(db.Float, nullable=True, default=0)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User", backref=db.backref("pricing_rules", lazy=True))

    @property
    def is_default(self) -> bool:
        """True when this rule is the fallback for the whole category."""
        return not self.match_field or not self.match_value

    def __repr__(self):
        tgt = f"{self.match_field}={self.match_value}" if not self.is_default else "default"
        return f"<PricingRule {self.category} {tgt}>"

