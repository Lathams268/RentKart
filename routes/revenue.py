"""Additive revenue routes: owner earnings/featured/Pro, admin ledger, ads."""
import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from models import Booking, Item, Subscription, db
from models_revenue import (BannerAd, BannerEvent, BookingAddon, FeaturedListing,
                            ProtectionClaim, RevenueEntry)
from routes.admin import admin_required
from utils.money import inr
from utils.plans import get_plan
from utils.revenue import (active_featured_for_owner, features, free_featured_available,
                           from_paise, get_settings, owner_pro_active,
                           owner_pro_price_paise, record_simple, save_settings,
                           to_paise, featured_days_left, expire_featured)

revenue_bp = Blueprint("revenue", __name__)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _money_filter(value):
    try:
        return inr(float(value))
    except Exception:
        return inr(0)


def _date_arg(name, default):
    raw = (request.args.get(name) or "").strip()
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return default


def _range():
    """Return (period, start_dt, end_dt) for the admin dashboard filters."""
    today = date.today()
    period = (request.args.get("period") or "30d").strip()
    end_dt = datetime.combine(today, time.max)
    if period == "today":
        start_dt = datetime.combine(today, time.min)
    elif period == "7d":
        start_dt = datetime.combine(today - timedelta(days=6), time.min)
    elif period == "custom":
        start_d = _date_arg("from", today - timedelta(days=29))
        end_d = _date_arg("to", today)
        if end_d < start_d:
            start_d, end_d = end_d, start_d
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)
    else:
        period = "30d"
        start_dt = datetime.combine(today - timedelta(days=29), time.min)
    return period, start_dt, end_dt


def _owner_rows(owner):
    """Payout rows for the owner's items (returned rows are final)."""
    items = Item.query.filter_by(owner_id=owner.id).all()
    item_ids = [it.id for it in items]
    if not item_ids:
        return [], []
    bookings = Booking.query.filter(
        Booking.item_id.in_(item_ids),
        Booking.status.in_(["picked_up", "returned", "completed"]),
    ).order_by(Booking.created_at.desc()).all()
    rows = []
    for booking in bookings:
        rec = booking.return_record
        rent = float(booking.total_rent or 0)
        if rec is not None:
            commission = float(rec.platform_fee or 0)
            penalties = float(rec.late_penalty or 0) + float(rec.damage_deduction or 0)
            net = float(rec.owner_earning or 0)
            final = True
        else:
            commission = round(rent * float(booking.commission_percent or 0) / 100.0, 2)
            penalties = 0.0
            net = round(rent - commission, 2)
            final = False
        rows.append({
            "booking": booking,
            "item": booking.item,
            "rent": rent,
            "commission": commission,
            "penalties": penalties,
            "net": net,
            "final": final,
        })
    return rows, items


# ---------------------------------------------------------------------------
# Owner earnings
# ---------------------------------------------------------------------------
@revenue_bp.route("/owner/earnings")
@login_required
def owner_earnings():
    rows, items = _owner_rows(current_user)
    earned_rows = [r for r in rows if r["final"]]
    pending_rows = [r for r in rows if not r["final"]]
    total_earned = round(sum(r["net"] for r in earned_rows), 2)
    total_pending = round(sum(r["net"] for r in pending_rows), 2)
    total_commission = round(sum(r["commission"] for r in earned_rows), 2)
    total_penalties = round(sum(r["penalties"] for r in earned_rows), 2)

    analytics = []
    for item in items:
        item_rows = [r for r in rows if r["item"] and r["item"].id == item.id]
        analytics.append({
            "item": item,
            "bookings": len(item_rows),
            "gross": round(sum(r["rent"] for r in item_rows), 2),
            "net": round(sum(r["net"] for r in item_rows), 2),
        })
    analytics.sort(key=lambda row: row["gross"], reverse=True)

    featured = active_featured_for_owner(current_user)
    settings = get_settings()
    return render_template(
        "revenue/owner_earnings.html",
        rows=rows, earned_rows=earned_rows, analytics=analytics,
        total_earned=total_earned, total_pending=total_pending,
        total_commission=total_commission, total_penalties=total_penalties,
        commission_percent=(rows[0]["booking"].commission_percent if rows else None),
        featured=featured, settings=settings,
        is_pro=owner_pro_active(current_user),
        plan_info=get_plan(current_user),
    )


@revenue_bp.route("/owner/earnings.csv")
@login_required
def owner_earnings_csv():
    rows, _items = _owner_rows(current_user)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Booking", "Date", "Item", "Rent (INR)", "Commission (INR)",
                     "Late/damage (INR)", "Owner net (INR)", "Status"])
    for row in rows:
        booking = row["booking"]
        writer.writerow([
            booking.order_id or booking.id,
            (booking.completed_at or booking.created_at or datetime.utcnow()).date().isoformat(),
            row["item"].title if row["item"] else "",
            f"{row['rent']:.2f}", f"{row['commission']:.2f}",
            f"{row['penalties']:.2f}", f"{row['net']:.2f}",
            "settled" if row["final"] else "pending payout",
        ])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=rentkart-earnings.csv"})


# ---------------------------------------------------------------------------
# Featured listings
# ---------------------------------------------------------------------------
@revenue_bp.route("/owner/featured")
@login_required
def owner_featured():
    expire_featured()
    items = Item.query.filter_by(owner_id=current_user.id).order_by(Item.created_at.desc()).all()
    active = active_featured_for_owner(current_user)
    settings = get_settings()
    prices = {int(weeks): from_paise(paise)
              for weeks, paise in (settings.get("featured_prices_paise") or {}).items()}
    return render_template(
        "revenue/owner_featured.html", items=items, active=active,
        prices=prices, settings=settings, is_pro=owner_pro_active(current_user),
        free_available=free_featured_available(current_user),
    )


@revenue_bp.route("/owner/featured/<int:item_id>", methods=["POST"])
@login_required
def owner_featured_buy(item_id):
    if not features()["featured"]:
        flash("Featured listings are switched off.", "error")
        return redirect(url_for("revenue.owner_featured"))
    item = Item.query.get_or_404(item_id)
    if item.owner_id != current_user.id:
        abort(403)
    active = FeaturedListing.query.filter(
        FeaturedListing.item_id == item.id,
        FeaturedListing.status == "active",
        FeaturedListing.ends_at >= datetime.utcnow(),
    ).first()
    if active:
        flash("This listing is already featured.", "error")
        return redirect(url_for("revenue.owner_featured"))

    try:
        weeks = int(request.form.get("weeks", "1"))
    except (TypeError, ValueError):
        weeks = 1
    weeks = max(1, min(3, weeks))

    free = bool(request.form.get("free")) and weeks == 1 and free_featured_available(current_user)
    if free:
        price_paise = 0
    else:
        price_paise = int((get_settings().get("featured_prices_paise") or {}).get(str(weeks), 0))
    if not free and price_paise <= 0:
        flash("This featured package is not priced yet.", "error")
        return redirect(url_for("revenue.owner_featured"))

    now = datetime.utcnow()
    listing = FeaturedListing(
        item_id=item.id, owner_id=current_user.id, weeks=weeks,
        price_paise=price_paise, free=free, status="active",
        starts_at=now, ends_at=now + timedelta(days=7 * weeks),
        order_id=f"RK-FEAT-{item.id}-{int(now.timestamp())}",
    )
    db.session.add(listing)
    db.session.flush()
    if price_paise:
        record_simple("featured", price_paise, user_id=current_user.id,
                      note=f"Featured {weeks} week(s): {item.title}"[:300],
                      source_ref=f"featured-{listing.id}")
    db.session.commit()
    if free:
        flash(f"Free Owner Pro featured week applied to '{item.title}' for 7 days.", "success")
    else:
        flash(f"Mock payment received. '{item.title}' is featured for {weeks * 7} days.", "success")
    return redirect(url_for("revenue.owner_featured"))


# ---------------------------------------------------------------------------
# Owner Pro plan
# ---------------------------------------------------------------------------
@revenue_bp.route("/owner/pro", methods=["GET", "POST"])
@login_required
def owner_pro():
    if not features()["owner_pro"]:
        flash("Owner Pro is switched off.", "error")
        return redirect(url_for("subscriptions.pricing"))

    cycle = (request.args.get("cycle") or request.form.get("billing_cycle") or "monthly").lower()
    if cycle not in ("monthly", "yearly"):
        cycle = "monthly"
    price_paise = owner_pro_price_paise(cycle)
    amount = from_paise(price_paise)
    plan_info = dict(current_app.config["PLANS"].get("owner_pro", {}))
    plan_info["price_month"] = from_paise(get_settings()["owner_pro_price_paise"])
    plan_info["commission_percent"] = get_settings()["owner_pro_commission_percent"]
    plan_info["label"] = plan_info.get("label", "Owner Pro")

    if request.method == "POST":
        today = date.today()
        days = 365 if cycle == "yearly" else 30
        sub = Subscription(
            user_id=current_user.id, plan="owner_pro", billing_cycle=cycle,
            status="active", start_date=today, end_date=today + timedelta(days=days),
            amount_paid=amount, payment_method="upi",
        )
        db.session.add(sub)
        db.session.flush()
        record_simple("subscription", price_paise, user_id=current_user.id,
                      note=f"Owner Pro ({cycle})", source_ref=f"subscription-{sub.id}")
        db.session.commit()
        flash(f"Owner Pro activated for {days} days (mock payment).", "success")
        return redirect(url_for("revenue.owner_earnings"))

    return render_template("subscribe_checkout.html", plan_key="owner_pro",
                           plan_info=plan_info, cycle=cycle, amount=amount)


# ---------------------------------------------------------------------------
# Sponsored banners (public counters)
# ---------------------------------------------------------------------------
@revenue_bp.route("/ads/<int:ad_id>/impression.png")
def ad_impression(ad_id):
    ad = BannerAd.query.get_or_404(ad_id)
    if features()["ads"] and ad.is_live():
        db.session.add(BannerEvent(ad_id=ad.id, kind="impression",
                                   user_id=current_user.id if current_user.is_authenticated else None))
        db.session.commit()
    pixel = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
             b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
             b"\x00\x02\x02D\x01\x00;")
    return Response(pixel, mimetype="image/gif",
                    headers={"Cache-Control": "no-store, max-age=0"})


@revenue_bp.route("/ads/<int:ad_id>/click")
def ad_click(ad_id):
    ad = BannerAd.query.get_or_404(ad_id)
    if features()["ads"] and ad.is_live():
        db.session.add(BannerEvent(ad_id=ad.id, kind="click",
                                   user_id=current_user.id if current_user.is_authenticated else None))
        db.session.commit()
        return redirect(ad.link_url)
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Admin: revenue dashboard / CSV
# ---------------------------------------------------------------------------
def _dashboard_data():
    period, start_dt, end_dt = _range()
    entries = RevenueEntry.query.filter(
        RevenueEntry.created_at >= start_dt,
        RevenueEntry.created_at <= end_dt,
    ).order_by(RevenueEntry.created_at.desc()).all()

    earned = [e for e in entries if e.status == "earned"]
    pending = [e for e in entries if e.status == "pending"]
    refunded = [e for e in entries if e.status == "refunded" and e.gross < 0]

    totals = {
        "earned": sum(e.gross for e in earned) / 100.0,
        "pending": sum(e.gross for e in pending) / 100.0,
        "refunded": abs(sum(e.gross for e in refunded)) / 100.0,
        "gst": sum(e.gst for e in earned) / 100.0,
        "net": sum(e.net for e in earned) / 100.0,
    }

    # Daily earned gross (last 31 days max on the chart).
    day = start_dt.date()
    last = end_dt.date()
    if (last - day).days > 61:
        day = last - timedelta(days=61)
    daily = []
    while day <= last:
        total = sum(e.gross for e in earned if e.created_at and e.created_at.date() == day)
        daily.append({"date": day, "value": total / 100.0})
        day += timedelta(days=1)

    by_source = {}
    for entry in earned:
        by_source[entry.type] = by_source.get(entry.type, 0) + entry.gross
    max_source = max(by_source.values(), default=0) or 1
    source_rows = [
        {"type": key, "label": RevenueEntry.TYPE_LABELS.get(key, key),
         "value": value / 100.0, "percent": round(value * 100.0 / max_source, 1)}
        for key, value in sorted(by_source.items(), key=lambda kv: kv[1], reverse=True)
    ]

    deposits = db.session.query(db.func.coalesce(db.func.sum(Booking.deposit), 0)).filter(
        Booking.status.in_(["approved", "picked_up"]),
        Booking.payment_status.in_(["paid", "paid_demo"]),
    ).scalar() or 0

    protection_income = sum(e.gross for e in earned if e.type == "protection") / 100.0
    claims_q = ProtectionClaim.query.filter(
        ProtectionClaim.created_at >= start_dt,
        ProtectionClaim.created_at <= end_dt,
    )
    claims_paid = sum(c.amount_paise for c in claims_q.all()) / 100.0

    ads = BannerAd.query.order_by(BannerAd.created_at.desc()).all()
    addons = BookingAddon.query.filter_by(kind="protection")\
        .order_by(BookingAddon.created_at.desc()).limit(10).all()
    claimed_booking_ids = {c.booking_id for c in ProtectionClaim.query.all()}

    return {
        "period": period, "start": start_dt, "end": end_dt,
        "entries": entries, "recent": entries[:25], "totals": totals,
        "daily": daily, "source_rows": source_rows, "deposits": deposits,
        "protection_income": protection_income, "claims_paid": claims_paid,
        "protection_margin": round(protection_income - claims_paid, 2),
        "protection_addons": addons, "claimed_booking_ids": claimed_booking_ids,
        "ads": ads,
    }


@revenue_bp.route("/admin/revenue")
@admin_required
def admin_revenue():
    data = _dashboard_data()
    return render_template("revenue/admin_revenue.html", **data)


@revenue_bp.route("/admin/revenue/export.csv")
@admin_required
def admin_revenue_csv():
    period, start_dt, end_dt = _range()
    entries = RevenueEntry.query.filter(
        RevenueEntry.created_at >= start_dt,
        RevenueEntry.created_at <= end_dt,
    ).order_by(RevenueEntry.created_at.desc()).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Type", "Status", "Booking", "Gross INR", "GST INR",
                     "Gateway INR", "Net INR", "Note"])
    for entry in entries:
        gst, gateway, net = (entry.gst / 100.0, entry.gateway_cost / 100.0,
                             entry.net / 100.0)
        writer.writerow([
            (entry.created_at or datetime.utcnow()).isoformat(timespec="seconds"),
            entry.type, entry.status, entry.booking_id or "",
            f"{entry.gross / 100.0:.2f}", f"{gst:.2f}", f"{gateway:.2f}",
            f"{net:.2f}", entry.note or "",
        ])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=rentkart-revenue.csv"})


@revenue_bp.route("/admin/revenue/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    settings = get_settings()
    if request.method == "POST":
        form = request.form
        merged = dict(settings)
        merged["featured_prices_paise"] = dict(settings.get("featured_prices_paise") or {})
        merged["renter_fee_category_overrides"] = dict(
            settings.get("renter_fee_category_overrides") or {})

        flags = ("renter_fee_enabled", "owner_commission_enabled", "featured_enabled",
                 "owner_pro_enabled", "protection_enabled", "penalty_share_enabled",
                 "services_enabled", "ads_enabled", "ledger_enabled")
        for flag in flags:
            merged[flag] = bool(form.get(flag))

        def _num(key, cast=float, lo=None, hi=None, current=None):
            try:
                value = cast(form.get(key, current))
            except (TypeError, ValueError):
                value = current
            if lo is not None:
                value = max(lo, value)
            if hi is not None:
                value = min(hi, value)
            return value

        merged["renter_fee_percent"] = _num("renter_fee_percent", float, 0, 50,
                                            settings["renter_fee_percent"])
        merged["renter_fee_min_paise"] = to_paise(_num(
            "renter_fee_min", float, 0, 10000, from_paise(settings["renter_fee_min_paise"])))
        merged["renter_fee_max_paise"] = to_paise(_num(
            "renter_fee_max", float, 1, 100000, from_paise(settings["renter_fee_max_paise"])))
        if merged["renter_fee_max_paise"] < merged["renter_fee_min_paise"]:
            merged["renter_fee_max_paise"] = merged["renter_fee_min_paise"]

        overrides = {}
        for pair in (form.get("category_overrides") or "").split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                try:
                    overrides[key.strip()] = max(0.0, min(50.0, float(val)))
                except ValueError:
                    continue
        merged["renter_fee_category_overrides"] = overrides

        merged["owner_commission_percent"] = _num(
            "owner_commission_percent", float, 0, 30, settings["owner_commission_percent"])
        merged["owner_commission_waiver_bookings"] = _num(
            "owner_commission_waiver_bookings", int, 0, 100,
            settings["owner_commission_waiver_bookings"])

        for weeks in ("1", "2", "3"):
            merged["featured_prices_paise"][weeks] = to_paise(_num(
                f"featured_price_{weeks}", float, 0, 100000,
                from_paise(settings["featured_prices_paise"].get(weeks, 0))))

        merged["owner_pro_price_paise"] = to_paise(_num(
            "owner_pro_price", float, 0, 100000, from_paise(settings["owner_pro_price_paise"])))
        merged["owner_pro_yearly_discount_percent"] = _num(
            "owner_pro_yearly_discount_percent", float, 0, 80,
            settings["owner_pro_yearly_discount_percent"])
        merged["owner_pro_commission_percent"] = _num(
            "owner_pro_commission_percent", float, 0, 30,
            settings["owner_pro_commission_percent"])
        merged["owner_pro_photos"] = _num("owner_pro_photos", int, 6, 30,
                                          settings["owner_pro_photos"])

        merged["protection_percent"] = _num(
            "protection_percent", float, 0, 20, settings["protection_percent"])
        merged["protection_cover_paise"] = to_paise(_num(
            "protection_cover", float, 0, 100000, from_paise(settings["protection_cover_paise"])))

        merged["penalty_share_percent"] = _num(
            "penalty_share_percent", float, 0, 100, settings["penalty_share_percent"])

        merged["service_delivery_paise"] = to_paise(_num(
            "service_delivery", float, 0, 10000, from_paise(settings["service_delivery_paise"])))
        merged["service_cleaning_paise"] = to_paise(_num(
            "service_cleaning", float, 0, 10000, from_paise(settings["service_cleaning_paise"])))
        merged["service_margin_percent"] = _num(
            "service_margin_percent", float, 0, 90, settings["service_margin_percent"])

        merged["gst_percent"] = _num("gst_percent", float, 0, 28, settings["gst_percent"])
        merged["gateway_percent"] = _num("gateway_percent", float, 0, 10,
                                         settings["gateway_percent"])

        save_settings(merged)
        flash("Revenue settings saved.", "success")
        return redirect(url_for("revenue.admin_settings"))

    return render_template("revenue/admin_settings.html", settings=settings)


@revenue_bp.route("/admin/revenue/ads", methods=["GET", "POST"])
@admin_required
def admin_ads():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        image_url = (request.form.get("image_url") or "").strip()
        link_url = (request.form.get("link_url") or "").strip()
        try:
            start = date.fromisoformat(request.form.get("start_date", ""))
            end = date.fromisoformat(request.form.get("end_date", ""))
        except (ValueError, TypeError):
            flash("Choose valid start and end dates.", "error")
            return redirect(url_for("revenue.admin_ads"))
        if not title or not image_url or not link_url:
            flash("Title, image URL and link URL are required.", "error")
            return redirect(url_for("revenue.admin_ads"))
        if not (image_url.startswith("http://") or image_url.startswith("https://")
                or image_url.startswith("/static/")):
            flash("Image URL must be http(s) or /static/...", "error")
            return redirect(url_for("revenue.admin_ads"))
        if not (link_url.startswith("http://") or link_url.startswith("https://")
                or link_url.startswith("/")):
            flash("Link URL must be http(s) or a site path.", "error")
            return redirect(url_for("revenue.admin_ads"))
        if end < start:
            flash("End date must be after the start date.", "error")
            return redirect(url_for("revenue.admin_ads"))
        try:
            price = max(0.0, float(request.form.get("price") or 0))
        except ValueError:
            price = 0.0
        ad = BannerAd(
            title=title, sponsor=(request.form.get("sponsor") or "").strip() or None,
            image_url=image_url, link_url=link_url, start_date=start, end_date=end,
            price_paise=to_paise(price), active=True,
        )
        db.session.add(ad)
        db.session.flush()
        if ad.price_paise:
            record_simple("ad", ad.price_paise, user_id=current_user.id,
                          note=f"Sponsored banner: {title}"[:300],
                          source_ref=f"ad-{ad.id}")
        db.session.commit()
        flash("Sponsored banner created.", "success")
        return redirect(url_for("revenue.admin_ads"))

    ads = BannerAd.query.order_by(BannerAd.created_at.desc()).all()
    return render_template("revenue/admin_ads.html", ads=ads)


@revenue_bp.route("/admin/revenue/ads/<int:ad_id>/toggle", methods=["POST"])
@admin_required
def admin_ad_toggle(ad_id):
    ad = BannerAd.query.get_or_404(ad_id)
    ad.active = not ad.active
    db.session.commit()
    flash(f"Banner {'activated' if ad.active else 'paused'}.", "success")
    return redirect(url_for("revenue.admin_ads"))


@revenue_bp.route("/admin/revenue/protection/<int:booking_id>/claim", methods=["POST"])
@admin_required
def admin_protection_claim(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    addon = BookingAddon.query.filter_by(booking_id=booking.id, kind="protection").first()
    if addon is None:
        flash("This booking has no protection add-on.", "error")
        return redirect(url_for("revenue.admin_revenue"))
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    amount_paise = min(to_paise(amount), int(get_settings()["protection_cover_paise"]))
    if amount_paise <= 0:
        flash("Enter a claim amount above zero.", "error")
        return redirect(url_for("revenue.admin_revenue"))
    claim = ProtectionClaim.query.filter_by(booking_id=booking.id).first()
    if claim is None:
        claim = ProtectionClaim(booking_id=booking.id, user_id=booking.item.owner_id,
                                amount_paise=amount_paise, status="paid",
                                note=(request.form.get("note") or "").strip()[:300] or None)
        db.session.add(claim)
    else:
        claim.amount_paise = amount_paise
        claim.status = "paid"
    db.session.commit()
    flash(f"Protection claim of {inr(from_paise(amount_paise))} recorded.", "success")
    return redirect(url_for("revenue.admin_revenue"))
