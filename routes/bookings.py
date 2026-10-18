"""Booking routes – request, approve, reject, handover, payment, dashboards."""
import os, uuid
from datetime import date, datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort, jsonify,
)
from flask_login import login_required, current_user
from models import db, Item, Booking, ReturnRecord, Review
from utils.booking import (
    calculate_price, booking_snapshot, is_available,
    generate_order_id, payment_expiry,
)
from utils.trust import get_user_trust
from utils.settlement import calculate_settlement

bookings_bp = Blueprint("bookings", __name__)

ALLOWED_IMG = {"png", "jpg", "jpeg"}


def _allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_IMG


# ---------- Create booking ----------
@bookings_bp.route("/items/<int:item_id>/book", methods=["POST"])
@login_required
def book_item(item_id):
    """Validate dates, check availability, create a 'requested' booking."""
    item = Item.query.get_or_404(item_id)

    # Owner cannot book own item
    if item.owner_id == current_user.id:
        flash("You cannot book your own item.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    try:
        start = date.fromisoformat(request.form["start_date"])
        end = date.fromisoformat(request.form["end_date"])
    except (KeyError, ValueError):
        flash("Please select valid start and end dates.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    if end < start:
        flash("End date cannot be before start date.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))
    if start < date.today():
        flash("Start date cannot be in the past.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    if not item.is_available or not is_available(item, start, end):
        flash("Item is not available for the selected dates.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    pricing = calculate_price(item, start, end, user=current_user)

    from utils.plans import commission_for
    owner_commission = commission_for(item.owner)

    booking = Booking(
        item_id=item.id,
        renter_id=current_user.id,
        start_date=start,
        end_date=end,
        commission_percent=owner_commission,
        **booking_snapshot(pricing),
        status="requested",
    )
    db.session.add(booking)
    db.session.commit()
    flash("Booking requested! Please complete payment.", "success")
    return redirect(url_for("bookings.payment", booking_id=booking.id))


# ---------- Checkout: order summary + create pending booking ----------
def _parse_checkout(item, source):
    """Parse/validate start, end, delivery from a dict-like source. Return (start, end, dm, error)."""
    try:
        start = date.fromisoformat(source.get("start", "") or source.get("start_date", ""))
        end = date.fromisoformat(source.get("end", "") or source.get("end_date", ""))
    except (ValueError, TypeError):
        return None, None, "pickup", "Please select valid start and end dates."
    dm = "delivery" if (source.get("delivery", "pickup") or "pickup").lower() == "delivery" else "pickup"
    if end < start:
        return None, None, dm, "End date cannot be before start date."
    if start < date.today():
        return None, None, dm, "Start date cannot be in the past."
    return start, end, dm, None


@bookings_bp.route("/items/<int:item_id>/checkout", methods=["GET"])
@login_required
def checkout(item_id):
    """Show the order summary page before payment. All money is server-calculated."""
    item = Item.query.get_or_404(item_id)
    if item.owner_id == current_user.id:
        flash("You cannot book your own item.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    start, end, dm, err = _parse_checkout(item, request.args)
    if err:
        flash(err, "error")
        return redirect(url_for("items.item_detail", item_id=item.id))
    if not item.is_available or not is_available(item, start, end):
        flash("Item is not available for the selected dates.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    pricing = calculate_price(item, start, end, user=current_user, delivery_method=dm)
    return render_template(
        "checkout.html", item=item, pricing=pricing, start=start, end=end,
        delivery_method=dm, today=date.today().isoformat(),
    )


@bookings_bp.route("/api/checkout-price")
@login_required
def api_checkout_price():
    """Server-side price recompute for the pickup/delivery toggle (JS reads this)."""
    item = Item.query.get_or_404(request.args.get("item_id", type=int) or 0)
    start, end, dm, err = _parse_checkout(item, request.args)
    if err:
        return jsonify({"error": err}), 400
    pricing = calculate_price(item, start, end, user=current_user, delivery_method=dm)
    return jsonify(pricing)


@bookings_bp.route("/items/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_submit(item_id):
    """Create (or reuse) a pending_payment booking, snapshotting server amounts."""
    item = Item.query.get_or_404(item_id)
    if item.owner_id == current_user.id:
        flash("You cannot book your own item.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    start, end, dm, err = _parse_checkout(item, request.form)
    if err:
        flash(err, "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    if not request.form.get("agree"):
        flash("Please agree to the rental terms and return date.", "error")
        return redirect(url_for("bookings.checkout", item_id=item.id,
                               start=start.isoformat(), end=end.isoformat(), delivery=dm))

    if not item.is_available or not is_available(item, start, end):
        flash("Item is not available for the selected dates.", "error")
        return redirect(url_for("items.item_detail", item_id=item.id))

    # Reuse an existing pending booking for the same user/item/dates (no duplicates).
    existing = Booking.query.filter_by(
        item_id=item.id, renter_id=current_user.id,
        start_date=start, end_date=end, status="pending_payment",
    ).first()
    if existing:
        return redirect(url_for("bookings.pay", booking_id=existing.id))

    # Amounts are always recalculated here; any total sent by the browser is ignored.
    pricing = calculate_price(item, start, end, user=current_user, delivery_method=dm)
    from utils.plans import commission_for
    booking = Booking(
        item_id=item.id,
        renter_id=current_user.id,
        start_date=start,
        end_date=end,
        commission_percent=commission_for(item.owner),
        order_id=generate_order_id(),
        payment_expires_at=payment_expiry(),
        payment_status="pending",
        **booking_snapshot(pricing),
        status="pending_payment",
    )
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for("bookings.pay", booking_id=booking.id))


# ---------- Placeholder pay route (fully implemented in Stage 3) ----------
@bookings_bp.route("/bookings/<int:booking_id>/pay", methods=["GET", "POST"])
@login_required
def pay(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template("payment.html", booking=booking)


# ---------- Payment ----------
@bookings_bp.route("/bookings/<int:booking_id>/payment", methods=["GET", "POST"])
@login_required
def payment(booking_id):
    """Mock payment – UPI (demo) or cash on pickup."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id:
        abort(403)

    if booking.status not in ("requested", "approved") or booking.payment_method:
        flash("Payment is not available for this booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    if request.method == "POST":
        method = request.form.get("payment_method", "")
        if method == "upi":
            booking.payment_method = "upi"
            booking.payment_status = "paid_demo"
            flash("UPI payment successful (demo).", "success")
        elif method == "cash":
            booking.payment_method = "cash"
            booking.payment_status = "pay_on_pickup"
            flash("Cash on pickup selected.", "success")
        else:
            flash("Choose a payment method.", "error")
            return redirect(url_for("bookings.payment", booking_id=booking.id))
        db.session.commit()
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    return render_template("payment.html", booking=booking)


# ---------- Booking detail ----------
@bookings_bp.route("/bookings/<int:booking_id>")
@login_required
def booking_detail(booking_id):
    """Show booking details. Phone revealed only after approval."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id and booking.item.owner_id != current_user.id:
        abort(403)
    renter_trust = get_user_trust(booking.renter)
    return render_template("booking_detail.html", booking=booking, renter_trust=renter_trust)


# ---------- Status transitions ----------
@bookings_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    """Renter cancels while requested or approved."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id:
        abort(403)
    if booking.status not in ("requested", "approved"):
        flash("Cannot cancel at this stage.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))
    booking.status = "cancelled"
    db.session.commit()
    flash("Booking cancelled.", "success")
    return redirect(url_for("bookings.booking_detail", booking_id=booking.id))


@bookings_bp.route("/bookings/<int:booking_id>/approve", methods=["POST"])
@login_required
def approve(booking_id):
    """Owner approves. Re-checks availability to prevent double approval."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id:
        abort(403)
    if booking.status != "requested":
        flash("Can only approve a requested booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    # Re-check availability (excluding this booking)
    overlap = Booking.query.filter(
        Booking.item_id == booking.item_id,
        Booking.id != booking.id,
        Booking.status.in_(["approved", "picked_up"]),
        Booking.start_date <= booking.end_date,
        Booking.end_date >= booking.start_date,
    ).first()
    if overlap:
        flash("Another booking overlaps these dates. Cannot approve.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    booking.status = "approved"
    db.session.commit()
    flash("Booking approved!", "success")
    return redirect(url_for("bookings.booking_detail", booking_id=booking.id))


@bookings_bp.route("/bookings/<int:booking_id>/reject", methods=["POST"])
@login_required
def reject(booking_id):
    """Owner rejects a requested booking."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id:
        abort(403)
    if booking.status != "requested":
        flash("Can only reject a requested booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))
    booking.status = "rejected"
    db.session.commit()
    flash("Booking rejected.", "success")
    return redirect(url_for("bookings.booking_detail", booking_id=booking.id))


@bookings_bp.route("/bookings/<int:booking_id>/handover", methods=["POST"])
@login_required
def handover(booking_id):
    """Owner marks item as handed over (picked_up). Optional note/photo."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id:
        abort(403)
    if booking.status != "approved":
        flash("Item can only be handed over after approval.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    booking.handover_note = request.form.get("handover_note", "").strip() or None

    # Optional photo
    photo = request.files.get("handover_photo")
    if photo and photo.filename:
        if not _allowed(photo.filename):
            flash("Photo must be png or jpg", "error")
            return redirect(url_for("bookings.booking_detail", booking_id=booking.id))
        ext = photo.filename.rsplit(".", 1)[1].lower()
        fname = f"handover_{uuid.uuid4().hex}.{ext}"
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        photo.save(os.path.join(upload_dir, fname))
        booking.handover_photo = fname

    booking.status = "picked_up"
    # Cash on pickup → mark paid
    if booking.payment_status == "pay_on_pickup":
        booking.payment_status = "paid_demo"

    db.session.commit()
    flash("Item handed over. Rental is now active!", "success")
    return redirect(url_for("bookings.booking_detail", booking_id=booking.id))


# ---------- Return flow ----------
@bookings_bp.route("/bookings/<int:booking_id>/return", methods=["GET", "POST"])
@login_required
def return_item(booking_id):
    """Owner completes the return, assesses damage/delay, creates ReturnRecord."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id:
        abort(403)
    if booking.return_record is not None or booking.status == "returned":
        flash("This booking has already been returned.", "error")
        return redirect(url_for("bookings.settlement", booking_id=booking.id))
    if booking.status != "picked_up":
        flash("Only active (picked up) rentals can be returned.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    if request.method == "POST":
        try:
            actual_date = date.fromisoformat(request.form.get("actual_return_date", ""))
        except (ValueError, TypeError):
            flash("Invalid return date.", "error")
            return redirect(url_for("bookings.return_item", booking_id=booking.id))

        if actual_date < booking.start_date:
            flash("Return date cannot be before start date.", "error")
            return redirect(url_for("bookings.return_item", booking_id=booking.id))

        damage_level = request.form.get("damage_level", "none")
        if damage_level not in current_app.config["DAMAGE_LEVELS"]:
            flash("Invalid damage level.", "error")
            return redirect(url_for("bookings.return_item", booking_id=booking.id))

        photo_filename = None
        photo = request.files.get("return_photo")
        if photo and photo.filename:
            if not _allowed(photo.filename):
                flash("Photo must be png or jpg", "error")
                return redirect(url_for("bookings.return_item", booking_id=booking.id))
            ext = photo.filename.rsplit(".", 1)[1].lower()
            photo_filename = f"return_{uuid.uuid4().hex}.{ext}"
            upload_dir = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_dir, exist_ok=True)
            photo.save(os.path.join(upload_dir, photo_filename))

        settlement = calculate_settlement(
            deposit=booking.deposit,
            end_date=booking.end_date,
            actual_return_date=actual_date,
            late_fee_per_day=booking.item.late_fee_per_day or 0,
            damage_level=damage_level,
            total_rent=booking.total_rent,
            commission_percent=getattr(booking, "commission_percent", 10.0),
        )

        return_rec = ReturnRecord(
            booking_id=booking.id,
            actual_return_date=actual_date,
            late_days=settlement["late_days"],
            late_fee_per_day=settlement["late_fee_per_day"],
            late_penalty=settlement["late_penalty"],
            damage_level=damage_level,
            damage_percent=settlement["damage_percent"],
            damage_deduction=settlement["damage_deduction"],
            deposit_held=settlement["deposit_held"],
            total_deductions=settlement["total_deductions"],
            refund_amount=settlement["refund_amount"],
            extra_due=settlement["extra_due"],
            platform_fee=settlement["platform_fee"],
            owner_earning=settlement["owner_earning"],
            return_note=request.form.get("return_note", "").strip() or None,
            return_photo=photo_filename,
        )
        booking.status = "returned"
        db.session.add(return_rec)
        db.session.commit()

        flash("Item returned and settlement generated!", "success")
        return redirect(url_for("bookings.settlement", booking_id=booking.id))

    return render_template(
        "return.html",
        booking=booking,
        damage_levels=current_app.config["DAMAGE_LEVELS"],
        today=date.today().isoformat(),
    )


# ---------- Settlement receipt ----------
@bookings_bp.route("/bookings/<int:booking_id>/settlement")
@login_required
def settlement(booking_id):
    """View final settlement breakdown and before/after condition comparison."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id and booking.item.owner_id != current_user.id:
        abort(403)
    if not booking.return_record:
        flash("Return settlement is not available for this booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    return render_template("settlement.html", booking=booking, rec=booking.return_record)


# ---------- Reviews ----------
@bookings_bp.route("/bookings/<int:booking_id>/review", methods=["POST"])
@login_required
def add_review(booking_id):
    """Renter leaves a rating and review for a returned booking."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id:
        abort(403)
    if booking.status != "returned":
        flash("Can only review returned bookings.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))
    if booking.review is not None:
        flash("You have already reviewed this booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    try:
        rating = int(request.form.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    comment = request.form.get("comment", "").strip() or None
    review = Review(
        booking_id=booking.id,
        reviewer_id=current_user.id,
        owner_id=booking.item.owner_id,
        rating=rating,
        comment=comment,
    )
    db.session.add(review)
    db.session.commit()
    flash("Thank you for your review!", "success")
    return redirect(url_for("bookings.booking_detail", booking_id=booking.id))


# ---------- Owner dashboard ----------
@bookings_bp.route("/dashboard/owner")
@login_required
def owner_dashboard():
    """Owner view: my items, incoming requests, active rentals, completed rentals, earnings."""
    my_items = Item.query.filter_by(owner_id=current_user.id).all()
    item_ids = [i.id for i in my_items]

    incoming = Booking.query.filter(
        Booking.item_id.in_(item_ids), Booking.status == "requested"
    ).order_by(Booking.created_at.desc()).all() if item_ids else []

    approved = Booking.query.filter(
        Booking.item_id.in_(item_ids), Booking.status == "approved"
    ).order_by(Booking.start_date).all() if item_ids else []

    active = Booking.query.filter(
        Booking.item_id.in_(item_ids), Booking.status == "picked_up"
    ).order_by(Booking.end_date).all() if item_ids else []

    completed = Booking.query.filter(
        Booking.item_id.in_(item_ids), Booking.status == "returned"
    ).order_by(Booking.created_at.desc()).all() if item_ids else []

    # Total earnings: use net owner_earning for returned bookings, total_rent for picked_up
    earned_bookings = Booking.query.filter(
        Booking.item_id.in_(item_ids),
        Booking.status.in_(["picked_up", "returned"]),
    ).all() if item_ids else []

    total_earnings = 0.0
    for b in earned_bookings:
        if b.return_record:
            total_earnings += getattr(b.return_record, "owner_earning", b.total_rent + b.return_record.total_deductions)
        else:
            total_earnings += b.total_rent
    total_earnings = round(total_earnings, 2)

    from utils.plans import get_plan, has_feature
    current_plan_key = current_user.current_plan()
    active_sub = current_user.active_subscription()
    plan_info = get_plan(current_user)
    days_left = active_sub.days_left if active_sub else 0
    show_expiry_warning = (active_sub is not None and 0 <= days_left <= 5)
    has_overflow_items = (len(my_items) > plan_info.get("max_items", 5))
    can_qr_poster = has_feature(current_user, "qr_poster")
    can_roi_tracker = has_feature(current_user, "roi_tracker")

    # Phase 7: ROI tracking metrics & insights
    from utils.roi import item_earnings, roi_progress, payback_days, utilization_30d
    item_insights = []
    idle_items = []
    best_item = None
    best_earned = -1.0
    total_net_earnings = 0.0

    for item in my_items:
        earned = item_earnings(item)
        total_net_earnings += earned
        util_pct = utilization_30d(item)
        progress = roi_progress(item)
        pdays = payback_days(item)

        if earned > best_earned and earned > 0:
            best_earned = earned
            best_item = item

        if util_pct == 0.0:
            idle_items.append(item)

        item_insights.append({
            "item": item,
            "has_purchase_price": item.purchase_price is not None and item.purchase_price > 0,
            "purchase_price": item.purchase_price,
            "earned": earned,
            "progress_percent": progress.percent,
            "to_recover": progress.to_recover,
            "payback_days": pdays,
            "utilization_30d": util_pct,
        })

    total_net_earnings = round(total_net_earnings, 2)

    return render_template(
        "owner_dashboard.html",
        my_items=my_items,
        incoming=incoming,
        approved=approved,
        active=active,
        completed=completed,
        total_earnings=total_earnings,
        total_net_earnings=total_net_earnings,
        today=date.today(),
        get_user_trust=get_user_trust,
        current_plan_key=current_plan_key,
        plan_info=plan_info,
        active_sub=active_sub,
        days_left=days_left,
        show_expiry_warning=show_expiry_warning,
        has_overflow_items=has_overflow_items,
        can_qr_poster=can_qr_poster,
        can_roi_tracker=can_roi_tracker,
        item_insights=item_insights,
        idle_items=idle_items,
        best_item=best_item,
    )


# ---------- Renter dashboard ----------
@bookings_bp.route("/dashboard/renter")
@login_required
def renter_dashboard():
    """Renter view: my bookings grouped by status with overdue tracking."""
    all_bookings = Booking.query.filter_by(renter_id=current_user.id)\
        .order_by(Booking.created_at.desc()).all()

    grouped = {}
    for b in all_bookings:
        grouped.setdefault(b.status, []).append(b)

    return render_template(
        "renter_dashboard.html",
        grouped=grouped,
        today=date.today(),
    )
