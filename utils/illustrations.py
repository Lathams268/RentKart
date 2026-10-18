"""Original flat SVG illustrations and item picture resolution for RentKart."""
from __future__ import annotations

import os
import re

from flask import has_request_context, url_for

from config import BASE_DIR, CATEGORIES, illustration_keys, match_subcategory

ILLUSTRATION_DIR = os.path.join(BASE_DIR, "static", "illustrations")
DEMO_PHOTOS_DIR = os.path.join(BASE_DIR, "static", "demo_photos")

# Accepted real-photo extensions, checked in this order.
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Legacy generated placeholder files (blue gradient + white circle) that must
# never count as an item's real photo, so the matching illustration shows.
PLACEHOLDER_IMAGE_RE = re.compile(r"^seed(?:_[a-z]+)*_\d+\.png$", re.IGNORECASE)


def is_placeholder_image(value) -> bool:
    """True when an image value is a legacy seed_<n>.png placeholder."""
    if not value:
        return False
    base = os.path.basename(str(value).replace("\\", "/"))
    return bool(PLACEHOLDER_IMAGE_RE.match(base))

CAT_COLORS = {
    "clothes": ("#FDE8EE", "#800020", "#DAA520"),
    "books": ("#E8F4FC", "#0F2350", "#14919B"),
    "farm_tools": ("#EAF6E4", "#1E6423", "#784B1E"),
    "electronics": ("#EEE8FA", "#370F55", "#1E50B4"),
    "event_items": ("#FFF1E6", "#E65014", "#DC286E"),
    "security": ("#F3F4F6", "#1F2937", "#F97316"),
}

KEY_CATEGORY = {}
for _ck, _cv in CATEGORIES.items():
    KEY_CATEGORY[_ck] = _ck
    for _sc in _cv.get("subcategories", []):
        KEY_CATEGORY[_sc["key"]] = _ck


def _slug(text) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s or "item"


def item_slug(item) -> str:
    slug = getattr(item, "slug", None)
    if slug:
        return _slug(slug)
    return _slug(getattr(item, "title", "") or "")


def illustration_path(key: str) -> str:
    return os.path.join(ILLUSTRATION_DIR, f"{key}.svg")


def _wrap(c1, accent, body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.35"/>
    </linearGradient>
  </defs>
  <rect width="800" height="600" fill="url(#bg)"/>
  {body}
</svg>
'''


def _open_book(cx=400, cy=320, smile=False, diya=False):
    extra = ""
    if smile:
        extra = f'<circle cx="{cx-40}" cy="{cy-10}" r="8" fill="#1F2937"/><circle cx="{cx+40}" cy="{cy-10}" r="8" fill="#1F2937"/><path d="M{cx-50} {cy+30} Q{cx} {cy+70} {cx+50} {cy+30}" fill="none" stroke="#1F2937" stroke-width="8" stroke-linecap="round"/>'
    if diya:
        extra = f'<ellipse cx="{cx}" cy="{cy+10}" rx="36" ry="16" fill="#F59E0B"/><path d="M{cx} {cy-30} Q{cx+18} {cy-8} {cx} {cy+8} Q{cx-8} {cy-10} {cx} {cy-30}Z" fill="#F97316"/><circle cx="{cx}" cy="{cy-34}" r="8" fill="#FDE68A"/>'
    return f'''
    <ellipse cx="{cx}" cy="{cy+90}" rx="210" ry="28" fill="#000" opacity="0.08"/>
    <path d="M{cx-180} {cy-80} Q{cx-20} {cy-120} {cx} {cy-40} L{cx} {cy+80} Q{cx-20} {cy} {cx-180} {cy+40} Z" fill="#FEF9C3" stroke="#92400E" stroke-width="6"/>
    <path d="M{cx+180} {cy-80} Q{cx+20} {cy-120} {cx} {cy-40} L{cx} {cy+80} Q{cx+20} {cy} {cx+180} {cy+40} Z" fill="#FFFBEB" stroke="#92400E" stroke-width="6"/>
    {extra}
    '''


def _book_stack():
    return '''
    <rect x="250" y="340" width="300" height="46" rx="6" fill="#1D4ED8"/>
    <rect x="240" y="292" width="320" height="46" rx="6" fill="#0F766E"/>
    <rect x="260" y="244" width="280" height="46" rx="6" fill="#7C3AED"/>
    <rect x="230" y="196" width="340" height="46" rx="6" fill="#B45309"/>
    '''


def _dress_hanger():
    return '''
    <path d="M400 90 L400 130" stroke="#6B7280" stroke-width="10" stroke-linecap="round"/>
    <path d="M280 160 Q400 90 520 160" fill="none" stroke="#6B7280" stroke-width="10"/>
    <path d="M250 170 L400 150 L550 170 L530 430 Q400 500 270 430 Z" fill="#BE185D"/>
    <path d="M310 170 L400 155 L490 170 L470 300 Q400 340 330 300 Z" fill="#F9A8D4"/>
    '''


def _coat():
    return '''
    <path d="M300 140 L400 170 L500 140 L560 210 L520 480 L280 480 L240 210 Z" fill="#1E3A8A"/>
    <path d="M400 170 L400 480" stroke="#FBBF24" stroke-width="8"/>
    <path d="M300 140 Q400 90 500 140" fill="none" stroke="#1E3A8A" stroke-width="18"/>
    <circle cx="400" cy="260" r="10" fill="#FBBF24"/>
    <circle cx="400" cy="320" r="10" fill="#FBBF24"/>
    '''


def _small_frock():
    return '''
    <circle cx="400" cy="150" r="36" fill="#FBCFE8"/>
    <path d="M370 185 L430 185 L500 420 L300 420 Z" fill="#EC4899"/>
    <rect x="385" y="185" width="30" height="40" fill="#F9A8D4"/>
    '''


def _gown():
    return '''
    <circle cx="400" cy="130" r="28" fill="#E0E7FF"/>
    <path d="M370 160 L430 160 L560 500 L240 500 Z" fill="#4F46E5"/>
    <path d="M380 160 L420 160 L440 240 L360 240 Z" fill="#818CF8"/>
    '''


def _blazer():
    return '''
    <rect x="300" y="150" width="200" height="300" rx="20" fill="#111827"/>
    <path d="M400 150 L400 450" stroke="#E5E7EB" stroke-width="6"/>
    <path d="M300 150 L250 230 L300 230" fill="#1F2937"/>
    <path d="M500 150 L550 230 L500 230" fill="#1F2937"/>
    <rect x="360" y="120" width="80" height="40" rx="8" fill="#F9FAFB"/>
    '''


def _tractor():
    return '''
    <rect x="220" y="230" width="280" height="120" rx="16" fill="#16A34A"/>
    <rect x="430" y="180" width="140" height="90" rx="12" fill="#166534"/>
    <circle cx="280" cy="380" r="70" fill="#1F2937"/>
    <circle cx="280" cy="380" r="32" fill="#9CA3AF"/>
    <circle cx="500" cy="400" r="50" fill="#1F2937"/>
    <circle cx="500" cy="400" r="22" fill="#9CA3AF"/>
    <rect x="250" y="250" width="90" height="40" rx="6" fill="#86EFAC"/>
    '''


def _plough():
    return '''
    <rect x="200" y="250" width="360" height="24" rx="8" fill="#7C4A1E"/>
    <path d="M520 250 L640 360 L500 360 Z" fill="#374151"/>
    <path d="M480 274 L600 400" stroke="#1F2937" stroke-width="16"/>
    <circle cx="240" cy="360" r="40" fill="#4B5563"/>
    '''


def _tank():
    return '''
    <ellipse cx="400" cy="200" rx="160" ry="50" fill="#0284C7"/>
    <rect x="240" y="200" width="320" height="200" fill="#0369A1"/>
    <ellipse cx="400" cy="400" rx="160" ry="50" fill="#0EA5E9"/>
    <rect x="385" y="140" width="30" height="50" fill="#075985"/>
    '''


def _sprayer():
    return '''
    <rect x="280" y="180" width="160" height="220" rx="40" fill="#16A34A"/>
    <rect x="320" y="140" width="80" height="50" rx="10" fill="#166534"/>
    <path d="M440 240 L560 200 L580 230 L460 270 Z" fill="#4B5563"/>
    <circle cx="590" cy="210" r="18" fill="#9CA3AF"/>
    <rect x="250" y="220" width="40" height="120" rx="12" fill="#14532D"/>
    '''


def _spade_hammer():
    return '''
    <rect x="250" y="160" width="36" height="280" rx="8" fill="#7C4A1E"/>
    <path d="M200 150 L336 150 L300 80 L236 80 Z" fill="#6B7280"/>
    <rect x="480" y="220" width="36" height="240" rx="8" fill="#7C4A1E"/>
    <rect x="430" y="170" width="140" height="60" rx="8" fill="#4B5563"/>
    '''


def _drill():
    return '''
    <rect x="220" y="250" width="260" height="90" rx="20" fill="#F97316"/>
    <rect x="470" y="270" width="160" height="40" rx="8" fill="#6B7280"/>
    <polygon points="630,290 700,270 700,310" fill="#9CA3AF"/>
    <rect x="250" y="340" width="70" height="90" rx="10" fill="#111827"/>
    '''


def _camera():
    return '''
    <rect x="220" y="210" width="360" height="220" rx="28" fill="#1F2937"/>
    <circle cx="400" cy="320" r="78" fill="#111827"/>
    <circle cx="400" cy="320" r="48" fill="#60A5FA"/>
    <circle cx="400" cy="320" r="18" fill="#1E3A8A"/>
    <rect x="280" y="170" width="90" height="50" rx="10" fill="#374151"/>
    <circle cx="520" cy="250" r="14" fill="#FBBF24"/>
    '''


def _speaker():
    return '''
    <rect x="250" y="150" width="180" height="320" rx="24" fill="#111827"/>
    <circle cx="340" cy="250" r="48" fill="#6B7280"/>
    <circle cx="340" cy="380" r="36" fill="#9CA3AF"/>
    <path d="M470 220 Q560 310 470 400" fill="none" stroke="#F97316" stroke-width="10"/>
    <path d="M510 180 Q640 310 510 440" fill="none" stroke="#FDBA74" stroke-width="8"/>
    '''


def _projector():
    return '''
    <rect x="180" y="260" width="280" height="120" rx="20" fill="#1F2937"/>
    <circle cx="250" cy="320" r="34" fill="#93C5FD"/>
    <polygon points="460,280 720,160 720,460 460,340" fill="#FDE68A" opacity="0.7"/>
    '''


def _drone():
    return '''
    <rect x="300" y="270" width="200" height="60" rx="16" fill="#0F172A"/>
    <circle cx="220" cy="220" r="40" fill="#64748B"/>
    <circle cx="580" cy="220" r="40" fill="#64748B"/>
    <circle cx="220" cy="380" r="40" fill="#64748B"/>
    <circle cx="580" cy="380" r="40" fill="#64748B"/>
    <line x1="300" y1="290" x2="220" y2="220" stroke="#0F172A" stroke-width="12"/>
    <line x1="500" y1="290" x2="580" y2="220" stroke="#0F172A" stroke-width="12"/>
    <line x1="300" y1="310" x2="220" y2="380" stroke="#0F172A" stroke-width="12"/>
    <line x1="500" y1="310" x2="580" y2="380" stroke="#0F172A" stroke-width="12"/>
    <circle cx="400" cy="300" r="18" fill="#38BDF8"/>
    '''


def _laptop():
    return '''
    <rect x="210" y="150" width="380" height="240" rx="12" fill="#1F2937"/>
    <rect x="230" y="170" width="340" height="200" fill="#93C5FD"/>
    <rect x="180" y="390" width="440" height="28" rx="6" fill="#374151"/>
    '''


def _generator():
    return '''
    <rect x="230" y="200" width="340" height="240" rx="18" fill="#374151"/>
    <path d="M400 250 L360 330 L410 330 L370 400 L460 300 L410 300 Z" fill="#FBBF24"/>
    <circle cx="280" cy="260" r="16" fill="#9CA3AF"/>
    '''


def _tent():
    return '''
    <path d="M400 120 L620 430 L180 430 Z" fill="#F97316"/>
    <path d="M400 120 L400 430" stroke="#9A3412" stroke-width="8"/>
    <path d="M400 280 L470 430 L330 430 Z" fill="#FED7AA"/>
    '''


def _chair():
    return '''
    <rect x="280" y="180" width="240" height="40" rx="8" fill="#B45309"/>
    <rect x="280" y="220" width="40" height="200" fill="#92400E"/>
    <rect x="480" y="220" width="40" height="200" fill="#92400E"/>
    <rect x="280" y="300" width="240" height="28" fill="#D97706"/>
    '''


def _balloons():
    return '''
    <circle cx="300" cy="200" r="55" fill="#F43F5E"/>
    <circle cx="400" cy="160" r="55" fill="#FBBF24"/>
    <circle cx="500" cy="210" r="55" fill="#22C55E"/>
    <line x1="300" y1="255" x2="300" y2="430" stroke="#6B7280" stroke-width="4"/>
    <line x1="400" y1="215" x2="400" y2="430" stroke="#6B7280" stroke-width="4"/>
    <line x1="500" y1="265" x2="500" y2="430" stroke="#6B7280" stroke-width="4"/>
    <path d="M240 430 Q400 360 560 430" fill="none" stroke="#E11D48" stroke-width="10"/>
    '''


def _spot():
    return '''
    <rect x="360" y="80" width="80" height="40" fill="#111827"/>
    <path d="M340 120 L460 120 L500 200 L300 200 Z" fill="#1F2937"/>
    <polygon points="300,200 500,200 640,500 160,500" fill="#FDE68A" opacity="0.55"/>
    '''


def _diya():
    return '''
    <ellipse cx="400" cy="360" rx="140" ry="40" fill="#B45309"/>
    <ellipse cx="400" cy="340" rx="110" ry="28" fill="#F59E0B"/>
    <path d="M400 250 Q430 300 400 340 Q380 300 400 250Z" fill="#F97316"/>
    <circle cx="400" cy="240" r="16" fill="#FEF3C7"/>
    '''


def _mic():
    return '''
    <rect x="360" y="140" width="80" height="180" rx="40" fill="#111827"/>
    <rect x="385" y="320" width="30" height="90" fill="#6B7280"/>
    <rect x="340" y="410" width="120" height="24" rx="8" fill="#9CA3AF"/>
    '''


def _console():
    return '''
    <rect x="220" y="230" width="360" height="160" rx="40" fill="#111827"/>
    <circle cx="300" cy="310" r="36" fill="#EF4444"/>
    <circle cx="500" cy="300" r="18" fill="#22C55E"/>
    <circle cx="540" cy="330" r="18" fill="#3B82F6"/>
    '''


def _screen():
    return '''
    <rect x="180" y="140" width="440" height="280" rx="16" fill="#111827"/>
    <rect x="200" y="160" width="400" height="240" fill="#93C5FD"/>
    <rect x="360" y="420" width="80" height="40" fill="#374151"/>
    '''


def _catering():
    return '''
    <ellipse cx="400" cy="360" rx="160" ry="40" fill="#9CA3AF"/>
    <path d="M250 360 Q400 80 550 360" fill="none" stroke="#6B7280" stroke-width="18"/>
    <circle cx="400" cy="200" r="24" fill="#D1D5DB"/>
    '''


def _photobooth():
    return '''
    <rect x="250" y="120" width="300" height="360" rx="12" fill="#F9FAFB" stroke="#111827" stroke-width="10"/>
    <circle cx="400" cy="280" r="70" fill="#1F2937"/>
    <circle cx="400" cy="280" r="36" fill="#60A5FA"/>
    <rect x="280" y="150" width="80" height="24" fill="#F97316"/>
    '''


def _soil():
    return '''
    <rect x="360" y="160" width="40" height="220" fill="#7C4A1E"/>
    <path d="M200 380 Q400 300 600 380 L600 460 L200 460 Z" fill="#A16207"/>
    <circle cx="400" cy="150" r="28" fill="#16A34A"/>
    '''


def _cart():
    return '''
    <rect x="230" y="220" width="300" height="140" rx="12" fill="#B45309"/>
    <circle cx="300" cy="400" r="40" fill="#1F2937"/>
    <circle cx="480" cy="400" r="40" fill="#1F2937"/>
    <rect x="520" y="240" width="80" height="24" fill="#7C4A1E"/>
    '''


def _harvester():
    return '''
    <rect x="200" y="240" width="360" height="120" rx="16" fill="#CA8A04"/>
    <circle cx="280" cy="390" r="50" fill="#1F2937"/>
    <circle cx="500" cy="390" r="50" fill="#1F2937"/>
    <rect x="430" y="170" width="120" height="80" fill="#A16207"/>
    '''


def _other_book():
    return _book_stack()


DRAWERS = {
    "clothes": _dress_hanger,
    "lehenga": _dress_hanger,
    "saree": _dress_hanger,
    "sherwani": _coat,
    "kurta": _coat,
    "kurta_set": _coat,
    "kids_wear": _small_frock,
    "western": _gown,
    "gown": _gown,
    "blazer": _blazer,
    "frock": _small_frock,
    "anarkali": _dress_hanger,
    "books": _book_stack,
    "comedy": lambda: _open_book(smile=True),
    "spiritual": lambda: _open_book(diya=True),
    "motivation": _open_book,
    "self_help": _open_book,
    "fiction": _open_book,
    "biography": _open_book,
    "mythology": lambda: _open_book(diya=True),
    "children_books": _open_book,
    "education": _book_stack,
    "business_books": _book_stack,
    "health": _open_book,
    "poetry": _open_book,
    "other_books": _other_book,
    "farm_tools": _tractor,
    "tractor": _tractor,
    "attachments": _plough,
    "water_tank": _tank,
    "sprayer": _sprayer,
    "harvesting": _harvester,
    "hand_tools": _spade_hammer,
    "power_tools": _drill,
    "soil": _soil,
    "transport": _cart,
    "electronics": _camera,
    "camera": _camera,
    "laptop": _laptop,
    "projector": _projector,
    "speaker": _speaker,
    "microphone": _mic,
    "drone": _drone,
    "lights": _spot,
    "generator": _generator,
    "console": _console,
    "screen": _screen,
    "event_items": _balloons,
    "decoration": _balloons,
    "chairs": _chair,
    "tent": _tent,
    "stage_lighting": _spot,
    "catering": _catering,
    "stage": _spot,
    "festival_items": _diya,
    "photobooth": _photobooth,
}


def write_illustration(key: str) -> str:
    os.makedirs(ILLUSTRATION_DIR, exist_ok=True)
    cat = KEY_CATEGORY.get(key, "clothes")
    c1, accent, _ = CAT_COLORS.get(cat, CAT_COLORS["clothes"])
    drawer = DRAWERS.get(key) or DRAWERS.get(cat) or _book_stack
    body = drawer()
    svg = _wrap(c1, accent, body)
    dest = illustration_path(key)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return dest


def generate_all_illustrations() -> list:
    written = []
    for key in illustration_keys():
        written.append(write_illustration(key))
    return written


def ensure_illustrations():
    os.makedirs(ILLUSTRATION_DIR, exist_ok=True)
    missing = [k for k in illustration_keys() if not os.path.isfile(illustration_path(k))]
    if missing or not os.listdir(ILLUSTRATION_DIR):
        generate_all_illustrations()


def _exists(*parts) -> str:
    path = os.path.join(*parts)
    return path if os.path.isfile(path) else ""


def _static_url(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if has_request_context():
        try:
            return url_for("static", filename=rel)
        except Exception:
            pass
    return "/static/" + rel


def _upload_file(item) -> str:
    image = getattr(item, "image", None)
    if not image:
        return ""
    # A legacy generated placeholder is treated as "no photo" so the illustration shows.
    if is_placeholder_image(image):
        return ""
    if str(image).startswith(("http://", "https://", "/static/")):
        return image
    rel = image.replace("\\", "/")
    if rel.startswith("uploads/") or rel.startswith("demo_photos/") or rel.startswith("illustrations/") or rel.startswith("logos/"):
        full = os.path.join(BASE_DIR, "static", rel.replace("/", os.sep))
        return rel if os.path.isfile(full) else ""
    full = os.path.join(BASE_DIR, "static", "uploads", os.path.basename(rel))
    return f"uploads/{os.path.basename(rel)}" if os.path.isfile(full) else ""


def _demo_photo_for_slug(slug: str) -> str:
    if not slug:
        return ""
    folder = DEMO_PHOTOS_DIR
    for ext in PHOTO_EXTS:
        name = slug + ext
        if os.path.isfile(os.path.join(folder, name)):
            return f"demo_photos/{name}"
    return ""


def _stock_photo(category: str, subcat_key: str = "") -> str:
    """Find a real stock photo for stock/<category>/<subcat_key> then .../default.
    Returns a static-relative path like 'demo_photos/stock/books/spiritual.jpg'."""
    if not category:
        return ""
    folder = os.path.join(DEMO_PHOTOS_DIR, "stock", category)
    for name in (n for n in (subcat_key, "default") if n):
        for ext in PHOTO_EXTS:
            if os.path.isfile(os.path.join(folder, name + ext)):
                return f"demo_photos/stock/{category}/{name}{ext}"
    return ""


def allowed_stock_pictures(category=None, attrs=None) -> list:
    """Allowed gallery files from illustrations + demo_photos/stock/<category>/."""
    ensure_illustrations()
    allowed = []
    keys = []
    if category and category in CATEGORIES:
        keys.append(category)
        sc = match_subcategory(category, attrs or {})
        if sc:
            keys.insert(0, sc["key"])
        else:
            for row in CATEGORIES[category].get("subcategories", []):
                keys.append(row["key"])
    else:
        keys = illustration_keys()
    seen = set()
    for key in keys:
        rel = f"illustrations/{key}.svg"
        if rel not in seen and os.path.isfile(os.path.join(BASE_DIR, "static", "illustrations", f"{key}.svg")):
            seen.add(rel)
            allowed.append(rel)
    if category:
        stock_dir = os.path.join(DEMO_PHOTOS_DIR, "stock", category)
        if os.path.isdir(stock_dir):
            for name in sorted(os.listdir(stock_dir)):
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".svg")):
                    rel = f"demo_photos/stock/{category}/{name}"
                    if rel not in seen:
                        seen.add(rel)
                        allowed.append(rel)
    return allowed


def is_allowed_stock_picture(value: str, category=None) -> bool:
    if not value or not isinstance(value, str):
        return False
    value = value.replace("\\", "/").lstrip("/")
    if ".." in value or value.startswith("/") or ":" in value:
        return False
    allowed = set(allowed_stock_pictures(category, None))
    if value in allowed:
        return True
    # still accept any generated illustration or stock file on disk
    full = os.path.normpath(os.path.join(BASE_DIR, "static", value))
    static_root = os.path.normpath(os.path.join(BASE_DIR, "static"))
    if not full.startswith(static_root):
        return False
    if not os.path.isfile(full):
        return False
    return value.startswith("illustrations/") or value.startswith("demo_photos/stock/")


def item_picture(item) -> dict:
    """Resolve a picture in priority order:
    1) the item's own uploaded photo (not a legacy seed_<n>.png)
    2) static/demo_photos/<item-slug>.(jpg|jpeg|png|webp)
    3) static/demo_photos/stock/<category>/<subcategory-key>.(...)
    4) static/demo_photos/stock/<category>/default.(...)
    5) the existing drawing for the sub-category, then the category drawing
    Real photos use object-fit: cover; drawings keep their current look.
    """
    ensure_illustrations()
    title = getattr(item, "title", "") or ""
    category = getattr(item, "category", "") or ""
    attrs = item.get_attributes() if hasattr(item, "get_attributes") else {}
    slug = item_slug(item)

    kind = "illustration"
    rel = ""
    fit = "cover"

    uploaded = _upload_file(item)
    demo = _demo_photo_for_slug(slug)
    sc = match_subcategory(category, attrs)
    subcat_key = sc["key"] if sc else ""
    stock = _stock_photo(category, subcat_key)

    if uploaded:
        kind, rel, fit = "photo", uploaded, "cover"
    elif demo:
        kind, rel, fit = "demo", demo, "cover"
    elif stock:
        kind, rel, fit = "stock", stock, "cover"
    else:
        if sc and os.path.isfile(illustration_path(sc["key"])):
            kind, rel, fit = "illustration", f"illustrations/{sc['key']}.svg", "cover"
        elif category and os.path.isfile(illustration_path(category)):
            kind, rel, fit = "category", f"illustrations/{category}.svg", "cover"
        else:
            owner = getattr(item, "owner", None)
            logo = getattr(owner, "shop_logo", None) if owner else None
            if logo:
                kind, rel, fit = "logo", (logo if "/" in str(logo) else f"uploads/{logo}"), "contain"
            else:
                kind, rel, fit = "initials", "", "cover"

    src = _static_url(rel) if rel else ""
    initials = ""
    if kind == "initials":
        owner = getattr(item, "owner", None)
        name = (getattr(owner, "shop_name", None) if owner else None) or (getattr(owner, "name", None) if owner else None) or title
        words = [w for w in str(name).split() if w]
        initials = (words[0][0] + (words[1][0] if len(words) > 1 else (words[0][1] if words and len(words[0]) > 1 else "K"))).upper() if words else "RK"
    return {
        "src": src,
        "path": rel,
        "kind": kind,
        "fit": fit,
        "initials": initials,
        "url": src,
    }


def picture_choices_payload(category, attrs=None):
    items = []
    for rel in allowed_stock_pictures(category, attrs):
        items.append({
            "value": rel,
            "src": _static_url(rel),
            "kind": "illustration" if rel.endswith(".svg") else "photo",
        })
    return items


if __name__ == "__main__":
    paths = generate_all_illustrations()
    print(f"Wrote {len(paths)} illustrations to {ILLUSTRATION_DIR}")
