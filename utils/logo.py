"""Original SVG shop logos for RentKart (shapes and text only)."""
import os
import re
import xml.sax.saxutils as saxutils

from flask import has_app_context, current_app, url_for

LOGO_STYLES = ("crest", "badge", "hexagon", "monogram", "ribbon")
_FONT = "Georgia, 'Times New Roman', Times, serif"
_SANS = "Arial, Helvetica, sans-serif"


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "shop"


def _esc(text) -> str:
    return saxutils.escape("" if text is None else str(text))


def _parse_colors(colors):
    named = {
        "maroon": "#800020",
        "gold": "#DAA520",
        "black": "#111111",
        "white": "#FFFFFF",
        "green": "#166534",
        "orange": "#EA580C",
        "blue": "#1D4ED8",
        "navy": "#1E3A8A",
        "purple": "#6B21A8",
        "teal": "#0F766E",
        "red": "#B91C1C",
        "cream": "#FEF3C7",
        "brown": "#7C4A1E",
    }
    if isinstance(colors, dict):
        primary = colors.get("primary") or colors.get("bg") or "#166534"
        secondary = colors.get("secondary") or colors.get("fg") or "#F97316"
        accent = colors.get("accent") or "#FDE68A"
        return primary, secondary, accent
    if isinstance(colors, (list, tuple)) and colors:
        primary = colors[0]
        secondary = colors[1] if len(colors) > 1 else "#F97316"
        accent = colors[2] if len(colors) > 2 else "#FEF3C7"
        return primary, secondary, accent
    text = str(colors or "").lower()
    found = [hexv for word, hexv in named.items() if word in text]
    if not found:
        found = ["#166534", "#F97316", "#FEF3C7"]
    while len(found) < 3:
        found.append("#FEF3C7")
    return found[0], found[1], found[2]


def _monogram(name: str) -> str:
    words = [w for w in re.split(r"\s+", name or "") if w]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if words:
        return words[0][:2].upper()
    return "RK"


def _symbol_crest(cx, cy, s, p, a, mono):
    return f'''
    <path d="M {cx} {cy - s} L {cx + s} {cy - s * 0.55} L {cx + s * 0.85} {cy + s * 0.35}
             L {cx} {cy + s} L {cx - s * 0.85} {cy + s * 0.35} L {cx - s} {cy - s * 0.55} Z"
          fill="{p}" stroke="{a}" stroke-width="4"/>
    <path d="M {cx - s * 0.35} {cy - s * 0.95} L {cx} {cy - s * 1.25} L {cx + s * 0.35} {cy - s * 0.95}
             L {cx + s * 0.15} {cy - s * 0.7} L {cx - s * 0.15} {cy - s * 0.7} Z"
          fill="{a}" stroke="{a}" stroke-width="1"/>
    <circle cx="{cx}" cy="{cy - s * 1.32}" r="{s * 0.12}" fill="{a}"/>
    <text x="{cx}" y="{cy + s * 0.12}" text-anchor="middle" font-family="{_FONT}"
          font-size="{s * 0.7}" font-weight="700" fill="{a}">{_esc(mono)}</text>
    '''


def _symbol_badge(cx, cy, s, p, sec, a, mono):
    return f'''
    <circle cx="{cx}" cy="{cy}" r="{s}" fill="none" stroke="{a}" stroke-width="6"/>
    <circle cx="{cx}" cy="{cy}" r="{s * 0.82}" fill="{p}" stroke="{sec}" stroke-width="3"/>
    <text x="{cx}" y="{cy + s * 0.22}" text-anchor="middle" font-family="{_FONT}"
          font-size="{s * 0.7}" font-weight="700" fill="{a}">{_esc(mono)}</text>
    '''


def _symbol_hexagon(cx, cy, s, p, a, mono):
    pts = []
    import math
    for i in range(6):
        ang = math.radians(60 * i - 30)
        pts.append(f"{cx + s * math.cos(ang):.1f},{cy + s * math.sin(ang):.1f}")
    return f'''
    <polygon points="{" ".join(pts)}" fill="{p}" stroke="{a}" stroke-width="4"/>
    <text x="{cx}" y="{cy + s * 0.22}" text-anchor="middle" font-family="{_FONT}"
          font-size="{s * 0.62}" font-weight="700" fill="{a}">{_esc(mono)}</text>
    '''


def _symbol_monogram(cx, cy, s, p, a, mono):
    return f'''
    <rect x="{cx - s}" y="{cy - s}" width="{s * 2}" height="{s * 2}" rx="{s * 0.2}"
          fill="{p}" stroke="{a}" stroke-width="4"/>
    <text x="{cx}" y="{cy + s * 0.28}" text-anchor="middle" font-family="{_FONT}"
          font-size="{s * 0.95}" font-weight="700" fill="{a}">{_esc(mono)}</text>
    '''


def _symbol_ribbon(cx, cy, s, p, sec, a, mono):
    return f'''
    <polygon points="{cx - s},{cy} {cx - s * 0.7},{cy - s * 0.85} {cx + s * 0.7},{cy - s * 0.85}
                     {cx + s},{cy} {cx + s * 0.7},{cy + s * 0.85} {cx - s * 0.7},{cy + s * 0.85}"
             fill="{p}" stroke="{a}" stroke-width="3"/>
    <rect x="{cx - s * 1.15}" y="{cy - s * 0.28}" width="{s * 2.3}" height="{s * 0.56}"
          fill="{sec}"/>
    <text x="{cx}" y="{cy + s * 0.16}" text-anchor="middle" font-family="{_SANS}"
          font-size="{s * 0.42}" font-weight="700" fill="{a}">{_esc(mono)}</text>
    '''


def _symbol(style, cx, cy, s, p, sec, a, mono):
    style = (style or "monogram").lower()
    if style == "crest":
        return _symbol_crest(cx, cy, s, p, a, mono)
    if style == "badge":
        return _symbol_badge(cx, cy, s, p, sec, a, mono)
    if style == "hexagon":
        return _symbol_hexagon(cx, cy, s, p, a, mono)
    if style == "ribbon":
        return _symbol_ribbon(cx, cy, s, p, sec, a, mono)
    return _symbol_monogram(cx, cy, s, p, a, mono)


def _logo_dir():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "logos"))
    if has_app_context():
        root = current_app.root_path
        base = os.path.join(root, "static", "logos")
    os.makedirs(base, exist_ok=True)
    return base


def make_logo_svg(name, tagline, style, colors):
    """Write original SVG logos to static/logos/<slug>.svg and <slug>-icon.svg."""
    slug = slugify_name(name)
    p, sec, a = _parse_colors(colors)
    mono = _monogram(name)
    name_u = _esc((name or "RENTKART").upper())
    tag_u = _esc((tagline or "LOCAL RENTALS").upper())
    style = (style or "monogram").lower()
    if style not in LOGO_STYLES:
        style = "monogram"

    banner = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200" viewBox="0 0 400 200">
  <rect width="400" height="200" fill="{sec}"/>
  <rect x="8" y="8" width="384" height="184" fill="{p}" rx="8"/>
  {_symbol(style, 90, 100, 52, p, sec, a, mono)}
  <text x="160" y="88" font-family="{_FONT}" font-size="18" font-weight="700"
        fill="{a}">{name_u}</text>
  <text x="160" y="118" font-family="{_SANS}" font-size="10" font-weight="600"
        letter-spacing="1.5" fill="{a}">{tag_u}</text>
</svg>
'''
    icon = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <rect width="200" height="200" fill="{p}"/>
  {_symbol(style, 100, 78, 48, p, sec, a, mono)}
  <text x="100" y="158" text-anchor="middle" font-family="{_FONT}" font-size="11"
        font-weight="700" fill="{a}">{name_u}</text>
  <text x="100" y="176" text-anchor="middle" font-family="{_SANS}" font-size="8"
        font-weight="600" letter-spacing="1.2" fill="{a}">{tag_u}</text>
</svg>
'''
    folder = _logo_dir()
    banner_path = os.path.join(folder, f"{slug}.svg")
    icon_path = os.path.join(folder, f"{slug}-icon.svg")
    with open(banner_path, "w", encoding="utf-8") as fh:
        fh.write(banner)
    with open(icon_path, "w", encoding="utf-8") as fh:
        fh.write(icon)
    return f"logos/{slug}.svg"


def shop_initials(owner_or_name) -> str:
    if owner_or_name is None:
        return "RK"
    name = owner_or_name if isinstance(owner_or_name, str) else (
        getattr(owner_or_name, "shop_name", None) or getattr(owner_or_name, "name", "") or ""
    )
    return _monogram(name)


def shop_logo_filename(owner) -> str:
    if not owner:
        return ""
    return getattr(owner, "shop_logo", None) or ""


def shop_logo_static_path(owner) -> str:
    """Return a static relative path for a shop logo, or empty string."""
    logo = shop_logo_filename(owner)
    if not logo:
        slug = getattr(owner, "shop_slug", None) if owner else None
        if slug:
            candidate = f"logos/{slug}.svg"
            folder = _logo_dir()
            if os.path.isfile(os.path.join(os.path.dirname(folder), "logos", f"{slug}.svg")) or os.path.isfile(
                os.path.join(folder, f"{slug}.svg")
            ):
                return candidate
        return ""
    if logo.endswith(".svg") or logo.startswith("logos/") or logo.startswith("demo_photos/"):
        return logo if "/" in logo else f"logos/{logo}"
    if logo.startswith("uploads/"):
        return logo
    return f"uploads/{logo}"


def shop_logo_url(owner):
    path = shop_logo_static_path(owner)
    if not path:
        return None
    try:
        return url_for("static", filename=path)
    except Exception:
        return f"/static/{path}"


def item_image_static_path(item) -> str:
    image = getattr(item, "image", None) if item else None
    if not image:
        return ""
    if image.startswith("demo_photos/") or image.startswith("logos/") or image.startswith("uploads/"):
        return image
    return f"uploads/{image}"
