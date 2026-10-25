"""Electronics, security and furniture art (ART stage 2) - generated SVG.

make_misc_art(category, type_value, subcat_key, ...) returns an 800x1000 SVG
with the same studio quality as the other art families: gradient background
tinted per category, floor shadow, shading and highlights, label ribbon.
Lookup order: type attribute value -> sub-category key -> category default.
"""
from __future__ import annotations

from utils.art_tools import (W, H, P, C, R, wheel, esc, _norm, _vid,
                             STEEL, WOOD, DARK, GLASS, shade as _hl,
                             BODY_GREEN, BODY_RED, BODY_YELLOW)


def R_(x, y, w_, h_, rx, fill, stroke=None, w=3, op=None):
    s = R(x, y, w_, h_, rx, fill, stroke, w)
    if op is not None:
        s = s.replace('/>', f' opacity="{op}"/>')
    return s

TINT = {
    "electronics": "#E8F0FA",
    "security": "#EAEFF3",
    "furniture": "#F6EFE4",
    "other": "#EAF3FA",
}

ACCENT = ("#3B4250", "#5BB7DF", "#1E222B")


def scene_bg(vid, tint):
    return (f'<defs>'
            f'<linearGradient id="bg{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{tint}"/>'
            f'<stop offset="72%" stop-color="#FFFFFF"/>'
            f'<stop offset="100%" stop-color="#DCE3EA" stop-opacity="0.6"/></linearGradient>'
            f'<radialGradient id="fl{vid}" cx="0.5" cy="0.5" r="0.5">'
            f'<stop offset="0%" stop-color="#000000" stop-opacity="0.25"/>'
            f'<stop offset="100%" stop-color="#000000" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="mt{vid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{STEEL[1]}"/>'
            f'<stop offset="55%" stop-color="{STEEL[0]}"/>'
            f'<stop offset="100%" stop-color="{STEEL[2]}"/></linearGradient>'
            f'<linearGradient id="sc{vid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="#123A5A"/>'
            f'<stop offset="60%" stop-color="#2A7AB8"/>'
            f'<stop offset="100%" stop-color="#6FBDEA"/></linearGradient>'
            f'</defs>'
            f'<rect width="{W}" height="{H}" fill="url(#bg{vid})"/>')


def floor(vid):
    return f'<ellipse cx="400" cy="874" rx="300" ry="36" fill="url(#fl{vid})"/>'


def label_ribbon(name, vid):
    t = esc(name if len(str(name or "")) <= 26 else str(name)[:25] + "…")
    return (f'<g><path d="M250 928 L550 928 L566 952 L550 976 L250 976 L234 952 Z" '
            f'fill="url(#mt{vid})" stroke="#37414F" stroke-width="2.5"/>'
            f'<rect x="258" y="934" width="284" height="8" rx="4" fill="#FFFFFF" opacity="0.45"/>'
            f'<text x="400" y="961" text-anchor="middle" font-family="Noto Sans, Noto Sans Devanagari, '
            f'Noto Sans Telugu, Noto Sans Kannada, Arial, sans-serif" font-size="24" '
            f'font-weight="700" fill="#1E222B">{t}</text></g>')


# ---------------------------------------------------------------------------
# Electronics
# ---------------------------------------------------------------------------
def _camera(vid):
    return (
        R(220, 480, 360, 220, 24, DARK[0], DARK[2], 5)
        + R(300, 440, 130, 46, 12, DARK[2])
        + R(250, 500, 80, 24, 8, "#6E7889")
        + C(470, 590, 96, "#31383F", "#8892A0", 6)
        + C(470, 590, 66, "#12304A", "#6E7889", 4)
        + C(470, 590, 40, "url(#sc" + vid + ")")
        + C(470, 590, 14, "#0B1620")
        + P("M436 556 a44 44 0 0 1 40 -18", fill="none", stroke="#FFFFFF", w=6, op=0.6)
        + C(560, 500, 12, "#D63B3B", "#8F1D1D", 2)
        + R(240, 660, 60, 20, 6, "#6E7889")
        + _hl("M220 480 L580 480 L580 512 L220 512 Z")
    )


def _laptop(vid):
    return (
        P("M230 430 L570 430 L570 660 L230 660 Z", fill=DARK[2], stroke="#12161D", w=5)
        + P("M246 446 L554 446 L554 644 L246 644 Z", fill="url(#sc" + vid + ")")
        + P("M246 446 L554 446 L554 470 L246 500 Z", fill="#FFFFFF", op=0.18, w=0)
        + P("M190 660 L610 660 L650 720 L150 720 Z", fill="#6E7889", stroke=DARK[2], w=5)
        + R(230, 676, 340, 20, 6, "#3B4250")
        + "".join(f'<line x1="{240 + i * 26}" y1="682" x2="{240 + i * 26}" y2="690" stroke="#8892A0" stroke-width="4"/>' for i in range(14))
        + R(360, 700, 80, 12, 4, "#4A5563")
    )


def _projector(vid):
    beam = P("M520 560 L760 400 L760 780 L520 640 Z", fill="#FCE78A", op=0.35, w=0)
    cone = P("M520 570 L700 470 L700 700 L520 630 Z", fill="#FCE78A", op=0.3, w=0)
    return (
        R(200, 540, 340, 160, 26, "#E8EEF4", STEEL[2], 5)
        + _hl("M200 540 L540 540 L540 574 L200 574 Z")
        + C(500, 600, 46, "#31383F", STEEL[2], 5) + C(500, 600, 26, "url(#sc" + vid + ")")
        + R(240, 570, 90, 40, 8, "#C9D2DC", STEEL[2], 3)
        + C(300, 660, 12, DARK[2]) + C(440, 660, 12, DARK[2])
        + P("M270 540 L270 500 L400 500 L400 540", fill="none", stroke=STEEL[2], w=10)
        + beam + cone
        + "".join(f'<line x1="560" y1="{500 + i * 40}" x2="740" y2="{440 + i * 60}" stroke="#FCE78A" stroke-width="4" opacity="0.5"/>' for i in range(4))
    )


def _speaker_e(vid):
    waves = "".join(f'<path d="M560 480 q{40 + i * 26} {50 + i * 26} 0 {110 + i * 44}" fill="none" stroke="#5BB7DF" stroke-width="7" opacity="{0.85 - i * 0.22}"/>' for i in range(3))
    return (
        R(230, 380, 300, 470, 22, DARK[0], DARK[2], 6)
        + _hl("M230 380 L530 380 L530 404 L230 404 Z")
        + C(380, 520, 88, "#23282F", "#6E7889", 6) + C(380, 520, 46, "#4A5563") + C(380, 520, 16, "#8892A0")
        + C(380, 700, 56, "#23282F", "#6E7889", 5) + C(380, 700, 26, "#4A5563")
        + R(250, 400, 260, 12, 6, ACCENT[1])
        + waves
        + R(210, 850, 340, 18, 8, "#31383F")
    )


def _microphone_e(vid):
    grille = "".join(f'<line x1="{330 + i * 10}" y1="{y}" x2="{330 + i * 10 + 6}" y2="{y}" stroke="#23282F" stroke-width="2.5"/>'
                     for i in range(13) for y in range(400, 520, 16))
    return (
        f'<rect x="330" y="380" width="140" height="170" rx="70" fill="url(#mt{vid})" stroke="{DARK[2]}" stroke-width="5"/>'
        + grille
        + R(384, 550, 32, 210, 12, "#31383F", DARK[2], 4)
        + R(366, 750, 68, 30, 10, DARK[2])
        + P("M400 800 L400 850", stroke="#31383F", w=12, fill="none")
        + f'<ellipse cx="400" cy="864" rx="110" ry="18" fill="#23282F"/>'
        + _hl("M344 400 Q400 370 456 400 L452 440 Q400 414 348 440 Z")
    )


def _led_screen(vid):
    shows = (R(250, 330, 300, 176, 4, "#123A5A")
             + P("M250 470 L340 400 L410 450 L480 380 L550 440 L550 506 L250 506 Z", fill="#2E9E4B", op=0.7, w=0)
             + C(500, 366, 20, "#F2B705"))
    return (
        R(200, 280, 400, 280, 12, "#12161D", "#3B4250", 8)
        + shows
        + P("M380 560 L420 560 L410 700 L390 700 Z", fill="#6E7889", stroke=DARK[2], w=3)
        + R(310, 700, 180, 22, 8, DARK[0], DARK[2], 3)
        + R(220, 258, 360, 8, 4, ACCENT[1])
    )


def _drone_e(vid):
    arms = "".join(f'<line x1="400" y1="560" x2="{x}" y2="{y}" stroke="#3B4250" stroke-width="14"/>'
                   for x, y in ((230, 440), (570, 440), (230, 680), (570, 680)))
    rotors = "".join(
        f'<g><circle cx="{x}" cy="{y}" r="62" fill="none" stroke="#8892A0" stroke-width="5"/>'
        f'<line x1="{x - 56}" y1="{y}" x2="{x + 56}" y2="{y}" stroke="#C9D2DC" stroke-width="9"/>'
        f'<circle cx="{x}" cy="{y}" r="10" fill="#31383F"/></g>'
        for x, y in ((230, 440), (570, 440), (230, 680), (570, 680)))
    return (
        arms + R(330, 505, 140, 110, 26, "#E8EEF4", DARK[2], 5)
        + rotors
        + C(400, 560, 20, "#23282F", "#6E7889", 3) + C(400, 560, 8, ACCENT[1])
        + R(370, 615, 60, 40, 12, "#31383F", DARK[2], 3) + C(400, 635, 12, "url(#sc" + vid + ")")
        + P("M340 470 q60 -30 120 0", fill="none", stroke="#D63B3B", w=5, op=0.8)
    )


def _lights_e(vid):
    string = P("M140 460 Q280 560 400 470 Q520 380 660 470", fill="none", stroke="#4A5563", w=5)
    bulbs = "".join(
        f'<g><path d="M{x - 12} {y} h24 v14 h-24 Z" fill="#31383F"/>'
        f'<circle cx="{x}" cy="{y + 34}" r="20" fill="#FCE78A" stroke="#A97C02" stroke-width="2.5"/>'
        f'<circle cx="{x}" cy="{y + 34}" r="34" fill="#FCE78A" opacity="0.28"/></g>'
        for x, y in [(190, 476), (270, 516), (350, 502), (430, 452), (510, 416), (590, 424), (650, 460)])
    stand = R(300, 700, 200, 120, 14, "#6E7889", DARK[2], 4) + P("M400 660 L400 700", stroke=DARK[2], w=10, fill="none")
    return string + bulbs + stand + _hl("M300 700 L500 700 L500 720 L300 720 Z")


def _console(vid):
    pad = (R(280, 620, 240, 130, 40, DARK[0], DARK[2], 5)
           + C(330, 668, 18, "#31383F", "#6E7889", 3) + C(470, 668, 18, "#31383F", "#6E7889", 3)
           + R(384, 646, 32, 10, 4, "#6E7889") + R(394, 636, 12, 30, 4, "#6E7889")
           + C(330, 668, 6, ACCENT[1]))
    console = (R(300, 420, 200, 150, 18, "#23282F", DARK[2], 5)
               + R(320, 440, 160, 8, 4, ACCENT[1])
               + C(400, 500, 30, "#31383F", "#6E7889", 4)
               + P("M360 540 L440 540", stroke="#6E7889", w=8, fill="none"))
    return console + pad + P("M400 570 L400 620", stroke=DARK[2], w=8, fill="none")


def _power_bank(vid):
    bolt = P("M400 470 L360 570 L400 570 L378 660 L450 540 L404 540 L430 470 Z", fill="#F2B705", stroke="#A97C02", w=3)
    lit = "#2E9E4B"
    dead = "#6E7889"
    cells = "".join(f'<rect x="{290 + i * 80}" y="700" width="60" height="16" rx="6" fill="{lit if i < 3 else dead}"/>' for i in range(4))
    return (
        R(260, 420, 280, 340, 30, "#3B4250", "#1E222B", 6)
        + _hl("M260 420 Q400 396 540 420 L540 460 Q400 436 260 460 Z")
        + bolt + cells
        + R(300, 760, 200, 30, 10, "#23282F", "#4A5563", 3)
        + C(400, 400, 14, ACCENT[1], DARK[2], 3)
    )


def _generator_e(vid):
    return (
        R(210, 500, 380, 220, 18, "#4A5563", "#23282F", 6)
        + _hl("M210 500 L590 500 L590 528 L210 528 Z")
        + R(240, 530, 140, 80, 10, "#1E222B", "#6E7889", 3)
        + C(310, 640, 24, "#C9D2DC", "#23282F", 4)
        + P("M430 570 L480 510 L456 570 L510 530 L462 610 L494 598 Z", fill="#F2B705")
        + R(240, 460, 320, 30, 10, "#23282F")
        + wheel(270, 760, 42) + wheel(530, 760, 42)
        + P("M590 640 L650 640 L650 680", stroke="#23282F", w=10, fill="none")
    )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
def _dome_cctv(vid):
    return (
        R(250, 400, 300, 40, 10, "#E8EEF4", STEEL[2], 4)
        + P("M300 440 A100 100 0 0 0 500 440 Z", fill="url(#mt" + vid + ")", stroke=STEEL[2], w=4)
        + P("M318 442 A82 82 0 0 0 482 442 Z", fill="#1E2A36", stroke="#0B1620", w=3)
        + P("M340 428 a52 52 0 0 1 60 -18", fill="none", stroke="#FFFFFF", w=6, op=0.5)
        + C(400, 470, 10, "#D63B3B") + C(400, 470, 20, "#D63B3B", op=0.35)
        + R(370, 496, 60, 12, 4, "#8892A0")
    )


def _bullet_cctv(vid):
    return (
        R(360, 420, 40, 120, 8, "#8892A0", STEEL[2], 3)
        + R(300, 380, 20, 60, 6, "#6E7889")
        + P("M220 560 L460 500 L470 570 L230 630 Z", fill="#E8EEF4", stroke=STEEL[2], w=5)
        + P("M460 500 L520 490 L528 556 L470 570 Z", fill="#C9D2DC", stroke=STEEL[2], w=4)
        + C(500, 524, 26, "#12161D", "#4A5563", 4) + C(494, 516, 8, "#5BB7DF", op=0.8)
        + R(210, 540, 30, 100, 8, "#31383F")
        + P("M240 640 L240 700", stroke=STEEL[2], w=10, fill="none")
        + R(190, 700, 110, 22, 8, STEEL[2])
        + _hl("M224 566 L456 512 L458 528 L226 582 Z")
    )


def _ptz_cctv(vid):
    return (
        R(340, 360, 120, 36, 10, "#E8EEF4", STEEL[2], 4)
        + P("M356 396 L444 396 L430 470 L370 470 Z", fill="#C9D2DC", stroke=STEEL[2], w=4)
        + C(400, 560, 100, "#31383F", "#12161D", 5)
        + C(400, 560, 64, "url(#sc" + vid + ")")
        + C(400, 560, 24, "#0B1620", "#6E7889", 3)
        + P("M356 528 a56 56 0 0 1 44 -24", fill="none", stroke="#FFFFFF", w=6, op=0.5)
        + R(386, 660, 28, 150, 8, STEEL[0], STEEL[2], 3)
        + R(330, 806, 140, 22, 8, STEEL[2])
        + C(472, 470, 8, "#D63B3B")
    )


def _gate_detector(vid):
    def post(x):
        return (R(x, 380, 56, 470, 18, "#E8EEF4", STEEL[2], 5)
                + "".join(f'<rect x="{x + 10}" y="{420 + i * 62}" width="36" height="30" rx="6" fill="{["#2E9E4B", "#F2B705", "#D63B3B"][i % 3]}" opacity="0.75"/>' for i in range(6))
                + R(x - 8, 360, 72, 26, 10, STEEL[2]))
    top = P("M232 340 Q400 240 568 340 L560 366 Q400 274 240 366 Z", fill="#C9D2DC", stroke=STEEL[2], w=4)
    return (post(210) + post(534) + top
            + C(400, 300, 26, "#1E222B", "#8892A0", 3)
            + P("M400 288 v10 M392 300 h16", stroke="#5BB7DF", w=4, fill="none")
            + P("M266 850 L534 850", stroke="#8892A0", w=8, fill="none")
            + "".join(f'<path d="M{300 + i * 50} 620 q10 -30 0 -60" stroke="#5BB7DF" stroke-width="3" fill="none" opacity="0.6"/>' for i in range(4)))


def _handheld_detector(vid):
    return (
        P("M320 820 L320 560 Q320 520 360 520 L440 520 Q480 520 480 560 L480 820 Q480 850 400 850 Q320 850 320 820 Z",
          fill="#E8EEF4", stroke=STEEL[2], w=5)
        + R(344, 640, 112, 160, 20, "#3B4250", "#1E222B", 4)
        + "".join(f'<line x1="{360 + i * 24}" y1="660" x2="{360 + i * 24}" y2="780" stroke="#5BB7DF" stroke-width="6" opacity="0.8"/>' for i in range(5))
        + R(352, 552, 96, 60, 12, "#C9D2DC", STEEL[2], 3)
        + C(460, 576, 12, "#D63B3B", "#8F1D1D", 2)
        + P("M400 520 L400 420 Q400 380 440 380 L560 380", fill="none", stroke=STEEL[2], w=12)
        + C(580, 380, 22, "#8892A0", STEEL[2], 4)
    )


def _xray_scanner(vid):
    belt = "".join(f'<line x1="{250 + i * 40}" y1="700" x2="{250 + i * 40}" y2="730" stroke="#4A5563" stroke-width="8"/>' for i in range(9))
    screen = (R(480, 380, 180, 130, 10, "#0B1620", "#3B4250", 5)
              + P("M500 500 L540 430 L580 470 L620 410 L640 440 L640 500 Z", fill="#2E9E4B", op=0.7, w=0)
              + R_(492, 392, 156, 10, 4, "#5BB7DF", op=0.6))
    return (
        R(180, 540, 440, 220, 20, "#E8EEF4", STEEL[2], 6)
        + P("M280 560 L420 560 L420 740 L280 740 Z", fill="#12161D", stroke="#3B4250", w=5)
        + P("M300 580 L400 580 L400 720 L300 720 Z", fill="#1E2A36")
        + P("M312 600 q40 60 20 100 M360 596 q10 70 34 96", stroke="#5BB7DF", w=5, fill="none", op=0.8)
        + belt + screen
        + R(180, 500, 440, 30, 8, "#C9D2DC", STEEL[2], 3)
        + C(210, 650, 10, "#D63B3B") + C(590, 650, 10, "#2E9E4B")
    )


def _walkie_set(vid):
    def radio(x, col):
        return (f'<g transform="translate({x} 0)">'
                + R(0, 520, 110, 260, 18, "#23282F", "#12161D", 5)
                + R(30, 460, 14, 64, 6, "#31383F")
                + C(37, 452, 10, "#12161D")
                + R(14, 548, 82, 60, 8, "#0B1620", "#4A5563", 3)
                + R(22, 560, 66, 10, 4, col) + R_(22, 578, 44, 10, 4, col, op=0.6)
                + "".join(f'<line x1="{20 + i * 14}" y1="628" x2="{20 + i * 14}" y2="648" stroke="#6E7889" stroke-width="5"/>' for i in range(6))
                + R(28, 664, 54, 30, 8, "#3B4250", "#6E7889", 2)
                + P("M96 540 Q140 560 132 640", fill="none", stroke="#4A5563", w=5, op=0.8)
                + "</g>")
    waves = "".join(f'<path d="M400 400 q{26 + i * 22} {16 + i * 12} {10 + i * 6} {52 + i * 26}" fill="none" stroke="#5BB7DF" stroke-width="4" opacity="{0.8 - i * 0.2}"/>' for i in range(3))
    return radio(240, "#2E9E4B") + radio(450, "#D63B3B") + waves + P("M400 380 q-4 -30 8 -44", stroke="#5BB7DF", w=4, fill="none", op=0.8)


def _barricades(vid):
    def panel(x):
        return (f'<g transform="translate({x} 0)">'
                + P("M0 560 L200 560 L200 720 L0 720 Z", fill="none", stroke="#8892A0", w=8)
                + "".join(f'<line x1="{24 + i * 30}" y1="568" x2="{184 - i * 30}" y2="712" stroke="{BODY_YELLOW[0]}" stroke-width="14"/>' for i in range(6))
                + P("M0 560 L200 560 L200 720 L0 720 Z", fill="none", stroke="#4A5563", w=4)
                + R(20, 720, 16, 90, 4, "#6E7889") + R(164, 720, 16, 90, 4, "#6E7889")
                + R(-6, 806, 60, 16, 6, "#31383F") + R(146, 806, 60, 16, 6, "#31383F")
                + "</g>")
    return panel(120) + panel(340) + panel(560) + C(220, 528, 12, "#D63B3B", op=0.8)


def _other_misc(vid):
    return (R(280, 500, 240, 220, 20, "#C9D2DC", STEEL[2], 5)
            + _hl("M280 500 L520 500 L520 530 L280 530 Z")
            + C(400, 610, 40, "#3B4250", STEEL[2], 4) + C(400, 610, 14, ACCENT[1])
            + R(320, 720, 160, 24, 8, STEEL[2]))


# ---------------------------------------------------------------------------
# Furniture
# ---------------------------------------------------------------------------
def _f_chair(vid):
    return (
        R(320, 420, 160, 190, 18, WOOD[0], WOOD[2], 5)
        + _hl("M320 420 L480 420 L480 452 L320 452 Z")
        + R(290, 610, 220, 34, 10, WOOD[1], WOOD[2], 4)
        + P("M310 644 L300 840 M490 644 L500 840 M330 644 L340 800 M470 644 L460 800", stroke=WOOD[2], w=10, fill="none")
        + "".join(f'<line x1="330" y1="{460 + i * 34}" x2="470" y2="{460 + i * 34}" stroke="{WOOD[2]}" stroke-width="4" opacity="0.5"/>' for i in range(4))
    )


def _f_sofa(vid):
    return (
        R(160, 470, 480, 150, 26, "#7A9CC4", "#3D5B80", 6)
        + R(200, 490, 130, 120, 16, "#A8C4E4", "#3D5B80", 3)
        + R(340, 490, 130, 120, 16, "#A8C4E4", "#3D5B80", 3)
        + R(480, 490, 130, 120, 16, "#A8C4E4", "#3D5B80", 3)
        + R(140, 590, 70, 200, 20, "#6988B0", "#3D5B80", 5)
        + R(590, 590, 70, 200, 20, "#6988B0", "#3D5B80", 5)
        + R(200, 620, 400, 90, 18, "#8FB2D8", "#3D5B80", 5)
        + _hl("M200 620 L600 620 L600 650 L200 650 Z")
        + R(210, 790, 36, 44, 6, "#31383F") + R(560, 790, 36, 44, 6, "#31383F")
    )


def _f_table(vid):
    return (
        R(170, 520, 460, 42, 10, WOOD[0], WOOD[2], 5)
        + _hl("M170 520 L630 520 L630 536 L170 536 Z")
        + R(196, 562, 30, 260, 8, WOOD[1], WOOD[2], 4)
        + R(574, 562, 30, 260, 8, WOOD[1], WOOD[2], 4)
        + P("M226 620 L574 620", stroke=WOOD[2], w=12, fill="none")
        + R(300, 484, 200, 36, 8, "#C9D2DC", STEEL[2], 3)
    )


def _f_bed(vid):
    return (
        R(150, 420, 60, 320, 12, WOOD[0], WOOD[2], 5)
        + R(170, 620, 480, 100, 14, "#E8EEF4", STEEL[2], 5)
        + P("M180 640 Q400 560 620 640 L620 700 L180 700 Z", fill="#8FB2D8", stroke="#3D5B80", w=4)
        + R(200, 560, 150, 70, 16, "#FFFFFF", "#B9C0C8", 4)
        + R(370, 570, 220, 60, 14, "#D63B3B", "#8F1D1D", 4)
        + _hl("M370 570 L590 570 L590 588 L370 588 Z")
        + P("M180 720 L180 820 M640 720 L640 820", stroke=WOOD[2], w=14, fill="none")
        + R(160, 700, 500, 30, 8, WOOD[1], WOOD[2], 4)
    )


def _f_cupboard(vid):
    knobs = C(390, 640, 10, "#31383F") + C(414, 640, 10, "#31383F")
    return (
        R(210, 380, 380, 440, 12, WOOD[0], WOOD[2], 6)
        + _hl("M210 380 L590 380 L590 410 L210 410 Z")
        + R(230, 400, 165, 400, 6, WOOD[1], WOOD[2], 4)
        + R(405, 400, 165, 400, 6, WOOD[1], WOOD[2], 4)
        + knobs
        + "".join(f'<line x1="244" y1="{440 + i * 80}" x2="380" y2="{440 + i * 80}" stroke="{WOOD[2]}" stroke-width="3" opacity="0.5"/>' for i in range(4))
        + R(226, 820, 348, 24, 6, WOOD[2])
    )


def _f_shelves(vid):
    books = ""
    cols = ["#D63B3B", "#2E9E4B", "#3D5B80", "#F2B705", "#8E44AD", "#5BB7DF"]
    for r, y in enumerate((560, 690)):
        for i in range(6):
            h = 74 + (i * 37 + r * 53) % 26
            books += f'<rect x="{244 + i * 32}" y="{y - h}" width="24" height="{h}" rx="3" fill="{cols[(i + r) % 6]}" stroke="#23282F" stroke-width="1.5"/>'
    pots = (C(530, 530, 26, "#B87333", "#7A4A10", 3) + P("M512 512 q18 -24 36 0", fill="none", stroke="#2E9E4B", w=6)
            + R(500, 620, 70, 60, 8, "#8892A0", STEEL[2], 3))
    return (
        R(220, 430, 360, 400, 10, WOOD[0], WOOD[2], 6)
        + R(232, 570, 336, 16, 4, WOOD[1], WOOD[2], 2)
        + R(232, 700, 336, 16, 4, WOOD[1], WOOD[2], 2)
        + books + pots
        + P("M240 830 L240 870 M560 830 L560 870", stroke=WOOD[2], w=12, fill="none")
    )


def _f_other(vid):
    return _f_chair(vid)


# ---------------------------------------------------------------------------
# Registry + public entry
# ---------------------------------------------------------------------------
_ELECTRONICS = {
    "camera": _camera, "dslrcamera": _camera,
    "laptop": _laptop, "projector": _projector,
    "speakersoundsystem": _speaker_e, "speaker": _speaker_e,
    "microphone": _microphone_e, "ledscreentv": _led_screen, "ledscreen": _led_screen,
    "screen": _led_screen, "tv": _led_screen,
    "drone": _drone_e, "lights": _lights_e, "seriallights": _lights_e,
    "gamingconsole": _console, "console": _console,
    "powerbankinverter": _power_bank, "powerbank": _power_bank,
    "inverter": _power_bank, "generator": _generator_e,
    "electronics": _camera, "other": _other_misc,
}
_SECURITY = {
    "domectv": _dome_cctv, "cctvdome": _dome_cctv, "dome": _dome_cctv,
    "bulletcctv": _bullet_cctv, "cctbbullet": _bullet_cctv, "bullet": _bullet_cctv,
    "ptzcamera": _ptz_cctv, "ptz": _ptz_cctv,
    "doorframemetaldetector": _gate_detector, "walkthroughdetector": _gate_detector,
    "metaldetector": _gate_detector,
    "handhelddetector": _handheld_detector, "handhealddetector": _handheld_detector,
    "xrayscanner": _xray_scanner, "xray": _xray_scanner,
    "walkietalkieset": _walkie_set, "walkietalkie": _walkie_set,
    "barricades": _barricades, "barricade": _barricades,
    "security": _dome_cctv, "other": _other_misc,
}
_FURNITURE = {
    "chair": _f_chair, "chairs": _f_chair, "sofa": _f_sofa, "sofas": _f_sofa,
    "table": _f_table, "tables": _f_table, "bed": _f_bed, "beds": _f_bed,
    "cupboard": _f_cupboard, "wardrobe": _f_cupboard, "shelves": _f_shelves,
    "shelf": _f_shelves, "furniture": _f_sofa, "other": _f_other,
}
_REGISTRIES = {"electronics": _ELECTRONICS, "security": _SECURITY,
               "furniture": _FURNITURE}


def resolve_key(category="", type_value="", subcat_key=""):
    reg = _REGISTRIES.get(str(category or "").strip().lower())
    if reg is None:
        return None
    for cand in (type_value, subcat_key, category):
        k = _norm(cand)
        if k and k in reg:
            return k
    return None


def make_misc_art(category="electronics", type_value="", subcat_key="", slug="", label="") -> str:
    """Return the 800x1000 SVG for one electronics/security/furniture item."""
    cat = str(category or "electronics").strip().lower()
    reg = _REGISTRIES.get(cat) or _ELECTRONICS
    key = resolve_key(cat, type_value, subcat_key) or ("camera" if cat == "electronics" else
                                                       "dome" if cat == "security" else "sofa")
    if cat == "electronics":
        key = key if key in _ELECTRONICS else "other"
    fn = reg.get(key) or reg.get("other") or _other_misc
    vid = _vid(slug or key)
    body = fn(vid)
    caption = label or type_value or subcat_key or key
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img" aria-label="{esc(caption)}">'
            + scene_bg(vid, TINT.get(cat, TINT["other"])) + floor(vid) + body + label_ribbon(caption, vid)
            + '</svg>')
