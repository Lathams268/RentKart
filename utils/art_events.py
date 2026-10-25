"""Events & decoration art (ART stage 2) - original generated SVG.

make_event_art(item_type, subcat_key, style, ...) returns an 800x1000 SVG with
the same studio quality as the farm tools: gradient background, floor shadow,
layered shapes, shading and a label ribbon. The "style" attribute drives the
palette: Traditional = gold + deep red, Modern = white + pastel, Mixed/empty
= a balanced festival palette.
"""
from __future__ import annotations

from utils.art_tools import (W, H, P, C, R, esc, _norm, _vid,
                             STEEL, WOOD)


def R_(x, y, w_, h_, rx, fill, stroke=None, w=3, op=None):
    s = R(x, y, w_, h_, rx, fill, stroke, w)
    if op is not None:
        s = s.replace('/>', f' opacity="{op}"/>')
    return s

# style -> (main, accent, light, dark, backdrop tint)
STYLES = {
    "traditional": ("#B8860B", "#C81E33", "#F6E7B0", "#7A4A10", "#FBF3DF"),
    "modern":      ("#E8ECF2", "#7FA6C9", "#F4E8F0", "#5C6B7A", "#EEF3F8"),
    "mixed":       ("#D9822B", "#8E44AD", "#FDEBC8", "#7A3B10", "#FDF4E3"),
}


def _pal(style):
    key = str(style or "").strip().lower()
    for k in STYLES:
        if key.startswith(k[:5]):
            return STYLES[k]
    return STYLES["mixed"]


def scene_bg(vid, pal):
    tint = pal[4]
    return (f'<defs>'
            f'<linearGradient id="bg{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{tint}"/>'
            f'<stop offset="70%" stop-color="#FFFFFF"/>'
            f'<stop offset="100%" stop-color="{pal[2]}" stop-opacity="0.7"/></linearGradient>'
            f'<radialGradient id="fl{vid}" cx="0.5" cy="0.5" r="0.5">'
            f'<stop offset="0%" stop-color="#000000" stop-opacity="0.25"/>'
            f'<stop offset="100%" stop-color="#000000" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="gd{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{pal[2]}"/>'
            f'<stop offset="45%" stop-color="{pal[0]}"/>'
            f'<stop offset="100%" stop-color="{pal[3]}"/></linearGradient>'
            f'<linearGradient id="cl{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{pal[1]}"/>'
            f'<stop offset="100%" stop-color="{pal[3]}" stop-opacity="0.8"/></linearGradient>'
            f'</defs>'
            f'<rect width="{W}" height="{H}" fill="url(#bg{vid})"/>')


def floor(vid):
    return f'<ellipse cx="400" cy="874" rx="300" ry="36" fill="url(#fl{vid})"/>'


def label_ribbon(name, vid):
    t = esc(name if len(str(name or "")) <= 26 else str(name)[:25] + "…")
    return (f'<g><path d="M250 928 L550 928 L566 952 L550 976 L250 976 L234 952 Z" '
            f'fill="url(#gd{vid})" stroke="#7A4A10" stroke-width="2.5"/>'
            f'<rect x="258" y="934" width="284" height="8" rx="4" fill="#FFFFFF" opacity="0.5"/>'
            f'<text x="400" y="961" text-anchor="middle" font-family="Noto Sans, Noto Sans Devanagari, '
            f'Noto Sans Telugu, Noto Sans Kannada, Arial, sans-serif" font-size="24" '
            f'font-weight="700" fill="#3B2405">{t}</text></g>')


def _garland(x0, x1, y, vid, n=9, sag=26):
    """Draped fabric/garland curve between two x positions."""
    step = (x1 - x0) / n
    parts = [f'<path d="M{x0} {y} ' +
             " ".join(f"Q{x0 + step * (i + 0.5)} {y + sag} {x0 + step * (i + 1)} {y}"
                      for i in range(n)) +
             f'" fill="none" stroke="url(#gd{vid})" stroke-width="9"/>']
    for i in range(1, n):
        t = i / n
        cy = y + sag * 2 * t * (1 - t) * 1.0
        parts.append(f'<circle cx="{x0 + step * i:.0f}" cy="{cy + 6:.0f}" r="7" fill="#C81E33"/>')
    return "".join(parts)


def _flower(cx, cy, r, petal, center, n=6):
    import math
    petals = "".join(
        f'<ellipse cx="{cx + r * math.cos(i * 6.283 / n):.0f}" cy="{cy + r * math.sin(i * 6.283 / n):.0f}" '
        f'rx="{r * 0.62:.0f}" ry="{r * 0.4:.0f}" fill="{petal}" '
        f'transform="rotate({i * 360 // n} {cx + r * math.cos(i * 6.283 / n):.0f} {cy + r * math.sin(i * 6.283 / n):.0f})"/>'
        for i in range(n))
    return petals + C(cx, cy, r * 0.45, center)


# ---------------------------------------------------------------------------
# Individual event items
# ---------------------------------------------------------------------------
def _shamiyana(pal, vid):
    drape = "".join(
        f'<path d="M{170 + i * 90} 520 Q{215 + i * 90} {600 + (i % 2) * 26} {260 + i * 90} 520" '
        f'fill="none" stroke="{pal[1]}" stroke-width="7" opacity="0.8"/>' for i in range(5))
    skirt = f'<path d="M150 780 L650 780 L650 840 Q400 872 150 840 Z" fill="url(#cl{vid})" opacity="0.9"/>'
    return (
        P("M400 300 L690 520 L110 520 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=5)
        + P("M400 300 L690 520 L400 470 Z", fill=pal[1], op=0.35, w=0)
        + P("M110 520 L690 520 L660 560 L140 560 Z", fill="url(#cl{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
        + drape + skirt
        + R(150, 560, 26, 280, 8, "#E4C36A", pal[3], 3) + R(624, 560, 26, 280, 8, "#E4C36A", pal[3], 3)
        + R(386, 470, 28, 300, 8, "#E4C36A", pal[3], 3)
        + C(400, 292, 16, pal[2], pal[3], 3)
        + P("M400 262 q10 -26 0 -44 q-10 20 0 44", fill=pal[0], stroke=pal[3], w=2)
    )


def _tent_house(pal, vid):
    return (
        P("M180 620 L180 430 Q400 320 620 430 L620 620 Z", fill="url(#cl{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=5)
        + P("M180 430 Q400 320 620 430 Q400 384 180 430 Z", fill=pal[2], op=0.8, w=0)
        + R(340, 500, 120, 120, 8, pal[3], pal[2], 4)
        + P("M400 500 L400 620", stroke=pal[2], w=4, fill="none")
        + _garland(190, 610, 452, vid, 8, 18)
        + R(160, 620, 480, 26, 8, "url(#gd" + vid + ")", pal[3], 3)
        + C(230, 660, 22, pal[1]) + C(570, 660, 22, pal[1])
    )


def _canopy(pal, vid):
    frill = "".join(
        f'<path d="M{170 + i * 58} 470 q29 34 58 0" fill="{pal[2]}" stroke="{pal[3]}" stroke-width="2.5"/>'
        for i in range(8))
    return (
        P("M160 470 L640 470 L610 380 L190 380 Z", fill="url(#cl{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
        + frill
        + R(186, 470, 20, 340, 6, "#E4C36A", pal[3], 2) + R(594, 470, 20, 340, 6, "#E4C36A", pal[3], 2)
        + P("M196 560 Q400 610 604 560", stroke=pal[1], w=6, fill="none", op=0.7)
        + C(400, 356, 14, pal[2], pal[3], 3)
    )


def _pandal(pal, vid):
    arches = "".join(
        f'<path d="M{200 + i * 140} 760 L{200 + i * 140} 560 Q{270 + i * 140} 470 {340 + i * 140} 560 L{340 + i * 140} 760" '
        f'fill="none" stroke="url(#gd{vid})" stroke-width="14"/>' for i in range(3))
    return (
        R(150, 420, 500, 60, 12, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 4)
        + P("M400 250 L680 420 L120 420 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
        + arches
        + R(140, 760, 520, 34, 10, pal[2], pal[3], 3)
        + _garland(160, 640, 432, vid, 9, 20)
        + _flower(400, 330, 26, pal[1], pal[2])
    )


def _chairs(cushioned):
    def draw(pal, vid):
        def one(x, back):
            seat = R(x, 660, 96, 22, 6, back, pal[3], 3)
            legs = (P(f"M{x + 8} 682 L{x + 4} 800", stroke="#8892A0" if not cushioned else pal[3], w=8, fill="none")
                    + P(f"M{x + 88} 682 L{x + 92} 800", stroke="#8892A0" if not cushioned else pal[3], w=8, fill="none"))
            backr = R(x + 8, 500 if cushioned else 520, 80, 160 if cushioned else 144, 12,
                      back, pal[3], 3)
            pad = R(x + 16, 512, 64, 120, 10, pal[1], pal[3], 2) if cushioned else ""
            return backr + pad + seat + legs
        row = one(150, pal[0]) + one(300, pal[0]) + one(450, pal[1]) + one(600, pal[0])
        extra = ("" if cushioned else
                 P("M158 520 q40 -18 74 0 M308 520 q40 -18 74 0 M458 520 q40 -18 74 0 M608 520 q40 -18 74 0",
                   stroke=pal[2], w=5, fill="none", op=0.9))
        return row + extra
    return draw


def _sofa(pal, vid):
    return (
        R(150, 560, 500, 60, 20, pal[1], pal[3], 4)
        + R(150, 480, 500, 120, 26, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 4)
        + R(190, 500, 130, 100, 16, pal[2], pal[3], 3) + R(330, 500, 130, 100, 16, pal[2], pal[3], 3) + R(470, 500, 130, 100, 16, pal[2], pal[3], 3)
        + R(140, 560, 60, 180, 18, pal[0], pal[3], 4) + R(600, 560, 60, 180, 18, pal[0], pal[3], 4)
        + R(200, 620, 400, 70, 14, pal[1], pal[3], 3)
        + R(180, 740, 40, 44, 8, pal[3]) + R(580, 740, 40, 44, 8, pal[3])
        + shade_oval(210, 650, 130) + shade_oval(360, 650, 130)
    )


def shade_oval(x, y, w_):
    return f'<rect x="{x}" y="{y}" width="{w_}" height="16" rx="8" fill="#FFFFFF" opacity="0.28"/>'


def _tables(pal, vid):
    def table(x, y, s):
        return (R(x, y + int(90 * s), int(220 * s), int(16 * s), 6, "url(#gd{0})".format(vid).replace("{0}", vid), pal[3], 3)
                + R(x + int(14 * s), y + int(106 * s), int(12 * s), int(120 * s), 4, pal[3])
                + R(x + int(194 * s), y + int(106 * s), int(12 * s), int(120 * s), 4, pal[3])
                + R(x, y + int(60 * s), int(220 * s), int(34 * s), 8, pal[1], pal[3], 3)
                + R_(x + int(10 * s), y + int(66 * s), int(200 * s), int(10 * s), 5, "#FFFFFF", op=0.4))
    return table(150, 470, 1.15) + table(430, 560, 0.9) + table(170, 680, 0.75)


def _carpet(pal, vid):
    border = P("M170 560 L630 560 L680 820 L120 820 Z", fill=pal[1], stroke=pal[3], w=5)
    inner = P("M200 588 L600 588 L642 792 L158 792 Z", fill="url(#cl{0})".format(vid).replace("{0}", vid), stroke=pal[2], w=3)
    motifs = "".join(_flower(230 + i * 84, 690, 20, pal[2], pal[3]) for i in range(5))
    fringe = "".join(f'<line x1="{130 + i * 11}" y1="820" x2="{126 + i * 11}" y2="846" stroke="{pal[3]}" stroke-width="4"/>' for i in range(51))
    return border + inner + motifs + fringe


def _flower_decor(pal, vid):
    spray = (P("M400 800 L400 620", stroke="#2E9E4B", w=10, fill="none")
             + P("M400 700 Q330 660 300 590", stroke="#2E9E4B", w=7, fill="none")
             + P("M400 700 Q470 660 500 590", stroke="#2E9E4B", w=7, fill="none"))
    vase = P("M350 800 L450 800 L436 872 L364 872 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
    return (vase + spray
            + _flower(300, 560, 34, pal[1], pal[2]) + _flower(500, 560, 34, pal[2], pal[1])
            + _flower(400, 500, 44, pal[0] if pal[0] != "#E8ECF2" else "#F4A6B8", "#F6E7B0")
            + _flower(340, 620, 24, "#D63B3B", pal[2]) + _flower(462, 620, 24, pal[2], "#D63B3B"))


def _balloon_arch(pal, vid):
    pts = [(160, 820), (150, 690), (180, 560), (250, 460), (350, 400), (450, 386),
           (550, 420), (625, 500), (660, 610), (662, 740), (648, 830)]
    cols = [pal[1], pal[2] if pal[2] != "#F6E7B0" else "#F9D6E0", pal[0] if pal[0] != "#E8ECF2" else "#8FBF9F", "#D63B3B"]
    blobs = "".join(
        f'<g><circle cx="{x}" cy="{y}" r="52" fill="{cols[i % 4]}" stroke="{pal[3]}" stroke-width="2.5"/>'
        f'<circle cx="{x - 16}" cy="{y - 18}" r="12" fill="#FFFFFF" opacity="0.55"/></g>'
        for i, (x, y) in enumerate(pts))
    return blobs + P("M160 872 L648 872", stroke=pal[3], w=6, fill="none", op=0.5)


def _mandap(pal, vid):
    pillars = "".join(
        f'<g><rect x="{x}" y="480" width="34" height="330" rx="8" fill="url(#gd{vid})" stroke="{pal[3]}" stroke-width="3"/>'
        f'<rect x="{x - 10}" y="470" width="54" height="22" rx="6" fill="{pal[2]}" stroke="{pal[3]}" stroke-width="2"/>'
        f'<rect x="{x - 12}" y="796" width="58" height="24" rx="6" fill="{pal[2]}" stroke="{pal[3]}" stroke-width="2"/></g>'
        for x in (200, 340, 480, 610))
    return (
        R(170, 380, 500, 60, 14, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 4)
        + P("M400 260 L700 380 L100 380 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
        + _garland(180, 656, 442, vid, 8, 22)
        + pillars
        + R(180, 820, 480, 26, 8, pal[2], pal[3], 3)
        + _flower(400, 320, 30, pal[1], pal[2]) + _flower(280, 470, 18, pal[2], pal[1]) + _flower(600, 470, 18, pal[1], pal[2])
    )


def _entrance_arch(pal, vid):
    leafy = "".join(
        f'<g><circle cx="{x}" cy="{y}" r="26" fill="{pal[1]}" stroke="{pal[3]}" stroke-width="2"/>'
        f'<circle cx="{x - 8}" cy="{y - 8}" r="6" fill="#FFFFFF" opacity="0.5"/></g>'
        for x, y in [(180, 840), (170, 740), (176, 640), (196, 545), (250, 465), (330, 410),
                     (420, 388), (508, 400), (582, 452), (628, 530), (645, 630), (642, 735), (632, 835)])
    bow = (P("M340 396 Q400 350 460 396 L452 424 Q400 386 348 424 Z", fill=pal[2], stroke=pal[3], w=3)
           + C(400, 410, 16, pal[0] if pal[0] != "#E8ECF2" else "#F4A6B8", pal[3], 3))
    return P("M150 860 L150 560 Q150 380 400 350 Q650 380 650 560 L650 860",
             fill="none", stroke=pal[3], w=16) + leafy + bow


def _rangoli(pal, vid):
    import math
    rings = ""
    for r, col, n in ((190, pal[1], 16), (140, pal[2] if pal[2] != "#F6E7B0" else "#F2C94C", 12), (92, pal[0] if pal[0] != "#E8ECF2" else "#7FA6C9", 8)):
        rings += "".join(
            f'<ellipse cx="{400 + r * math.cos(i * 6.283 / n):.0f}" cy="{680 + r * 0.62 * math.sin(i * 6.283 / n):.0f}" '
            f'rx="20" ry="12" fill="{col}" stroke="{pal[3]}" stroke-width="2" '
            f'transform="rotate({i * 360 // n} {400 + r * math.cos(i * 6.283 / n):.0f} {680 + r * 0.62 * math.sin(i * 6.283 / n):.0f})"/>'
            for i in range(n))
    return (f'<ellipse cx="400" cy="680" rx="250" ry="160" fill="{pal[4]}" stroke="{pal[3]}" stroke-width="4"/>'
            + rings + _flower(400, 680, 36, pal[1], "#F2C94C")
            + "".join(f'<circle cx="{400 + 236 * math.cos(i * 0.785):.0f}" cy="{680 + 150 * math.sin(i * 0.785):.0f}" r="8" fill="#D63B3B"/>' for i in range(8)))


def _theme_decor(pal, vid):
    return (
        R(150, 380, 500, 380, 10, pal[1], pal[3], 5)
        + R(172, 402, 456, 336, 8, "none", pal[2], 4)
        + P("M240 640 Q400 470 560 640 Q400 560 240 640 Z", fill=pal[2], stroke=pal[3], w=3, op=0.9)
        + _flower(400, 470, 34, pal[2], pal[3]) + C(400, 640, 40, pal[0] if pal[0] != "#E8ECF2" else "#F4A6B8", pal[3], 4)
        + _garland(150, 650, 380, vid, 10, 16)
        + R_(200, 770, 400, 20, 6, pal[3], op=0.6)
    )


def _serial_lights(pal, vid):
    wire = P("M120 480 Q260 560 400 480 Q540 400 680 480", fill="none", stroke="#4A5563", w=4)
    bulbs = "".join(
        f'<g><circle cx="{x}" cy="{y}" r="15" fill="#FCE78A" stroke="{pal[3]}" stroke-width="2"/>'
        f'<circle cx="{x}" cy="{y}" r="26" fill="#FCE78A" opacity="0.30"/></g>'
        for x, y in [(160, 498), (230, 526), (300, 524), (370, 494), (440, 456), (510, 434), (580, 440), (650, 468)])
    glow = f'<rect x="120" y="400" width="560" height="200" fill="#FCE78A" opacity="0.08"/>'
    return glow + wire + bulbs + _garland(160, 640, 700, vid, 6, 12)


def _chandelier(pal, vid):
    arms = "".join(
        f'<path d="M400 420 Q{250 + i * 75} 470 {230 + i * 85} 540" fill="none" stroke="url(#gd{vid})" stroke-width="7"/>'
        for i in range(5))
    candles = "".join(
        f'<g><rect x="{222 + i * 85}" y="500" width="16" height="44" rx="4" fill="#F6E7B0" stroke="{pal[3]}" stroke-width="2"/>'
        f'<ellipse cx="{230 + i * 85}" cy="492" rx="7" ry="13" fill="#F2B705"/>'
        f'<ellipse cx="{230 + i * 85}" cy="492" rx="14" ry="22" fill="#FCE78A" opacity="0.35"/></g>'
        for i in range(5))
    drops = "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="{pal[2]}" stroke="{pal[3]}" stroke-width="1.5"/>'
                    for x, y in [(280, 596), (340, 620), (400, 634), (460, 620), (520, 596)])
    return (P("M400 300 L400 380", stroke=pal[3], w=6, fill="none")
            + C(400, 404, 26, "url(#gd" + vid + ")", pal[3], 3) + arms + candles + drops
            + P("M300 452 Q400 500 500 452", fill="none", stroke=pal[1], w=4, op=0.8))


def _dj_set(pal, vid):
    deck = (R(260, 560, 280, 90, 12, "#23282F", "#4A5563", 4)
            + C(330, 605, 30, "#31383F", "#8892A0", 3) + C(470, 605, 30, "#31383F", "#8892A0", 3)
            + "".join(f'<rect x="{300 + i * 40}" y="576" width="10" height="6" rx="2" fill="{c}"/>'
                      for i, c in enumerate(["#D63B3B", "#F2B705", "#2E9E4B", "#5BB7DF", "#8E44AD"])))
    return (
        R(200, 650, 400, 200, 14, "#3B4250", "#1E222B", 5)
        + deck
        + R(330, 400, 140, 120, 14, "#1E222B", "#6E7889", 3) + C(400, 460, 34, "#31383F", "#8892A0", 4)
        + P("M240 420 Q200 360 250 320", stroke="#8892A0", w=7, fill="none")
        + C(258, 312, 14, "#F2B705", "#A97C02", 3) + C(545, 315, 14, "#D63B3B", "#8F1D1D", 3)
        + P("M560 420 Q600 360 552 322", stroke="#8892A0", w=7, fill="none")
        + "".join(f'<path d="M{400 + 160 * (-1 if i % 2 else 1)} {700 - i * 40} l30 -14" stroke="#5BB7DF" stroke-width="4" opacity="0.6"/>' for i in range(4))
    )


def _speakers(pal, vid):
    def box(x, s):
        w_, h_ = int(150 * s), int(240 * s)
        y = 820 - h_
        return (R(x, y, w_, h_, 14, "#3B4250", "#1E222B", 5)
                + C(x + w_ // 2, y + int(80 * s), int(48 * s), "#23282F", "#8892A0", 4)
                + C(x + w_ // 2, y + int(80 * s), int(22 * s), "#6E7889")
                + C(x + w_ // 2, y + int(170 * s), int(28 * s), "#23282F", "#8892A0", 3)
                + R(x + int(14 * s), y + int(12 * s), int(120 * s), 8, 4, pal[1]))
    waves = "".join(f'<path d="M560 560 q{30 + i * 16} {26 + i * 12} 0 {56 + i * 20}" fill="none" stroke="#5BB7DF" stroke-width="5" opacity="{0.8 - i * 0.2}"/>' for i in range(3))
    return box(200, 1.1) + box(380, 0.8) + waves


def _microphones(pal, vid):
    def mic(x, tilt):
        return (f'<g transform="rotate({tilt} {x} 700)">'
                + P(f"M{x} 480 L{x} 720", stroke="#23282F", w=14, fill="none")
                + C(x, 452, 40, "#4A5563", "#1E222B", 4)
                + f'<path d="M{x - 30} 440 q30 -34 60 0 q-30 20 -60 0" fill="#8892A0"/>'
                + "".join(f'<line x1="{x - 24 + i * 10}" y1="436" x2="{x - 24 + i * 10}" y2="462" stroke="#23282F" stroke-width="2.5"/>' for i in range(6))
                + R(x - 34, 716, 68, 18, 8, "#3B4250")
                + "</g>")
    return mic(320, -8) + mic(480, 8) + P("M320 800 Q400 850 480 800", fill="none", stroke=pal[1], w=4, op=0.7)


def _stagesetup(pal, vid):
    backdrop = (R(180, 340, 440, 300, 6, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 5)
                + R(204, 364, 392, 252, 4, "none", pal[2], 3)
                + _flower(400, 470, 40, pal[2], pal[1]))
    lights = "".join(f'<g><rect x="{196 + i * 92}" y="316" width="18" height="22" rx="4" fill="#23282F"/>'
                     f'<ellipse cx="{205 + i * 92}" cy="352" rx="18" ry="26" fill="#FCE78A" opacity="0.35"/></g>' for i in range(5))
    platform = (P("M140 700 L660 700 L690 780 L110 780 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=5)
                + R(110, 780, 580, 34, 6, WOOD[0], WOOD[2], 4)
                + shade_oval(200, 716, 380))
    return backdrop + lights + platform + _garland(180, 620, 340, vid, 9, 14)


def _backdrop(pal, vid):
    curtain = "".join(
        f'<path d="M{162 + i * 48} 360 q12 250 0 470" stroke="{pal[1]}" stroke-width="10" fill="none" opacity="0.55"/>'
        for i in range(10))
    valance = P("M140 360 L660 360 L660 420 Q400 470 140 420 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
    return (R(140, 360, 520, 480, 4, pal[2] if pal[2] != "#F6E7B0" else "#FBEBC8", pal[3], 5)
            + curtain + valance
            + P("M250 840 Q400 800 550 840", fill="none", stroke=pal[1], w=6, op=0.8)
            + _flower(400, 560, 46, pal[1], pal[0] if pal[0] != "#E8ECF2" else "#F4A6B8"))


def _flower_wall(pal, vid):
    rows = ""
    cols = [pal[1], pal[2] if pal[2] != "#F6E7B0" else "#F9C9D6", "#D63B3B", pal[0] if pal[0] != "#E8ECF2" else "#8FBF9F"]
    for r in range(5):
        for c in range(8):
            rows += _flower(180 + c * 62 + (28 if r % 2 else 0), 400 + r * 88, 26, cols[(r + c) % 4], "#F2C94C", n=5)
    return R(140, 350, 520, 500, 8, "#2E5A34", pal[3], 5) + rows


def _photobooth(pal, vid):
    frame = (R(200, 340, 400, 440, 10, "none", "url(#gd" + vid + ")", 16)
             + R(182, 322, 436, 26, 8, pal[1], pal[3], 3)
             + R(182, 772, 436, 26, 8, pal[1], pal[3], 3))
    prop = (P("M400 560 m-90 0 a90 90 0 1 0 180 0 a90 90 0 1 0 -180 0", fill=pal[2], stroke=pal[3], w=4)
            + P("M330 620 L300 760 L360 700 Z", fill=pal[2], stroke=pal[3], w=4)
            + P("M470 620 L500 760 L440 700 Z", fill=pal[2], stroke=pal[3], w=4))
    stick = P("M520 780 L470 640", stroke="#8892A0", w=8, fill="none")
    star = P("M540 560 l14 30 33 4 -24 23 6 33 -29 -16 -29 16 6 -33 -24 -23 33 -4 Z", fill="#F2B705", stroke="#A97C02", w=3)
    return frame + prop + stick + star + C(280, 420, 12, pal[1]) + C(340, 400, 8, pal[0]) + C(520, 430, 10, pal[1])


def _props_set(pal, vid):
    mustache = P("M300 620 q40 -60 100 -20 q60 -40 100 20 q-60 40 -100 10 q-40 30 -100 -10 Z",
                 fill="#23282F")
    lips = P("M340 500 q60 -40 120 0 q-60 60 -120 0 Z", fill="#D63B3B", stroke="#8F1D1D", w=3)
    glasses = (C(330, 740, 34, "none", "#23282F", 8) + C(430, 740, 34, "none", "#23282F", 8)
               + P("M364 740 L396 740", stroke="#23282F", w=8, fill="none")
               + P("M296 726 L260 706 M464 726 L500 706", stroke="#23282F", w=6, fill="none"))
    sign = R(470, 470, 150, 90, 10, pal[2], pal[3], 4) + P("M500 515 L540 515 M500 540 L590 540", stroke=pal[1], w=8, fill="none")
    stick2 = P("M545 560 L545 700", stroke="#8892A0", w=7, fill="none")
    return P("M250 820 L640 820", stroke=pal[3], w=5, fill="none", op=0.5) + mustache + lips + glasses + sign + stick2


def _utensils(pal, vid):
    pot = (C(400, 600, 130, "#8892A0", "#4A5563", 6)
           + P("M270 600 Q400 760 530 600 L530 640 Q400 780 270 640 Z", fill="#6E7889", stroke="#4A5563", w=5)
           + R(240, 560, 320, 26, 10, "#C9D2DC", "#4A5563", 4)
           + C(400, 540, 20, "#4A5563")
           + P("M300 590 Q360 560 420 588", stroke="#FFFFFF", w=6, fill="none", op=0.5))
    ladle = P("M560 500 Q620 560 600 660 L640 700", stroke="#B8434A", w=9, fill="none") + C(648, 712, 24, "#D63B3B", "#8F1D1D", 4)
    spoons = "".join(P(f"M{x} 480 L{x - 30} 780", stroke="#8892A0", w=7, fill="none") + C(x + 4, 468, 20, "#C9D2DC", "#4A5563", 3)
                     for x in (210, 250, 290))
    return pot + ladle + spoons


def _cooking_vessels(pal, vid):
    kadhi = (P("M240 560 L560 560 L520 720 Q400 770 280 720 Z", fill="#8892A0", stroke="#4A5563", w=5)
            + R(224, 540, 352, 26, 12, "#C9D2DC", "#4A5563", 4)
            + C(400, 520, 16, "#4A5563")
            + P("M250 574 Q400 610 550 574", stroke="#FFFFFF", w=5, fill="none", op=0.4))
    pans = (C(620, 700, 60, "#6E7889", "#23282F", 5) + P("M680 700 L760 690", stroke="#23282F", w=12, fill="none")
            + C(620, 700, 34, "#4A5563"))
    small = C(200, 700, 46, "#B87333", "#7A4A10", 4) + P("M160 690 L240 690", stroke="#7A4A10", w=5, fill="none")
    return kadhi + pans + small


def _chafing_dish(pal, vid):
    return (
        R(230, 620, 340, 90, 12, "#C9D2DC", "#4A5563", 5)
        + P("M250 620 Q400 570 550 620", fill="#8892A0", stroke="#4A5563", w=5)
        + C(400, 566, 16, "#4A5563")
        + R(250, 710, 300, 30, 8, "#8892A0", "#4A5563", 3)
        + P("M280 740 L270 810 M520 740 L530 810 M400 740 L400 816", stroke="#4A5563", w=9, fill="none")
        + C(400, 780, 20, "#F2B705", "#A97C02", 3)
        + "".join(f'<path d="M{370 + i * 30} 540 q4 -22 -4 -40" stroke="#E8EEF4" stroke-width="4" fill="none" opacity="0.7"/>' for i in range(3))
    )


def _water_dispenser(pal, vid):
    return (
        R(310, 560, 180, 280, 16, "#E8EEF4", STEEL[2], 5)
        + P("M330 560 L330 430 Q400 380 470 430 L470 560 Z", fill="#9FC6E8", stroke="#1B4C66", w=5)
        + shade_oval(350, 430, 100)
        + R(360, 640, 34, 26, 6, "#1B4C66") + R(412, 640, 34, 26, 6, "#1B4C66")
        + P("M377 668 L377 700 L430 700", stroke="#1B4C66", w=6, fill="none", op=0.5)
        + R(340, 760, 120, 26, 8, "#C9D2DC", STEEL[2], 3)
        + C(400, 850, 10, STEEL[2])
    )


def _ganesh(pal, vid):
    return (
        R(280, 720, 240, 60, 10, "url(#gd{0})".format(vid).replace("{0}", vid), pal[3], 4)
        + P("M400 470 Q310 480 310 590 Q310 690 400 700 Q490 690 490 590 Q490 480 400 470 Z",
            fill="#E8A33C", stroke="#8F5A10", w=5)
        + C(400, 430, 74, "#E8A33C", "#8F5A10", 5)
        + P("M326 400 Q280 340 320 300 Q350 340 356 386 Z", fill="#E8A33C", stroke="#8F5A10", w=4)
        + P("M474 400 Q520 340 480 300 Q450 340 444 386 Z", fill="#E8A33C", stroke="#8F5A10", w=4)
        + P("M400 470 Q376 540 402 600 Q420 560 414 486", fill="#F2C94C", stroke="#8F5A10", w=4)
        + C(378, 424, 9, "#23282F") + C(422, 424, 9, "#23282F")
        + C(400, 372, 12, "#D63B3B")
        + _flower(250, 560, 26, pal[1], pal[2]) + _flower(550, 560, 26, pal[1], pal[2])
        + P("M240 660 q12 -30 0 -60 M560 660 q-12 -30 0 -60", stroke=pal[1], w=5, fill="none", op=0.7)
    )


def _diwali_lights(pal, vid):
    diya = (P("M310 640 L490 640 L450 720 Q400 744 350 720 Z", fill="#B87333", stroke="#7A4A10", w=5)
            + P("M330 640 Q400 616 470 640", fill="#D98B4A", stroke="#7A4A10", w=3)
            + P("M400 636 q10 -34 0 -66 q-12 30 0 66", fill="#F2B705")
            + P("M400 628 q5 -22 0 -42 q-7 18 0 42", fill="#FCDE85")
            + C(400, 590, 40, "#FCE78A", op=0.3))
    rows = "".join(
        f'<g><path d="M{x - 34} {y} L{x + 34} {y} L{x + 22} {y + 26} Q{x} {y + 38} {x - 22} {y + 26} Z" fill="#B87333" stroke="#7A4A10" stroke-width="3"/>'
        f'<path d="M{x} {y - 2} q6 -18 0 -32 q-8 14 0 32" fill="#F2B705"/></g>'
        for x, y in [(180, 800), (300, 812), (420, 812), (540, 806), (650, 788)])
    sparkles = "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="#FCE78A"/>'
                       for x, y in [(200, 480), (600, 440), (320, 380), (500, 500), (250, 620), (620, 600)])
    return diyas_lights_bg(pal, vid) + diya + rows + sparkles


def diyas_lights_bg(pal, vid):
    return _garland(150, 660, 380, vid, 10, 18) + _garland(150, 660, 440, vid, 10, 14)


def _pooja_items(pal, vid):
    kalash = (P("M340 600 L460 600 L444 700 Q400 726 356 700 Z", fill="url(#gd{0})".format(vid).replace("{0}", vid), stroke=pal[3], w=4)
              + C(400, 588, 24, "#E8A33C", pal[3], 3) + P("M400 560 q8 -22 0 -40 q-10 18 0 40", fill="#2E9E4B"))
    diya = P("M520 700 q34 -10 60 0 l-10 24 q-20 8 -40 0 Z" , fill="#B87333", stroke="#7A4A10", w=3) + P("M552 694 q5 -16 0 -28 q-7 12 0 28", fill="#F2B705")
    bell = (P("M240 700 Q240 600 300 600 Q360 600 360 700 Z", fill="#E8A33C", stroke=pal[3], w=4)
            + R(296, 560, 8, 44, 4, pal[3]) + C(300, 552, 10, "#E8A33C", pal[3], 3)
            + C(300, 700, 10, pal[3]))
    incense = "".join(P(f"M{x} 820 L{x - 10} 560", stroke="#8F5A10", w=3, fill="none")
                      + f'<circle cx="{x - 11}" cy="556" r="5" fill="#D63B3B"/>'
                      + f'<path d="M{x - 12} 540 q-8 -26 4 -50" stroke="#C9D2DC" stroke-width="3" fill="none" opacity="0.8"/>'
                      for x in (500, 520, 540))
    return R(220, 720, 400, 24, 8, WOOD[0], WOOD[2], 3) + bell + kalash + diya + incense


def _garba_set(pal, vid):
    import math
    sticks = "".join(
        f'<line x1="{400 + 150 * math.cos(a):.0f}" y1="{640 + 150 * 0.7 * math.sin(a):.0f}" '
        f'x2="{400 + 190 * math.cos(a):.0f}" y2="{640 + 190 * 0.7 * math.sin(a):.0f}" '
        f'stroke="#8F5A10" stroke-width="8" stroke-linecap="round"/>'
        for a in [i * 0.785 for i in range(8)])
    lantern = (R(370, 430, 60, 80, 12, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 4)
               + P("M400 410 L400 380", stroke=pal[3], w=4, fill="none")
               + "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="#FCE78A"/>'
                         for x, y in [(386, 450), (414, 470), (400, 490)]))
    dandiya = (P("M240 560 L300 500", stroke="#D63B3B", w=10, fill="none")
               + P("M250 500 L310 560", stroke="#F2B705", w=10, fill="none"))
    return (f'<ellipse cx="400" cy="640" rx="230" ry="160" fill="none" stroke="url(#gd{vid})" stroke-width="7"/>'
            + f'<ellipse cx="400" cy="640" rx="150" ry="104" fill="none" stroke="{pal[1]}" stroke-width="4" stroke-dasharray="10 8"/>'
            + sticks + lantern + dandiya + _flower(400, 640, 34, pal[1], pal[2]))


def _christmas(pal, vid):
    import math
    tree = (P("M400 380 L300 560 L500 560 Z", fill="#2E7D46", stroke="#14612C", w=4)
            + P("M400 460 L270 680 L530 680 Z", fill="#2E9E4B", stroke="#14612C", w=4)
            + P("M400 560 L240 800 L560 800 Z", fill="#2E7D46", stroke="#14612C", w=4)
            + R(376, 800, 48, 44, 6, WOOD[0], WOOD[2], 3)
            + P("M400 344 l12 26 28 4 -20 20 5 28 -25 -13 -25 13 5 -28 -20 -20 28 -4 Z", fill="#F2B705", stroke="#A97C02", w=3))
    balls = "".join(f'<circle cx="{400 + r * math.cos(a):.0f}" cy="{y}" r="12" fill="{c}"/>'
                    for (r, a, y, c) in [(40, 2.0, 500, "#D63B3B"), (-46, 1.1, 620, "#F2B705"),
                                         (60, -0.5, 640, "#5BB7DF"), (-90, 2.6, 740, "#D63B3B"),
                                         (100, -2.2, 748, "#8E44AD")])
    gift = R(590, 730, 110, 84, 8, "#D63B3B", "#8F1D1D", 4) + R(590, 762, 110, 16, 4, "#F6E7B0") + R(632, 730, 16, 84, 3, "#F6E7B0")
    return tree + balls + gift + P("M250 420 q20 -24 44 0", stroke="#FFFFFF", w=5, fill="none", op=0.8)


def _eid(pal, vid):
    moon = P("M480 420 a90 90 0 1 1 -96 -124 a72 72 0 1 0 96 124", fill="#F6E7B0", stroke=pal[3], w=5)
    star = P("M300 380 l10 22 24 3 -17 17 4 24 -21 -12 -21 12 4 -24 -17 -17 24 -3 Z", fill="#F2C94C", stroke=pal[3], w=2)
    lantern = (R(470, 560, 100, 150, 18, "url(#gd{0})".format(vid).replace("{0}", vid), pal[3], 4)
               + P("M520 540 L520 500", stroke=pal[3], w=5, fill="none")
               + R_(486, 576, 68, 20, 6, pal[2], op=0.8) + R_(486, 620, 68, 20, 6, pal[2], op=0.8)
               + P("M520 710 L520 740", stroke=pal[3], w=4, fill="none") + C(520, 748, 8, pal[1]))
    dome = (P("M180 820 L180 700 Q260 600 340 700 L340 820 Z", fill=pal[1], stroke=pal[3], w=4)
            + P("M260 620 q0 -34 0 -44 M260 620 l-14 -20 h28 Z", stroke=pal[3], w=4, fill="none")
            + R(240, 740, 40, 80, 14, pal[3])
            + R(150, 820, 220, 22, 6, pal[2], pal[3], 3))
    stars = "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="#F6E7B0"/>'
                    for x, y in [(160, 460), (220, 520), (640, 340), (600, 500), (140, 560)])
    return moon + star + lantern + dome + stars


def _other_event(pal, vid):
    return (R(260, 480, 280, 220, 20, "url(#cl{0})".format(vid).replace("{0}", vid), pal[3], 5)
            + _garland(240, 560, 480, vid, 6, 16) + C(400, 590, 46, pal[2], pal[3], 4)
            + P("M400 560 l0 60 M370 590 l60 0", stroke=pal[3], w=8, fill="none"))


def _reg(name, fn):
    return (_norm(name), fn)


_REGISTRY = {
    # item_type options
    "flowerdecor": _flower_decor, "balloondecor": _balloon_arch, "balloonarch": _balloon_arch,
    "mandapdecor": _mandap, "entrancearch": _entrance_arch, "rangoliset": _rangoli,
    "themedecor": _theme_decor,
    "chairs": _chairs(False), "plasticchairs": _chairs(False), "cushionedchairs": _chairs(True),
    "sofas": _sofa, "tables": _tables, "stagechairs": _chairs(True), "carpets": _carpet,
    "shamiyanatent": _shamiyana, "tenthouseset": _tent_house, "canopy": _canopy, "pandal": _pandal,
    "seriallights": _serial_lights, "chandelier": _chandelier, "djset": _dj_set,
    "speakers": _speakers, "microphones": _microphones,
    "utensilsset": _utensils, "cookingvessels": _cooking_vessels, "chafingdish": _chafing_dish,
    "waterdispenser": _water_dispenser,
    "stagesetup": _stagesetup, "stage": _stagesetup, "backdrop": _backdrop, "flowerwall": _flower_wall,
    "ganeshidoldecor": _ganesh, "diwalilights": _diwali_lights, "poojaitems": _pooja_items,
    "navaratrigarbaset": _garba_set, "christmasdecor": _christmas, "eiddecor": _eid,
    "photobooth": _photobooth, "propsset": _props_set,
    # extra names from the feature brief
    "decoration": _flower_wall, "chairsseating": _chairs(False),
    "tentsandpandals": _shamiyana, "tent": _shamiyana,
    "lightingandsound": _serial_lights, "stage_lighting": _chandelier, "stagelightning": _chandelier,
    "catering": _chafing_dish, "cateringequipment": _chafing_dish,
    "stageandbackdrops": _stagesetup, "festival_items": _diwali_lights,
    "festivalitems": _diwali_lights, "photoboothandprops": _photobooth,
    "event_items": _shamiyana, "other": _other_event,
}
# "chairs" subcategory collides with the item_type "Chairs" - both map to chairs.
# stage_lighting / festival_items keys below normalize with underscores kept by
# _norm? They do NOT - _norm strips them, so register the stripped variants:
_REGISTRY["stagelighting"] = _chandelier
_REGISTRY["festivalitems"] = _diwali_lights
_REGISTRY["photobooth"] = _photobooth


def resolve_key(subcat_key="", item_type=""):
    """Registry key lookup: item_type first (most specific), then sub-category."""
    for cand in (item_type, subcat_key):
        k = _norm(cand)
        if k and k in _REGISTRY:
            return k
    return None


def make_event_art(item_type="", subcat_key="", style="", slug="", label="") -> str:
    """Return the 800x1000 SVG for one event/decoration item."""
    key = resolve_key(subcat_key, item_type) or "other"
    pal = _pal(style)
    vid = _vid(slug or key)
    body = _REGISTRY[key](pal, vid)
    caption = label or item_type or subcat_key or key
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img" aria-label="{esc(caption)}">'
            + scene_bg(vid, pal) + floor(vid) + body + label_ribbon(caption, vid)
            + '</svg>')
