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
from utils.illustrations import item_slug

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
