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
