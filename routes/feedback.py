"""Feedback routes – submission with rate limiting and user view."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Feedback

feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """Submit feedback for guest or logged-in user with rate limit (5/hr) and length check (10-500)."""
    # Accept JSON or form-encoded data
    data = request.get_json(silent=True) or request.form

    msg = (data.get("message") or "").strip()
    if len(msg) < 10 or len(msg) > 500:
        return jsonify({"error": "Message must be between 10 and 500 characters."}), 400

    fb_type = (data.get("type") or "other").strip().lower()
    if fb_type not in Feedback.TYPES:
        fb_type = "other"

    rating_raw = data.get("rating")
    rating = None
    if rating_raw:
        try:
            r_val = int(rating_raw)
            if 1 <= r_val <= 5:
                rating = r_val
        except (ValueError, TypeError):
            pass

    page_url = (data.get("page_url") or "").strip() or None

    related_item_id = None
    raw_item = data.get("related_item_id")
    if raw_item:
        try:
            related_item_id = int(raw_item)
        except (ValueError, TypeError):
            related_item_id = None

    related_booking_id = None
    raw_booking = data.get("related_booking_id")
    if raw_booking:
        try:
            related_booking_id = int(raw_booking)
        except (ValueError, TypeError):
            related_booking_id = None

    # Rate limiting: max 5 submissions per user or IP per hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    ip_addr = request.remote_addr or "127.0.0.1"

    if current_user.is_authenticated:
        recent_count = Feedback.query.filter(
            Feedback.user_id == current_user.id,
            Feedback.created_at >= one_hour_ago
        ).count()
    else:
        recent_count = Feedback.query.filter(
            Feedback.ip_address == ip_addr,
            Feedback.created_at >= one_hour_ago
        ).count()

    if recent_count >= 5:
        return jsonify({"error": "Rate limit exceeded. Maximum 5 feedback submissions per hour."}), 429

    feedback = Feedback(
        user_id=current_user.id if current_user.is_authenticated else None,
        type=fb_type,
        rating=rating,
        message=msg,
        page_url=page_url,
        related_item_id=related_item_id,
        related_booking_id=related_booking_id,
        status="new",
        reply_seen=True,
        ip_address=ip_addr,
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"success": True, "message": "Thank you! Your feedback has been received."}), 201


@feedback_bp.route("/my-feedback")
@login_required
def my_feedback():
    """Show the user's submitted feedback with status badges and admin replies."""
    submissions = Feedback.query.filter_by(user_id=current_user.id)\
        .order_by(Feedback.created_at.desc()).all()

    # Mark all unseen replies as seen
    unseen = [f for f in submissions if not f.reply_seen]
    if unseen:
        for f in unseen:
            f.reply_seen = True
        db.session.commit()

    return render_template("my_feedback.html", submissions=submissions)
