"""Bulk-listing blueprint (additive feature).

Stage 1: category template downloads (CSV / XLSX) and shop pricing rules.
Later stages extend this same blueprint with upload / preview / import /
photos / bulk-edit. Registered under the /bulk URL prefix.
"""
import io

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    abort, Response, send_file, current_app,
)
from flask_login import login_required, current_user

from models import db, PricingRule
from utils import bulk_import as bi
from utils import bulk_rules as br

bulk_bp = Blueprint("bulk", __name__, url_prefix="/bulk")


# --------------------------------------------------------------------------- #
# Stage 1 - downloadable templates
# --------------------------------------------------------------------------- #
def _valid_category(category):
    if category not in current_app.config["CATEGORIES"]:
        abort(404)
    return category


@bulk_bp.route("/template/<category>.csv")
@login_required
def template_csv(category):
    """CSV template built from the category's config fields."""
    _valid_category(category)
    text = bi.build_template_csv(current_app.config, category)
    filename = f"rentkart_{category}_template.csv"
    return Response(
        "\ufeff" + text,  # UTF-8 BOM so Excel opens Indian scripts correctly
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bulk_bp.route("/template/<category>.xlsx")
@login_required
def template_xlsx(category):
    """XLSX template built from the category's config fields."""
    _valid_category(category)
    data = bi.build_template_xlsx(current_app.config, category)
    filename = f"rentkart_{category}_template.xlsx"
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# --------------------------------------------------------------------------- #
# Stage 1 - shop pricing rules
# --------------------------------------------------------------------------- #
def _rule_match_fields(category):
    """Select/text fields a rule may match on for this category."""
    cat = current_app.config["CATEGORIES"].get(category) or {}
    out = []
    for f in cat.get("fields", []):
        if f.get("options"):
            out.append({"name": f["name"], "label": f.get("label", f["name"]),
                        "options": list(f["options"])})
        else:
            out.append({"name": f["name"], "label": f.get("label", f["name"]),
                        "options": []})
    return out


@bulk_bp.route("/rules", methods=["GET", "POST"])
@login_required
def rules():
    """Manage the current owner's pricing rules for a chosen category."""
    cfg = current_app.config
    categories = cfg["CATEGORIES"]
    category = request.values.get("category", "books").strip()
    if category not in categories:
        category = "books"

    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            rid = request.form.get("rule_id", type=int)
            rule = PricingRule.query.get_or_404(rid)
            if rule.owner_id != current_user.id:
                abort(403)
            db.session.delete(rule)
            db.session.commit()
            flash("Rule deleted.", "success")
        else:
            match_field = (request.form.get("match_field") or "").strip() or None
            match_value = (request.form.get("match_value") or "").strip() or None
            if not match_field or not match_value:
                match_field = match_value = None  # default rule
            rule = PricingRule(
                owner_id=current_user.id,
                category=category,
                match_field=match_field,
                match_value=match_value,
                price_per_day=_num(request.form.get("price_per_day")),
                deposit=_num(request.form.get("deposit"), default=0),
                late_fee_per_day=_num(request.form.get("late_fee_per_day"), default=0),
            )
            db.session.add(rule)
            db.session.commit()
            flash("Rule saved.", "success")
        return redirect(url_for("bulk.rules", category=category))

    my_rules = (
        PricingRule.query.filter_by(owner_id=current_user.id, category=category)
        .order_by(PricingRule.created_at.desc()).all()
    )
    return render_template(
        "bulk/rules.html",
        categories=categories,
        category=category,
        my_rules=my_rules,
        match_fields=_rule_match_fields(category),
        field_options={f["name"]: get_field_options(cfg, category, f["name"])
                       for f in _rule_match_fields(category)},
    )


def get_field_options(cfg, category, field_name):
    """Delegated to config.get_field_options (all options, no parent value)."""
    import config as _config
    return _config.get_field_options(category, field_name)


def _num(raw, default=None):
    """Parse a whole-rupee float; returns default when blank/invalid."""
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(round(float(raw)))
    except (TypeError, ValueError):
        return default
