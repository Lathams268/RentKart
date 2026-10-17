"""Item routes – add, detail, browse."""
import os, uuid, json
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app,
)
from flask_login import login_required, current_user
from models import db, Item

items_bp = Blueprint("items", __name__, url_prefix="/items")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@items_bp.route("/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_availability(item_id):
    """Toggle item availability (owner only)."""
    item = Item.query.get_or_404(item_id)
    if item.owner_id != current_user.id:
        from flask import abort
        abort(403)
    item.is_available = not item.is_available
    db.session.commit()
    status_str = "available" if item.is_available else "unavailable"
    flash(f"Item marked as {status_str}.", "success")
    return redirect(request.referrer or url_for("bookings.owner_dashboard"))


@items_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_item():
    """Add a new rental item with dynamic category-specific fields."""
    from utils.plans import can_add_item
    from markupsafe import Markup

    if not can_add_item(current_user):
        pricing_url = url_for("subscriptions.pricing")
        flash(Markup(f'Item limit reached for your plan. <a href="{pricing_url}" class="underline font-bold">Upgrade plan</a> to list more items.'), "error")
        return redirect(url_for("bookings.owner_dashboard"))

    categories = current_app.config["CATEGORIES"]

    if request.method == "POST":
        # --- Common fields ---
        category      = request.form.get("category", "").strip()
        title         = request.form.get("title", "").strip()
        description   = request.form.get("description", "").strip()
        price_per_day = request.form.get("price_per_day", "").strip()
        deposit       = request.form.get("deposit", "0").strip()
        late_fee      = request.form.get("late_fee_per_day", "0").strip()
        purchase_price_raw = request.form.get("purchase_price", "").strip()
        lat           = request.form.get("lat", type=float)
        lng           = request.form.get("lng", type=float)

        purchase_price = None
        if purchase_price_raw:
            try:
                purchase_price = int(float(purchase_price_raw))
            except (ValueError, TypeError):
                purchase_price = None

        # Validation
        errors = []
        if category not in categories:
            errors.append("Please select a valid category.")
        if not title:
            errors.append("Title is required.")
        if not price_per_day:
            errors.append("Price per day is required.")
        else:
            try:
                price_per_day = float(price_per_day)
            except ValueError:
                errors.append("Price must be a number.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("items.add_item"))

        # Image upload
        image_filename = None
        file = request.files.get("image")
        if file and file.filename and _allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            upload_dir = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, image_filename))

        # Dynamic attributes from category config
        attrs = {}
        if category in categories:
            for field in categories[category]["fields"]:
                val = request.form.get(f"attr_{field['name']}", "").strip()
                if field["type"] == "checkbox":
                    val = f"attr_{field['name']}" in request.form
                attrs[field["name"]] = val

        item = Item(
            owner_id=current_user.id,
            category=category,
            title=title,
            description=description,
            price_per_day=price_per_day,
            deposit=float(deposit or 0),
            late_fee_per_day=float(late_fee or 0),
            lat=lat if lat else current_user.lat,
            lng=lng if lng else current_user.lng,
            image=image_filename,
            purchase_price=purchase_price,
        )
        item.set_attributes(attrs)
        db.session.add(item)
        db.session.commit()
        flash("Item listed successfully!", "success")
        return redirect(url_for("items.item_detail", item_id=item.id))

    return render_template(
        "add_item.html",
        categories=categories,
        categories_json=json.dumps(categories),
    )


@items_bp.route("/<int:item_id>")
def item_detail(item_id):
    """Show a single item with its dynamic attributes, reviews, and smart deposit booking card."""
    from datetime import date
    from models import Review, Booking
    from utils.booking import get_blocked_dates
    from utils.trust import get_user_trust
    item = Item.query.get_or_404(item_id)
    categories = current_app.config["CATEGORIES"]
    cat_config = categories.get(item.category, {})
    attrs = item.get_attributes()
    blocked_dates = get_blocked_dates(item)

    trust_info = get_user_trust(current_user) if current_user.is_authenticated else None
    mult = trust_info["multiplier"] if trust_info else 1.0
    smart_deposit = round((item.deposit or 0) * mult)

    latest_reviews = Review.query.join(Booking).filter(Booking.item_id == item.id)\
        .order_by(Review.created_at.desc()).limit(5).all()

    return render_template(
        "item_detail.html",
        item=item,
        cat_config=cat_config,
        attrs=attrs,
        blocked_dates=blocked_dates,
        today=date.today().isoformat(),
        trust_info=trust_info,
        smart_deposit=smart_deposit,
        latest_reviews=latest_reviews,
    )
