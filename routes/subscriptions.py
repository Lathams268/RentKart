"""Subscription routes – pricing, demo checkout, subscription management."""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from models import db, Subscription, Item
from config import PLANS
from utils.plans import get_plan

subscriptions_bp = Blueprint("subscriptions", __name__)


@subscriptions_bp.route("/pricing")
def pricing():
    """Public pricing page with monthly/yearly toggle and comparison table."""
    return render_template("pricing.html", plans=PLANS)


@subscriptions_bp.route("/subscribe/<plan>", methods=["GET", "POST"])
def subscribe(plan):
    """Demo checkout to subscribe or upgrade to Pro or Business."""
    if plan not in PLANS:
        abort(404)

    # Free plan button must not go to checkout: redirect to dashboard or login
    if plan == "free":
        flash("The Free plan is active by default.", "info")
        return redirect(url_for("bookings.owner_dashboard") if current_user.is_authenticated else url_for("auth.login"))

    cycle = request.args.get("cycle", "monthly")
    if cycle not in ("monthly", "yearly"):
        cycle = "monthly"

    # If the user is not logged in, redirect to /login?next=<the subscribe URL including the cycle>
    if not current_user.is_authenticated:
        flash("Please log in to continue.", "error")
        sub_url = url_for("subscriptions.subscribe", plan=plan, cycle=cycle)
        return redirect(url_for("auth.login", next=sub_url))

    plan_info = PLANS[plan]

    # If the user already has that plan active, show a message instead of charging again
    if current_user.current_plan() == plan:
        flash(f"You already have an active {plan_info['label']} plan.", "info")
        return redirect(url_for("subscriptions.subscription_view"))

    amount = plan_info["price_month"] if cycle == "monthly" else plan_info["price_month"] * 10

    if request.method == "POST":
        payment_method = request.form.get("payment_method", "upi")
        billing_cycle = request.form.get("billing_cycle", cycle)
        if billing_cycle not in ("monthly", "yearly"):
            billing_cycle = "monthly"

        # Calculate duration and demo amount
        days = 365 if billing_cycle == "yearly" else 30
        charge_amount = plan_info["price_month"] if billing_cycle == "monthly" else plan_info["price_month"] * 10
        start = date.today()
        end = start + timedelta(days=days)

        # Create subscription record (one row per purchase)
        sub = Subscription(
            user_id=current_user.id,
            plan=plan,
            billing_cycle=billing_cycle,
            status="active",
            start_date=start,
            end_date=end,
            amount_paid=charge_amount,
            payment_method=payment_method if payment_method in ("upi", "card") else "upi",
        )
        db.session.add(sub)
        db.session.commit()
        flash(f"Successfully subscribed to {plan_info['label']} Plan (Demo)! All features are now unlocked.", "success")
        return redirect(url_for("subscriptions.subscription_view"))

    return render_template(
        "subscribe_checkout.html",
        plan_key=plan,
        plan_info=plan_info,
        cycle=cycle,
        amount=amount,
    )



@subscriptions_bp.route("/subscription")
@login_required
def subscription_view():
    """Manage current plan, view renewal date, days left, usage meter, and payment history."""
    current_plan_key = current_user.current_plan()
    plan_info = PLANS.get(current_plan_key, PLANS["free"])
    active_sub = current_user.active_subscription()

    item_count = Item.query.filter_by(owner_id=current_user.id).count()
    max_items = plan_info["max_items"]

    history = Subscription.query.filter_by(user_id=current_user.id)\
        .order_by(Subscription.created_at.desc()).all()

    return render_template(
        "subscription.html",
        current_plan=current_plan_key,
        plan_info=plan_info,
        active_sub=active_sub,
        item_count=item_count,
        max_items=max_items,
        history=history,
        today=date.today(),
    )


@subscriptions_bp.route("/subscription/cancel", methods=["POST"])
@login_required
def cancel_subscription():
    """Cancel subscription. Plan remains active until end_date."""
    active_sub = current_user.active_subscription()
    if not active_sub or active_sub.status == "cancelled":
        flash("No active cancellable subscription found.", "error")
        return redirect(url_for("subscriptions.subscription_view"))

    active_sub.status = "cancelled"
    db.session.commit()
    flash(f"Subscription cancelled. Your benefits remain active until {active_sub.end_date}.", "info")
    return redirect(url_for("subscriptions.subscription_view"))
