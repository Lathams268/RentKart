"""Item routes – add, edit, detail, browse."""
import os, uuid, json
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort,
)
from flask_login import login_required, current_user
from models import db, Item
from utils.events import record_event
from utils.media import MediaError, max_photos, save_photos, thumb_for

items_bp = Blueprint("items", __name__, url_prefix="/items")

MAX_GALLERY = 6


def _photo_limit():
    """Plan-aware photo limit (Owner Pro gets more; free stays at 6)."""
    from utils.revenue import photo_limit_for
    return photo_limit_for(current_user)


def _photo_files():
    """Every photo input on the listing form (new + legacy field names)."""
    files = (request.files.getlist("photos")
             + request.files.getlist("gallery")
             + [request.files.get("image")])
    return [f for f in files if f and getattr(f, "filename", "")]


def _gallery_url(name: str) -> str:
    """Public URL for a gallery file name (media key, upload or full URL)."""
    name = str(name or "")
    if name.startswith(("http://", "https://", "/static/")):
        return name
    rel = name if "/" in name else f"uploads/{name}"
    return url_for("static", filename=rel)


@items_bp.route("/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_availability(item_id):
    """Toggle item availability (owner only)."""
    item = Item.query.get_or_404(item_id)
    if item.owner_id != current_user.id:
        abort(403)
    item.is_available = not item.is_available
    db.session.commit()
    status_str = "available" if item.is_available else "unavailable"
    record_event(current_user, "listing_paused" if not item.is_available else "listing_updated",
                 detail={"item_id": item.id, "available": item.is_available})
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

        # Delivery + cash-on-pickup (every category)
        delivery_available = "delivery_available" in request.form
        cod_available = "cod_available" in request.form
        delivery_charge_raw = request.form.get("delivery_charge", "0").strip() or "0"
        try:
            delivery_charge = float(delivery_charge_raw)
        except ValueError:
            delivery_charge = 0.0
        # Whole-rupee rounding on save (delivery charge + late fee per day)
        delivery_charge = float(round(delivery_charge))

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

        # Discount percent (0-90, optional, whole number)
        discount_raw = request.form.get("discount_percent", "0").strip() or "0"
        try:
            discount_percent = int(float(discount_raw))
        except (ValueError, TypeError):
            discount_percent = 0
        discount_percent = max(0, min(90, discount_percent))

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("items.add_item"))

        # Photos: up to 6 files, validated and re-encoded by utils.media.
        try:
            photos = save_photos(_photo_files(), limit=_photo_limit())
        except MediaError as exc:
            flash(str(exc), "error")
            return redirect(url_for("items.add_item"))
        if len(_photo_files()) > _photo_limit():
            flash(f"Only the first {_photo_limit()} photos were kept.", "error")
        image_key = photos[0]["key"] if photos else None
        gallery = [p["key"] for p in photos]
        # Free-text search tags (comma separated) feed the marketplace search.
        tags = (request.form.get("tags") or "").strip()[:1000]

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
            discount_percent=discount_percent,
            deposit=float(deposit or 0),
            late_fee_per_day=float(round(float(late_fee or 0))),
            lat=lat if lat else current_user.lat,
            lng=lng if lng else current_user.lng,
            image=image_key,
            purchase_price=purchase_price,
            delivery_available=delivery_available,
            delivery_charge=delivery_charge,
            cod_available=cod_available,
            tags=tags,
        )
        item.set_attributes(attrs)
        item.set_images(gallery)
        db.session.add(item)
        db.session.commit()
        record_event(current_user, "listing_created",
                     detail={"item_id": item.id, "title": item.title})
        flash("Item listed successfully!", "success")
        return redirect(url_for("items.item_detail", item_id=item.id))

    return render_template(
        "add_item.html",
        item=None,
        attrs={},
        gallery=[],
        categories=categories,
        categories_json=json.dumps(categories),
    )


@items_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    """Owner edit: prices, photos, tags, availability and category fields."""
    item = Item.query.get_or_404(item_id)
    if item.owner_id != current_user.id and not current_user.is_admin:
        abort(403)

    categories = current_app.config["CATEGORIES"]
    attrs = item.get_attributes()

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        price_raw = request.form.get("price_per_day", "").strip()
        if category not in categories:
            flash("Please select a valid category.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))
        if not title:
            flash("Title is required.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))
        try:
            price_per_day = float(price_raw)
            if price_per_day < 0:
                raise ValueError
        except (TypeError, ValueError):
            flash("Price per day must be a positive number.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        try:
            deposit = float(request.form.get("deposit", "0") or 0)
        except ValueError:
            deposit = 0.0
        try:
            late_fee = float(request.form.get("late_fee_per_day", "0") or 0)
        except ValueError:
            late_fee = 0.0
        try:
            discount = int(float(request.form.get("discount_percent", "0") or 0))
        except (TypeError, ValueError):
            discount = 0
        discount = max(0, min(90, discount))

        purchase_raw = (request.form.get("purchase_price") or "").strip()
        purchase_price = None
        if purchase_raw:
            try:
                purchase_price = int(float(purchase_raw))
            except (TypeError, ValueError):
                purchase_price = None
        try:
            delivery_charge = float(round(float(request.form.get("delivery_charge", "0") or 0)))
        except ValueError:
            delivery_charge = 0.0

        item.category = category
        item.title = title
        item.description = (request.form.get("description") or "").strip()
        item.price_per_day = price_per_day
        item.deposit = deposit
        item.late_fee_per_day = late_fee
        item.discount_percent = discount
        item.purchase_price = purchase_price
        item.tags = (request.form.get("tags") or "").strip()[:1000]
        item.delivery_available = "delivery_available" in request.form
        item.delivery_charge = delivery_charge
        item.cod_available = "cod_available" in request.form
        # Pausing from the edit form keeps the listing but hides it from browse.
        item.is_available = "is_available" in request.form

        new_attrs = {}
        for field in categories[category]["fields"]:
            name = field["name"]
            if field["type"] == "checkbox":
                new_attrs[name] = f"attr_{name}" in request.form
            else:
                new_attrs[name] = (request.form.get(f"attr_{name}") or "").strip()
        item.set_attributes(new_attrs)

        # Photos: keep ticked photos, add new uploads, cover = first photo.
        keep = set(request.form.getlist("keep_image"))
        current = []
        for key in ([item.image] if item.image else []) + item.get_images():
            if key and key not in current:
                current.append(key)
        kept = [key for key in current if key in keep]
        try:
            new_photos = save_photos(_photo_files(), limit=_photo_limit())
        except MediaError as exc:
            flash(str(exc), "error")
            return redirect(url_for("items.edit_item", item_id=item.id))
        combined = kept + [p["key"] for p in new_photos]
        if len(combined) > _photo_limit():
            combined = combined[:_photo_limit()]
            flash(f"Only the first {_photo_limit()} photos were kept.", "error")
        item.set_images(combined)
        if combined:
            item.image = combined[0]
        elif request.form.get("photos_managed"):
            item.image = None  # the owner removed every photo

        db.session.commit()
        record_event(current_user, "listing_updated",
                     detail={"item_id": item.id, "available": item.is_available})
        flash("Listing updated.", "success")
        return redirect(url_for("items.item_detail", item_id=item.id))

    gallery_photos = []
    for key in ([item.image] if item.image else []) + item.get_images():
        if not key or any(p["key"] == key for p in gallery_photos):
            continue
        gallery_photos.append({
            "key": key,
            "url": _gallery_url(key),
            "thumb": _gallery_url(thumb_for(key)) if "/" in str(key) else _gallery_url(key),
        })
    return render_template(
        "add_item.html",
        item=item,
        attrs=attrs,
        gallery=gallery_photos,
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

    # Image gallery: cover first, then the owner's photos (large + thumbnail).
    from utils.illustrations import item_picture
    gallery = []
    main_pic = item_picture(item)
    if main_pic.get("src"):
        gallery.append({"src": main_pic["src"], "thumb": main_pic["src"],
                        "kind": main_pic.get("kind", "photo")})
    for name in item.get_images():
        url = _gallery_url(name)
        if all(entry["src"] != url for entry in gallery):
            thumb = _gallery_url(thumb_for(name)) if "/" in str(name) else url
            gallery.append({"src": url, "thumb": thumb, "kind": "photo"})

    return render_template(
        "item_detail.html",
        item=item,
        cat_config=cat_config,
        attrs=attrs,
        gallery=gallery,
        blocked_dates=blocked_dates,
        today=date.today().isoformat(),
        trust_info=trust_info,
        smart_deposit=smart_deposit,
        latest_reviews=latest_reviews,
    )
