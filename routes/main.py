"""Main routes – home page and browse with filters/sorting."""
import json
from flask import Blueprint, render_template, request, current_app, url_for, jsonify, session, redirect
from flask_login import current_user, login_required
from config import get_field_options
from models import Item
from utils.geo import attach_distances
from utils.trust import get_user_trust
from utils.illustrations import item_picture

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


def _norm_str(s):
    if s is None:
        return ""
    return str(s).strip().lower().replace("–", "-").replace("—", "-")


def _norm_compact(s):
    if s is None:
        return ""
    return _norm_str(s).replace(" ", "")


def item_matches_gender(item, target_gender):
    if not target_gender or target_gender.lower() == "all":
        return True
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    g = _norm_str(attrs.get("gender"))
    t = _norm_str(target_gender)
    full_text = f"{item.title} {item.description or ''}".lower()
    if not g:
        if t in ("boys", "boy") and ("boy" in full_text):
            return True
        if t in ("girls", "girl") and ("girl" in full_text):
            return True
        if t in ("men", "man") and ("men" in full_text or "man" in full_text):
            return True
        if t in ("women", "woman") and ("women" in full_text or "woman" in full_text or "saree" in full_text or "lehenga" in full_text):
            return True
        return False
    if g == t:
        return True
    if t in ("boys", "boy"):
        return g in ("boys", "boy") or (g == "kids" and "girl" not in full_text)
    if t in ("girls", "girl"):
        return g in ("girls", "girl") or (g == "kids" and "boy" not in full_text)
    if t in ("kids", "kid"):
        return g in ("kids", "boys", "girls", "unisex")
    if t in ("men", "man"):
        return g in ("men", "man")
    if t in ("women", "woman"):
        return g in ("women", "woman")
    return g == t


def item_matches_age_group(item, target_age_group):
    if not target_age_group or str(target_age_group).lower() == "all":
        return True
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    ag = _norm_compact(attrs.get("age_group"))
    t = _norm_compact(target_age_group)
    if ag in ("18+", "18") and t in ("18+", "18"):
        return True
    if not ag:
        full_text = f"{item.title} {item.description or ''}".lower().replace("–", "-")
        return t in full_text
    return ag == t


def item_matches_clothing_type(item, target_type):
    if not target_type or target_type.lower() == "all":
        return True
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    ctype = _norm_str(attrs.get("clothing_type"))
    t = _norm_str(target_type)
    if not ctype:
        return t in _norm_str(item.title)
    return t == ctype or t in ctype or ctype in t


def item_matches_size(item, target_size):
    if not target_size or target_size.lower() == "all":
        return True
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    s = _norm_compact(attrs.get("size"))
    t = _norm_compact(target_size)
    return s == t


def item_matches_brand(item, target_brand):
    if not target_brand or target_brand.lower() == "all":
        return True
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    b = _norm_str(attrs.get("brand"))
    t = _norm_str(target_brand)
    full_text = f"{item.title} {item.description or ''}".lower()
    return t in b or t in full_text


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
    matched_genre = None

    if raw_query:
        norm_query = raw_query.lower()
        matched_val = keyword_map.get(norm_query)
        if not matched_val:
            for k, v in keyword_map.items():
                if len(k.split()) > 1 and k in norm_query:
                    matched_val = v
                    break
        if not matched_val:
            for token in norm_query.split():
                clean_tok = token.strip(".,!?;:'\"")
                if clean_tok in keyword_map:
                    matched_val = keyword_map[clean_tok]
                    break

        if matched_val:
            if isinstance(matched_val, dict):
                matched_category = matched_val.get("category")
                matched_genre = matched_val.get("genre")
            elif isinstance(matched_val, tuple):
                matched_category, matched_genre = matched_val
            else:
                matched_category = matched_val

    sel_category = request.args.get("category", "").strip()
    if matched_category:
        sel_category = matched_category
        search = ""
    else:
        search = raw_query

    # Dedicated clothing section: boys / girls / all
    clothing_section = request.args.get("clothing_section", "").strip().lower()
    if clothing_section in ("boys", "girls"):
        sel_category = "clothes"

    sel_genre = request.args.get("genre", "").strip() or request.args.get("attr_genre", "").strip()
    if matched_genre and not sel_genre:
        sel_genre = matched_genre

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

    # --- Filter: price per day range (min and max) ---
    raw_min_price = (request.args.get("min_price") or "").strip()
    min_price = None
    if raw_min_price:
        try:
            val = float(raw_min_price)
            if val >= 0:
                min_price = val
        except (ValueError, TypeError):
            min_price = None

    raw_max_price = (request.args.get("max_price") or "").strip()
    max_price = None
    if raw_max_price:
        try:
            val = float(raw_max_price)
            if val > 0:
                max_price = val
        except (ValueError, TypeError):
            max_price = None

    if min_price is not None:
        q = q.filter(Item.price_per_day >= min_price)

    if max_price is not None:
        q = q.filter(Item.price_per_day <= max_price)

    items = q.all()

    # In-memory safety filter for min and max price
    if min_price is not None:
        items = [i for i in items if i.price_per_day >= min_price]
    if max_price is not None:
        items = [i for i in items if i.price_per_day <= max_price]

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
    from utils.trending import matches_genre, get_trending_books, GENRE_METADATA
    attr_filters = {}
    if sel_category and sel_category in categories:
        for field in categories[sel_category]["fields"]:
            fname = field["name"]
            val = (request.args.get(f"attr_{fname}") or request.args.get(fname) or "").strip()
            if fname == "age_group" and val in ("18", "18+"):
                val = "18+"
            if val and val.lower() != "all":
                attr_filters[fname] = val

    # Also capture common clothes fields if category wasn't explicitly selected
    for fname in ["gender", "age_group", "clothing_type", "size", "style", "color"]:
        if fname not in attr_filters:
            val = (request.args.get(f"attr_{fname}") or request.args.get(fname) or "").strip()
            if fname == "age_group" and val in ("18", "18+"):
                val = "18+"
            if val and val.lower() != "all":
                attr_filters[fname] = val

    if clothing_section == "boys" and "gender" not in attr_filters:
        attr_filters["gender"] = "Boys"
    elif clothing_section == "girls" and "gender" not in attr_filters:
        attr_filters["gender"] = "Girls"

    # Handle genre filtering for books
    if sel_category == "books" and sel_genre and sel_genre.lower() != "all":
        attr_filters["genre"] = sel_genre
        if sel_genre.lower() == "trending":
            items = get_trending_books(items=items)
        else:
            filtered = []
            for item in items:
                attrs = item.get_attributes()
                b_genre = attrs.get("genre", "")
                if not b_genre and sel_genre.lower() in ("general", "other"):
                    filtered.append(item)
                elif matches_genre(b_genre, sel_genre):
                    filtered.append(item)
            items = filtered

    # Handle brand filtering
    sel_brand = request.args.get("brand", "").strip() or request.args.get("attr_brand", "").strip()
    if sel_brand and sel_brand.lower() != "all":
        attr_filters["brand"] = sel_brand

    # Reset child filters that are no longer valid when parent filter changes
    from utils.filters import (
        is_valid_size, is_valid_clothing_type,
        build_remove_filter_url, compute_best_filter_to_remove, get_you_might_like
    )
    if "age_group" in attr_filters and "size" in attr_filters:
        if not is_valid_size(attr_filters["age_group"], attr_filters["size"]):
            attr_filters.pop("size", None)

    if "clothing_type" in attr_filters:
        c_gen = attr_filters.get("gender")
        c_sty = attr_filters.get("style")
        c_typ = attr_filters.get("clothing_type")
        if not is_valid_clothing_type(c_gen, c_sty, c_typ):
            attr_filters.pop("clothing_type", None)

    # Apply attribute filters (excluding genre which was already filtered above for books)
    filter_keys = [k for k in attr_filters.keys() if not (sel_category == "books" and k == "genre")]
    if filter_keys:
        filtered = []
        for item in items:
            attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
            match = True
            for k in filter_keys:
                target_val = attr_filters[k]
                if not target_val or target_val.lower() == "all":
                    continue
                if k == "gender":
                    if not item_matches_gender(item, target_val):
                        match = False
                        break
                elif k == "age_group":
                    if not item_matches_age_group(item, target_val):
                        match = False
                        break
                elif k == "clothing_type":
                    if not item_matches_clothing_type(item, target_val):
                        match = False
                        break
                elif k == "size":
                    if not item_matches_size(item, target_val):
                        match = False
                        break
                elif k == "brand":
                    if not item_matches_brand(item, target_val):
                        match = False
                        break
                elif k == "language" and sel_category == "books":
                    item_val = attrs.get(k)
                    if not item_val or target_val.lower() not in str(item_val).lower():
                        match = False
                        break
                else:
                    item_val = attrs.get(k)
                    if not item_val:
                        if target_val.lower() not in item.title.lower():
                            match = False
                            break
                    elif str(item_val).strip().lower() != str(target_val).strip().lower():
                        match = False
                        break
            if match:
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

    # --- Book Rows & Category Rows Data Preparation ---
    book_genres = []
    if "books" in categories and categories["books"].get("fields"):
        book_genres = categories["books"]["fields"][0].get("options", [])

    has_extra_book_filters = bool([k for k in attr_filters if k != "genre"])
    show_book_rows = (sel_category == "books" and not sel_genre and not search and view != "map" and not has_extra_book_filters)
    trending_books = []
    genre_rows = []
    if show_book_rows:
        trending_books = get_trending_books(items=items)
        for g_opt in book_genres:
            g_items = [it for it in items if matches_genre(it.get_attributes().get("genre", ""), g_opt)]
            if g_items:
                genre_rows.append({
                    "genre": g_opt,
                    "items": g_items,
                    "meta": GENRE_METADATA.get(g_opt, {}),
                })
        # Check for old books without genre
        general_items = [it for it in items if not it.get_attributes().get("genre")]
        if general_items:
            genre_rows.append({
                "genre": "General",
                "items": general_items,
                "meta": {"emoji": "📖", "short_label": "General", "color": "bg-gray-100 text-gray-700 border-gray-300"},
            })

    # On main browse page (when no category filter, no search text, and no other filter applied)
    has_any_filter = bool(sel_category or search or request.args.get("sort") or min_price is not None or max_price is not None or max_dist is not None or attr_filters or sel_brand)
    show_category_rows = (not has_any_filter and view != "map")
    category_rows = []
    if show_category_rows:
        for c_key, c_val in categories.items():
            c_items = [it for it in items if it.category == c_key]
            if not c_items:
                continue
            # Keep Featured (Business plan) items first, then current sort (nearest by default)
            c_items.sort(key=lambda i: (not has_feature(i.owner, "featured"), i.distance_km is None, i.distance_km or 0))
            category_rows.append({
                "key": c_key,
                "label": c_val["label"],
                "icon": c_val["icon"],
                "items": c_items,
            })

    # Dedicated clothes section handling (Boys vs Girls vs Adult Collections)
    has_specific_clothes_filters = bool(
        search or min_price is not None or max_price is not None
        or max_dist is not None or attr_filters or (sel_brand and sel_brand.lower() != "all")
        or clothing_section
    )
    show_clothes_sections = (sel_category == "clothes" and not has_specific_clothes_filters and view != "map")

    boys_items = []
    girls_items = []
    adult_clothes_items = []
    if sel_category == "clothes":
        boys_items = [it for it in items if item_matches_gender(it, "boys")]
        girls_items = [it for it in items if item_matches_gender(it, "girls")]
        adult_clothes_items = [it for it in items if item_matches_gender(it, "men") or item_matches_gender(it, "women")]

    CATEGORY_FILTER_NAMES = {
        "clothes": ["gender", "age_group", "clothing_type", "size", "style", "color"],
        "books": ["language"],
        "farm_tools": ["tool_group", "tool_type"],
        "event_items": ["event_group", "item_type", "style", "festival_or_event"],
        "electronics": ["device_type", "condition"],
    }

    # Build extra select fields for the selected category
    cat_select_fields = []
    if sel_category and sel_category in categories:
        target_names = CATEGORY_FILTER_NAMES.get(sel_category)
        for field in categories[sel_category]["fields"]:
            if field["type"] != "select":
                continue
            if sel_category == "books" and field["name"] == "genre":
                continue
            if target_names is not None and field["name"] not in target_names:
                continue

            f_copy = dict(field)
            if field.get("depends_on"):
                parent_name = field["depends_on"]
                parent_val = attr_filters.get(parent_name)
                f_copy["options"] = get_field_options(sel_category, field["name"], parent_val)
            cat_select_fields.append(f_copy)

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
                "image_url": item_picture(item).get("src"),
            })
    map_items_json = json.dumps(map_items)

    # --- Empty State: Active removable chips, best filter removal suggestion, you might like ---
    active_filter_chips = []
    removal_suggestion = ""
    removal_url = ""
    you_might_like = []
    clear_all_url = url_for("main.browse", lat=lat, lng=lng, view=view)

    if not items:
        req_args = dict(request.args)
        if sel_category:
            c_lbl = categories.get(sel_category, {}).get("label", sel_category.title())
            active_filter_chips.append({
                "key": "category",
                "label": f"Category: {c_lbl}",
                "remove_url": build_remove_filter_url(req_args, "category"),
            })
        if clothing_section:
            active_filter_chips.append({
                "key": "clothing_section",
                "label": f"Section: {clothing_section.title()}",
                "remove_url": build_remove_filter_url(req_args, "clothing_section"),
            })
        if search:
            active_filter_chips.append({
                "key": "search",
                "label": f"Search: '{search}'",
                "remove_url": build_remove_filter_url(req_args, "search"),
            })
        if min_price is not None:
            mp_show = int(min_price) if min_price == int(min_price) else min_price
            active_filter_chips.append({
                "key": "min_price",
                "label": f"Min price Rs {mp_show}",
                "remove_url": build_remove_filter_url(req_args, "min_price"),
            })
        if max_price is not None:
            mp_show = int(max_price) if max_price == int(max_price) else max_price
            active_filter_chips.append({
                "key": "max_price",
                "label": f"Max price Rs {mp_show}",
                "remove_url": build_remove_filter_url(req_args, "max_price"),
            })
        if max_dist is not None:
            active_filter_chips.append({
                "key": "max_dist",
                "label": f"Distance ≤ {int(max_dist)} km",
                "remove_url": build_remove_filter_url(req_args, "max_dist"),
            })
        if sel_brand and sel_brand.lower() != "all":
            active_filter_chips.append({
                "key": "brand",
                "label": f"Brand: {sel_brand}",
                "remove_url": build_remove_filter_url(req_args, "brand"),
            })
        if sel_genre and sel_genre.lower() != "all":
            active_filter_chips.append({
                "key": "genre",
                "label": f"Genre: {sel_genre}",
                "remove_url": build_remove_filter_url(req_args, "genre"),
            })
        for fname, fval in attr_filters.items():
            if fname in ("genre", "brand") or not fval or fval.lower() == "all":
                continue
            lbl = fname.replace("_", " ").title()
            active_filter_chips.append({
                "key": f"attr_{fname}",
                "label": f"{lbl}: {fval}",
                "remove_url": build_remove_filter_url(req_args, f"attr_{fname}"),
            })

        def evaluate_without(filter_key):
            eq = Item.query.filter_by(is_available=True)
            t_cat = None if filter_key == "category" else sel_category
            if t_cat and t_cat in categories:
                eq = eq.filter_by(category=t_cat)
            t_search = "" if filter_key == "search" else search
            if t_search:
                pat = f"%{t_search}%"
                eq = eq.filter(Item.title.ilike(pat) | Item.description.ilike(pat))
            t_min = None if filter_key == "min_price" else min_price
            if t_min is not None:
                eq = eq.filter(Item.price_per_day >= t_min)
            t_max = None if filter_key == "max_price" else max_price
            if t_max is not None:
                eq = eq.filter(Item.price_per_day <= t_max)

            c_items = eq.all()
            if t_min is not None:
                c_items = [it for it in c_items if it.price_per_day >= t_min]
            if t_max is not None:
                c_items = [it for it in c_items if it.price_per_day <= t_max]

            c_visible = []
            for item in c_items:
                oid = item.owner_id
                if oid not in owner_visible_ids:
                    oplan = get_plan(item.owner)
                    m_all = oplan.get("max_items", 5)
                    all_o = Item.query.filter_by(owner_id=oid).order_by(Item.created_at.asc(), Item.id.asc()).all()
                    owner_visible_ids[oid] = set(it.id for it in all_o[:m_all])
                if item.id in owner_visible_ids[oid]:
                    c_visible.append(item)
            c_items = c_visible

            t_dist = None if filter_key == "max_dist" else max_dist
            if t_dist is not None and lat is not None and lng is not None:
                attach_distances(c_items, lat, lng)
                c_items = [it for it in c_items if it.distance_km is not None and it.distance_km <= t_dist]

            t_attrs = {}
            for k, v in attr_filters.items():
                if filter_key in (k, f"attr_{k}"):
                    continue
                t_attrs[k] = v

            t_sec = "" if filter_key == "clothing_section" else clothing_section
            if t_sec == "boys" and "gender" not in t_attrs and filter_key != "clothing_section":
                t_attrs["gender"] = "Boys"
            elif t_sec == "girls" and "gender" not in t_attrs and filter_key != "clothing_section":
                t_attrs["gender"] = "Girls"

            t_brand = "" if filter_key == "brand" else sel_brand
            if t_brand and t_brand.lower() != "all":
                t_attrs["brand"] = t_brand

            for k, target_val in t_attrs.items():
                if not target_val or target_val.lower() == "all":
                    continue
                if k == "gender":
                    c_items = [it for it in c_items if item_matches_gender(it, target_val)]
                elif k == "age_group":
                    c_items = [it for it in c_items if item_matches_age_group(it, target_val)]
                elif k == "clothing_type":
                    c_items = [it for it in c_items if item_matches_clothing_type(it, target_val)]
                elif k == "size":
                    c_items = [it for it in c_items if item_matches_size(it, target_val)]
                elif k == "brand":
                    c_items = [it for it in c_items if item_matches_brand(it, target_val)]
                else:
                    c_items = [it for it in c_items if str(it.get_attributes().get(k, "")).strip().lower() == str(target_val).strip().lower()]

            return len(c_items)

        best_cand, best_cnt, r_url = compute_best_filter_to_remove(active_filter_chips, evaluate_without)
        if best_cand and best_cnt > 0:
            removal_suggestion = f"No items match all filters. Removing '{best_cand['label']}' gives {best_cnt} results"
            removal_url = r_url

        all_avail = Item.query.filter_by(is_available=True).all()
        attach_distances(all_avail, lat, lng)
        you_might_like = get_you_might_like(all_avail, limit=4)

    return render_template(
        "browse.html",
        items=items,
        active_filter_chips=active_filter_chips,
        removal_suggestion=removal_suggestion,
        removal_url=removal_url,
        you_might_like=you_might_like,
        clear_all_url=clear_all_url,
        map_items=map_items,
        map_items_json=map_items_json,
        view=view,
        categories=categories,
        lat=lat,
        lng=lng,
        sel_category=sel_category,
        sel_genre=sel_genre,
        search=search,
        min_price=min_price,
        max_price=max_price,
        max_dist=max_dist,
        sort=sort or "nearest",
        cat_select_fields=cat_select_fields,
        attr_filters=attr_filters,
        book_genres=book_genres,
        show_book_rows=show_book_rows,
        trending_books=trending_books,
        genre_rows=genre_rows,
        show_category_rows=show_category_rows,
        category_rows=category_rows,
        sel_brand=sel_brand,
        clothing_section=clothing_section,
        show_clothes_sections=show_clothes_sections,
        boys_items=boys_items,
        girls_items=girls_items,
        adult_clothes_items=adult_clothes_items,
        age_groups=["0–2", "3–5", "6–8", "9–12", "13–17", "18+"],
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

