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
