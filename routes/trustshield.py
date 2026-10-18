"""RentKart TrustShield blueprint (all NEW, additive).

Handles private evidence serving, handover/return condition reports, customer
confirmation, Pillow-only comparison, verified penalty proposals, disputes,
admin resolution and the item condition history. It never edits existing
functions; settlement finalisation reuses the existing calculate_settlement via
utils/ts_settlement.py.
"""
from datetime import datetime, date

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
    current_app, send_file,
)
from flask_login import login_required, current_user

from models import (
    db, Item, Booking, ReturnRecord, ConditionReport, EvidenceFile, DamageRecord,
    DamageCase, DamageClaimItem, Dispute, DisputeFile, ComparisonResult,
)

ts_bp = Blueprint("trustshield", __name__)


# --------------------------------------------------------------------------
# Permission helpers
# --------------------------------------------------------------------------
def _resolve_booking(ev):
    """Best-effort booking for an EvidenceFile (via its report or column)."""
    if getattr(ev, "booking_id", None):
        return Booking.query.get(ev.booking_id)
    if getattr(ev, "report_id", None):
        rep = ConditionReport.query.get(ev.report_id)
        if rep:
            return Booking.query.get(rep.booking_id)
    return None


def can_view_booking(booking, user) -> bool:
    """Renter, item owner and admins may view TrustShield evidence/reports."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    if booking is None:
        return False
    if booking.renter_id == user.id:
        return True
    if booking.item and booking.item.owner_id == user.id:
        return True
    return False


# --------------------------------------------------------------------------
# Private evidence serving
# --------------------------------------------------------------------------
@ts_bp.route("/evidence/<int:evidence_id>")
@login_required
def serve_evidence(evidence_id):
    """Serve a stored evidence file only to the renter, item owner or admin."""
    ev = EvidenceFile.query.get_or_404(evidence_id)
    booking = _resolve_booking(ev)
    if booking is None and getattr(ev, "item_id", None):
        item = Item.query.get(ev.item_id)
        if not (current_user.is_admin or (item and item.owner_id == current_user.id)):
            abort(403)
    elif not can_view_booking(booking, current_user):
        abort(403)

    from utils.ts_evidence import abs_path
    path = abs_path(current_app, ev.stored_name)
    import os
    if not os.path.isfile(path):
        abort(404)
    mimetype = "image/jpeg" if ev.kind == "photo" else (
        "video/mp4" if ev.stored_name.endswith("mp4") else None)
    return send_file(path, mimetype=mimetype, as_attachment=False,
                     download_name=ev.stored_name, conditional=True,
                     max_age=0)


# --------------------------------------------------------------------------
# Shared config / lookup helpers
# --------------------------------------------------------------------------
def _ts_cfg(key, default=None):
    val = current_app.config.get(key, None)
    if val is not None:
        return val
    import config as _c
    return getattr(_c, key, default)


def _checklist_for(category):
    import config as _c
    return _c.CONDITION_CHECKLISTS.get(category) or _c.CONDITION_CHECKLISTS["default"]


def _rules_for(category):
    import config as _c
    return _c.TS_DAMAGE_RULES.get(category) or _c.TS_DAMAGE_RULES["default"]


def _angles():
    return _ts_cfg("PHOTO_ANGLES", ["front", "back", "left", "right"])


def _latest_report(booking_id, phase):
    return (ConditionReport.query.filter_by(booking_id=booking_id, phase=phase)
            .order_by(ConditionReport.id.desc()).first())


def _existing_damages(item_id):
    return DamageRecord.query.filter_by(item_id=item_id, status="existing")\
        .filter(DamageRecord.repaired_at.is_(None)).order_by(DamageRecord.id).all()


# --------------------------------------------------------------------------
# STAGE 2 - Handover condition report (owner) + customer confirmation (renter)
# --------------------------------------------------------------------------
@ts_bp.route("/ts/bookings/<int:booking_id>/handover", methods=["GET", "POST"])
@login_required
def handover_report(booking_id):
    """Owner uploads the pre-delivery condition report for a TrustShield booking."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    if not booking.trustshield:
        flash("This booking is not on TrustShield.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))
    if booking.status not in ("approved", "awaiting_customer_confirmation"):
        flash("A handover report can be made for an approved booking.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    category = booking.item.category
    submitted = booking.status == "awaiting_customer_confirmation"
    min_photos = int(_ts_cfg("MIN_PHOTOS_HANDOVER", 4))

    if request.method == "POST":
        photos_raw = request.files.getlist("photo")
        angles_raw = request.form.getlist("angle")
        videos_raw = request.files.getlist("video")
        vangles_raw = request.form.getlist("video_angle")
        # Pair each angle label with its file (DOM order), keeping only real files.
        photo_pairs = [(angles_raw[i] if i < len(angles_raw) and angles_raw[i] else "unlabeled", f)
                       for i, f in enumerate(photos_raw) if f and f.filename]
        video_pairs = [(vangles_raw[i] if i < len(vangles_raw) and vangles_raw[i] else "unlabeled", f)
                       for i, f in enumerate(videos_raw) if f and f.filename]

        if len(photo_pairs) < min_photos:
            flash(f"Please upload at least {min_photos} clear condition photos.", "error")
            return redirect(url_for("trustshield.handover_report", booking_id=booking.id))

        report = ConditionReport(booking_id=booking.id, item_id=booking.item_id,
                                 phase="handover", status="submitted",
                                 created_by=current_user.id,
                                 note=(request.form.get("note", "").strip() or None))
        db.session.add(report)
        db.session.flush()  # get report.id

        from utils.ts_evidence import save_image, save_video
        max_p = int(_ts_cfg("MAX_PHOTO_MB", 6))
        max_v = int(_ts_cfg("MAX_VIDEO_MB", 40))
        covered = []
        try:
            for angle, f in photo_pairs:
                name, size = save_image(current_app, f, max_mb=max_p, kind="photo")
                db.session.add(EvidenceFile(report_id=report.id, booking_id=booking.id,
                                           item_id=booking.item_id, kind="photo", angle=angle,
                                           stored_name=name, size_bytes=size,
                                           original_name=f.filename, mime="image/jpeg",
                                           exif_stripped=True, uploaded_by=current_user.id))
                covered.append(angle)
            for angle, f in video_pairs:
                name, size = save_video(current_app, f, max_mb=max_v, kind="video")
                db.session.add(EvidenceFile(report_id=report.id, booking_id=booking.id,
                                           item_id=booking.item_id, kind="video", angle=angle,
                                           stored_name=name, size_bytes=size,
                                           original_name=f.filename, uploaded_by=current_user.id))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("trustshield.handover_report", booking_id=booking.id))

        # Checklist
        selected = set(request.form.getlist("check"))
        report.set_checklist([{"item": lbl, "ok": lbl in selected}
                              for lbl in _checklist_for(category)])
        report.set_accessories([a.strip() for a in request.form.getlist("accessory") if a.strip()])
        report.set_angles(covered)

        # New existing-damage rows added by the owner
        d_types = request.form.getlist("d_type")
        d_areas = request.form.getlist("d_area")
        d_angles = request.form.getlist("d_angle")
        d_descs = request.form.getlist("d_desc")
        d_photos = request.files.getlist("d_photo")
        for i in range(len(d_types)):
            if not (d_types[i] or "").strip():
                continue
            dr = DamageRecord(item_id=booking.item_id, booking_id=booking.id,
                              damage_type=d_types[i].strip(),
                              area=(d_areas[i].strip() if i < len(d_areas) else None),
                              angle=(d_angles[i].strip() if i < len(d_angles) else None),
                              description=(d_descs[i].strip() if i < len(d_descs) else None),
                              status="existing", source_phase="handover",
                              reported_by=current_user.id)
            db.session.add(dr)
            db.session.flush()
            if i < len(d_photos) and d_photos[i] and d_photos[i].filename:
                try:
                    name, size = save_image(current_app, d_photos[i], max_mb=max_p, kind="damage")
                    db.session.add(EvidenceFile(damage_record_id=dr.id, booking_id=booking.id,
                                                item_id=booking.item_id, kind="photo",
                                                angle=dr.angle, stored_name=name, size_bytes=size,
                                                original_name=d_photos[i].filename, exif_stripped=True,
                                                uploaded_by=current_user.id))
                except ValueError:
                    pass

        booking.status = "awaiting_customer_confirmation"
        db.session.commit()
        flash("Condition report uploaded. Waiting for the customer to confirm.", "success")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    return render_template("trustshield/handover.html", booking=booking,
                           angles=_angles(), checklist=_checklist_for(category),
                           existing_damages=_existing_damages(booking.item_id),
                           min_photos=min_photos, submitted=submitted)


@ts_bp.route("/ts/bookings/<int:booking_id>/condition", methods=["GET", "POST"])
@login_required
def condition_view(booking_id):
    """Renter reviews the handover condition and confirms / reports mismatch / cancels."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.renter_id != current_user.id and not current_user.is_admin:
        abort(403)
    report = _latest_report(booking.id, "handover")
    if report is None:
        flash("No condition report is available yet.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    photos = EvidenceFile.query.filter_by(report_id=report.id, kind="photo")\
        .order_by(EvidenceFile.id).all()
    videos = EvidenceFile.query.filter_by(report_id=report.id, kind="video")\
        .order_by(EvidenceFile.id).all()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "confirm":
            if not request.form.get("confirm_accept"):
                flash("Please tick the box to confirm the condition.", "error")
                return redirect(url_for("trustshield.condition_view", booking_id=booking.id))
            # Same side effects as the old handover, reused (never edited here).
            booking.status = "picked_up"
            if booking.payment_status == "pay_on_pickup":
                booking.payment_status = "paid_demo"
            report.status = "confirmed"
            report.confirmed_by = current_user.id
            report.confirmed_at = datetime.utcnow()
            db.session.commit()
            flash("Condition confirmed. Enjoy your rental!", "success")
            return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

        if action == "mismatch":
            reason = request.form.get("mismatch_reason", "").strip() or "Customer reported a mismatch."
            report.status = "mismatch"
            report.mismatch_reason = reason
            booking.status = "approved"   # back to owner to resubmit
            db.session.commit()
            flash("Mismatch reported. The owner has been asked to re-upload the condition.", "success")
            return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

        if action == "cancel":
            from routes.bookings import _refund
            booking.status = "cancelled"
            msg = _refund(booking)
            db.session.commit()
            flash("Booking cancelled. " + (msg or ""), "success")
            return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

        flash("Unknown action.", "error")
        return redirect(url_for("trustshield.condition_view", booking_id=booking.id))

    return render_template("trustshield/condition.html", booking=booking, report=report,
                           photos=list(photos), videos=list(videos),
                           existing_damages=_existing_damages(booking.item_id))


# --------------------------------------------------------------------------
# Shared report parser (photos by angle + videos + checklist + accessories)
# --------------------------------------------------------------------------
def _parse_and_store_report(booking, phase):
    """Store a ConditionReport + evidence from the current request.
    Returns (report, error_message)."""
    photos_raw = request.files.getlist("photo")
    angles_raw = request.form.getlist("angle")
    videos_raw = request.files.getlist("video")
    vangles_raw = request.form.getlist("video_angle")
    photo_pairs = [(angles_raw[i] if i < len(angles_raw) and angles_raw[i] else "unlabeled", f)
                   for i, f in enumerate(photos_raw) if f and f.filename]
    video_pairs = [(vangles_raw[i] if i < len(vangles_raw) and vangles_raw[i] else "unlabeled", f)
                   for i, f in enumerate(videos_raw) if f and f.filename]

    min_photos = int(_ts_cfg("MIN_PHOTOS_RETURN" if phase == "return" else "MIN_PHOTOS_HANDOVER", 4))
    if len(photo_pairs) < min_photos:
        return None, f"Please upload at least {min_photos} clear condition photos."

    report = ConditionReport(booking_id=booking.id, item_id=booking.item_id,
                             phase=phase, status="submitted", created_by=current_user.id,
                             note=(request.form.get("note", "").strip() or None))
    rd = request.form.get("actual_return_date", "").strip()
    if rd:
        try:
            report.return_date = date.fromisoformat(rd)
        except ValueError:
            pass
    db.session.add(report)
    db.session.flush()

    from utils.ts_evidence import save_image, save_video
    max_p = int(_ts_cfg("MAX_PHOTO_MB", 6))
    max_v = int(_ts_cfg("MAX_VIDEO_MB", 40))
    covered = []
    try:
        for angle, f in photo_pairs:
            name, size = save_image(current_app, f, max_mb=max_p, kind="photo")
            db.session.add(EvidenceFile(report_id=report.id, booking_id=booking.id,
                                       item_id=booking.item_id, kind="photo", angle=angle,
                                       stored_name=name, size_bytes=size, original_name=f.filename,
                                       mime="image/jpeg", exif_stripped=True, uploaded_by=current_user.id))
            covered.append(angle)
        for angle, f in video_pairs:
            name, size = save_video(current_app, f, max_mb=max_v, kind="video")
            db.session.add(EvidenceFile(report_id=report.id, booking_id=booking.id,
                                       item_id=booking.item_id, kind="video", angle=angle,
                                       stored_name=name, size_bytes=size, original_name=f.filename,
                                       uploaded_by=current_user.id))
    except ValueError as e:
        db.session.rollback()
        return None, str(e)

    selected = set(request.form.getlist("check"))
    report.set_checklist([{"item": lbl, "ok": lbl in selected}
                          for lbl in _checklist_for(booking.item.category)])
    report.set_accessories([a.strip() for a in request.form.getlist("accessory") if a.strip()])
    report.set_angles(covered)
    return report, None


# --------------------------------------------------------------------------
# STAGE 3 - Return evidence + Pillow comparison (SUGGESTIONS ONLY)
# --------------------------------------------------------------------------
@ts_bp.route("/ts/bookings/<int:booking_id>/return", methods=["GET", "POST"])
@login_required
def return_report(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    if not booking.trustshield:
        return redirect(url_for("bookings.return_item", booking_id=booking.id))
    if booking.status != "picked_up":
        flash("Only an active (picked up) rental can be returned.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    existing = _latest_report(booking.id, "handover")
    if existing and existing.status != "confirmed":
        flash("The customer must confirm the condition before return.", "error")
        return redirect(url_for("bookings.booking_detail", booking_id=booking.id))

    if request.method == "POST":
        report, err = _parse_and_store_report(booking, "return")
        if err:
            flash(err, "error")
            return redirect(url_for("trustshield.return_report", booking_id=booking.id))

        # Run the suggestion-only comparison and store results (no charges here).
        handover = _latest_report(booking.id, "handover")
        if handover:
            _run_comparison(booking, handover, report)
        db.session.commit()
        flash("Return report uploaded. Please review the flagged changes.", "success")
        return redirect(url_for("trustshield.review", booking_id=booking.id))

    return render_template("trustshield/return.html", booking=booking,
                           angles=_angles(), checklist=_checklist_for(booking.item.category),
                           existing_damages=_existing_damages(booking.item_id),
                           min_photos=int(_ts_cfg("MIN_PHOTOS_RETURN", 4)),
                           today=date.today().isoformat())


def _run_comparison(booking, handover, report):
    from utils.ts_compare import compare_pair, pair_by_angle, overlaps_existing
    from utils.ts_evidence import abs_path
    ComparisonResult.query.filter_by(booking_id=booking.id).delete()
    ho_files = EvidenceFile.query.filter_by(report_id=handover.id).all()
    rt_files = EvidenceFile.query.filter_by(report_id=report.id).all()
    existing_damages = _existing_damages(booking.item_id)
    for angle, of, rf, missing in pair_by_angle(ho_files, rt_files):
        cr = ComparisonResult(booking_id=booking.id, handover_report_id=handover.id,
                              return_report_id=report.id, angle=angle)
        if missing:
            cr.confidence = "needs_manual"
            cr.needs_manual = True
            cr.set_regions([])
        else:
            res = compare_pair(current_app, abs_path(current_app, of.stored_name),
                               abs_path(current_app, rf.stored_name))
            cr.similarity = res["similarity"]
            cr.confidence = res["confidence"]
            cr.set_regions(res["regions"])
            cr.overlay_stored_name = res["overlay_stored_name"]
            cr.needs_manual = bool(res["regions"]) and cr.confidence == "low"
            cr.matched_existing = overlaps_existing(angle, existing_damages) is not None
            if cr.overlay_stored_name:
                db.session.add(EvidenceFile(report_id=report.id, booking_id=booking.id,
                                           item_id=booking.item_id, kind="overlay", angle=angle,
                                           stored_name=cr.overlay_stored_name,
                                           original_name="overlay.jpg", mime="image/jpeg",
                                           exif_stripped=True, uploaded_by=current_user.id))
        db.session.add(cr)


def _report_photo_evidence(report_id, angle, kind="photo"):
    return EvidenceFile.query.filter_by(report_id=report_id, angle=angle, kind=kind).first()


@ts_bp.route("/ts/bookings/<int:booking_id>/review", methods=["GET", "POST"])
@login_required
def review(booking_id):
    """Owner reviews suggested changes and confirms / dismisses them (suggestions)."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    handover = _latest_report(booking.id, "handover")
    report = _latest_report(booking.id, "return")
    comparisons = ComparisonResult.query.filter_by(booking_id=booking.id)\
        .order_by(ComparisonResult.id).all()
    category = booking.item.category
    rules = _rules_for(category)
    from utils.ts_compare import overlaps_existing as tsc_overlaps

    if request.method == "POST":
        action = request.form.get("action", "")
        angle = request.form.get("angle", "").strip()
        if action in ("confirm_new", "add_missed"):
            cr = ComparisonResult.query.filter_by(booking_id=booking.id, angle=angle).first()
            match = tsc_overlaps(angle, _existing_damages(booking.item_id))
            if match is not None:
                # Previously reported: NOT attributed to this renter.
                if cr:
                    cr.matched_existing = True
                    db.session.commit()
                flash("Matched a previously reported damage - not charged to the customer.", "success")
            else:
                dr = DamageRecord(item_id=booking.item_id, booking_id=booking.id,
                                  damage_type=request.form.get("rule_key", "damage"),
                                  area=request.form.get("area", "").strip() or None,
                                  angle=angle or None,
                                  description=request.form.get("description", "").strip() or None,
                                  status="new_proposed", source_phase="return",
                                  reported_by=current_user.id,
                                  attributed_renter_id=booking.renter_id)
                db.session.add(dr)
                db.session.commit()
                flash("Change confirmed as possible new damage (proposed only).", "success")
            return redirect(url_for("trustshield.review", booking_id=booking.id))

        if action in ("not_damage", "not_sure"):
            cr = ComparisonResult.query.filter_by(booking_id=booking.id, angle=angle).first()
            if cr:
                cr.needs_manual = (action == "not_sure")
                db.session.commit()
            flash("Noted. Nothing was charged.", "success")
            return redirect(url_for("trustshield.review", booking_id=booking.id))

        if action == "no_new_damage":
            from utils.ts_settlement import finalize_settlement
            rdate = (report.return_date if report and report.return_date else date.today())
            finalize_settlement(booking, rdate, verified_amount=0,
                                return_note="TrustShield: owner confirmed no new damage.")
            flash("Returned with no new damage. Settlement generated.", "success")
            return redirect(url_for("bookings.settlement", booking_id=booking.id))

        flash("Unknown action.", "error")
        return redirect(url_for("trustshield.review", booking_id=booking.id))

    rows = []
    for cr in comparisons:
        ov = None
        if cr.overlay_stored_name:
            ov = EvidenceFile.query.filter_by(booking_id=booking.id, kind="overlay",
                                             angle=cr.angle).first()
        rows.append({
            "cr": cr,
            "orig": _report_photo_evidence(handover.id, cr.angle) if handover else None,
            "ret": _report_photo_evidence(report.id, cr.angle) if report else None,
            "overlay": ov,
        })
    return render_template("trustshield/review.html", booking=booking,
                           handover=handover, report=report, rows=rows, rules=rules,
                           existing_damages=_existing_damages(booking.item_id))


# --------------------------------------------------------------------------
# STAGE 4 - Verified penalty, finalization, disputes, admin
# --------------------------------------------------------------------------
def _active_case(booking_id):
    return (DamageCase.query.filter_by(booking_id=booking_id)
            .order_by(DamageCase.id.desc()).first())


def _new_proposed_records(booking_id):
    return DamageRecord.query.filter_by(booking_id=booking_id, status="new_proposed")\
        .order_by(DamageRecord.id).all()


def _store_quote(app, file_storage, max_mb):
    """Validate + store a repair quote (photo or PDF). Returns EvidenceFile-ready
    (stored_name, size, mime) or raises ValueError."""
    raw = getattr(file_storage, "filename", "") or ""
    ext = raw.rsplit(".", 1)[1].lower() if "." in raw else ""
    if ext not in ("jpg", "jpeg", "png", "pdf"):
        raise ValueError("Quote must be a photo (JPG/PNG) or a PDF.")
    data = file_storage.read()
    if not data:
        raise ValueError("Empty quote file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError("Quote file is too large (max %d MB)." % max_mb)
    from utils.ts_evidence import save_bytes
    if ext == "pdf":
        name, size = save_bytes(app, data, suffix=".pdf", kind="quote")
        return name, size, "application/pdf"
    from werkzeug.datastructures import FileStorage
    import io
    name, size = __import__("utils.ts_evidence", fromlist=["save_image"])\
        .save_image(app, FileStorage(stream=io.BytesIO(data)), max_mb=max_mb, kind="quote")
    return name, size, "image/jpeg"


def _late_preview(booking, actual_return_date):
    from utils.settlement import calculate_settlement
    s = calculate_settlement(deposit=booking.deposit, end_date=booking.end_date,
                             actual_return_date=actual_return_date,
                             late_fee_per_day=booking.item.late_fee_per_day or 0,
                             damage_level="none", total_rent=booking.total_rent,
                             commission_percent=getattr(booking, "commission_percent", 10.0))
    return s


@ts_bp.route("/ts/bookings/<int:booking_id>/propose", methods=["GET", "POST"])
@login_required
def propose_penalty(booking_id):
    """Owner turns confirmed new damages into a penalty proposal (nothing charged)."""
    booking = Booking.query.get_or_404(booking_id)
    if booking.item.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    records = _new_proposed_records(booking.id)
    category = booking.item.category
    deposit = float(booking.deposit or 0)
    cap_percent = float(_ts_cfg("DAMAGE_CAP_PERCENT_OF_DEPOSIT", 100))
    quote_max = int(_ts_cfg("QUOTE_MAX_MB", 5))
    from utils.ts_penalty import propose_cost, cap_amount
    from datetime import timedelta
    from decimal import Decimal as _Dec, ROUND_HALF_UP

    def _cap_limit(dep, pct):
        v = _Dec(str(dep)) * _Dec(str(pct)) / _Dec("100")
        return int(v.quantize(_Dec("1"), rounding=ROUND_HALF_UP))

    existing_case = _active_case(booking.id)
    if existing_case is not None:
        return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

    if request.method == "POST":
        choices = []
        total = 0
        for rec in records:
            rule_key = request.form.get(f"rule_{rec.id}", rec.damage_type or "scratch")
            pc = propose_cost(category, rule_key, deposit) or propose_cost(category, "scratch", deposit)
            amt_raw = request.form.get(f"amount_{rec.id}", "").strip()
            amount = int(float(amt_raw)) if amt_raw else pc["default"]
            if amount < pc["min"]:
                amount = pc["min"]
            needs_quote = amount > pc["max"]
            choices.append({"rec": rec, "pc": pc, "amount": amount, "needs_quote": needs_quote,
                            "rule_key": rule_key})
            total += amount

        cap_limit = _cap_limit(deposit, cap_percent)
        if total > cap_limit:
            flash(f"Total penalty exceeds the cap of Rs {cap_limit} "
                  f"({int(cap_percent)}% of deposit). Please reduce amounts.", "error")
            return redirect(url_for("trustshield.propose_penalty", booking_id=booking.id))

        # Every above-range claim must carry a quote attachment.
        for ch in choices:
            if ch["needs_quote"]:
                f = request.files.get(f"quote_{ch['rec'].id}")
                if not (f and f.filename):
                    db.session.rollback()
                    flash(f"'{ch['pc']['label']}' is above the rule range - attach a repair "
                          "quote or invoice (photo or PDF).", "error")
                    return redirect(url_for("trustshield.propose_penalty", booking_id=booking.id))

        case = DamageCase(booking_id=booking.id, item_id=booking.item_id,
                          created_by=current_user.id, status="awaiting_customer",
                          review_deadline=datetime.utcnow() +
                          timedelta(hours=int(_ts_cfg("CUSTOMER_REVIEW_HOURS", 48))))
        db.session.add(case)
        db.session.flush()
        try:
            for ch in choices:
                quote_id = None
                if ch["needs_quote"]:
                    f = request.files.get(f"quote_{ch['rec'].id}")
                    name, size, mime = _store_quote(current_app, f, quote_max)
                    ev = EvidenceFile(booking_id=booking.id, item_id=booking.item_id,
                                      kind="quote", stored_name=name, size_bytes=size,
                                      original_name=f.filename, mime=mime, exif_stripped=True,
                                      uploaded_by=current_user.id)
                    db.session.add(ev)
                    db.session.flush()
                    quote_id = ev.id
                claim = DamageClaimItem(
                    case_id=case.id, damage_record_id=ch["rec"].id, rule_key=ch["rule_key"],
                    label=ch["pc"]["label"], severity=ch["pc"]["severity"],
                    min_amount=ch["pc"]["min"], max_amount=ch["pc"]["max"],
                    proposed_amount=ch["amount"], verified_amount=0,
                    percent_of_deposit=ch["pc"]["percent_of_deposit"],
                    requires_quote=ch["needs_quote"], quote_file_id=quote_id,
                    admin_approved=False, status="proposed")
                db.session.add(claim)
            case.proposed_total = total
            db.session.commit()
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("trustshield.propose_penalty", booking_id=booking.id))

        flash("Penalty proposed. The customer must review it before anything is deducted.",
              "success")
        return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

    rows = []
    for rec in records:
        rule_key = rec.damage_type or "scratch"
        pc = propose_cost(category, rule_key, deposit) or propose_cost(category, "scratch", deposit)
        rows.append({"rec": rec, "pc": pc})
    return render_template("trustshield/propose.html", booking=booking, rows=rows,
                           rules=_rules_for(category), deposit=deposit,
                           cap_percent=cap_percent, cap_total=_cap_limit(deposit, cap_percent),
                           total_default=sum(r["pc"]["default"] for r in rows))


@ts_bp.route("/ts/bookings/<int:booking_id>/damage-report", methods=["GET", "POST"])
@login_required
def damage_report(booking_id):
    """Customer reviews evidence + proposed penalty and accepts / disputes."""
    booking = Booking.query.get_or_404(booking_id)
    if not can_view_booking(booking, current_user):
        abort(403)
    case = _active_case(booking.id)
    if case is None:
        return redirect(url_for("trustshield.review", booking_id=booking.id))

    # Lazy deadline handling: past due with no answer -> admin review, NOT charged.
    if case.status == "awaiting_customer" and case.review_deadline and \
            datetime.utcnow() > case.review_deadline:
        case.status = "admin_review"
        db.session.commit()

    handover = _latest_report(booking.id, "handover")
    report = _latest_report(booking.id, "return")
    rdate = report.return_date if report and report.return_date else date.today()
    late = _late_preview(booking, rdate)

    if request.method == "POST" and booking.renter_id == current_user.id:
        from utils.ts_penalty import deposit_status_text
        action = request.form.get("action", "")
        if case.finalized or case.status in ("resolved", "closed"):
            flash("This damage report is already finalised.", "error")
            return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

        if action == "accept_all":
            for claim in case.claims:
                if claim.status == "proposed":
                    claim.status = "accepted"
                    claim.verified_amount = claim.proposed_amount
                    claim.decided_by = current_user.id
            from utils.ts_settlement import finalize_case
            finalize_case(booking, case, actual_return_date=rdate)
            flash("Accepted. Settlement generated.", "success")
            return redirect(url_for("bookings.settlement", booking_id=booking.id))

        if action in ("dispute_all", "accept_some_dispute_rest"):
            if case.dispute is not None:
                flash("You have already raised a dispute for this case.", "error")
                return redirect(url_for("trustshield.damage_report", booking_id=booking.id))
            reason = request.form.get("reason", "").strip()
            comment = request.form.get("comment", "").strip()
            import config as _c
            if reason not in _c.TS_DISPUTE_REASONS:
                flash("Please choose a valid reason.", "error")
                return redirect(url_for("trustshield.damage_report", booking_id=booking.id))
            if len(comment) < 10 or len(comment) > 600:
                flash("Your comment must be between 10 and 600 characters.", "error")
                return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

            if action == "dispute_all":
                disputed = [cl.id for cl in case.claims if cl.status == "proposed"]
            else:
                accept_ids = {int(x) for x in request.form.getlist("accept_claim") if x.isdigit()}
                disputed = [cl.id for cl in case.claims
                            if cl.status == "proposed" and cl.id not in accept_ids]
                for cl in case.claims:
                    if cl.status == "proposed" and cl.id in accept_ids:
                        cl.status = "accepted"
                        cl.verified_amount = cl.proposed_amount
                        cl.decided_by = current_user.id
            if not disputed:
                flash("Nothing to dispute - please accept or select items to dispute.", "error")
                return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

            dispute = Dispute(case_id=case.id, raised_by=current_user.id, reason=reason,
                              comment=comment)
            dispute.set_claim_ids(disputed)
            db.session.add(dispute)
            db.session.flush()
            for cl in case.claims:
                if cl.id in disputed:
                    cl.status = "disputed"
            # Optional counter-evidence (photos only, small).
            for f in request.files.getlist("counter"):
                if f and f.filename:
                    from utils.ts_evidence import save_image
                    try:
                        name, size = save_image(current_app, f,
                                                max_mb=int(_ts_cfg("MAX_PHOTO_MB", 6)), kind="counter")
                        db.session.add(DisputeFile(dispute_id=dispute.id, stored_name=name,
                                                   kind="photo", original_name=f.filename,
                                                   size_bytes=size, uploaded_by=current_user.id))
                    except ValueError:
                        pass
            case.status = "disputed"
            db.session.commit()
            flash("Dispute raised. An admin will review the disputed items. "
                  "Nothing has been charged.", "success")
            return redirect(url_for("trustshield.damage_report", booking_id=booking.id))

    import config as _c
    from utils.ts_penalty import deposit_status_text
    galleries = _galleries(handover, report)
    return render_template("trustshield/damage_report.html", booking=booking, case=case,
                           claims=case.claims, galleries=galleries,
                           existing_damages=_existing_damages(booking.item_id),
                           late=late, deposit=float(booking.deposit or 0),
                           refund_status=deposit_status_text(booking, case=case),
                           dispute_reasons=_c.TS_DISPUTE_REASONS, report=report)


def _galleries(handover, report):
    """Per-angle gallery: original, return, overlay EvidenceFiles."""
    comparisons = ComparisonResult.query.filter_by(
        booking_id=(report.booking_id if report else None)).order_by(ComparisonResult.id).all() \
        if report else []
    out = []
    for cr in comparisons:
        out.append({
            "cr": cr,
            "orig": _report_photo_evidence(handover.id, cr.angle) if handover else None,
            "ret": _report_photo_evidence(report.id, cr.angle) if report else None,
            "overlay": EvidenceFile.query.filter_by(booking_id=cr.booking_id, kind="overlay",
                                                    angle=cr.angle).first()
            if cr.overlay_stored_name else None,
        })
    return out


# --------------------------------------------------------------------------
# Admin: dispute queue + per-item resolution
# --------------------------------------------------------------------------
@ts_bp.route("/admin/ts/disputes")
@login_required
def admin_disputes():
    if not current_user.is_admin:
        abort(403)
    disputes = Dispute.query.order_by(Dispute.id.desc()).all()
    rows = []
    for d in disputes:
        c = DamageCase.query.get(d.case_id)
        rows.append({"d": d, "case": c,
                     "booking": Booking.query.get(c.booking_id) if c else None})
    return render_template("trustshield/admin_disputes.html", disputes=disputes, rows=rows)


@ts_bp.route("/admin/ts/disputes/<int:dispute_id>", methods=["GET", "POST"])
@login_required
def admin_dispute_detail(dispute_id):
    if not current_user.is_admin:
        abort(403)
    dispute = Dispute.query.get_or_404(dispute_id)
    case = DamageCase.query.get(dispute.case_id)
    booking = Booking.query.get(case.booking_id)
    disputed_ids = set(dispute.get_claim_ids())

    if request.method == "POST":
        note = request.form.get("note", "").strip()
        for cid in disputed_ids:
            claim = DamageClaimItem.query.get(cid)
            if claim is None or claim.status != "disputed":
                continue
            decision = request.form.get(f"decision_{cid}", "")
            if decision == "uphold":
                claim.status = "upheld"
                claim.verified_amount = claim.proposed_amount
            elif decision == "reduce":
                amt_raw = request.form.get(f"amount_{cid}", "").strip()
                amt = int(float(amt_raw)) if amt_raw else 0
                claim.status = "reduced"
                claim.verified_amount = max(0, min(amt, int(claim.proposed_amount)))
            elif decision == "reject":
                claim.status = "rejected"
                claim.verified_amount = 0
            else:
                flash("Please decide every disputed item (uphold / reduce / reject).", "error")
                return redirect(url_for("trustshield.admin_dispute_detail", dispute_id=dispute.id))
            claim.decided_by = current_user.id
            claim.note = note or None
            claim.admin_approved = True
        remaining = [DamageClaimItem.query.get(cid) for cid in disputed_ids]
        if any(cl is not None and cl.status == "disputed" for cl in remaining):
            return redirect(url_for("trustshield.admin_dispute_detail", dispute_id=dispute.id))
        dispute.status = "resolved"
        dispute.resolved_by = current_user.id
        dispute.resolved_at = datetime.utcnow()
        dispute.resolution_note = note or None
        from utils.ts_settlement import finalize_case
        rdate = _latest_report(booking.id, "return")
        finalize_case(booking, case,
                      actual_return_date=(rdate.return_date if rdate and rdate.return_date else date.today()))
        flash("Dispute resolved and settlement finalised.", "success")
        return redirect(url_for("trustshield.admin_disputes"))

    claims = [cl for cl in case.claims if cl.id in disputed_ids]
    return render_template("trustshield/admin_dispute_detail.html",
                           dispute=dispute, case=case, booking=booking, claims=claims,
                           galleries=_galleries(_latest_report(booking.id, "handover"),
                                                _latest_report(booking.id, "return")),
                           existing_damages=_existing_damages(booking.item_id))
