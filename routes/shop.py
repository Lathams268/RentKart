"""Digital Shop routes – public mini-shop, QR code generation, WhatsApp share, and A4 poster."""
import io
import urllib.parse
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
import qrcode
from models import db, User, Item
from utils.shop import generate_shop_slug
from utils.trust import get_user_trust

shop_bp = Blueprint("shop", __name__)


import os
import time
from werkzeug.utils import secure_filename


def _save_logo(file):
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext in ("png", "jpg", "jpeg"):
            fn = f"logo_{current_user.id}_{int(time.time())}.{ext}"
            upload_dir = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, fn))
            return fn
    return None


@shop_bp.route("/shop/create", methods=["POST"])
@login_required
def create_shop():
    """Create or update owner's digital shop with an auto-generated unique slug."""
    shop_name = request.form.get("shop_name", "").strip()
    shop_description = request.form.get("shop_description", "").strip()
    shop_theme_color = request.form.get("shop_theme_color", "").strip()

    if not shop_name:
        flash("Shop name is required.", "error")
        return redirect(url_for("bookings.owner_dashboard"))

    # Auto-generate unique slug
    slug = generate_shop_slug(shop_name, user_id=current_user.id)
    current_user.shop_name = shop_name
    current_user.shop_description = shop_description
    current_user.shop_slug = slug
    if shop_theme_color:
        current_user.shop_theme_color = shop_theme_color

    logo_fn = _save_logo(request.files.get("shop_logo"))
    if logo_fn:
        current_user.shop_logo = logo_fn

    db.session.commit()
    flash(f"Shop '{shop_name}' created successfully!", "success")
    return redirect(url_for("bookings.owner_dashboard"))


@shop_bp.route("/shop/edit", methods=["POST"])
@login_required
def edit_shop():
    """Update shop settings including name, description, theme color, and logo."""
    shop_name = request.form.get("shop_name", "").strip()
    shop_description = request.form.get("shop_description", "").strip()
    shop_theme_color = request.form.get("shop_theme_color", "").strip()

    if shop_name:
        current_user.shop_name = shop_name
    current_user.shop_description = shop_description
    if shop_theme_color:
        current_user.shop_theme_color = shop_theme_color

    logo_fn = _save_logo(request.files.get("shop_logo"))
    if logo_fn:
        current_user.shop_logo = logo_fn

    db.session.commit()
    flash("Shop updated successfully!", "success")
    return redirect(url_for("bookings.owner_dashboard"))


@shop_bp.route("/shop/<slug>")
def shop_page(slug):
    """Public digital shop page showing owner details, trust badge, and available items."""
    owner = User.query.filter_by(shop_slug=slug).first_or_404()
    trust = get_user_trust(owner)
    categories = current_app.config.get("CATEGORIES", {})

    # Available items belonging to this owner
    items = Item.query.filter_by(owner_id=owner.id, is_available=True).all()

    # WhatsApp share link
    shop_url = url_for("shop.shop_page", slug=slug, _external=True)
    wa_message = f"Check out {owner.shop_name or owner.name} on RentKart! Browse items for rent: {shop_url}"
    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(wa_message)}"

    return render_template(
        "shop.html",
        owner=owner,
        trust=trust,
        items=items,
        categories=categories,
        shop_url=shop_url,
        whatsapp_url=whatsapp_url,
    )


@shop_bp.route("/shop/<slug>/qr")
def shop_qr(slug):
    """Generate and return a PNG QR code for the shop page URL."""
    owner = User.query.filter_by(shop_slug=slug).first_or_404()
    shop_url = url_for("shop.shop_page", slug=slug, _external=True)

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2,
    )
    qr.add_data(shop_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=False, download_name=f"{slug}-qr.png")


@shop_bp.route("/shop/<slug>/poster")
def shop_poster(slug):
    """Printable A4 marketing poster for the shop with big QR and 'Scan to rent from us'."""
    owner = User.query.filter_by(shop_slug=slug).first_or_404()
    from utils.plans import has_feature
    is_locked = not has_feature(owner, "qr_poster")
    trust = get_user_trust(owner)
    shop_url = url_for("shop.shop_page", slug=slug, _external=True)
    return render_template(
        "shop_poster.html",
        owner=owner,
        trust=trust,
        shop_url=shop_url,
        is_locked=is_locked,
    )
