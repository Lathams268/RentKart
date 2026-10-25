"""Revenue features: fees, commission, add-ons, ledger and helpers.

All new money values are INTEGER paise. Existing booking columns stay in rupees,
so conversion happens only at the boundary (``to_paise`` / ``from_paise``).
Set ``REVENUE_ENABLED=False`` to fall back to the pre-revenue behaviour: the
legacy ``RENTER_FEE_*`` config block keeps working untouched.
"""
import json
import os
import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import current_app, g, has_app_context

from utils.money import inr


# ---------------------------------------------------------------------------
# Config + settings
# ---------------------------------------------------------------------------
def _cfg(key, default=None):
    from utils.booking import _cfg as booking_cfg
    return booking_cfg(key, default)


def _env_defaults():
    """Effective defaults from config.py / environment."""
    return {
        "renter_fee_enabled": bool(_cfg("REVENUE_RENTER_FEE_ENABLED", True)),
        "renter_fee_percent": float(_cfg("REVENUE_RENTER_FEE_PERCENT", 8.0)),
        "renter_fee_min_paise": int(_cfg("REVENUE_RENTER_FEE_MIN_PAISE", 2900)),
        "renter_fee_max_paise": int(_cfg("REVENUE_RENTER_FEE_MAX_PAISE", 99900)),
        "renter_fee_category_overrides": dict(
            _cfg("REVENUE_RENTER_FEE_CATEGORY_OVERRIDES", {}) or {}),

        "owner_commission_enabled": bool(_cfg("REVENUE_OWNER_COMMISSION_ENABLED", True)),
        "owner_commission_percent": float(_cfg("REVENUE_OWNER_COMMISSION_PERCENT", 5.0)),
        "owner_commission_waiver_bookings": int(
            _cfg("REVENUE_COMMISSION_WAIVER_BOOKINGS", 3)),

        "featured_enabled": bool(_cfg("REVENUE_FEATURED_ENABLED", True)),
        "featured_prices_paise": dict(_cfg(
            "REVENUE_FEATURED_PRICES_PAISE",
            {"1": 9900, "2": 19900, "3": 29900})),

        "owner_pro_enabled": bool(_cfg("REVENUE_OWNER_PRO_ENABLED", True)),
        "owner_pro_price_paise": int(_cfg("REVENUE_OWNER_PRO_PRICE_PAISE", 39900)),
        "owner_pro_yearly_discount_percent": float(
            _cfg("REVENUE_OWNER_PRO_YEARLY_DISCOUNT_PERCENT", 20.0)),
        "owner_pro_commission_percent": float(
            _cfg("REVENUE_OWNER_PRO_COMMISSION_PERCENT", 2.0)),
        "owner_pro_photos": int(_cfg("REVENUE_OWNER_PRO_PHOTOS", 12)),
        "owner_pro_free_featured_days": int(
            _cfg("REVENUE_OWNER_PRO_FREE_FEATURED_DAYS", 7)),

        "protection_enabled": bool(_cfg("REVENUE_PROTECTION_ENABLED", True)),
        "protection_percent": float(_cfg("REVENUE_PROTECTION_PERCENT", 5.0)),
        "protection_cover_paise": int(_cfg("REVENUE_PROTECTION_COVER_PAISE", 500000)),

        "penalty_share_enabled": bool(_cfg("REVENUE_PENALTY_SHARE_ENABLED", True)),
        "penalty_share_percent": float(_cfg("REVENUE_PENALTY_SHARE_PERCENT", 15.0)),

        "services_enabled": bool(_cfg("REVENUE_SERVICES_ENABLED", True)),
        "service_delivery_paise": int(_cfg("REVENUE_SERVICE_DELIVERY_PAISE", 9900)),
        "service_cleaning_paise": int(_cfg("REVENUE_SERVICE_CLEANING_PAISE", 19900)),
        "service_margin_percent": float(_cfg("REVENUE_SERVICE_MARGIN_PERCENT", 30.0)),

        "ads_enabled": bool(_cfg("REVENUE_ADS_ENABLED", True)),
        "ledger_enabled": bool(_cfg("REVENUE_LEDGER_ENABLED", True)),
        "gst_percent": float(_cfg("REVENUE_GST_PERCENT", 18.0)),
        "gateway_percent": float(_cfg("REVENUE_GATEWAY_PERCENT", 2.0)),
    }


def default_settings():
    return _env_defaults()


def revenue_enabled():
    """Master switch. False restores the old checkout / ledger behaviour."""
    return bool(_cfg("REVENUE_ENABLED", True))


def _cache_get(name):
    if has_app_context():
        try:
            return getattr(g, name, None)
        except Exception:
            return None
    return None


def _cache_set(name, value):
    if has_app_context():
        try:
            setattr(g, name, value)
        except Exception:
            pass


def get_settings():
    """Defaults merged with the single admin-editable JSON row (cached/request)."""
    if not revenue_enabled():
        s = default_settings()
        for key in ("renter_fee_enabled", "owner_commission_enabled", "featured_enabled",
                    "owner_pro_enabled", "protection_enabled", "penalty_share_enabled",
                    "services_enabled", "ads_enabled", "ledger_enabled"):
            s[key] = False
        return s

    cached = _cache_get("_rk_revenue_settings")
    if cached is not None:
        return cached

    settings = default_settings()
    if has_app_context():
        try:
            from models_revenue import RevenueSetting
            row = RevenueSetting.query.filter_by(key="revenue").first()
            if row and row.value:
                stored = json.loads(row.value)
                for key, val in stored.items():
                    if key in settings:
                        settings[key] = val
        except Exception:
            # Table not created yet (or a read-only context): use defaults.
            pass
    _cache_set("_rk_revenue_settings", settings)
    return settings


def save_settings(changes):
    """Merge and persist settings. Returns the merged dict."""
    from models import db
    from models_revenue import RevenueSetting

    merged = dict(get_settings())
    merged.update({k: v for k, v in (changes or {}).items() if k in merged})
    row = RevenueSetting.query.filter_by(key="revenue").first()
    if row is None:
        row = RevenueSetting(key="revenue", value=json.dumps(merged))
        db.session.add(row)
    else:
        row.value = json.dumps(merged)
    db.session.commit()
    _cache_set("_rk_revenue_settings", None)
    return merged


def features():
    """Per-feature on/off map. Every value is False when the master flag is off."""
    s = get_settings()
    on = revenue_enabled()
    return {
        "renter_fee": on and bool(s["renter_fee_enabled"]),
        "owner_commission": on and bool(s["owner_commission_enabled"]),
        "featured": on and bool(s["featured_enabled"]),
        "owner_pro": on and bool(s["owner_pro_enabled"]),
        "protection": on and bool(s["protection_enabled"]),
        "penalty_share": on and bool(s["penalty_share_enabled"]),
        "services": on and bool(s["services_enabled"]),
        "ads": on and bool(s["ads_enabled"]),
        "ledger": on and bool(s["ledger_enabled"]),
    }


# ---------------------------------------------------------------------------
# Money helpers (paise)
# ---------------------------------------------------------------------------
def to_paise(rupees):
    return int((Decimal(str(rupees or 0)) * 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def from_paise(paise):
    return float((Decimal(int(paise or 0)) / 100).quantize(Decimal("0.01")))


def paise_inr(paise):
    return inr(from_paise(paise))


def _round_paise(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Fee / commission / add-on math
# ---------------------------------------------------------------------------
def fee_percent_for(category=None):
    s = get_settings()
    overrides = s.get("renter_fee_category_overrides") or {}
    if category and category in overrides:
        try:
            return float(overrides[category])
        except (TypeError, ValueError):
            pass
    return float(s["renter_fee_percent"])


def renter_fee_paise(rent_rupees, category=None):
    """Percent of rent, clamped to min/max. Returns 0 when the feature is off."""
    if not features()["renter_fee"]:
        return 0
    try:
        rent = Decimal(str(rent_rupees or 0))
    except Exception:
        rent = Decimal("0")
    if rent <= 0:
        return 0
    s = get_settings()
    percent = Decimal(str(fee_percent_for(category)))
    raw = (rent * 100) * percent / Decimal("100")
    fee = _round_paise(raw)
    return min(max(fee, int(s["renter_fee_min_paise"])), int(s["renter_fee_max_paise"]))


def owner_pro_active(user):
    if not user or not features()["owner_pro"]:
        return False
    try:
        if user.current_plan() == "owner_pro":
            return True
    except Exception:
        pass
    # Owner Pro can be bought on top of Pro/Business, so check its own window.
    try:
        from models import Subscription
        today = date.today()
        return Subscription.query.filter(
            Subscription.user_id == user.id,
            Subscription.plan == "owner_pro",
            Subscription.status.in_(["active", "cancelled"]),
            Subscription.end_date >= today,
        ).first() is not None
    except Exception:
        return False


def _paid_booking_count(owner):
    from models import Booking, Item
    item_ids = [row.id for row in Item.query.filter_by(owner_id=owner.id).all()]
    if not item_ids:
        return 0
    return Booking.query.filter(
        Booking.item_id.in_(item_ids),
        Booking.payment_status.in_(["paid", "paid_demo"]),
        Booking.status.notin_(["cancelled", "rejected", "pending_payment"]),
    ).count()


def commission_percent_for(owner, default=None):
    """Owner commission percent after waiver / Pro benefits.

    When the revenue feature is off (or no ``default`` and no plan), the existing
    plan commission is returned so old behaviour is unchanged.
    """
    if default is None:
        try:
            from utils.plans import commission_for
            default = commission_for(owner)
        except Exception:
            default = 10.0
    if not features()["owner_commission"]:
        return float(default)
    s = get_settings()
    if owner_pro_active(owner):
        return float(s["owner_pro_commission_percent"])
    waiver = int(s["owner_commission_waiver_bookings"] or 0)
    if waiver and owner is not None and _paid_booking_count(owner) < waiver:
        return 0.0
    return float(s["owner_commission_percent"])


def protection_fee_paise(rent_rupees):
    if not features()["protection"]:
        return 0
    s = get_settings()
    rent = Decimal(str(rent_rupees or 0))
    if rent <= 0:
        return 0
    return _round_paise((rent * 100) * Decimal(str(s["protection_percent"])) / Decimal("100"))


def protection_cover_paise():
    return int(get_settings()["protection_cover_paise"])


def service_price_paise(kind):
    s = get_settings()
    if kind == "service_delivery":
        return int(s["service_delivery_paise"])
    if kind == "service_cleaning":
        return int(s["service_cleaning_paise"])
    return 0


def service_margin_paise(kind):
    price = service_price_paise(kind)
    pct = Decimal(str(get_settings()["service_margin_percent"]))
    return _round_paise(Decimal(price) * pct / Decimal("100"))


def build_addon_lines(rent_rupees, selected=None):
    """Return add-on lines from a checkbox map. Amounts are paise + rupees."""
    selected = selected or {}
    feats = features()
    lines = []
    if feats["protection"] and selected.get("protection"):
        amount = protection_fee_paise(rent_rupees)
        if amount > 0:
            lines.append({
                "kind": "protection",
                "label": "Damage protection add-on",
                "amount_paise": amount,
                "platform_paise": amount,
                "owner_paise": 0,
                "amount": from_paise(amount),
            })
    if feats["services"]:
        specs = (
            ("service_delivery", "service_delivery", "Doorstep delivery / pickup"),
            ("service_cleaning", "service_cleaning", "Cleaning / dry-cleaning"),
        )
        for key, setting_kind, label in specs:
            if not selected.get(key):
                continue
            amount = service_price_paise(setting_kind)
            if amount <= 0:
                continue
            platform = service_margin_paise(setting_kind)
            lines.append({
                "kind": key,
                "label": label,
                "amount_paise": amount,
                "platform_paise": platform,
                "owner_paise": max(0, amount - platform),
                "amount": from_paise(amount),
            })
    return lines


def penalty_share_paise(amount_rupees):
    if not features()["penalty_share"]:
        return 0
    amount = Decimal(str(amount_rupees or 0))
    if amount <= 0:
        return 0
    pct = Decimal(str(get_settings()["penalty_share_percent"]))
    return _round_paise((amount * 100) * pct / Decimal("100"))


def gst_parts(gross_paise):
    """GST is treated as included in the gross platform amount."""
    s = get_settings()
    gross = int(gross_paise or 0)
    if gross == 0:
        return 0, 0, 0
    sign = 1 if gross > 0 else -1
    value = abs(gross)
    gst_pct = Decimal(str(s["gst_percent"]))
    gst = _round_paise(Decimal(value) * gst_pct / (Decimal("100") + gst_pct))
    gateway = _round_paise(Decimal(value) * Decimal(str(s["gateway_percent"])) / Decimal("100"))
    net = value - gst - gateway
    return sign * gst, sign * gateway, sign * net


# ---------------------------------------------------------------------------
# Booking add-ons
# ---------------------------------------------------------------------------
def save_booking_addons(booking, pricing):
    """Replace the add-on snapshot for a booking from a pricing dict."""
    from models import db
    from models_revenue import BookingAddon

    BookingAddon.query.filter_by(booking_id=booking.id).delete()
    for line in pricing.get("addon_lines", []):
        db.session.add(BookingAddon(
            booking_id=booking.id,
            kind=line["kind"],
            label=line["label"],
            amount_paise=int(line["amount_paise"]),
            platform_paise=int(line.get("platform_paise", 0)),
            owner_paise=int(line.get("owner_paise", 0)),
        ))
    db.session.flush()


def booking_addons(booking):
    from models_revenue import BookingAddon
    return BookingAddon.query.filter_by(booking_id=booking.id).all()


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def _entry_exists(booking_id, kind, source_ref=None):
    from models_revenue import RevenueEntry
    q = RevenueEntry.query.filter_by(booking_id=booking_id, type=kind)
    if source_ref:
        q = q.filter_by(source_ref=source_ref)
    return q.first() is not None


def _make_entry(kind, gross_paise, *, booking_id=None, user_id=None,
                status="pending", source_ref=None, note=None, created_at=None):
    from models import db
    from models_revenue import RevenueEntry

    gross = int(gross_paise or 0)
    if gross == 0:
        return None
    gst, gateway, net = gst_parts(gross)
    entry = RevenueEntry(
        booking_id=booking_id, user_id=user_id, type=kind,
        gross=gross, gst=gst, gateway_cost=gateway, net=net,
        status=status, source_ref=source_ref, note=note,
        created_at=created_at or datetime.utcnow(),
        earned_at=datetime.utcnow() if status == "earned" else None,
    )
    db.session.add(entry)
    return entry


def record_booking_charges(booking):
    """Create pending ledger entries at payment time (idempotent)."""
    if not features()["ledger"]:
        return []
    created = []
    fee_paise = to_paise(booking.platform_fee or 0)
    if fee_paise and not _entry_exists(booking.id, "renter_fee"):
        entry = _make_entry("renter_fee", fee_paise, booking_id=booking.id,
                            user_id=booking.renter_id, note="Renter platform fee")
        if entry:
            created.append(entry)

    percent = float(booking.commission_percent or 0)
    commission = to_paise(round(float(booking.total_rent or 0) * percent / 100.0, 2))
    if commission and not _entry_exists(booking.id, "owner_commission"):
        entry = _make_entry("owner_commission", commission, booking_id=booking.id,
                            user_id=booking.item.owner_id,
                            note=f"Owner commission {percent:g}%")
        if entry:
            created.append(entry)

    for addon in booking_addons(booking):
        if addon.kind == "protection":
            if not _entry_exists(booking.id, "protection", f"addon-{addon.id}"):
                entry = _make_entry("protection", addon.amount_paise,
                                    booking_id=booking.id, user_id=booking.renter_id,
                                    source_ref=f"addon-{addon.id}",
                                    note="Damage protection add-on")
                if entry:
                    created.append(entry)
        elif addon.kind.startswith("service_"):
            if addon.platform_paise and not _entry_exists(
                    booking.id, "service", f"addon-{addon.id}"):
                entry = _make_entry("service", addon.platform_paise,
                                    booking_id=booking.id, user_id=booking.renter_id,
                                    source_ref=f"addon-{addon.id}",
                                    note=f"Platform margin: {addon.label}")
                if entry:
                    created.append(entry)
    return created


def mark_booking_earned(booking):
    """Move pending booking revenue to earned (rental completed)."""
    from models import db
    from models_revenue import RevenueEntry
    rows = RevenueEntry.query.filter_by(booking_id=booking.id, status="pending").all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "earned"
        row.earned_at = now
    if rows:
        db.session.flush()
    return len(rows)


def reverse_booking(booking, reason="refund"):
    """Refund all booking revenue and write negative reversal entries."""
    from models import db
    from models_revenue import RevenueEntry
    originals = RevenueEntry.query.filter(
        RevenueEntry.booking_id == booking.id,
        RevenueEntry.status.in_(["pending", "earned"]),
    ).all()
    reversed_count = 0
    for entry in originals:
        entry.status = "refunded"
        mirror_ref = f"reversal-{entry.id}"
        if RevenueEntry.query.filter_by(type=entry.type, source_ref=mirror_ref).first():
            continue
        gst, gateway, net = gst_parts(entry.gross)
        db.session.add(RevenueEntry(
            booking_id=entry.booking_id, user_id=entry.user_id, type=entry.type,
            gross=-entry.gross, gst=-gst, gateway_cost=-gateway, net=-net,
            status="refunded", source_ref=mirror_ref,
            note=f"Reversal: {reason}"[:300],
            created_at=datetime.utcnow(),
        ))
        reversed_count += 1
    if originals:
        db.session.flush()
    return reversed_count


def record_penalty_share(booking, return_record):
    """Record the platform share of late/damage fees (pending until completion)."""
    if not features()["penalty_share"] or return_record is None:
        return None
    if _entry_exists(booking.id, "penalty_share"):
        return None
    base = float(return_record.late_penalty or 0) + float(return_record.damage_deduction or 0)
    share = penalty_share_paise(base)
    if not share:
        return None
    return _make_entry(
        "penalty_share", share, booking_id=booking.id,
        user_id=booking.item.owner_id, status="pending",
        note="Platform share of late/damage fees")


def record_simple(kind, gross_paise, *, user_id=None, booking_id=None,
                  note=None, status="earned", created_at=None, source_ref=None):
    """Record a non-booking revenue entry (featured, subscription, ad)."""
    if not features()["ledger"]:
        return None
    return _make_entry(kind, gross_paise, booking_id=booking_id, user_id=user_id,
                       status=status, source_ref=source_ref, note=note,
                       created_at=created_at)


def record_subscription(user, plan, amount_rupees):
    if str(plan) != "owner_pro" or not features()["owner_pro"]:
        return None
    return record_simple("subscription", to_paise(amount_rupees), user_id=user.id,
                         note="Owner Pro subscription")


# ---------------------------------------------------------------------------
# Featured listings
# ---------------------------------------------------------------------------
def expire_featured():
    """Lazily mark elapsed windows as expired (called on browse/owner pages)."""
    from models import db
    from models_revenue import FeaturedListing
    stale = FeaturedListing.query.filter(
        FeaturedListing.status == "active",
        FeaturedListing.ends_at < datetime.utcnow(),
    ).all()
    for row in stale:
        row.status = "expired"
    if stale:
        db.session.commit()
    return len(stale)


def _featured_id_set():
    cached = _cache_get("_rk_featured_ids")
    if cached is not None:
        return cached
    ids = set()
    if features()["featured"]:
        try:
            from models_revenue import FeaturedListing
            rows = FeaturedListing.query.filter(
                FeaturedListing.status == "active",
                FeaturedListing.ends_at >= datetime.utcnow(),
            ).all()
            ids = {row.item_id for row in rows}
        except Exception:
            ids = set()
    _cache_set("_rk_featured_ids", ids)
    return ids


def is_featured(item):
    if not item:
        return False
    return getattr(item, "id", None) in _featured_id_set()


def featured_days_left(item):
    if not item:
        return 0
    try:
        from models_revenue import FeaturedListing
        row = FeaturedListing.query.filter(
            FeaturedListing.item_id == item.id,
            FeaturedListing.status == "active",
            FeaturedListing.ends_at >= datetime.utcnow(),
        ).order_by(FeaturedListing.ends_at.desc()).first()
        return row.days_left if row else 0
    except Exception:
        return 0


def active_featured_for_owner(owner):
    from models_revenue import FeaturedListing
    rows = FeaturedListing.query.filter(
        FeaturedListing.owner_id == owner.id,
        FeaturedListing.status == "active",
        FeaturedListing.ends_at >= datetime.utcnow(),
    ).order_by(FeaturedListing.ends_at.desc()).all()
    return {row.item_id: row for row in rows}


# ---------------------------------------------------------------------------
# Sponsored banners
# ---------------------------------------------------------------------------
def sponsored_banner():
    """Return one live banner for the home/browse pages (cached per request)."""
    cached = _cache_get("_rk_sponsored_banner")
    if cached is not None:
        return cached or None
    ad = None
    if features()["ads"]:
        try:
            from models_revenue import BannerAd
            today = date.today()
            rows = BannerAd.query.filter(
                BannerAd.active.is_(True),
                BannerAd.start_date <= today,
                BannerAd.end_date >= today,
            ).order_by(BannerAd.id.desc()).all()
            if rows:
                # Rotate daily so multiple sponsors share impressions.
                ad = rows[date.today().toordinal() % len(rows)]
        except Exception:
            ad = None
    _cache_set("_rk_sponsored_banner", ad or False)
    return ad


# ---------------------------------------------------------------------------
# Owner helpers
# ---------------------------------------------------------------------------
def photo_limit_for(user):
    limit = int(_cfg("PHOTO_MAX_PER_ITEM", 6))
    s = get_settings()
    if features()["owner_pro"] and owner_pro_active(user):
        limit = max(limit, int(s["owner_pro_photos"]))
    return limit


def owner_pro_price_paise(cycle="monthly"):
    s = get_settings()
    monthly = int(s["owner_pro_price_paise"])
    if str(cycle).lower() == "yearly":
        discount = Decimal(str(s["owner_pro_yearly_discount_percent"]))
        yearly = Decimal(monthly * 12) * (Decimal("100") - discount) / Decimal("100")
        return _round_paise(yearly)
    return monthly


def free_featured_available(owner):
    """True when an Owner Pro member has not used this month's free week."""
    if not owner_pro_active(owner):
        return False
    from models_revenue import FeaturedListing
    today = date.today()
    start = datetime(today.year, today.month, 1)
    used = FeaturedListing.query.filter(
        FeaturedListing.owner_id == owner.id,
        FeaturedListing.free.is_(True),
        FeaturedListing.starts_at >= start,
    ).first()
    return used is None


# ---------------------------------------------------------------------------
# Migration safety
# ---------------------------------------------------------------------------
def backup_db_once(app):
    """Copy the SQLite file before the additive tables are created (once)."""
    try:
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
        if not uri.startswith("sqlite:///") or ":memory:" in uri:
            return None
        path = uri[len("sqlite:///"):]
        if not os.path.isfile(path):
            return None
        # Throwaway test databases are rebuilt on every run; never back them up.
        name = os.path.basename(path).lower()
        if app.config.get("TESTING") or name.startswith("test_"):
            return None
        from sqlalchemy import inspect
        from models import db
        if "revenue_entry" in inspect(db.engine).get_table_names():
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.pre_revenue_{stamp}.bak"
        shutil.copy2(path, dest)
        app.logger.info("Revenue migration backup written to %s", dest)
        return dest
    except Exception:
        app.logger.warning("Revenue migration backup could not be written.", exc_info=True)
        return None
