"""Rich, colour-aware clothes art (ART stage 1) - original generated SVG only.

make_clothes_art() builds an 800x1000 (4:5) studio scene for a garment:
a soft background gradient tinted from the item's colour, a hanging rail and
hanger (or a mannequin-free stand for kids suits), a floor shadow, and a
layered garment drawn from paths, gradients, folds, trims, repeating
<pattern> embroidery/print, a gold border, sequin dots and a lighter lining.

Two items of the same garment look different because the pattern kind,
pattern phase and sequin scatter are chosen from a hash of the item slug.
No external URLs, fonts or scripts ever leave this module; all text is XML
escaped.
"""
from __future__ import annotations

import hashlib
import re
from xml.sax.saxutils import escape as _x

# ---------------------------------------------------------------------------
# Palettes: colour name -> (base, light, dark)
# ---------------------------------------------------------------------------
PALETTE = {
    "red":        ("#C81E33", "#F26371", "#7C0B1B"),
    "maroon":     ("#7B1E3B", "#B0475F", "#4A0F24"),
    "pink":       ("#E85D9B", "#FBB2CE", "#B53A6E"),
    "orange":     ("#F07818", "#FFB877", "#B85410"),
    "yellow":     ("#F2B705", "#FCE181", "#C08E00"),
    "green":      ("#1F8A43", "#7CC796", "#0E5A2A"),
    "blue":       ("#2464C8", "#8AB4EE", "#123F86"),
    "navy":       ("#1F3564", "#5E76A8", "#0D1B36"),
    "purple":     ("#6D3FA8", "#B48DE0", "#45236E"),
    "black":      ("#20222A", "#5A5E6B", "#0B0C10"),
    "white":      ("#F4F2EC", "#FFFFFF", "#CFCBC0"),
    "cream":      ("#EFE0B8", "#FFF6DC", "#C9B277"),
    "gold":       ("#C9A227", "#F0D67A", "#8F6E10"),
    "silver":     ("#B9C0C8", "#E8ECF1", "#7E8894"),
    "multicolor": ("#E85D9B", "#F2B705", "#2464C8"),
}
DEFAULT_TRIPLE = ("#800020", "#FDE8EE", "#4A0F24")
MULTI_SET = ["#E85D9B", "#F2B705", "#2464C8", "#1F8A43", "#6D3FA8", "#F07818"]
GOLD = "#C9A227"
GOLD_LIGHT = "#F0D67A"
LINING_OPACITY = 0.85

PATTERN_KINDS = ("floral", "paisley", "geometric", "border_plain")

W, H = 800, 1000


def esc(text) -> str:
    """XML-escape any text that goes into the SVG."""
    return _x(str(text or ""))


def _slug_norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _seed(slug) -> int:
    return int(hashlib.md5(_slug_norm(slug or "item").encode("utf-8")).hexdigest()[:8], 16)


def _norm(text) -> str:
    return re.sub(r"[^a-z]", "", str(text or "").lower())


def triple_for(color):
    """Return (base, light, dark, multi_bool) for a colour name."""
    key = _norm(color)
    for name, trip in PALETTE.items():
        if key and (name.startswith(key[:4]) or key.startswith(name[:4])):
            if name == "multicolor":
                return (trip[0], trip[1], trip[2], True)
            return (trip[0], trip[1], trip[2], False)
    return (DEFAULT_TRIPLE[0], DEFAULT_TRIPLE[1], DEFAULT_TRIPLE[2], False)


# ---------------------------------------------------------------------------
# Garment classification from config clothing_type / style / gender / age
# ---------------------------------------------------------------------------
def classify(clothing_type, style="", gender="", age_group="") -> tuple:
    """Return (builder, kids_flag). builder is a key in _BUILDERS."""
    ct = _norm(clothing_type)
    st = _norm(style)
    ag = _norm(age_group)
    kids = (st == "kids" or ag in ("02", "35", "68", "912", "1317")
            or ct.startswith("kids"))
    pairs = [
        ("capelehenga", "lehenga"), ("croptoplehenga", "lehenga"),
        ("lehenga", "lehenga"), ("pavadai", "pavadai"),
        ("angavastram", "stole"), ("anarkali", "anarkali"),
        ("sareegown", "gown"), ("saree", "saree"), ("sari", "saree"),
        ("sherwani", "sherwani"),
        ("salwar", "salwar"), ("sharara", "salwar"), ("palazzo", "salwar"),
        ("coord", "coord"), ("jumpsuit", "jumpsuit"),
        ("tuxedo", "tuxedo"), ("blazer", "blazer"),
        ("nehru", "nehru"), ("jacket", "nehru"), ("shrug", "nehru"),
        ("gown", "gown"), ("cocktail", "gown"), ("dress", "gown"),
        ("frock", "frock"), ("shirt", "shirt"),
        ("jeans", "jeans"), ("pants", "pants"), ("trousers", "pants"),
        ("skirt", "skirt"), ("dhoti", "dhoti"),
        ("kurta", "kurta"), ("kurti", "kurti"), ("top", "kurti"),
        ("ethnic", "kurta"),
    ]
    for needle, builder in pairs:
        if needle in ct:
            if builder == "kurta" and ("set" in ct or "pajama" in ct):
                builder = "kurta_set"
            return (builder, kids)
    if kids:
        return ("frock", True)
    return ("kurta", False)


# ---------------------------------------------------------------------------
# SVG scaffolding: gradients, patterns, background, floor shadow, rail
# ---------------------------------------------------------------------------
def _pattern_defs(kind: str, pid: str, p) -> str:
    base, light, dark, multi = p
    inks = MULTI_SET if multi else [GOLD, light]
    ink = inks[0]
    if kind == "floral":
        one, two = inks[0], inks[1 % len(inks)]
        return (f'<pattern id="{pid}" width="56" height="56" patternUnits="userSpaceOnUse">'
                f'<g fill="none" stroke="{one}" stroke-width="2.6" opacity="0.85">'
                f'<circle cx="14" cy="14" r="5"/><path d="M14 3v4M14 21v4M3 14h4M21 14h4M6 6l3 3M19 19l3 3M22 6l-3 3M9 19l-3 3"/>'
                f'<circle cx="40" cy="38" r="4"/></g>'
                f'<circle cx="14" cy="14" r="2" fill="{two}"/></pattern>')
    if kind == "paisley":
        return (f'<pattern id="{pid}" width="60" height="60" patternUnits="userSpaceOnUse" '
                f'patternTransform="rotate({18 * (hash(pid) % 4)})">'
                f'<path d="M18 8 Q34 10 32 28 Q30 44 14 42 Q26 36 26 24 Q26 14 18 8Z" '
                f'fill="none" stroke="{inks[0]}" stroke-width="2.6" opacity="0.9"/>'
                f'<circle cx="22" cy="24" r="3" fill="{inks[-1]}"/>'
                f'<path d="M46 14 Q54 22 46 30" fill="none" stroke="{inks[1 % len(inks)]}" stroke-width="2"/></pattern>')
    if kind == "geometric":
        return (f'<pattern id="{pid}" width="48" height="48" patternUnits="userSpaceOnUse">'
                f'<path d="M24 6 L42 24 L24 42 L6 24Z" fill="none" stroke="{inks[0]}" stroke-width="2.2" opacity="0.85"/>'
                f'<path d="M24 16 L32 24 L24 32 L16 24Z" fill="{inks[1 % len(inks)]}" opacity="0.5"/></pattern>')
    # border_plain: sparse micro-shimmer dots only
    return (f'<pattern id="{pid}" width="40" height="40" patternUnits="userSpaceOnUse">'
            f'<circle cx="8" cy="8" r="1.6" fill="{inks[0]}" opacity="0.7"/>'
            f'<circle cx="28" cy="24" r="1.4" fill="{inks[-1]}" opacity="0.6"/></pattern>')


def _defs(p, pk: str, pid: str, vid: str) -> str:
    base, light, dark, multi = p
    top = light if not multi else "#FDF3E3"
    return f'''<defs>
  <linearGradient id="bg{vid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{top}" stop-opacity="0.65"/>
    <stop offset="70%" stop-color="#FFFFFF"/>
    <stop offset="100%" stop-color="{light}" stop-opacity="0.5"/>
  </linearGradient>
  <linearGradient id="cloth{vid}" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0%" stop-color="{light}"/>
    <stop offset="45%" stop-color="{base}"/>
    <stop offset="100%" stop-color="{dark}"/>
  </linearGradient>
  <linearGradient id="sheen{vid}" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0"/>
    <stop offset="45%" stop-color="#FFFFFF" stop-opacity="0.4"/>
    <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="gold{vid}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{GOLD_LIGHT}"/>
    <stop offset="50%" stop-color="{GOLD}"/>
    <stop offset="100%" stop-color="{GOLD_LIGHT}"/>
  </linearGradient>
  <radialGradient id="floor{vid}" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0%" stop-color="#000000" stop-opacity="0.22"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
  </radialGradient>
  {_pattern_defs(pk, pid, p)}
</defs>'''


def _scene_bg(p, vid: str) -> str:
    return (f'<rect width="{W}" height="{H}" fill="url(#bg{vid})"/>'
            f'<ellipse cx="400" cy="430" rx="330" ry="380" fill="#FFFFFF" opacity="0.35"/>')


def _floor_shadow(vid: str) -> str:
    return f'<ellipse cx="400" cy="922" rx="240" ry="34" fill="url(#floor{vid})"/>'


def _rail() -> str:
    return ('<rect x="120" y="58" width="560" height="10" rx="5" fill="#9AA3AD"/>'
            '<rect x="120" y="58" width="560" height="4" rx="2" fill="#D7DCE2"/>'
            '<circle cx="120" cy="63" r="9" fill="#7E8894"/><circle cx="680" cy="63" r="9" fill="#7E8894"/>')


def _hanger(y=86) -> str:
    return (f'<path d="M400 {y - 16} q0 14 -12 16 q-14 3 -14 16" fill="none" stroke="#6B7280" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M318 {y + 34} L400 {y + 16} L482 {y + 34}" fill="none" stroke="#6B7280" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M318 {y + 34} Q400 {y + 58} 482 {y + 34}" fill="none" stroke="#6B7280" stroke-width="7"/>')


def _sequins(path_seed: int, band_y: list, x0=300, x1=500, n=26) -> str:
    """Deterministic scatter of small gold sequin dots inside a band."""
    out = []
    h = path_seed
    for i in range(n):
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        x = x0 + (h % (x1 - x0))
        y = band_y[i % len(band_y)] + (h >> 7) % 26
        r = 2 + (h >> 13) % 2
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{GOLD_LIGHT}" stroke="{GOLD}" stroke-width="0.8" opacity="0.9"/>')
    return "".join(out)


# ---------------------------------------------------------------------------
# Shared garment primitives (all drawn around cx=400)
# ---------------------------------------------------------------------------
def _fold_lines(x0, x1, y0, y1, n=5, color="#000000", op=0.16) -> str:
    out = []
    step = (x1 - x0) / max(1, n)
    for i in range(n + 1):
        x = x0 + i * step
        lean = 10 if i % 2 else -8
        out.append(f'<path d="M{x:.0f} {y0} Q{x + lean:.0f} {(y0 + y1) / 2:.0f} {x:.0f} {y1}" '
                   f'fill="none" stroke="{color}" stroke-width="3" opacity="{op}"/>')
    return "".join(out)


def _gold_border_path(d: str, vid: str, width=7) -> str:
    return f'<path d="{d}" fill="none" stroke="url(#gold{vid})" stroke-width="{width}" stroke-linejoin="round"/>'


def _sleeves(p, vid, y=210, length=120, width=52, flare=18):
    base, light, dark, _ = p
    return (f'<path d="M300 {y} q-46 18 -58 {length} q22 14 44 6 q18 -60 34 -92 Z" fill="url(#cloth{vid})" stroke="{dark}" stroke-width="2.5" opacity="0.95"/>'
            f'<path d="M500 {y} q46 18 58 {length} q-22 14 -44 6 q-18 -60 -34 -92 Z" fill="url(#cloth{vid})" stroke="{dark}" stroke-width="2.5" opacity="0.95"/>')


def _bodice(p, vid, pid, y0=196, y1=390, neck="round"):
    base, light, dark, _ = p
    if neck == "v":
        collar = f'M330 {y0} L400 {y0 + 58} L470 {y0} L470 {y0 - 14} L330 {y0 - 14} Z'
    else:
        collar = f'M330 {y0} Q400 {y0 + 34} 470 {y0} L470 {y0 - 16} L330 {y0 - 16} Z'
    return (f'<path d="M318 {y0 + 4} L482 {y0 + 4} L{488} {y1} L312 {y1} Z" fill="url(#cloth{vid})" stroke="{dark}" stroke-width="3"/>'
            f'<path d="{collar}" fill="{light}" opacity="{LINING_OPACITY}" stroke="{dark}" stroke-width="2.5"/>'
            f'<path d="M318 {y0 + 4} L482 {y0 + 4}" stroke="url(#gold{vid})" stroke-width="5" fill="none"/>'
            f'<path d="M318 {y1} L482 {y1}" stroke="url(#gold{vid})" stroke-width="6" fill="none"/>'
            f'<rect x="330" y="{y0 + 26}" width="140" height="{y1 - y0 - 40}" fill="url(#{pid})" opacity="0.55"/>')


# ---------------------------------------------------------------------------
# Builders - each returns the garment body for a scene
# ---------------------------------------------------------------------------
def _g_lehenga(p, vid, pid, sd, kids=False):
    s = 0.82 if kids else 1.0
    y_bod = 200 if not kids else 230
    skirt_top = y_bod + 150
    hem = 880 if not kids else 800
    cx = 400
    spread = (220 if not kids else 160)
    skirt = (f'M{cx - spread} {hem} Q{cx} {skirt_top - 60} {cx + spread} {hem} '
             f'L{cx + spread - 30} {hem} Q{cx} {hem + 26} {cx - spread + 30} {hem} Z')
    flare = (f'M{cx - 66} {skirt_top} L{cx + 66} {skirt_top} '
             f'Q{cx + spread} {skirt_top + 220} {cx + spread} {hem} '
             f'Q{cx} {hem + 34} {cx - spread} {hem} '
             f'Q{cx - spread} {skirt_top + 220} {cx - 66} {skirt_top} Z')
    bands = ""
    for i, t in enumerate((0.42, 0.62, 0.82)):
        yb = skirt_top + (hem - skirt_top) * t
        hw = 66 + (spread - 66) * t
        bands += (f'<path d="M{cx - hw:.0f} {yb:.0f} Q{cx} {yb + 26:.0f} {cx + hw:.0f} {yb:.0f}" '
                  f'fill="none" stroke="url(#gold{vid})" stroke-width="{8 - i}" opacity="0.95"/>')
        bands += (f'<path d="M{cx - hw:.0f} {yb + 12:.0f} Q{cx} {yb + 34:.0f} {cx + hw:.0f} {yb + 12:.0f}" '
                  f'fill="none" stroke="{p[2]}" stroke-width="3" opacity="0.5"/>')
    dupatta = (f'M300 {y_bod + 6} Q236 420 262 {hem - 130} Q280 {hem - 60} 240 {hem - 20} '
               f'L306 {hem - 60} Q330 480 348 {y_bod + 40} Z')
    body = (
        _sleeves(p, vid, y=y_bod + 6, length=110 if not kids else 80, width=46)
        + _bodice(p, vid, pid, y0=y_bod, y1=skirt_top, neck="round")
        + f'<path d="{flare}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{flare}" fill="url(#{pid})" opacity="0.65"/>'
        + _fold_lines(cx - spread + 26, cx + spread - 26, skirt_top + 60, hem - 12, 6)
        + bands
        + f'<path d="{skirt}" fill="none" stroke="url(#gold{vid})" stroke-width="13"/>'
        + f'<path d="{dupatta}" fill="{p[1]}" opacity="0.72" stroke="{p[2]}" stroke-width="2.5"/>'
        + f'<path d="{dupatta}" fill="url(#{pid})" opacity="0.5"/>'
        + _gold_border_path(dupatta, vid, 5)
        + _sequins(sd, [skirt_top + 90, skirt_top + 190, hem - 90])
    )
    if kids:
        body += (f'<path d="M368 {y_bod - 12} q32 -18 64 0 q-8 22 -32 22 q-24 0 -32 -22Z" fill="{GOLD}" stroke="{GOLD}" opacity="0.9"/>'
                 f'<path d="M400 {y_bod - 2} l-26 -16 l6 22Z M400 {y_bod - 2} l26 -16 l-6 22Z" fill="{p[2]}" opacity="0.6"/>')
    return body, kids is True


def _g_saree(p, vid, pid, sd, kids=False):
    base, light, dark, multi = p
    pallu = (f'M470 210 Q560 420 512 700 Q498 800 528 866 L462 866 Q440 640 430 420 Z')
    pleats = "".join(
        f'<path d="M{352 + i * 18} 360 q10 240 -4 506" fill="none" stroke="{dark}" stroke-width="4" opacity="0.4"/>'
        for i in range(6))
    body = (
        _bodice(p, vid, pid, y0=206, y1=330, neck="v")
        + _sleeves(p, vid, y=212, length=100)
        + f'<path d="M300 330 L500 330 Q520 640 508 872 Q400 906 292 872 Q282 620 300 330 Z" fill="url(#cloth{vid})" stroke="{dark}" stroke-width="3.5"/>'
        + pleats
        + f'<path d="M292 872 Q400 906 508 872" fill="none" stroke="url(#gold{vid})" stroke-width="12"/>'
        + f'<path d="{pallu}" fill="{light}" opacity="0.88" stroke="{dark}" stroke-width="3"/>'
        + f'<path d="{pallu}" fill="url(#{pid})" opacity="0.6"/>'
        + _gold_border_path(pallu, vid, 8)
        + _sequins(sd, [420, 540, 700], x0=320, x1=480, n=18)
    )
    return body, kids


def _g_sherwani(p, vid, pid, sd, kids=False):
    s = 0.85 if kids else 1.0
    hem = int(700 + 170 * s)
    coat = (f'M316 214 L484 214 L508 {hem} L292 {hem} Z')
    panel = f'374 300 426 {hem - 40}'
    buttons = "".join(f'<circle cx="400" cy="{290 + i * 56}" r="6.4" fill="{GOLD_LIGHT}" stroke="{GOLD}" stroke-width="1.5"/>'
                      for i in range(7))
    churidar = (f'<path d="M352 {hem - 24} L390 {hem - 24} L384 906 L358 906 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>'
                f'<path d="M410 {hem - 24} L448 {hem - 24} L442 906 L416 906 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>'
                + "".join(f'<path d="M358 {906 - i * 18} q13 8 26 0" fill="none" stroke="{p[2]}" stroke-width="2" opacity="0.6"/>'
                          for i in range(5))
                + "".join(f'<path d="M416 {906 - i * 18} q13 8 26 0" fill="none" stroke="{p[2]}" stroke-width="2" opacity="0.6"/>'
                          for i in range(5)))
    collar = (f'<path d="M366 214 L400 246 L434 214 L434 190 L366 190 Z" fill="{p[2]}" opacity="0.9"/>'
              f'<path d="M366 190 L434 190" stroke="url(#gold{vid})" stroke-width="5"/>')
    emb = _sequins(sd, [330, 430, 530], x0=380, x1=420, n=16)
    body = (
        _sleeves(p, vid, y=220, length=250, width=58, flare=10)
        + f'<path d="{coat}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="M400 246 L400 {hem}" stroke="{p[2]}" stroke-width="3" opacity="0.7"/>'
        + f'<rect x="{panel.split()[0]}" y="300" width="52" height="{hem - 340}" fill="url(#{pid})" opacity="0.6" stroke="{GOLD}" stroke-width="2.5"/>'
        + collar + buttons
        + f'<path d="M292 {hem} L508 {hem}" stroke="url(#gold{vid})" stroke-width="9"/>'
        + emb + churidar
    )
    return body, kids


def _g_kurta_set(p, vid, pid, sd, kids=False):
    hem = 820 if not kids else 740
    kurta = f'M318 210 L482 210 L500 {hem} L300 {hem} Z'
    pants = (f'<path d="M332 {hem - 12} L392 {hem - 12} L388 916 L344 916 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>'
             f'<path d="M408 {hem - 12} L468 {hem - 12} L456 916 L412 916 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>')
    neckline = (f'<path d="M368 210 L400 268 L432 210 L432 196 L368 196 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>'
                f'<path d="M400 268 L400 360" stroke="{GOLD}" stroke-width="4"/>')
    body = (
        _sleeves(p, vid, y=216, length=220, width=54)
        + f'<path d="{kurta}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{kurta}" fill="url(#{pid})" opacity="0.5"/>'
        + _fold_lines(330, 470, 320, hem - 30, 4)
        + neckline
        + f'<path d="M300 {hem} L500 {hem}" stroke="url(#gold{vid})" stroke-width="8"/>'
        + _sequins(sd, [300, 420], x0=372, x1=428, n=10)
        + pants
    )
    return body, kids


def _g_anarkali(p, vid, pid, sd, kids=False):
    flare = ('M330 330 L470 330 Q600 640 580 894 Q400 934 220 894 Q200 640 330 330 Z')
    rows = "".join(
        f'<path d="M{250 - i * 12} {480 + i * 90} Q400 {530 + i * 90} {550 + i * 12} {480 + i * 90}" '
        f'fill="none" stroke="url(#gold{vid})" stroke-width="6" opacity="0.9"/>'
        for i in range(4))
    body = (
        _sleeves(p, vid, y=214, length=170)
        + _bodice(p, vid, pid, y0=206, y1=330, neck="round")
        + f'<path d="{flare}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{flare}" fill="url(#{pid})" opacity="0.6"/>'
        + _fold_lines(250, 550, 380, 880, 7)
        + rows
        + f'<path d="M220 894 Q400 934 580 894" fill="none" stroke="url(#gold{vid})" stroke-width="12"/>'
        + _sequins(sd, [420, 560, 720, 850], x0=300, x1=500, n=24)
    )
    return body, kids


def _g_salwar(p, vid, pid, sd, kids=False):
    kurti = 'M322 208 L478 208 L494 560 L306 560 Z'
    bottoms = ('<path d="M324 556 L394 556 Q388 720 360 900 L330 900 Q322 720 324 556 Z" fill="' + p[1] + '" stroke="' + p[2] + '" stroke-width="2.5"/>'
               '<path d="M406 556 L476 556 Q478 720 470 900 L440 900 Q412 720 406 556 Z" fill="' + p[1] + '" stroke="' + p[2] + '" stroke-width="2.5"/>')
    dup = ('M460 216 Q560 500 520 820 L472 820 Q508 520 428 260 Z')
    body = (
        _sleeves(p, vid, y=214, length=180)
        + f'<path d="{kurti}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + _bodice(p, vid, pid, y0=200, y1=250, neck="round")
        + f'<path d="{kurti}" fill="url(#{pid})" opacity="0.45"/>'
        + _fold_lines(330, 470, 300, 540, 4)
        + f'<path d="M306 560 L494 560" stroke="url(#gold{vid})" stroke-width="7"/>'
        + bottoms
        + f'<path d="{dup}" fill="{p[0]}" opacity="0.65" stroke="{p[2]}" stroke-width="2.5"/>'
        + _gold_border_path(dup, vid, 5)
        + _sequins(sd, [320, 450], x0=340, x1=460, n=14)
    )
    return body, kids


def _g_frock(p, vid, pid, sd, kids=True):
    bodice = 'M330 250 L470 250 L482 420 L318 420 Z'
    skirt = 'M318 420 L482 420 Q566 620 546 764 Q400 806 254 764 Q234 620 318 420 Z'
    ruffles = "".join(
        f'<path d="M{262 + i * 24} {752 - (i % 3) * 6} q12 26 24 0" fill="{p[1]}" opacity="0.8" stroke="{p[2]}" stroke-width="2"/>'
        for i in range(12))
    bow = (f'<path d="M400 262 l-34 -18 l6 26 l-6 26 l34 -18 Z" fill="{GOLD}" opacity="0.95"/>'
           f'<path d="M400 262 l34 -18 l-6 26 l6 26 l-34 -18 Z" fill="{GOLD}" opacity="0.95"/>'
           f'<circle cx="400" cy="268" r="9" fill="{GOLD_LIGHT}" stroke="{GOLD}" stroke-width="2"/>')
    puffed = ('<path d="M300 262 q-34 8 -40 44 q22 16 44 6 Z" fill="url(#cloth{0})" stroke="{1}" stroke-width="2.5"/>'.format(vid, p[2])
              + '<path d="M500 262 q34 8 40 44 q-22 16 -44 6 Z" fill="url(#cloth{0})" stroke="{1}" stroke-width="2.5"/>'.format(vid, p[2]))
    body = (
        f'<path d="{bodice}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + f'<path d="M330 250 Q400 282 470 250 L470 238 L330 238 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>'
        + puffed + bow
        + f'<path d="{skirt}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{skirt}" fill="url(#{pid})" opacity="0.6"/>'
        + _fold_lines(290, 510, 450, 740, 6)
        + f'<path d="M318 420 L482 420" stroke="url(#gold{vid})" stroke-width="7"/>'
        + ruffles
        + _sequins(sd, [500, 600, 700], x0=320, x1=480, n=20)
    )
    return body, kids


def _g_gown(p, vid, pid, sd, kids=False):
    top = 'M340 200 Q400 232 460 200 L472 340 L328 340 Z'
    skirt = 'M328 340 L472 340 Q580 660 552 902 Q400 942 248 902 Q220 660 328 340 Z'
    slit = f'<path d="M430 420 L470 892" stroke="{p[2]}" stroke-width="4" opacity="0.55"/>'
    lining = f'<path d="M428 430 L464 890" stroke="{p[1]}" stroke-width="14" opacity="{LINING_OPACITY}"/>'
    body = (
        f'<path d="{top}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + f'<path d="M340 200 Q400 176 460 200" fill="none" stroke="url(#gold{vid})" stroke-width="6"/>'
        + f'<path d="{skirt}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{skirt}" fill="url(#{pid})" opacity="0.5"/>'
        + _fold_lines(290, 510, 400, 890, 7)
        + lining + slit
        + f'<path d="M248 902 Q400 942 552 902" fill="none" stroke="url(#gold{vid})" stroke-width="11"/>'
        + _sequins(sd, [380, 500, 640, 780], x0=300, x1=500, n=26)
    )
    return body, kids


def _g_blazer(p, vid, pid, sd, kids=False, tux=False):
    hem = 690
    jacket = f'M312 208 L488 208 L506 {hem} L294 {hem} Z'
    lapel_l = f'M362 208 L400 300 L356 330 L336 236 Z'
    lapel_r = f'M438 208 L400 300 L444 330 L464 236 Z'
    shirt = f'M400 300 L382 {hem} L418 {hem} Z'
    tie_fill = "#E85D9B" if not tux else "#111827"
    tie = (f'<path d="M400 306 l14 14 l-8 96 l4 96 l-10 18 l-10 -18 l4 -96 l-8 -96 Z" fill="{tie_fill}"/>'
           if not tux else
           '<path d="M392 312 l8 10 l8 -10 -8 24 Z" fill="#111827"/><rect x="386" y="352" width="28" height="8" rx="3" fill="#111827"/>')
    pocket = f'<rect x="438" y="480" width="46" height="10" rx="4" fill="{p[2]}"/>'
    buttons = ('<circle cx="400" cy="500" r="6" fill="#F5F5F5"/>'
               + (f'<circle cx="400" cy="560" r="6" fill="#F5F5F5"/>' if not tux else ''))
    trousers = (f'<path d="M320 {hem} L396 {hem} L392 918 L338 918 Z" fill="{p[2]}" stroke="#00000033"/>'
                f'<path d="M404 {hem} L480 {hem} L464 918 L410 918 Z" fill="{p[2]}" stroke="#00000033"/>')
    body = (
        _sleeves(p, vid, y=216, length=260, width=58, flare=8)
        + f'<path d="{jacket}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{shirt}" fill="#F8F8F4"/>'
        + f'<path d="{lapel_l}" fill="{p[2]}" opacity="0.92"/><path d="{lapel_r}" fill="{p[2]}" opacity="0.92"/>'
        + tie + pocket + buttons
        + (f'<path d="M294 {hem} L506 {hem}" stroke="url(#gold{vid})" stroke-width="6"/>' if tux else '')
        + trousers
        + _sequins(sd, [], n=0)
    )
    return body, kids


def _g_tuxedo(p, vid, pid, sd, kids=False):
    return _g_blazer(p, vid, pid, sd, kids=kids, tux=True)


def _g_shirt(p, vid, pid, sd, kids=False):
    hem = 560
    body_ = f'M316 210 L484 210 L498 {hem} L302 {hem} Z'
    yoke = 'M316 210 L484 210 L478 268 L322 268 Z'
    placket = f'<rect x="388" y="232" width="24" height="{hem - 250}" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>'
    coll = (f'<path d="M368 210 L400 246 L388 210 Z" fill="{p[2]}"/><path d="M432 210 L400 246 L412 210 Z" fill="{p[2]}"/>'
            f'<path d="M368 210 Q400 196 432 210" fill="none" stroke="{p[2]}" stroke-width="4"/>')
    buttons = "".join(f'<circle cx="400" cy="{300 + i * 58}" r="5" fill="#FAFAFA" stroke="{p[2]}"/>' for i in range(4))
    cuff = (f'<rect x="238" y="392" width="44" height="20" rx="5" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>'
            f'<rect x="518" y="392" width="44" height="20" rx="5" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>')
    pants = (f'<path d="M304 {hem} L398 {hem} L392 918 L322 918 Z" fill="#4B5563"/>'
             f'<path d="M402 {hem} L496 {hem} L478 918 L408 918 Z" fill="#4B5563"/>')
    body = (
        _sleeves(p, vid, y=218, length=210, width=56, flare=6)
        + f'<path d="{body_}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + f'<path d="{yoke}" fill="{p[1]}" opacity="0.5"/>'
        + _fold_lines(330, 470, 300, hem - 20, 4, color=p[2], op=0.25)
        + placket + coll + buttons + cuff
        + f'<path d="M302 {hem} L498 {hem}" stroke="{p[2]}" stroke-width="4" fill="none"/>'
        + pants
    )
    return body, kids


def _g_pants(p, vid, pid, sd, kids=False, jeans=False):
    waist = 330
    leg = (f'<path d="M312 {waist} L398 {waist} L390 918 L326 918 Z" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
           f'<path d="M402 {waist} L488 {waist} L474 918 L410 918 Z" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>')
    stitch = (f'<path d="M352 {waist + 40} L352 900" stroke="{GOLD}" stroke-width="3" stroke-dasharray="10 7" opacity="0.85"/>'
              f'<path d="M448 {waist + 40} L448 900" stroke="{GOLD}" stroke-width="3" stroke-dasharray="10 7" opacity="0.85"/>')
    pockets = (f'<path d="M320 {waist + 14} q26 26 52 8" fill="none" stroke="{p[2]}" stroke-width="3"/>'
               f'<path d="M480 {waist + 14} q-26 26 -52 8" fill="none" stroke="{p[2]}" stroke-width="3"/>')
    belt = (f'<rect x="312" y="{waist - 26}" width="176" height="26" rx="6" fill="{p[2]}"/>'
            f'<rect x="388" y="{waist - 24}" width="26" height="22" rx="4" fill="{GOLD}"/>')
    hemline = (f'<path d="M326 900 L390 900 M410 900 L474 900" stroke="{p[2]}" stroke-width="5"/>'
               if jeans else '')
    top = f'<path d="M330 240 L470 240 L470 {waist} L330 {waist} Z" fill="{p[1]}" opacity="0.35"/>' if jeans else ''
    body = belt + leg + top + pockets + (stitch if jeans else '') + hemline
    return body, kids


def _g_jeans(p, vid, pid, sd, kids=False):
    return _g_pants(p, vid, pid, sd, kids=kids, jeans=True)


def _g_skirt(p, vid, pid, sd, kids=False):
    skirt = 'M320 420 L480 420 Q524 700 508 826 Q400 862 292 826 Q276 700 320 420 Z'
    top = f'<path d="M318 380 L482 380 L480 424 L320 424 Z" fill="{p[2]}"/>'
    body = (
        f'<path d="{skirt}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{skirt}" fill="url(#{pid})" opacity="0.55"/>'
        + _fold_lines(330, 470, 450, 810, 5)
        + f'<path d="M292 826 Q400 862 508 826" fill="none" stroke="url(#gold{vid})" stroke-width="9"/>'
        + top + _sequins(sd, [500, 620, 740], x0=330, x1=470, n=18)
    )
    return body, kids


def _g_dhoti(p, vid, pid, sd, kids=False):
    drape = 'M330 300 Q400 250 470 300 L500 500 Q470 700 488 890 Q400 922 312 890 Q330 700 300 500 Z'
    fold = '<path d="M400 320 Q382 560 400 890" fill="none" stroke="{0}" stroke-width="5" opacity="0.6"/>'
    border = (f'<path d="M312 890 Q400 922 488 890" fill="none" stroke="url(#gold{vid})" stroke-width="10"/>')
    waist = f'<rect x="318" y="286" width="164" height="24" rx="10" fill="{p[2]}"/>'
    body = (
        f'<path d="{drape}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + fold.format(p[2])
        + '<path d="M352 350 q-24 200 -12 520 M448 350 q24 200 12 520" fill="none" stroke="{0}" stroke-width="3" opacity="0.45"/>'.format(p[2])
        + border + waist + _sequins(sd, [430, 560], x0=350, x1=450, n=10)
    )
    return body, kids


def _g_kurti(p, vid, pid, sd, kids=False):
    hem = 640 if not kids else 560
    tunic = f'M322 208 L478 208 L496 {hem} L304 {hem} Z'
    neck = f'<path d="M372 208 L400 262 L428 208 L428 194 L372 194 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2.5"/>'
    leg = (f'<path d="M330 {hem - 6} L394 {hem - 6} L388 916 L342 916 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>'
           f'<path d="M406 {hem - 6} L470 {hem - 6} L458 916 L412 916 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>')
    body = (
        _sleeves(p, vid, y=214, length=190)
        + f'<path d="{tunic}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + f'<path d="{tunic}" fill="url(#{pid})" opacity="0.5"/>'
        + neck + _fold_lines(336, 464, 300, hem - 24, 4)
        + f'<path d="M304 {hem} L496 {hem}" stroke="url(#gold{vid})" stroke-width="7"/>'
        + _sequins(sd, [300, 380], x0=372, x1=428, n=8) + leg
    )
    return body, kids


def _g_coord(p, vid, pid, sd, kids=False):
    crop = 'M326 210 L474 210 L486 430 L314 430 Z'
    wide = 'M314 470 L486 470 L520 900 Q400 934 280 900 Z'
    gap = f'<rect x="314" y="430" width="172" height="40" fill="#FFFFFF" opacity="0"/>'
    belt = f'<rect x="316" y="462" width="168" height="20" rx="8" fill="{p[2]}"/>'
    body = (
        _sleeves(p, vid, y=216, length=150)
        + f'<path d="{crop}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3"/>'
        + f'<path d="M356 210 Q400 238 444 210 L444 198 L356 198 Z" fill="{p[1]}" stroke="{p[2]}" stroke-width="2"/>'
        + gap + belt
        + f'<path d="{wide}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{wide}" fill="url(#{pid})" opacity="0.5"/>'
        + _fold_lines(330, 470, 520, 880, 5)
        + f'<path d="M280 900 Q400 934 520 900" fill="none" stroke="url(#gold{vid})" stroke-width="9"/>'
        + _sequins(sd, [300, 560, 700], x0=330, x1=470, n=16)
    )
    return body, kids


def _g_jumpsuit(p, vid, pid, sd, kids=False):
    suit = ('M322 208 L478 208 L492 470 L486 900 Q440 916 412 900 L400 620 '
            'L388 900 Q360 916 314 900 L308 470 Z')
    belt = f'<rect x="312" y="440" width="176" height="22" rx="8" fill="{p[2]}"/>'
    body = (
        _sleeves(p, vid, y=214, length=200)
        + f'<path d="{suit}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{suit}" fill="url(#{pid})" opacity="0.45"/>'
        + f'<path d="M356 208 Q400 240 444 208" fill="none" stroke="{p[2]}" stroke-width="4"/>'
        + belt + _fold_lines(340, 460, 500, 880, 5)
        + _sequins(sd, [320, 560], x0=350, x1=450, n=12)
    )
    return body, kids


def _g_pavadai(p, vid, pid, sd, kids=True):
    leh = _g_lehenga(p, vid, pid, sd, kids=True)[0]
    bow = f'<path d="M400 462 l-24 -14 l4 20 l-4 20 l24 -14 Z M400 462 l24 -14 l-4 20 l4 20 l-24 -14 Z" fill="{GOLD}"/>'
    return leh + bow, True


def _g_stole(p, vid, pid, sd, kids=False):
    drape = 'M300 260 Q560 320 500 560 Q470 640 520 700 L300 660 Q240 420 300 260 Z'
    body = (
        f'<path d="{drape}" fill="url(#cloth{vid})" stroke="{p[2]}" stroke-width="3.5"/>'
        + f'<path d="{drape}" fill="url(#{pid})" opacity="0.55"/>'
        + _gold_border_path(drape, vid, 8)
        + _sequins(sd, [420, 560], x0=320, x1=480, n=18)
    )
    return body, kids


_BUILDERS = {
    "lehenga": _g_lehenga, "saree": _g_saree, "sherwani": _g_sherwani,
    "kurta": _g_kurta_set, "kurta_set": _g_kurta_set, "kurset": _g_kurta_set,
    "anarkali": _g_anarkali, "salwar": _g_salwar, "palazzo": _g_salwar,
    "sharara": _g_salwar, "frock": _g_frock, "gown": _g_gown,
    "cocktail": _g_gown, "blazer": _g_blazer, "suit": _g_blazer,
    "tuxedo": _g_tuxedo, "shirt": _g_shirt, "top": _g_shirt,
    "kurti": _g_kurti, "pants": _g_pants, "jeans": _g_jeans,
    "skirt": _g_skirt, "dhoti": _g_dhoti, "coord": _g_coord,
    "jumpsuit": _g_jumpsuit, "pavadai": _g_pavadai, "nehru": _g_blazer,
    "stole": _g_stole, "angavastram": _g_stole, "other": _g_kurta_set,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def make_clothes_art(clothing_type, color, style, gender, age_group, slug="") -> str:
    """Return a complete 800x1000 SVG string for one garment."""
    p = triple_for(color)
    builder_name, kids = classify(clothing_type, style, gender, age_group)
    builder = _BUILDERS.get(builder_name, _g_kurta_set)
    sd = _seed(slug)
    pk = PATTERN_KINDS[sd % len(PATTERN_KINDS)]
    vid = f"{sd % 997:03d}"
    pid = f"pat{vid}"
    label = esc(clothing_type or "garment")
    body, _kids_out = builder(p, vid, pid, sd, kids=kids)
    sheen = f'<rect x="230" y="140" width="340" height="780" fill="url(#sheen{vid})" opacity="0.5"/>'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{label} {esc(color or "")}">'
        + _defs(p, pk, pid, vid)
        + _scene_bg(p, vid)
        + _floor_shadow(vid)
        + _rail() + _hanger()
        + body
        + sheen
        + '</svg>'
    )
    return svg
