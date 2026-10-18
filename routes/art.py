"""Generated-art blueprint (ART feature).

Serves original, in-code-generated SVG artwork through cached routes - never
one file per item. Every response carries an ETag (md5 of the SVG) and a
Cache-Control max-age, and honours If-None-Match with 304.

Stage 1: /art/clothes/<item_id>.svg
Stage 2 adds /art/item/<item_id>.svg (tools, events, electronics, ...).
Stage 3 adds /art/cover/<item_id>.svg (book covers).
"""
import hashlib

from flask import Blueprint, make_response, request

from models import Item
from utils.art_clothes import make_clothes_art
from utils.art_events import make_event_art
from utils.art_misc import make_misc_art
from utils.art_tools import make_tool_art
from utils.illustrations import item_slug
from config import match_subcategory

art_bp = Blueprint("art", __name__, url_prefix="/art")

CACHE_SECONDS = 86400


def _svg_response(svg: str) -> "Response":
    """Return an image/svg+xml response with ETag + max-age caching."""
    etag = '"' + hashlib.md5(svg.encode("utf-8")).hexdigest() + '"'
    if request.headers.get("If-None-Match") == etag:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        return resp
    resp = make_response(svg)
    resp.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@art_bp.route("/clothes/<int:item_id>.svg")
def clothes_art(item_id):
    """Rich colour-aware garment art for one clothes item."""
    item = Item.query.get_or_404(item_id)
    attrs = item.get_attributes()
    svg = make_clothes_art(
        attrs.get("clothing_type", ""),
        attrs.get("color", ""),
        attrs.get("style", ""),
        attrs.get("gender", ""),
        attrs.get("age_group", ""),
        slug=item_slug(item),
    )
    return _svg_response(svg)


@art_bp.route("/item/<int:item_id>.svg")
def item_art(item_id):
    """Generated art for farm tools, events, electronics, security, furniture.

    Lookup order inside each family: type attribute (tool_type / item_type /
    device_type / security_type) -> matched sub-category key -> category
    default. Never returns a blank box.
    """
    item = Item.query.get_or_404(item_id)
    attrs = item.get_attributes()
    category = item.category or ""
    sc = match_subcategory(category, attrs)
    subcat_key = sc["key"] if sc else ""
    slug = item_slug(item)
    if category == "farm_tools":
        svg = make_tool_art(tool_type=attrs.get("tool_type", ""),
                            subcat_key=subcat_key, slug=slug)
    elif category == "event_items":
        svg = make_event_art(item_type=attrs.get("item_type", ""),
                             subcat_key=subcat_key,
                             style=attrs.get("style", ""), slug=slug)
    else:
        cat = category if category in ("electronics", "security", "furniture") \
            else "electronics"
        type_value = (attrs.get("device_type") or attrs.get("security_type")
                      or attrs.get("item_type") or attrs.get("tool_type") or "")
        svg = make_misc_art(category=cat, type_value=type_value,
                            subcat_key=subcat_key, slug=slug)
    return _svg_response(svg)
