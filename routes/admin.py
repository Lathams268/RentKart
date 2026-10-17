"""Admin routes – metrics dashboard and feedback management."""
from datetime import date
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from models import db, User, Item, Booking, Feedback, Subscription
from config import PLANS

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator ensuring only users with is_admin=True can access."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route("")
@admin_required
def dashboard():
    """Admin overview with platform statistics, MRR, and Chart.js feedback visualization."""
    today = date.today()

    total_users = User.query.count()
    total_items = Item.query.count()
    total_bookings = Booking.query.count()

    # Active subscriptions per plan and Monthly Recurring Revenue (MRR)
    # Active subscriptions are those with status in ('active', 'cancelled') and end_date >= today
    active_subs = Subscription.query.filter(
        Subscription.status.in_(["active", "cancelled"]),
        Subscription.end_date >= today,
    ).all()

    active_subs_by_plan = {"free": 0, "pro": 0, "business": 0}
    # Count owners on free (all users who don't have an active pro/business sub)
    paid_user_ids = set()
    mrr = 0.0

    for sub in active_subs:
        if sub.plan in active_subs_by_plan:
            active_subs_by_plan[sub.plan] += 1
            paid_user_ids.add(sub.user_id)
            mrr += PLANS.get(sub.plan, {}).get("price_month", 0)

    # Free plan count = total users - users on active paid plans
    active_subs_by_plan["free"] = max(0, total_users - len(paid_user_ids))

    # Feedback metrics
    all_feedbacks = Feedback.query.all()
    ratings = [f.rating for f in all_feedbacks if f.rating is not None]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    new_feedback_count = Feedback.query.filter_by(status="new").count()

    # Feedback distribution by type for Chart.js
    feedback_types = ["bug", "suggestion", "complaint", "praise", "other"]
    feedback_counts = {t: 0 for t in feedback_types}
    for f in all_feedbacks:
        if f.type in feedback_counts:
            feedback_counts[f.type] += 1
        else:
            feedback_counts["other"] += 1

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_items=total_items,
        total_bookings=total_bookings,
        active_subs_by_plan=active_subs_by_plan,
        mrr=mrr,
        avg_rating=avg_rating,
        new_feedback_count=new_feedback_count,
        feedback_types=feedback_types,
        feedback_counts=[feedback_counts[t] for t in feedback_types],
    )


@admin_bp.route("/feedback")
@admin_required
def feedback_list():
    """List of all feedback entries with filters for type, status, and rating."""
    f_type = request.args.get("type", "").strip().lower()
    f_status = request.args.get("status", "").strip().lower()
    f_rating = request.args.get("rating", type=int)

    q = Feedback.query

    if f_type and f_type in Feedback.TYPES:
        q = q.filter_by(type=f_type)
    if f_status and f_status in Feedback.STATUSES:
        q = q.filter_by(status=f_status)
    if f_rating and 1 <= f_rating <= 5:
        q = q.filter_by(rating=f_rating)

    feedbacks = q.order_by(Feedback.created_at.desc()).all()

    return render_template(
        "admin/feedback.html",
        feedbacks=feedbacks,
        sel_type=f_type,
        sel_status=f_status,
        sel_rating=f_rating,
        types=Feedback.TYPES,
        statuses=Feedback.STATUSES,
    )


@admin_bp.route("/feedback/<int:feedback_id>/status", methods=["POST"])
@admin_required
def update_status(feedback_id):
    """Mark feedback as reviewed or resolved."""
    fb = Feedback.query.get_or_404(feedback_id)
    new_status = request.form.get("status", "").strip()
    if new_status in Feedback.STATUSES:
        fb.status = new_status
        db.session.commit()
        flash(f"Feedback #{fb.id} status updated to {new_status}.", "success")
    return redirect(request.referrer or url_for("admin.feedback_list"))


@admin_bp.route("/feedback/<int:feedback_id>/reply", methods=["POST"])
@admin_required
def reply_feedback(feedback_id):
    """Save admin reply to feedback and notify user by setting reply_seen to False."""
    fb = Feedback.query.get_or_404(feedback_id)
    reply_text = request.form.get("admin_reply", "").strip()
    if reply_text:
        fb.admin_reply = reply_text
        fb.reply_seen = False
        if fb.status == "new":
            fb.status = "reviewed"
        db.session.commit()
        flash(f"Reply saved for feedback #{fb.id}.", "success")
    return redirect(request.referrer or url_for("admin.feedback_list"))
