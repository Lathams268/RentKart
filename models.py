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


class Item(db.Model):
    """A rentable item listed on the marketplace."""
    id               = db.Column(db.Integer, primary_key=True)
    owner_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category         = db.Column(db.String(50), nullable=False)
    title            = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.Text, nullable=True)
    price_per_day    = db.Column(db.Float, nullable=False)
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
    handover_note    = db.Column(db.Text, nullable=True)
    handover_photo   = db.Column(db.String(300), nullable=True)
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
