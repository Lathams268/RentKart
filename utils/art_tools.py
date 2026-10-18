"""Farm tools art (ART stage 2) - original generated SVG, gradient studio look.

make_tool_art(tool_type, ...) returns an 800x1000 SVG: soft gradient
background, floor shadow, shading + highlights on the tool, and a small
label ribbon with the tool name. Every look-up is by normalised tool_type /
sub-category key, so config options never get hardcoded here.
"""
from __future__ import annotations

import hashlib
import re
from xml.sax.saxutils import escape as _x

W, H = 800, 1000

STEEL = ("#8E9AAA", "#C9D2DC", "#4A5563")
BODY_GREEN = ("#2E9E4B", "#7BD690", "#14612C")
BODY_RED = ("#D63B3B", "#F08A8A", "#8F1D1D")
BODY_YELLOW = ("#F2B705", "#FCDE85", "#A97C02")
WOOD = ("#A97C50", "#D2AF8C", "#6E4A28")
DARK = ("#3B4250", "#6E7889", "#1E222B")
GLASS = "#9FC6E8"


def esc(t) -> str:
    return _x(str(t or ""))


def _norm(t) -> str:
    return re.sub(r"[^a-z0-9]", "", str(t or "").lower())


def _vid(slug) -> str:
    return f"{int(hashlib.md5(str(slug or 'tool').encode()).hexdigest()[:6], 16) % 997:03d}"


def scene_bg(vid: str, tint="#EAF3FA") -> str:
    return (f'<defs>'
            f'<linearGradient id="bg{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{tint}"/>'
            f'<stop offset="72%" stop-color="#FFFFFF"/>'
            f'<stop offset="100%" stop-color="#D9CBB0" stop-opacity="0.55"/></linearGradient>'
            f'<radialGradient id="fl{vid}" cx="0.5" cy="0.5" r="0.5">'
            f'<stop offset="0%" stop-color="#000000" stop-opacity="0.25"/>'
            f'<stop offset="100%" stop-color="#000000" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="mt{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{STEEL[1]}"/>'
            f'<stop offset="55%" stop-color="{STEEL[0]}"/>'
            f'<stop offset="100%" stop-color="{STEEL[2]}"/></linearGradient>'
            f'</defs>'
            f'<rect width="{W}" height="{H}" fill="url(#bg{vid})"/>')


def floor(vid: str) -> str:
    return f'<ellipse cx="400" cy="874" rx="300" ry="36" fill="url(#fl{vid})"/>'


def P(d, fill="none", stroke=None, w=3, op=None, extra=""):
    s = f'<path d="{d}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"'
    if op is not None:
        s += f' opacity="{op}"'
    return s + extra + '/>'


def C(cx, cy, r, fill, stroke=None, w=3, op=None):
    s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{w}"'
    if op is not None:
        s += f' opacity="{op}"'
    return s + '/>'


def R(x, y, w_, h_, rx, fill, stroke=None, w=3):
    s = f'<rect x="{x}" y="{y}" width="{w_}" height="{h_}" rx="{rx}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{w}"'
    return s + '/>'


def wheel(cx, cy, r, hub="#C9D2DC", rim="#23282F"):
    spokes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + (r-8) * __import__("math").cos(i * 0.785):.0f}" '
        f'y2="{cy + (r-8) * __import__("math").sin(i * 0.785):.0f}" stroke="{hub}" stroke-width="5"/>'
        for i in range(8))
    return (C(cx, cy, r, rim) + C(cx, cy, r - 9, "#31383F") + spokes +
            C(cx, cy, max(6, r * 0.22), hub) +
            f'<path d="M{cx - r * 0.6} {cy - r * 0.6} a{r * 0.85} {r * 0.85} 0 0 1 {r * 1.1} -{r * 0.25}" '
            f'fill="none" stroke="#FFFFFF" stroke-width="4" opacity="0.5"/>')


def label_ribbon(name: str, vid: str) -> str:
    t = esc(name if len(str(name or "")) <= 26 else str(name)[:25] + "…")
    return (f'<g><path d="M250 928 L550 928 L566 952 L550 976 L250 976 L234 952 Z" '
            f'fill="url(#mt{vid})" stroke="#37414F" stroke-width="2.5"/>'
            f'<rect x="258" y="934" width="284" height="8" rx="4" fill="#FFFFFF" opacity="0.45"/>'
            f'<text x="400" y="961" text-anchor="middle" font-family="Noto Sans, Noto Sans Devanagari, '
            f'Noto Sans Telugu, Noto Sans Kannada, Arial, sans-serif" font-size="24" '
            f'font-weight="700" fill="#1E222B">{t}</text></g>')


def shade(d, op=0.28):
    """White highlight pass over a shape path."""
    return P(d, fill="#FFFFFF", op=op, w=0)


# ---------------------------------------------------------------------------
# Individual tools
# ---------------------------------------------------------------------------
def _tractor(big=True):
    def draw(vid):
        body = BODY_GREEN
        if big:
            parts = [
                wheel(250, 720, 150), wheel(560, 780, 84),
                P("M170 560 L470 540 L480 430 L360 420 L340 470 L200 480 Z", fill=f"url(#mt{vid})", stroke=body[2], w=4),
                R(360, 300, 190, 160, 18, body[0], body[2], 4),
                R(380, 320, 120, 90, 10, GLASS, "#3A5866", 3),
                P("M390 330 L480 330 L440 400 L400 400 Z", fill="#FFFFFF", op=0.4, w=0),
                R(560, 470, 120, 120, 14, body[0], body[2], 4),
                R(575, 490, 60, 50, 8, GLASS, "#3A5866", 2),
                P("M560 500 L680 500", stroke=body[2], w=6),
                R(180, 470, 60, 14, 6, "#F5F0DC", body[2], 2),
                P("M250 560 Q120 600 130 700", stroke=body[2], w=8),
                R(120, 660, 44, 70, 8, "#D9B24A", "#7A5A18", 3),
            ]
        else:
            parts = [
                wheel(270, 740, 105), wheel(550, 775, 66),
                P("M200 620 L460 600 L470 500 L360 490 L345 530 L220 540 Z", fill=f"url(#mt{vid})", stroke=body[2], w=4),
                R(370, 380, 150, 130, 16, body[0], body[2], 4),
                R(388, 398, 96, 70, 8, GLASS, "#3A5866", 3),
                R(530, 520, 90, 90, 12, body[0], body[2], 3),
                R(195, 540, 50, 12, 5, "#F5F0DC", body[2], 2),
                P("M270 620 Q160 660 170 740", stroke=body[2], w=6),
            ]
        parts.append(shade("M360 420 L480 430 L470 500 L355 490 Z"))
        return "".join(parts)
    return draw


def _plough(vid):
    return (
        P("M140 560 L560 500 L560 540 L160 600 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + P("M560 500 Q680 560 640 700 L520 660 Q560 580 520 540 Z", fill=STEEL[0], stroke=STEEL[2], w=4)
        + P("M580 540 Q650 590 620 670", stroke="#E8EEF4", w=6, op=0.7)
        + P("M240 600 L240 760", stroke=STEEL[2], w=10)
        + P("M200 760 L280 760 L260 820 L220 820 Z", fill=STEEL[2])
        + P("M380 580 L380 740", stroke=STEEL[2], w=10)
        + wheel(180, 720, 70)
        + shade("M140 560 L560 500 L560 520 L150 580 Z")
    )


def _rotavator(vid):
    cage = "".join(
        f'<path d="M{300 + i * 34} 640 q10 70 {i % 2 * 20 - 10} 130" stroke="{STEEL[2]}" stroke-width="7" fill="none"/>'
        for i in range(8))
    return (
        R(220, 460, 380, 150, 20, BODY_RED[0], BODY_RED[2], 4)
        + shade("M220 460 L600 460 L600 500 L220 500 Z")
        + R(250, 420, 90, 60, 10, STEEL[0], STEEL[2], 3)
        + P("M200 520 L120 420 L150 400 L230 500 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=3)
        + cage
        + P("M240 640 Q410 760 580 640 Q410 700 240 640 Z", fill="#B8434A", stroke=BODY_RED[2], w=3, op=0.85)
        + R(320, 380, 180, 40, 12, STEEL[2])
    )


def _cultivator(vid):
    tines = "".join(
        f'<path d="M{260 + i * 60} 560 q10 120 34 180 q-24 -60 -18 -180 Z" fill="{STEEL[1]}" stroke="{STEEL[2]}" stroke-width="3"/>'
        for i in range(6))
    return (
        R(200, 470, 420, 100, 16, BODY_YELLOW[0], BODY_YELLOW[2], 4)
        + shade("M200 470 L620 470 L620 500 L200 500 Z")
        + P("M620 500 L700 430 L716 452 L640 520 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=3)
        + tines
        + R(300, 420, 220, 54, 12, STEEL[2])
    )


def _drill(vid):
    discs = "".join(wheel(250 + i * 90, 700, 46, hub="#D9CBAF", rim="#4A5563") for i in range(4))
    return (
        R(190, 420, 440, 150, 18, BODY_GREEN[0], BODY_GREEN[2], 4)
        + R(230, 340, 180, 90, 12, "#D9CBAF", STEEL[2], 3)
        + shade("M230 340 L410 340 L410 366 L230 366 Z")
        + "".join(P(f"M{280 + i * 70} 570 L{280 + i * 70} 660", stroke=STEEL[2], w=8) for i in range(4))
        + discs
        + P("M630 470 L710 400 L726 424 L650 492 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=3)
    )


def _harrow(vid):
    grid = "".join(
        f'<line x1="{220 + i * 52}" y1="500" x2="{220 + i * 52}" y2="700" stroke="{STEEL[2]}" stroke-width="6"/>'
        for i in range(8)) + "".join(
        f'<line x1="220" y1="{520 + j * 60}" x2="604" y2="{520 + j * 60}" stroke="{STEEL[0]}" stroke-width="8"/>'
        for j in range(4))
    teeth = "".join(
        f'<path d="M{232 + i * 52} 700 l-8 60 l20 -12 Z" fill="{STEEL[1]}" stroke="{STEEL[2]}" stroke-width="2"/>'
        for i in range(8))
    return (
        R(200, 460, 428, 60, 12, BODY_RED[0], BODY_RED[2], 4)
        + shade("M200 460 L628 460 L628 482 L200 482 Z") + grid + teeth
        + P("M200 470 L120 400", stroke=STEEL[2], w=10)
    )


def _leveller(vid):
    return (
        R(160, 560, 500, 60, 10, f"url(#mt{vid})", STEEL[2], 4)
        + shade("M160 560 L660 560 L660 578 L160 578 Z")
        + "".join(P(f"M{210 + i * 90} 620 l0 90 l26 -20 Z", fill=STEEL[2]) for i in range(5))
        + wheel(620, 720, 66) + wheel(210, 720, 66)
        + R(300, 460, 240, 100, 12, BODY_YELLOW[0], BODY_YELLOW[2], 4)
        + shade("M300 460 L540 460 L540 486 L300 486 Z")
        + P("M540 500 L660 420 L676 444 L560 520 Z", fill=STEEL[2])
    )


def _trolley(vid):
    return (
        R(170, 500, 470, 130, 14, WOOD[0], WOOD[2], 4)
        + "".join(f'<line x1="{200 + i * 60}" y1="505" x2="{200 + i * 60}" y2="625" stroke="{WOOD[2]}" stroke-width="5"/>' for i in range(8))
        + shade("M170 500 L640 500 L640 524 L170 524 Z")
        + wheel(260, 700, 88) + wheel(560, 700, 88)
        + P("M170 540 Q80 560 60 620", stroke=STEEL[2], w=9)
        + R(150, 460, 60, 26, 8, STEEL[2])
    )


def _water_tank(vid):
    marks = "".join(
        f'<line x1="285" y1="{520 + i * 55}" x2="325" y2="{520 + i * 55}" stroke="#1B4C66" stroke-width="4" opacity="0.8"/>'
        for i in range(5))
    return (
        R(270, 430, 280, 330, 26, "#5BB7DF", "#1B4C66", 5)
        + P("M270 470 Q410 505 550 470 L550 456 Q410 490 270 456 Z", fill="#8FD3F2", w=0)
        + shade("M270 430 L550 430 L550 560 Q410 600 270 560 Z")
        + R(250, 400, 320, 40, 14, "#3F96C4", "#1B4C66", 4)
        + R(380, 360, 60, 44, 10, "#2F7CA6", "#1B4C66", 3)
        + marks
        + P("M410 760 L410 812 L470 812", stroke="#1B4C66", w=12)
        + P("M452 812 l0 26 l30 0 l0 -26 Z", fill=STEEL[0], stroke=STEEL[2], w=3)
        + P("M550 690 L610 690 L610 764 L590 764 L590 710 L550 710 Z", fill=STEEL[2])
        + R(300, 770, 220, 26, 10, WOOD[2])
    )


def _pump(vid):
    return (
        R(230, 620, 360, 150, 16, STEEL[0], STEEL[2], 4)
        + C(330, 545, 88, BODY_GREEN[0], BODY_GREEN[2], 4)
        + C(330, 545, 48, "#D9CBAF", STEEL[2], 3)
        + P("M330 470 q40 -60 10 -110", stroke=STEEL[2], w=14)
        + R(410, 330, 90, 40, 10, STEEL[2])
        + P("M418 620 Q520 540 560 620", stroke=STEEL[2], w=12)
        + shade("M230 620 L590 620 L590 650 L230 650 Z")
        + R(560, 580, 90, 60, 12, "#8892A0", STEEL[2], 3)
        + "".join(f'<line x1="{575 + i * 16}" y1="586" x2="{575 + i * 16}" y2="634" stroke="{STEEL[2]}" stroke-width="4"/>' for i in range(4))
    )


def _sprinkler(vid):
    sprays = "".join(
        f'<path d="M400 620 Q{300 + i * 50} {520 - (i % 3) * 26} {240 + i * 80} 560" stroke="#6FBDEA" stroke-width="4" fill="none" opacity="0.85"/>'
        for i in range(7))
    return (
        P("M240 780 L560 780", stroke="#1B4C66", w=14)
        + P("M400 780 L400 640", stroke="#1B4C66", w=12)
        + C(400, 620, 30, STEEL[0], STEEL[2], 4)
        + R(370, 570, 60, 44, 12, "#3F96C4", "#1B4C66", 3)
        + sprays
        + "".join(f'<circle cx="{260 + i * 60}" cy="{806 + (i % 2) * 8}" r="5" fill="#6FBDEA" opacity="0.8"/>' for i in range(6))
    )


def _drip_kit(vid):
    lines = "".join(
        f'<path d="M{220 + i * 90} 560 L{220 + i * 90} 820" stroke="#2F7CA6" stroke-width="6"/>'
        f'<circle cx="{220 + i * 90}" cy="{640 + (i % 2) * 60}" r="12" fill="#6FBDEA" stroke="#1B4C66" stroke-width="3"/>'
        for i in range(5))
    return (
        R(160, 470, 500, 90, 18, "#1B4C66")
        + shade("M160 470 L660 470 L660 496 L160 496 Z")
        + R(560, 380, 120, 90, 10, STEEL[0], STEEL[2], 3)
        + lines
    )


def _pipes(vid):
    ring = "".join(
        f'<circle cx="400" cy="640" r="{120 - i * 26}" fill="none" stroke="{c}" stroke-width="20"/>'
        for i, c in enumerate(["#3F96C4", "#5BB7DF", "#8FD3F2"]))
    return (
        ring
        + P("M400 460 m-130 0 a130 130 0 0 1 260 0", fill="none", stroke="#1B4C66", w=8, op=0.5)
        + R(560, 560, 90, 30, 8, STEEL[2])
    )


def _power_sprayer(vid):
    return (
        R(300, 440, 200, 260, 40, BODY_RED[0], BODY_RED[2], 5)
        + shade("M300 440 Q400 400 500 440 L500 470 Q400 434 300 470 Z")
        + R(370, 370, 60, 70, 12, "#B8434A", BODY_RED[2], 3)
        + P("M500 520 L640 470 L650 492 L512 542 Z", fill=STEEL[0], stroke=STEEL[2], w=3)
        + C(668, 470, 20, "#D9CBAF", STEEL[2], 3)
        + "".join(f'<path d="M688 470 q26 -12 44 -4" stroke="#6FBDEA" stroke-width="4" fill="none"/>' for i in range(3))
        + P("M300 500 L240 540 L240 700 L300 680", stroke="#7A5A18", w=10, fill="none")
        + R(330, 700, 140, 30, 10, STEEL[2])
    )


def _knapsack_sprayer(vid):
    return (
        R(310, 400, 190, 300, 28, BODY_YELLOW[0], BODY_YELLOW[2], 5)
        + shade("M310 400 L500 400 L500 450 L310 450 Z")
        + R(380, 350, 50, 50, 10, "#A97C02")
        + P("M310 440 Q240 480 250 560", stroke=STEEL[2], w=8, fill="none")
        + P("M500 440 Q570 480 560 560", stroke=STEEL[2], w=8, fill="none")
        + P("M500 600 L640 640 L640 780", stroke=STEEL[2], w=8, fill="none")
        + P("M640 780 L700 820 L660 838 L622 800 Z", fill="#D63B3B", stroke=BODY_RED[2], w=3)
        + "".join(f'<path d="M690 820 q30 6 52 -2" stroke="#6FBDEA" stroke-width="3.5" fill="none"/>' for i in range(3))
    )


def _drone_sprayer(vid):
    arms = "".join(
        f'<line x1="400" y1="560" x2="{x}" y2="{y}" stroke="#1F2530" stroke-width="12"/>'
        for x, y in ((220, 440), (580, 440), (220, 680), (580, 680)))
    rotors = "".join(
        f'<g><circle cx="{x}" cy="{y}" r="58" fill="none" stroke="#6E7889" stroke-width="5"/>'
        f'<line x1="{x - 52}" y1="{y}" x2="{x + 52}" y2="{y}" stroke="#9AA6B4" stroke-width="8"/>'
        f'<line x1="{x}" y1="{y - 52}" x2="{x}" y2="{y + 52}" stroke="#9AA6B4" stroke-width="8"/></g>'
        for x, y in ((220, 440), (580, 440), (220, 680), (580, 680)))
    return (
        arms + R(330, 510, 140, 100, 22, "#2E9E4B", "#14612C", 4)
        + rotors
        + R(360, 610, 80, 46, 12, "#D9CBAF", "#4A5563", 3)
        + "".join(f'<path d="M{x} 660 q0 40 {o} 70" stroke="#6FBDEA" stroke-width="4" fill="none" opacity="0.85"/>'
                  for x, o in ((300, -14), (360, -6), (440, 6), (500, 14)))
        + C(400, 520, 12, "#F2B705", "#A97C02", 2)
    )


def _harvester(vid):
    reel = "".join(
        f'<line x1="640" y1="560" x2="{640 + 60 * __import__("math").cos(i * 1.047):.0f}" y2="{620 + 60 * __import__("math").sin(i * 1.047):.0f}" stroke="#4A5563" stroke-width="6"/>'
        for i in range(6))
    return (
        R(170, 470, 420, 190, 20, BODY_YELLOW[0], BODY_YELLOW[2], 5)
        + R(420, 350, 160, 130, 14, "#A97C02", BODY_YELLOW[2], 4)
        + R(440, 372, 90, 66, 8, GLASS, "#3A5866", 3)
        + shade("M170 470 L590 470 L590 502 L170 502 Z")
        + wheel(250, 700, 92) + wheel(520, 710, 66)
        + P("M590 600 L660 560 L660 660 L600 660 Z", fill=STEEL[0], stroke=STEEL[2], w=3)
        + reel + C(640, 620, 20, "#C9D2DC", "#4A5563", 3)
    )


def _thresher(vid):
    return (
        R(230, 520, 340, 180, 16, BODY_RED[0], BODY_RED[2], 4)
        + C(400, 500, 60, "#D9CBAF", STEEL[2], 4)
        + "".join(f'<line x1="400" y1="500" x2="{400 + 90 * __import__("math").cos(i * 0.785):.0f}" y2="{500 + 90 * __import__("math").sin(i * 0.785):.0f}" stroke="{STEEL[2]}" stroke-width="6"/>' for i in range(8))
        + P("M230 560 L140 640 L170 660 L240 600 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=3)
        + R(430, 640, 150, 40, 10, WOOD[0], WOOD[2], 3)
        + "".join(f'<path d="M{450 + i * 28} 680 q6 60 -4 110" stroke="#A97C50" stroke-width="4" fill="none" opacity="0.7"/>' for i in range(5))
        + wheel(300, 740, 58) + wheel(520, 740, 58)
    )


def _paddy_cutter(vid):
    return (
        P("M180 640 L560 600 L600 660 L200 700 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + "".join(f'<path d="M{210 + i * 46} 690 l10 34 l14 -30 Z" fill="{STEEL[1]}" stroke="{STEEL[2]}" stroke-width="2"/>' for i in range(8))
        + P("M600 620 Q680 600 700 520", stroke="#4A5563", w=10, fill="none")
        + R(660, 470, 90, 54, 12, BODY_RED[0], BODY_RED[2], 3)
        + P("M180 640 L120 560", stroke=WOOD[2], w=10)
    )


def _sickle(vid):
    return (
        P("M280 640 Q260 460 460 420 Q620 400 660 500 Q560 450 460 480 Q340 520 320 660 Z",
          fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + P("M282 648 L250 760 Q244 790 274 792 L304 780 L322 664 Z", fill=WOOD[0], stroke=WOOD[2], w=4)
        + shade("M300 600 Q300 470 460 440 Q560 430 620 470 Q540 460 460 470 Q330 500 320 620 Z", op=0.5)
    )


def _winnowing_fan(vid):
    return (
        C(400, 560, 140, "#D9CBAF", STEEL[2], 5)
        + "".join(f'<path d="M400 560 L{400 + 120 * __import__("math").cos(i * 0.698):.0f} {560 + 120 * __import__("math").sin(i * 0.698):.0f}" stroke="{STEEL[2]}" stroke-width="5"/>' for i in range(9))
        + R(270, 700, 260, 90, 14, WOOD[0], WOOD[2], 4)
        + P("M400 560 m-24 0 a24 24 0 1 0 48 0 a24 24 0 1 0 -48 0", fill=STEEL[0], stroke=STEEL[2], w=3)
        + "".join(f'<path d="M560 {520 + i * 24} q30 6 54 0" stroke="#A97C50" stroke-width="4" fill="none" opacity="0.7"/>' for i in range(4))
    )


def _spade(vid):
    return (
        R(384, 360, 32, 360, 10, WOOD[0], WOOD[2], 4)
        + R(350, 330, 100, 40, 16, WOOD[0], WOOD[2], 4)
        + P("M330 720 L470 720 L450 830 Q400 872 350 830 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + P("M400 730 L400 850", stroke=STEEL[2], w=5, op=0.6)
        + shade("M330 720 L470 720 L462 758 L338 758 Z")
    )


def _pickaxe(vid):
    return (
        R(388, 380, 26, 420, 8, WOOD[0], WOOD[2], 4)
        + P("M240 420 Q400 300 560 420 Q400 372 240 420 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + P("M240 420 L200 460 L258 428 Z", fill=STEEL[2])
        + P("M560 420 L600 460 L542 428 Z", fill=STEEL[2])
        + shade("M280 404 Q400 336 520 404 Q400 376 280 404 Z", op=0.5)
    )


def _axe(vid):
    return (
        R(392, 350, 26, 460, 8, WOOD[0], WOOD[2], 4)
        + P("M418 380 Q560 400 540 520 Q470 560 412 520 Z", fill=f"url(#mt{vid})", stroke=STEEL[2], w=4)
        + P("M540 400 Q592 460 540 540", stroke="#E8EEF4", w=8, fill="none", op=0.8)
        + R(378, 330, 54, 30, 8, STEEL[2])
    )


def _crowbar(vid):
    return (
        P("M300 820 Q270 700 340 640 L470 350 Q500 300 560 320", stroke=f"url(#mt{vid})", w=26, fill="none")
        + P("M300 820 Q330 860 380 848", stroke=STEEL[2], w=26, fill="none")
        + P("M470 400 L520 420", stroke=BODY_RED[0], w=26, op=0.9)
    )


def _ladder(vid):
    rails = (P("M300 340 L280 880", stroke=WOOD[0], w=18) + P("M500 340 L520 880", stroke=WOOD[0], w=18)
             + P("M300 340 L280 880", stroke=WOOD[2], w=4, fill="none"))
    rungs = "".join(
        f'<line x1="{302 + i * 2.6:.0f}" y1="{400 + i * 62}" x2="{498 + i * 2.6:.0f}" y2="{400 + i * 62}" '
        f'stroke="{WOOD[1]}" stroke-width="12"/><line x1="{302 + i * 2.6:.0f}" y1="{406 + i * 62}" x2="{498 + i * 2.6:.0f}" y2="{406 + i * 62}" stroke="{WOOD[2]}" stroke-width="3" opacity="0.6"/>'
        for i in range(8))
    return rails + rungs


def _drill_machine(vid):
    return (
        R(260, 470, 300, 150, 26, BODY_RED[0], BODY_RED[2], 5)
        + R(300, 620, 80, 150, 14, BODY_RED[2])
        + R(560, 500, 150, 60, 10, f"url(#mt{vid})", STEEL[2], 3)
        + P("M710 530 L780 512 L780 548 Z", fill=STEEL[2])
        + C(520, 500, 18, "#F2B705", "#A97C02", 3)
        + shade("M260 470 L560 470 L560 496 L260 496 Z")
        + P("M420 470 Q460 420 540 450", stroke=STEEL[2], w=10, fill="none")
    )


def _grinder(vid):
    return (
        R(260, 500, 260, 130, 24, "#4A5563", "#23282F", 4)
        + C(560, 565, 86, "#8892A0", "#23282F", 5)
        + C(560, 565, 30, "#31383F")
        + "".join(f'<path d="M{560 + 70 * __import__("math").cos(i * 1.047):.0f} {565 + 70 * __import__("math").sin(i * 1.047):.0f} l14 10" stroke="{STEEL[1]}" stroke-width="5"/>' for i in range(6))
        + R(300, 440, 120, 60, 12, "#23282F")
        + P("M260 560 L180 620 L200 660 L280 610", fill="#4A5563", stroke="#23282F", w=3)
        + shade("M300 500 L500 500 L500 524 L300 524 Z")
    )


def _welding_machine(vid):
    sparks = "".join(
        f'<path d="M{620 + (i * 26) % 90} {560 - (i * 37) % 80} l12 -18" stroke="#F2B705" stroke-width="4"/>'
        for i in range(6))
    return (
        R(220, 470, 340, 220, 18, DARK[0], DARK[2], 5)
        + C(320, 560, 34, "#C9D2DC", DARK[2], 3)
        + R(400, 520, 110, 60, 8, "#1E222B", "#6E7889", 3)
        + P("M560 500 Q660 470 690 540 L640 580", stroke="#8F1D1D", w=10, fill="none")
        + sparks + C(668, 545, 16, "#FCDE85")
        + P("M220 620 L150 700", stroke="#1E222B", w=8)
        + R(250, 420, 180, 30, 10, "#6E7889")
    )


def _chainsaw(vid):
    teeth = "".join(
        f'<path d="M{540 + i * 26} 560 l10 -12 l10 12 Z" fill="{STEEL[1]}"/>'
        f'<path d="M{540 + i * 26} 604 l10 12 l10 -12 Z" fill="{STEEL[1]}"/>'
        for i in range(6))
    return (
        R(240, 480, 260, 140, 26, BODY_ORANGE, "#A34700", 5)
        + P("M500 500 L760 500 L760 580 L500 580 Z", fill="none", stroke=STEEL[2], w=8)
        + teeth
        + P("M270 480 Q300 400 420 420 L500 480", fill="none", stroke="#23282F", w=14)
        + C(400, 550, 16, "#F2B705", "#A97C02", 3)
        + shade("M240 480 L500 480 L500 505 L240 505 Z")
    )


BODY_ORANGE = "#E8720C"


def _brush_cutter(vid):
    return (
        P("M240 420 L420 380 L470 430 L300 480 Z", fill=BODY_ORANGE, stroke="#A34700", w=4)
        + R(420, 420, 200, 50, 16, "#4A5563", "#23282F", 3)
        + P("M560 470 Q640 620 560 760", stroke="#23282F", w=12, fill="none")
        + P("M560 760 L640 800", stroke="#8892A0", w=10)
        + C(680, 812, 44, "none", STEEL[2], 6)
        + "".join(f'<path d="M{680 + 44 * __import__("math").cos(i * 1.047):.0f} {812 + 44 * __import__("math").sin(i * 1.047):.0f} l12 8" stroke="{STEEL[1]}" stroke-width="5"/>' for i in range(6))
        + P("M240 420 Q180 380 160 320", stroke="#23282F", w=10, fill="none")
    )


def _generator(vid):
    return (
        R(200, 480, 420, 240, 22, "#4A5563", "#23282F", 5)
        + shade("M200 480 L620 480 L620 512 L200 512 Z")
        + R(230, 510, 150, 90, 12, "#1E222B", "#6E7889", 3)
        + C(300, 640, 26, "#C9D2DC", "#23282F", 4)
        + P("M430 560 L480 500 L455 560 L510 520 L460 600 L492 588 Z", fill="#F2B705")
        + R(240, 440, 340, 34, 12, "#23282F")
        + C(560, 560, 22, "#D63B3B", "#8F1D1D", 3)
    )


def _cart(vid):
    return (
        P("M200 520 L620 520 L590 680 L230 680 Z", fill=WOOD[0], stroke=WOOD[2], w=5)
        + "".join(f'<line x1="{230 + i * 55}" y1="526" x2="{240 + i * 52}" y2="674" stroke="{WOOD[2]}" stroke-width="4"/>' for i in range(7))
        + shade("M200 520 L620 520 L612 552 L208 552 Z")
        + wheel(300, 740, 78) + wheel(540, 740, 78)
        + P("M200 560 Q120 600 100 680", stroke=WOOD[2], w=10, fill="none")
    )


def _storage_tank(vid):
    return (
        R(240, 400, 340, 380, 24, "#7E8894", "#4A5563", 5)
        + P("M240 440 Q410 480 580 440", stroke="#B9C0C8", w=8, fill="none")
        + shade("M240 400 Q410 360 580 400 L580 430 Q410 396 240 430 Z")
        + C(410, 380, 26, "#4A5563")
        + "".join(f'<line x1="240" y1="{500 + i * 60}" x2="580" y2="{500 + i * 60}" stroke="#4A5563" stroke-width="5" opacity="0.7"/>' for i in range(4))
        + P("M580 700 L640 700 L640 770", stroke="#4A5563", w=12, fill="none")
    )


def _grain_bin(vid):
    grain = "".join(
        f'<circle cx="{260 + i * 24}" cy="{560 - (i % 4) * 10}" r="7" fill="#E4C36A"/>'
        for i in range(13))
    return (
        P("M250 560 L560 560 L530 830 L280 830 Z", fill=STEEL[0], stroke=STEEL[2], w=5)
        + P("M230 560 Q405 470 580 560 Q405 520 230 560 Z", fill="#C9D2DC", stroke=STEEL[2], w=4)
        + grain
        + "".join(f'<line x1="275" y1="{620 + i * 60}" x2="535" y2="{620 + i * 60}" stroke="{STEEL[2]}" stroke-width="4" opacity="0.7"/>' for i in range(3))
        + R(360, 760, 90, 70, 8, "#6E4A28", STEEL[2], 3)
    )


def _tarpaulin(vid):
    folds = "".join(
        f'<path d="M{230 + i * 60} 560 Q{260 + i * 60} {640 - (i % 3) * 30} {230 + i * 60} 760" '
        f'stroke="#1B4C66" stroke-width="4" fill="none" opacity="0.5"/>'
        for i in range(6))
    eyes = "".join(
        f'<circle cx="{x}" cy="{y}" r="7" fill="none" stroke="#F2B705" stroke-width="3"/>'
        for x, y in ((216, 545), (400, 522), (588, 545), (212, 775), (400, 796), (592, 775)))
    return (
        P("M210 540 Q400 490 594 540 L612 770 Q400 820 192 770 Z", fill="#3F6E8C", stroke="#1B4C66", w=5)
        + shade("M210 540 Q400 500 594 540 L590 590 Q400 552 214 590 Z")
        + folds + eyes
    )


# ---------------------------------------------------------------------------
# Registry + public entry
# ---------------------------------------------------------------------------
def _reg(name, fn):
    return (_norm(name), fn)


_REGISTRY = {
    "minitractor": _tractor(False), "tractor3550hp": _tractor(True),
    "tractor50hp": _tractor(True), "tractor": _tractor(True),
    "plough": _plough, "rotavator": _rotavator, "cultivator": _cultivator,
    "seeddrill": _drill, "seedrill": _drill, "trolley": _trolley, "harrow": _harrow, "leveller": _leveller,
    "watertank": _water_tank, "waterpump": _pump, "sprinklerset": _sprinkler,
    "sprinkler": _sprinkler, "dripkit": _drip_kit, "pipesandhoses": _pipes,
    "powersprayer": _power_sprayer, "knapsacksprayer": _knapsack_sprayer,
    "dronesprayer": _drone_sprayer, "drone": _drone_sprayer,
    "harvester": _harvester, "thresher": _thresher, "paddycutter": _paddy_cutter,
    "sickleset": _sickle, "sickle": _sickle, "winnowingfan": _winnowing_fan,
    "tiller": _cultivator, "handweeder": _sickle, "postholedigger": _spade,
    "spade": _spade, "pickaxe": _pickaxe, "axe": _axe, "crowbar": _crowbar,
    "ladder": _ladder, "drillmachine": _drill_machine, "grinder": _grinder,
    "weldingmachine": _welding_machine, "chainsaw": _chainsaw,
    "brushcutter": _brush_cutter, "generator": _generator, "cart": _cart,
    "storagetank": _storage_tank, "grainbin": _grain_bin, "tarpaulin": _tarpaulin,
    "farm_tools": _tractor(True), "tractorattachments": _plough, "attachments": _plough,
    "waterandirrigation": _water_tank, "watertank": _water_tank,
    "sprayingandpestcontrol": _knapsack_sprayer, "sprayer": _knapsack_sprayer,
    "harvesting": _harvester, "soilandlandpreparation": _cultivator, "soil": _cultivator,
    "handtools": _spade, "hand_tools": _spade, "powertools": _drill_machine,
    "power_tools": _drill_machine, "transportstorage": _cart,
    "transport": _cart, "other": _cart,
}


def resolve_key(subcat_key="", tool_type="", category="farm_tools"):
    """Pick the registry key: tool_type first, then sub-cat, then category."""
    for cand in (tool_type, subcat_key, category):
        k = _norm(cand)
        if k and k in _REGISTRY:
            return k
    return None


def make_tool_art(tool_type="", subcat_key="", slug="", label="") -> str:
    """Return the 800x1000 SVG for a farm tool."""
    key = resolve_key(subcat_key, tool_type) or "other"
    vid = _vid(slug or key)
    drawer = _REGISTRY[key]
    body = drawer(vid)
    caption = label or tool_type or subcat_key or key
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img" aria-label="{esc(caption)}">'
            + scene_bg(vid) + floor(vid) + body + label_ribbon(caption, vid)
            + '</svg>')
