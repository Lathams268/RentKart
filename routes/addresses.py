"""Saved delivery addresses (Stage 1): list, add, edit, delete, set default.

Only the owner of an address can see or change it (403 otherwise). Nothing here
touches money. All stored text is trimmed/validated server-side via utils.address.
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort,
)
from flask_login import login_required, current_user
from models import db, Address
from utils.address import validate_address

addresses_bp = Blueprint("addresses", __name__)


def _get_owned_address(addr_id):
    addr = Address.query.get_or_404(addr_id)
    if addr.user_id != current_user.id:
        abort(403)
    return addr


def _redirect_back():
    nxt = request.form.get("next") or ""
    if nxt.startswith("/items/"):
        return redirect(nxt)
    return redirect(url_for("addresses.address_list"))


@addresses_bp.route("/addresses", methods=["GET"])
@login_required
def address_list():
    """List the user's saved addresses with an inline add form (prefilled)."""
    addrs = Address.query.filter_by(user_id=current_user.id).all()
    form = {
        "full_name": current_user.name,
        "phone": current_user.phone,
        "city": current_user.village_or_city,
        "label": "Home",
        "house_no": "", "building": "", "street": "", "landmark": "",
        "district": "", "state": "", "pincode": "",
    }
    return render_template(
        "addresses.html",
        addresses=addrs, form=form, errors={},
        states=current_app.config["INDIAN_STATES"],
        labels=Address.LABELS, next=request.args.get("next", ""),
    )


@addresses_bp.route("/addresses", methods=["POST"])
@login_required
def address_add():
    """Validate and save a new address. First address becomes the default."""
    clean, errors = validate_address(request.form)
    if errors:
        addrs = Address.query.filter_by(user_id=current_user.id).all()
        return render_template(
            "addresses.html", addresses=addrs, form=request.form.to_dict(),
            errors=errors, states=current_app.config["INDIAN_STATES"],
            labels=Address.LABELS, next=request.form.get("next", ""),
        ), 400

    has_default = Address.query.filter_by(user_id=current_user.id, is_default=True).first()
    addr = Address(user_id=current_user.id, is_default=(has_default is None), **clean)
    db.session.add(addr)
    db.session.commit()
    flash("Address saved.", "success")
    return _redirect_back()


@addresses_bp.route("/addresses/<int:addr_id>/edit", methods=["POST"])
@login_required
def address_edit(addr_id):
    addr = _get_owned_address(addr_id)
    clean, errors = validate_address(request.form)
    if errors:
        addrs = Address.query.filter_by(user_id=current_user.id).all()
        # Re-render the list with the offending address shown in the form area.
        return render_template(
            "addresses.html", addresses=addrs, form=dict(clean, id=addr.id),
            errors=errors, states=current_app.config["INDIAN_STATES"],
            labels=Address.LABELS, editing=addr, next=request.form.get("next", ""),
        ), 400
    for key, val in clean.items():
        setattr(addr, key, val)
    db.session.commit()
    flash("Address updated.", "success")
    return _redirect_back()


@addresses_bp.route("/addresses/<int:addr_id>/delete", methods=["POST"])
@login_required
def address_delete(addr_id):
    addr = _get_owned_address(addr_id)
    db.session.delete(addr)
    db.session.commit()
    flash("Address deleted.", "success")
    return _redirect_back()


@addresses_bp.route("/addresses/<int:addr_id>/default", methods=["POST"])
@login_required
def address_default(addr_id):
    addr = _get_owned_address(addr_id)
    Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
    addr.is_default = True
    db.session.commit()
    flash("Default address updated.", "success")
    return _redirect_back()
