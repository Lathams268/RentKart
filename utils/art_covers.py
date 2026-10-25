"""Generated book covers (ART stage 3) - one SVG per book, on demand.

make_cover_svg(title, author, genre, language, slug) builds a 600x900 front
cover: spine shadow, page-edge highlights, drop shadow, a genre palette and
motif, a word-wrapped auto-sized title (Telugu / Hindi / Kannada included via
the Noto font stack), the author at the bottom and a small genre ribbon.
All text is escaped; the SVG is served by routes/art.py (never a file per
book) and cached with ETag + max-age.
"""
from __future__ import annotations

import hashlib
import re
from xml.sax.saxutils import escape as _x

W, H = 600, 900
FONT = ("Noto Sans, Noto Sans Devanagari, Noto Sans Telugu, "
        "Noto Sans Kannada, Arial, sans-serif")

# genre keyword -> (deep, mid, accent, ribbon label short)
GENRES = {
    "comedy":      ("#F4A300", "#FFD84D", "#E5484D", "Comedy"),
    "inspirational": ("#B23A8C", "#F2A65A", "#FFE29A", "Inspirational"),
    "spiritual":   ("#7A3E9E", "#C77FD4", "#F6D76F", "Spiritual"),
    "selfhelp":    ("#0F6B5C", "#2FA47B", "#F2B705", "Self-Help"),
    "fiction":     ("#22304A", "#4A6FA5", "#D7E3F4", "Fiction"),
    "biography":   ("#5C4632", "#A98467", "#EBD9C3", "Biography"),
    "mythology":   ("#9A3412", "#E8843C", "#FBD38D", "Mythology"),
    "children":    ("#0EA5E9", "#7DD3FC", "#FDE047", "Children"),
    "education":   ("#1E3A8A", "#3B82F6", "#FCD34D", "Study"),
    "business":    ("#1F2937", "#0E7490", "#34D399", "Business"),
    "health":      ("#15803D", "#4ADE80", "#FCA5A5", "Health"),
    "poetry":      ("#831843", "#D946EF", "#FBCFE8", "Poetry"),
    "other":       ("#374151", "#6B7280", "#E5E7EB", "Book"),
}


def esc(t) -> str:
    # quotes escaped too: titles go into attributes such as aria-label
    return _x(str(t or ""), {'"': "&quot;", "'": "&apos;"})


def _vid(slug) -> str:
    return f"{int(hashlib.md5(str(slug or 'book').encode()).hexdigest()[:6], 16) % 997:03d}"


def genre_key(genre: str) -> str:
    g = str(genre or "").lower()
    if "comedy" in g or "humor" in g:
        return "comedy"
    if "inspir" in g or "motiva" in g:
        return "inspirational"
    if "spiritual" in g or "devotional" in g or "god" in g or "religio" in g:
        return "spiritual"
    if "self" in g:
        return "selfhelp"
    if "fiction" in g or "novel" in g:
        return "fiction"
    if "biograph" in g or "autobiograph" in g:
        return "biography"
    if "myth" in g:
        return "mythology"
    if "children" in g or "kid" in g:
        return "children"
    if "education" in g or "exam" in g:
        return "education"
    if "business" in g or "finance" in g or "money" in g:
        return "business"
    if "health" in g or "fitness" in g or "yoga" in g:
        return "health"
    if "poetr" in g or "poem" in g or "ghazal" in g:
        return "poetry"
    return "other"


def _wrap(words, max_units):
    """Greedy word wrap; width estimated in 'units' (approx chars at 1em)."""
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if _units(cand) <= max_units or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _units(s):
    """Width estimate: Latin chars ~1, Indic combining-heavy scripts ~1.25."""
    n = 0.0
    for ch in s:
        o = ord(ch)
        n += 1.25 if o > 0x0900 else (0.4 if ch in "iIl.,' ':;|" else 1.0)
    return n


def fit_title(title, box_w=470.0, max_lines=4):
    """Pick (size, lines) so the title fits the box in at most max_lines."""
    words = [w for w in str(title or "Untitled").split() if w] or ["Untitled"]
    for size in (58, 50, 44, 38, 33, 29, 25):
        max_units = box_w / (size * 0.52)
        lines = _wrap(words, max_units)
        if len(lines) <= max_lines:
            return size, lines
    # still too long: hard-truncate the wrap into max_lines by units
    max_units = box_w / (25 * 0.52)
    lines = _wrap(words, max_units)[: max_lines - 1]
    rest = " ".join(_wrap(words, max_units)[max_lines - 1:])
    lines.append(rest[:int(max_units) - 1] + "…")
    return 25, lines


# ---------------------------------------------------------------------------
# Genre motifs (drawn inside a 600x900 cover, centred near y=330)
# ---------------------------------------------------------------------------
def _m_comedy(vid, pal):
    return (
        f'<circle cx="300" cy="320" r="88" fill="{pal[2]}" stroke="#FFFFFF" stroke-width="5"/>'
        f'<circle cx="268" cy="300" r="9" fill="#3B2405"/><circle cx="332" cy="300" r="9" fill="#3B2405"/>'
        f'<path d="M258 340 q42 40 84 0" fill="none" stroke="#3B2405" stroke-width="9" stroke-linecap="round"/>'
        f'<g><path d="M410 210 h120 a10 10 0 0 1 10 10 v54 a10 10 0 0 1 -10 10 h-70 l-18 24 v-24 h-32 a10 10 0 0 1 -10 -10 v-54 a10 10 0 0 1 10 -10 z" fill="#FFFFFF" opacity="0.9"/>'
        f'<text x="472" y="256" text-anchor="middle" font-family="{FONT}" font-size="26" fill="{pal[0]}">:)</text></g>'
        f'<path d="M120 240 h96 a10 10 0 0 1 10 10 v40 a10 10 0 0 1 -10 10 h-96 a10 10 0 0 1 -10 -10 v-40 a10 10 0 0 1 10 -10 z" fill="#FFFFFF" opacity="0.75"/>'
    )


def _m_inspirational(vid, pal):
    rays = "".join(
        f'<line x1="300" y1="330" x2="{300 + 150 * __import__("math").cos(-0.2 - i * 0.35):.0f}" '
        f'y2="{330 + 150 * __import__("math").sin(-0.2 - i * 0.35):.0f}" stroke="{pal[2]}" stroke-width="7" opacity="0.7"/>'
        for i in range(8))
    return (
        f'<circle cx="300" cy="330" r="74" fill="{pal[2]}"/>'
        f'<circle cx="300" cy="330" r="74" fill="none" stroke="#FFFFFF" stroke-width="4" opacity="0.8"/>'
        + rays
        + f'<rect x="70" y="392" width="460" height="10" fill="{pal[0]}" opacity="0.5"/>'
        + f'<path d="M120 420 Q300 440 470 402 L520 470 Q300 500 90 452 Z" fill="{pal[1]}" opacity="0.85"/>'
        + f'<path d="M150 436 Q300 456 440 424" fill="none" stroke="#FFFFFF" stroke-width="4" opacity="0.6" stroke-dasharray="14 10"/>'
    )


def _m_spiritual(vid, pal):
    petals = "".join(
        f'<ellipse cx="{300 + 46 * __import__("math").cos(i * 0.698 - 1.57):.0f}" '
        f'cy="{316 + 46 * __import__("math").sin(i * 0.698 - 1.57) * 0.8:.0f}" '
        f'rx="22" ry="34" fill="{pal[2]}" opacity="0.9" '
        f'transform="rotate({i * 36 - 90} {300 + 46 * __import__("math").cos(i * 0.698 - 1.57):.0f} {316 + 46 * __import__("math").sin(i * 0.698 - 1.57) * 0.8:.0f})"/>'
        for i in range(10))
    diya = (
        f'<path d="M255 430 q45 26 90 0 l-10 26 q-35 14 -70 0 z" fill="{pal[1]}" stroke="{pal[0]}" stroke-width="3"/>'
        f'<path d="M300 418 q8 -22 0 -38 q-9 16 0 38" fill="#F2B705"/>'
    )
    rays = "".join(
        f'<line x1="300" y1="300" x2="{300 + 120 * __import__("math").cos(-1.57 + i * 0.7):.0f}" '
        f'y2="{300 + 120 * __import__("math").sin(-1.57 + i * 0.7):.0f}" stroke="#FFFFFF" stroke-width="3" opacity="0.5"/>'
        for i in range(9))
    return rays + petals + f'<circle cx="300" cy="318" r="20" fill="{pal[0]}"/>' + diya


def _m_selfhelp(vid, pal):
    return (
        f'<path d="M200 420 L200 300 L260 300 L236 420 Z" fill="{pal[2]}"/>'
        f'<text x="222" y="284" text-anchor="middle" font-family="{FONT}" font-size="120" font-weight="800" fill="#FFFFFF">1</text>'
        f'<path d="M320 420 Q360 300 470 250" fill="none" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" opacity="0.95"/>'
        f'<path d="M470 250 L430 254 L458 292 Z" fill="#FFFFFF"/>'
        f'<rect x="150" y="440" width="300" height="10" rx="5" fill="#FFFFFF" opacity="0.5"/>'
    )


def _m_fiction(vid, pal):
    bldg = ""
    hs = [120, 190, 90, 230, 150, 260, 110, 180]
    for i, h in enumerate(hs):
        x = 70 + i * 58
        bldg += f'<rect x="{x}" y="{470 - h}" width="46" height="{h}" fill="{pal[0]}" opacity="{0.55 + (i % 3) * 0.2}"/>'
        for wy in range(int(470 - h) + 12, 456, 26):
            bldg += f'<rect x="{x + 8}" y="{wy}" width="8" height="10" fill="{pal[2]}" opacity="0.8"/>'
            bldg += f'<rect x="{x + 26}" y="{wy}" width="8" height="10" fill="{pal[2]}" opacity="0.55"/>'
    moon = (f'<circle cx="470" cy="230" r="42" fill="{pal[2]}" opacity="0.95"/>'
            f'<circle cx="486" cy="222" r="34" fill="{pal[1]}"/>')
    return moon + f'<rect x="60" y="200" width="480" height="10" fill="none"/>' + bldg + f'<rect x="60" y="470" width="480" height="8" fill="{pal[2]}" opacity="0.4"/>'


def _m_biography(vid, pal):
    frame = (f'<rect x="180" y="180" width="240" height="300" rx="10" fill="none" stroke="{pal[2]}" stroke-width="8"/>'
             f'<rect x="192" y="192" width="216" height="276" rx="6" fill="{pal[2]}" opacity="0.25"/>')
    silhouette = (f'<circle cx="300" cy="296" r="52" fill="{pal[0]}"/>'
                  f'<path d="M222 480 q78 -120 156 0 z" fill="{pal[0]}"/>')
    return frame + silhouette + f'<path d="M180 512 h240" stroke="{pal[2]}" stroke-width="6"/>'


def _m_mythology(vid, pal):
    tiers = ""
    for i, (w_, h_) in enumerate([(280, 40), (230, 44), (180, 48), (130, 52), (80, 56)]):
        y = 470 - i * (h_ + 6) - h_
        tiers += f'<path d="M{300 - w_ / 2} {y + h_} L{300 - w_ / 2 + 14} {y} L{300 + w_ / 2 - 14} {y} L{300 + w_ / 2} {y + h_} Z" fill="{pal[1 if i % 2 else 0]}" stroke="{pal[0]}" stroke-width="3"/>'
    kalasam = (f'<rect x="286" y="130" width="28" height="30" rx="6" fill="{pal[2]}"/>'
               f'<circle cx="300" cy="122" r="12" fill="{pal[2]}"/>')
    doors = f'<rect x="270" y="410" width="60" height="60" rx="6" fill="{pal[0]}"/>'
    mand = "".join(
        f'<circle cx="{300 + 210 * __import__("math").cos(i * 0.785):.0f}" cy="{560 + 60 * __import__("math").sin(i * 0.785):.0f}" r="9" fill="{pal[2]}" opacity="0.8"/>'
        for i in range(8))
    return tiers + kalasam + doors + mand


def _m_children(vid, pal):
    import math
    stars = ""
    for (sx, sy, r) in [(140, 220, 22), (460, 200, 26), (500, 330, 16), (110, 360, 14), (300, 170, 18)]:
        pts = " ".join(f"{sx + r * math.cos(-1.57 + i * 1.2566):.0f},{sy + r * math.sin(-1.57 + i * 1.2566):.0f}" for i in range(10))
        stars += f'<polygon points="{pts}" fill="{pal[2]}" stroke="#FFFFFF" stroke-width="3"/>'
    balloon = (f'<circle cx="230" cy="360" r="40" fill="{pal[2]}"/><path d="M230 400 l-8 18 h16 z" fill="{pal[0]}"/>'
               f'<path d="M230 418 q10 40 -6 70" stroke="{pal[0]}" stroke-width="4" fill="none"/>')
    blocks = (f'<rect x="330" y="380" width="60" height="60" rx="8" fill="{pal[1]}" stroke="{pal[0]}" stroke-width="4"/>'
              f'<rect x="400" y="330" width="52" height="52" rx="8" fill="{pal[0]}" stroke="{pal[2]}" stroke-width="4"/>'
              f'<text x="360" y="422" text-anchor="middle" font-family="{FONT}" font-size="34" font-weight="800" fill="#FFFFFF">A</text>')
    arc = f'<path d="M100 480 Q300 540 500 480" stroke="{pal[2]}" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.8"/>'
    return stars + balloon + blocks + arc


def _m_education(vid, pal):
    cap = (f'<path d="M300 220 L470 280 L300 340 L130 280 Z" fill="{pal[0]}" stroke="#FFFFFF" stroke-width="4"/>'
           f'<path d="M210 300 v50 q90 44 180 0 v-50 l-90 40 z" fill="{pal[1]}" stroke="{pal[0]}" stroke-width="3"/>'
           f'<line x1="470" y1="280" x2="470" y2="360" stroke="{pal[2]}" stroke-width="5"/>'
           f'<circle cx="470" cy="366" r="8" fill="{pal[2]}"/>')
    def pencil(x, rot):
        return (f'<g transform="rotate({rot} {x} 470)">'
                f'<rect x="{x - 8}" y="400" width="16" height="110" fill="{pal[2]}" stroke="{pal[0]}" stroke-width="2"/>'
                f'<path d="M{x - 8} 400 l8 -26 l8 26 z" fill="#EBD9C3" stroke="{pal[0]}" stroke-width="2"/>'
                f'<rect x="{x - 8}" y="496" width="16" height="14" fill="#E5484D"/></g>')
    return cap + pencil(180, -18) + pencil(300, 0) + pencil(420, 18)


def _m_business(vid, pal):
    bars = ""
    hs = [60, 100, 150, 210]
    for i, h in enumerate(hs):
        x = 160 + i * 80
        bars += f'<rect x="{x}" y="{470 - h}" width="56" height="{h}" rx="6" fill="{pal[1 + (i % 2) * 0] if i < 3 else pal[2]}" stroke="{pal[0]}" stroke-width="3"/>'
    arrow = (f'<path d="M150 420 Q320 260 460 180" fill="none" stroke="#FFFFFF" stroke-width="8" opacity="0.9"/>'
             f'<path d="M460 180 L414 192 L446 226 Z" fill="#FFFFFF"/>')
    return bars + arrow + f'<rect x="130" y="470" width="360" height="8" fill="{pal[2]}" opacity="0.6"/>'


def _m_health(vid, pal):
    heart = (f'<path d="M300 300 c-14 -42 -84 -46 -92 4 c-6 40 52 76 92 110 c40 -34 98 -70 92 -110 c-8 -50 -78 -46 -92 -4 z" '
             f'fill="#E5484D" stroke="#8F1D1D" stroke-width="5"/>')
    leaf = (f'<path d="M380 420 q70 -80 120 -60 q-16 84 -104 84 z" fill="{pal[1]}" stroke="{pal[0]}" stroke-width="4"/>'
            f'<path d="M396 424 q44 -34 84 -44" fill="none" stroke="{pal[0]}" stroke-width="3" opacity="0.7"/>')
    pulse = f'<path d="M120 500 h110 l24 -40 l30 70 l22 -30 h170" fill="none" stroke="{pal[2]}" stroke-width="7" stroke-linecap="round"/>'
    return heart + leaf + pulse


def _m_poetry(vid, pal):
    feather = (f'<g transform="rotate(24 380 320)">'
               f'<path d="M380 180 q64 90 20 240 l-18 -6 q34 -138 -22 -222 z" fill="{pal[2]}" stroke="{pal[0]}" stroke-width="4"/>'
               f'<path d="M382 196 q40 96 8 214" fill="none" stroke="{pal[0]}" stroke-width="3"/>'
               f'<path d="M390 560 l2 -80" stroke="{pal[0]}" stroke-width="6"/></g>')
    flowers = ""
    for (fx, fy, fr) in [(150, 420, 26), (210, 470, 18), (120, 480, 14)]:
        flowers += f'<circle cx="{fx}" cy="{fy}" r="{fr}" fill="{pal[1]}" stroke="#FFFFFF" stroke-width="3"/>'
        flowers += f'<circle cx="{fx}" cy="{fy}" r="{fr * 0.4:.0f}" fill="{pal[2]}"/>'
        flowers += f'<path d="M{fx} {fy + fr} q-6 40 4 70" stroke="#2E9E4B" stroke-width="5" fill="none"/>'
    lines = "".join(f'<rect x="110" y="{220 + i * 34}" width="{160 - i * 22}" height="6" rx="3" fill="#FFFFFF" opacity="0.55"/>' for i in range(5))
    return lines + flowers + feather


def _m_other(vid, pal):
    shapes = (f'<circle cx="200" cy="290" r="70" fill="{pal[2]}" opacity="0.85"/>'
              f'<rect x="300" y="230" width="140" height="140" rx="18" fill="{pal[1]}" stroke="{pal[0]}" stroke-width="5" transform="rotate(12 370 300)"/>'
              f'<path d="M300 470 l70 -110 l70 110 z" fill="{pal[0]}" opacity="0.85"/>')
    rings = "".join(f'<circle cx="300" cy="330" r="{160 + i * 26}" fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.25"/>' for i in range(3))
    return rings + shapes


_MOTIFS = {
    "comedy": _m_comedy, "inspirational": _m_inspirational, "spiritual": _m_spiritual,
    "selfhelp": _m_selfhelp, "fiction": _m_fiction, "biography": _m_biography,
    "mythology": _m_mythology, "children": _m_children, "education": _m_education,
    "business": _m_business, "health": _m_health, "poetry": _m_poetry, "other": _m_other,
}


def _title_band_style(gk):
    """Some genres read better on a light band behind the title."""
    return gk in ("children", "business", "education", "health", "fiction", "mythology")


def make_cover_svg(title="", author="", genre="", language="", slug="") -> str:
    """Return the 600x900 SVG book cover for one book item."""
    gk = genre_key(genre)
    pal = GENRES[gk]
    vid = _vid(slug or title)
    size, lines = fit_title(title)
    band = _title_band_style(gk)
    # title block lives between y 556 and 772, vertically centred there
    step = int(size * 1.22)
    y0, y1 = 556, 772
    start_y = y0 + ((y1 - y0) - step * len(lines)) / 2 + size * 0.72
    author_s = 30 if len(str(author or "")) <= 24 else 24
    ribbon_lbl = esc(pal[3])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">'
        f'<defs>'
        f'<linearGradient id="cv{vid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{pal[1]}"/>'
        f'<stop offset="55%" stop-color="{pal[0]}"/>'
        f'<stop offset="100%" stop-color="{pal[0]}"/></linearGradient>'
        f'<linearGradient id="sp{vid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="#000000" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="#000000" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="pg{vid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.9"/>'
        f'<stop offset="100%" stop-color="#C9CFD6" stop-opacity="0.9"/></linearGradient>'
        f'<linearGradient id="sh{vid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#000000" stop-opacity="0.30"/>'
        f'<stop offset="100%" stop-color="#000000" stop-opacity="0"/></linearGradient>'
        f'</defs>'
        # drop shadow + page edge + cover slab
        f'<rect x="34" y="30" width="546" height="850" fill="url(#sh{vid})"/>'
        f'<rect x="556" y="34" width="16" height="836" rx="3" fill="url(#pg{vid})"/>'
        f'<path d="M556 40 l16 -6 M556 120 l16 -6 M556 760 l16 6" stroke="#FFFFFF" stroke-width="2" opacity="0.7"/>'
        f'<rect x="26" y="26" width="534" height="848" rx="8" fill="url(#cv{vid})" stroke="#00000030" stroke-width="2"/>'
        f'<rect x="26" y="26" width="30" height="848" fill="url(#sp{vid})"/>'
        f'<rect x="66" y="40" width="6" height="820" fill="#FFFFFF" opacity="0.14"/>'
        # subtle texture stripes driven by the slug hash
        + "".join(f'<rect x="86" y="{60 + (i * 97 + int(vid) * 7) % 780}" width="450" height="3" fill="#FFFFFF" opacity="0.05"/>' for i in range(5))
        # motif
        + _MOTIFS[gk](vid, pal)
        # genre ribbon (top-right corner flag)
        + f'<g transform="rotate(-6 470 86)">'
          f'<path d="M382 66 h150 l22 22 l-22 22 h-150 z" fill="{pal[2]}" stroke="#FFFFFF" stroke-width="3"/>'
          f'<text x="455" y="98" text-anchor="middle" font-family="{FONT}" font-size="21" font-weight="700" '
          f'fill="{pal[0]}">{ribbon_lbl}</text></g>'
        # optional light band behind the title
        + (f'<rect x="56" y="{y0 - 10}" width="488" height="{y1 - y0 + 6}" rx="12" fill="#FFFFFF" opacity="0.82"/>' if band else "")
        # title lines
        + _title_text(lines, size, band, pal, start_y, step)
        # rule + author
        + f'<rect x="180" y="{782}" width="240" height="4" rx="2" fill="{pal[2]}" opacity="0.9"/>'
        + f'<text x="300" y="826" text-anchor="middle" font-family="{FONT}" font-size="{author_s}" '
          f'font-weight="600" letter-spacing="1" fill="#FFFFFF" opacity="0.95">{esc(str(author or "").strip() or "Anonymous")}</text>'
        + f'<text x="300" y="856" text-anchor="middle" font-family="{FONT}" font-size="15" '
          f'fill="#FFFFFF" opacity="0.6">{esc(language or "")}</text>'
        + '</svg>')
    return svg


def _title_text(lines, size, band, pal, start_y, step):
    fill = "#22262E" if band else "#FFFFFF"
    shadow = "" if band else f'stroke="{pal[0]}" stroke-width="1" '
    out = []
    for i, ln in enumerate(lines):
        y = int(start_y + i * step)
        out.append(f'<text x="300" y="{y}" text-anchor="middle" font-family="{FONT}" '
                   f'font-size="{size}" font-weight="800" fill="{fill}" {shadow}>{esc(ln)}</text>')
    return "".join(out)
