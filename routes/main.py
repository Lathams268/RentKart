"""Main routes – home page and browse with filters/sorting."""
import json
from flask import Blueprint, render_template, request, current_app, url_for, jsonify, session, redirect
from flask_login import current_user, login_required
from models import Item
from utils.geo import attach_distances
from utils.trust import get_user_trust

main_bp = Blueprint("main", __name__)


@main_bp.route("/profile")
@login_required
def profile():
    """User profile showing Trust Score, tier, progress bar, and improvement tips."""
    trust = get_user_trust(current_user)
    tips = [
        "Return rented items on or before the agreed end date to maintain a perfect record.",
        "Inspect items during handover and return them clean and undamaged to avoid deductions.",
        "Complete multiple clean rentals to unlock up to 50% discount on security deposits.",
    ]
    return render_template("profile.html", user=current_user, trust=trust, tips=tips)


@main_bp.route("/")
def index():
    """Landing page with hero, CTA buttons, and category icons."""
    categories = current_app.config["CATEGORIES"]
    return render_template("index.html", categories=categories)


@main_bp.route("/browse")
def browse():
    """Browse items with filters, sorting, and distance badges."""
    categories = current_app.config["CATEGORIES"]

    # --- Determine user location ---
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None and lng is None and current_user.is_authenticated:
        lat = current_user.lat
        lng = current_user.lng

    # --- View mode (list or map) ---
    view = request.args.get("view", "list").strip()
    if view not in ("list", "map"):
        view = "list"

    # --- Voice / text search handling via KEYWORD_MAP ---
    raw_query = (request.args.get("q") or request.args.get("search") or "").strip()
    keyword_map = current_app.config.get("KEYWORD_MAP", {})
    matched_category = None

    if raw_query:
        norm_query = raw_query.lower()
        if norm_query in keyword_map:
            matched_category = keyword_map[norm_query]
        else:
            for token in norm_query.split():
                clean_tok = token.strip(".,!?;:'\"")
                if clean_tok in keyword_map:
                    matched_category = keyword_map[clean_tok]
                    break

    sel_category = request.args.get("category", "").strip()
    if matched_category:
        sel_category = matched_category
        search = ""
    else:
        search = raw_query

    # --- Base query: only available items ---
    q = Item.query.filter_by(is_available=True)

    # --- Filter: category ---
    if sel_category and sel_category in categories:
        q = q.filter_by(category=sel_category)

    # --- Filter: search (title or description, case-insensitive) ---
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            Item.title.ilike(pattern) | Item.description.ilike(pattern)
        )

    # --- Filter: max price per day ---
    max_price = request.args.get("max_price", type=float)
    if max_price is not None:
        q = q.filter(Item.price_per_day <= max_price)

    items = q.all()

    # --- Phase 6: Hide extra items beyond owner's active plan limit (oldest items stay visible) ---
    from utils.plans import get_plan, has_feature
    owner_visible_ids = {}
    visible_items = []
    for item in items:
        oid = item.owner_id
        if oid not in owner_visible_ids:
            oplan = get_plan(item.owner)
            max_allowed = oplan.get("max_items", 5)
            all_owner_items = Item.query.filter_by(owner_id=oid)\
                .order_by(Item.created_at.asc(), Item.id.asc()).all()
            owner_visible_ids[oid] = set(it.id for it in all_owner_items[:max_allowed])
        if item.id in owner_visible_ids[oid]:
            visible_items.append(item)
    items = visible_items

    # --- Attach distances ---
    attach_distances(items, lat, lng)

    # --- Filter: max distance (only if location known) ---
    max_dist = request.args.get("max_dist", type=float)
    if max_dist is not None and lat is not None and lng is not None:
        items = [i for i in items if i.distance_km is not None and i.distance_km <= max_dist]

    # --- Category-specific attribute filters ---
    attr_filters = {}
    if sel_category and sel_category in categories:
        for field in categories[sel_category]["fields"]:
            if field["type"] == "select":
                val = request.args.get(f"attr_{field['name']}", "").strip()
                if val:
                    attr_filters[field["name"]] = val
    if attr_filters:
        filtered = []
        for item in items:
            attrs = item.get_attributes()
            if all(attrs.get(k) == v for k, v in attr_filters.items()):
                filtered.append(item)
        items = filtered

    # --- Sorting ---
    sort = request.args.get("sort", "").strip()
    if sort == "cheapest":
        items.sort(key=lambda i: i.price_per_day)
    elif sort == "newest":
        items.sort(key=lambda i: i.created_at or 0, reverse=True)
    else:
        # Default: Business items appear first, then nearest (items without distance go last)
        items.sort(key=lambda i: (not has_feature(i.owner, "featured"), i.distance_km is None, i.distance_km or 0))

    # Build extra select fields for the selected category (max 2)
    cat_select_fields = []
    if sel_category and sel_category in categories:
        for field in categories[sel_category]["fields"]:
            if field["type"] == "select":
                cat_select_fields.append(field)
            if len(cat_select_fields) >= 2:
                break

    # Build map items list for map view (only items with valid lat/lng)
    map_items = []
    for item in items:
        if item.lat is not None and item.lng is not None:
            map_items.append({
                "id": item.id,
                "title": item.title,
                "price_per_day": item.price_per_day,
                "deposit": item.deposit,
                "distance_km": item.distance_km,
                "lat": item.lat,
                "lng": item.lng,
                "village_or_city": item.owner.village_or_city if item.owner else "",
                "url": url_for("items.item_detail", item_id=item.id),
                "image_url": url_for("static", filename="uploads/" + item.image) if item.image else None,
            })
    map_items_json = json.dumps(map_items)

    return render_template(
        "browse.html",
        items=items,
        map_items=map_items,
        map_items_json=map_items_json,
        view=view,
        categories=categories,
        lat=lat,
        lng=lng,
        sel_category=sel_category,
        search=search,
        max_price=max_price,
        max_dist=max_dist,
        sort=sort or "nearest",
        cat_select_fields=cat_select_fields,
        attr_filters=attr_filters,
    )


# ---------- Phase 7: Price Hint API & Language Toggle ----------
@main_bp.route("/api/price-hint")
def price_hint():
    """Return JSON price suggestion with seasonal boost for a category."""
    from utils.pricing import suggest_price
    from datetime import date
    category = request.args.get("category", "").strip()
    d_str = request.args.get("date") or request.args.get("today")
    target_d = None
    if d_str:
        try:
            target_d = date.fromisoformat(d_str)
        except Exception:
            pass
    return jsonify(suggest_price(category, today=target_d))



@main_bp.route("/set-language/<lang_code>")
def set_language(lang_code):
    """Set active language code in session if valid and redirect back."""
    from translations import SUPPORTED_LANGUAGES
    if lang_code in SUPPORTED_LANGUAGES:
        session["lang"] = lang_code
    return redirect(request.referrer or url_for("main.index"))

