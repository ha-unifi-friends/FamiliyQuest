#!/usr/bin/env python3
"""Draws the coats of arms of the 26 Swiss cantons as smooth vector pictures → family_quest/app/web/geo/arms.json.

Own simplified drawings (no third-party artwork): fields, crosses, keys, croziers and stars are geometry,
the animals and figures are put together from ellipses, rounded bars and strokes. 100×120 shield, Swiss form.
Run again after changes:  python3 tools/build_arms.py
"""
import json
import math
from pathlib import Path

W, H = 100, 120
SHIELD = "M0 0H100V68C100 98 80 112 50 120C20 112 0 98 0 68Z"

RED, BLUE, LBLUE, YEL, BLK, WHT, GRN = "#D8232A", "#0F6CB6", "#2F8FD8", "#FFCC00", "#1B1B1B", "#FFFFFF", "#1E9A45"


def f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def rect(x, y, w, h, fill, r=0, rot=0, cx=None, cy=None):
    t = f' transform="rotate({f(rot)} {f(cx if cx is not None else x + w / 2)} {f(cy if cy is not None else y + h / 2)})"' if rot else ""
    rr = f' rx="{f(r)}"' if r else ""
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"{rr} fill="{fill}"{t}/>'


def ell(cx, cy, rx, ry, fill, rot=0):
    t = f' transform="rotate({f(rot)} {f(cx)} {f(cy)})"' if rot else ""
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="{fill}"{t}/>'


def circ(cx, cy, r, fill):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="{fill}"/>'


def path(d, fill="none", stroke=None, sw=0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{f(sw)}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ""
    return f'<path d="{d}" fill="{fill}"{s}{extra}/>'


def limb(x1, y1, x2, y2, w, fill):
    """A rounded bar from (x1,y1) to (x2,y2) – legs, arms, tails."""
    return f'<path d="M{f(x1)} {f(y1)}L{f(x2)} {f(y2)}" stroke="{fill}" stroke-width="{f(w)}" stroke-linecap="round" fill="none"/>'


def g(content, tx=0, ty=0, s=1, rot=0, flip=False):
    t = f"translate({f(tx)} {f(ty)})"
    if rot:
        t += f" rotate({f(rot)})"
    if s != 1 or flip:
        t += f" scale({f(-s if flip else s)} {f(s)})"
    return f'<g transform="{t}">{"".join(content)}</g>'


def cross(cx, cy, s, fill):
    """Swiss cross: arms 1/6 longer than wide (s = total width)."""
    a = s * 6 / 20
    return path(f"M{f(cx - a / 2)} {f(cy - s / 2)}h{f(a)}v{f((s - a) / 2)}h{f((s - a) / 2)}v{f(a)}h{f(-(s - a) / 2)}"
                f"v{f((s - a) / 2)}h{f(-a)}v{f(-(s - a) / 2)}h{f(-(s - a) / 2)}v{f(-a)}h{f((s - a) / 2)}z", fill)


def star(cx, cy, r, fill, rot=-90):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.4
        a = math.radians(rot + i * 36)
        pts.append(f"{f(cx + rr * math.cos(a))} {f(cy + rr * math.sin(a))}")
    return path("M" + "L".join(pts) + "Z", fill)


def key(fill, hole, double=False):
    """Key standing upright, ring at the top, bit(s) at the bottom; local box −16..16 × 0..80."""
    parts = [circ(0, 12, 11, fill), circ(0, 12, 6, hole), circ(0, 12, 0.01, fill),
             rect(-3.2, 21, 6.4, 57, fill, 1.5), rect(-7, 22, 14, 4, fill, 1.5)]
    bit = path("M3 54h13v22H3v-4h7v-5H3v-4h7v-5H3z", fill)
    parts.append(bit)
    if double:
        parts.append(g([bit], flip=True))
    return parts


def crozier(fill, field, knobs=False):
    """Basel crozier, hook to the left; local box −26..14 × 0..110."""
    p = [path("M0 46V24C0 6-24 4-24 22C-24 32-14 34-11 27", stroke=fill, sw=8),
         rect(-4, 40, 8, 54, fill),
         rect(-9, 52, 18, 7, fill, 3), rect(-9, 76, 18, 7, fill, 3),
         path("M-11 92h22l-4 6 4 12-8-7-3 9-3-9-8 7 4-12z", fill)]
    if knobs:
        for a in range(150, 361, 35):
            r = math.radians(a)
            p.append(circ(-12 + 16.5 * math.cos(r), 20 + 16.5 * math.sin(r), 3.2, fill))
    return p


def bear_walk(c=BLK, claws=RED):
    """Bear walking to the left; centre of the body at 0 0, about 80 wide."""
    return [ell(4, -2, 24, 13, c), ell(-8, -8, 15, 10, c, -10),
            limb(-17, 2, -21, 20, 7.5, c), limb(-8, 4, -9, 21, 7.5, c), limb(14, 2, 12, 20, 7.5, c), limb(23, 0, 26, 18, 7.5, c),
            limb(27, -6, 32, -10, 5, c),
            circ(-26, -11, 9, c), ell(-35, -8, 7, 5, c, 15), circ(-22, -20, 3.6, c),
            circ(-28, -13, 1.3, WHT), ell(-41, -5, 2.4, 1.3, claws, 30),
            path("M-25 23l-2 3M-22 23l-1 3M-12 24l-2 3M-9 24l-1 3M9 23l-2 3M12 23l-1 3M23 21l-2 3M26 21l-1 3", stroke=claws, sw=1.4)]


def bear_rampant(c=BLK, claws=RED):
    """Bear standing up on its hind legs, facing left; about 70 wide × 95 high, feet at y≈46."""
    return [ell(2, 0, 15, 27, c, 12), ell(-2, -18, 14, 13, c),
            limb(-6, -16, -24, -26, 8, c), limb(-6, -8, -26, -6, 8, c),
            limb(4, 18, -6, 42, 9, c), limb(10, 16, 14, 42, 9, c), limb(16, 18, 24, 22, 5, c),
            circ(-8, -34, 10, c), ell(-18, -32, 7.5, 5.5, c, 18), circ(-2, -43, 4, c),
            circ(-10, -37, 1.4, WHT), ell(-24, -29, 2.6, 1.3, claws, 30),
            path("M-28-29l-3-1M-28-27l-3 1M-30-8l-3-1M-30-6l-3 1M-10 44l-2 3M-6 45l-1 3M11 45l-1 3M15 45l0 3", stroke=claws, sw=1.4)]


def lion_walk(c=YEL, dark="#B8860B"):
    """Lion walking to the left with mane and tail; centre at 0 0, about 70 wide."""
    return [path("M22-4C34-10 30-26 38-28", stroke=c, sw=3.2), ell(38.5, -29, 4, 3, c, -30),
            ell(4, 0, 21, 9, c), limb(-12, 3, -16, 19, 6.5, c), limb(-4, 4, -4, 19, 6.5, c),
            limb(13, 3, 11, 19, 6.5, c), limb(20, 1, 24, 18, 6.5, c),
            circ(-17, -8, 11, c), path("M-28-10a11 11 0 0 1 20-8", stroke=dark, sw=1.2),
            ell(-27, -5, 6, 4.5, c, 10), circ(-22, -10, 1.3, BLK), ell(-33, -2, 2.4, 1.2, RED, 25)]


def ram_rampant(c=BLK, horn="#6B5A2A"):
    """Ram rearing up, facing left; feet at y≈46."""
    return [ell(4, 2, 14, 26, c, 18), limb(6, 20, -6, 44, 8, c), limb(12, 18, 16, 44, 8, c),
            limb(-2, -10, -22, -18, 7, c), limb(-2, -2, -24, 4, 7, c), limb(18, 22, 26, 20, 5, c),
            ell(-6, -30, 9, 12, c, 30), ell(-14, -24, 6, 9, c, 40),
            path("M-4-36C6-44 14-32 6-26C0-22-6-28 0-31", stroke=horn, sw=4.5),
            circ(-10, -32, 1.3, WHT)]


def ibex_rampant(c=BLK):
    """Ibex (Steinbock) rearing up, facing left, with long horns curved backwards."""
    return [ell(4, 2, 13, 24, c, 15), limb(6, 18, -4, 42, 7, c), limb(12, 16, 16, 42, 7, c),
            limb(-2, -8, -20, -18, 6, c), limb(-2, 0, -22, 4, 6, c), limb(16, 22, 22, 18, 4.5, c),
            ell(-6, -28, 7, 11, c, 30), ell(-12, -22, 5, 8, c, 40),
            path("M-4-36C-2-50 12-58 26-52", stroke=c, sw=4.5), path("M-2-34C2-46 14-50 24-46", stroke=c, sw=3),
            path("M-14-18l-3 7", stroke=c, sw=2.5), circ(-8, -30, 1.2, WHT)]


def half_eagle(c=BLK):
    """Half of a crowned eagle, joined to the right edge (x=0), facing left."""
    feathers = "M0-18C-16-24-34-22-46-10L-40-10-46-2-38-2-44 6-36 6-40 14-30 12-32 20-22 16-20 24-12 18-6 24 0 18Z"
    return [path(feathers, c), ell(0, 4, 8, 16, c), limb(-2, 18, -8, 34, 4.5, c),
            path("M-8 34l-6 2M-8 34l-4 5M-8 34l1 6", stroke=RED, sw=2),
            limb(0, -14, -4, -26, 7, c), circ(-6, -32, 7, c), path("M-12-34l-8 3 7 2z", RED),
            circ(-7, -33, 1.2, WHT), path("M-12-40l2-6 3 4 3-6 3 6 3-4 1 6z", RED)]


def fridolin():
    """St. Fridolin as a pilgrim in a black habit, walking to the left with staff, book and halo."""
    skin = "#F2C9A0"
    return [circ(-2, -34, 11, "none") + '<circle cx="-2" cy="-34" r="11" fill="none" stroke="#FFCC00" stroke-width="3"/>',
            path("M-14-20C-18 0-22 20-26 42H20C16 20 12 0 10-20C6-24-10-24-14-20Z", BLK),
            path("M-28-48L-34 44", stroke="#8B5A2B", sw=3), limb(-12, -14, -28, -6, 6, BLK),
            circ(-30, -7, 3, skin), rect(-24, 2, 12, 15, RED, 1.5, -10), circ(-3, -33, 7.5, skin),
            path("M-10-31l-3 2 3 1", skin), circ(-6, -34, 0.9, BLK)]


def fasces(c=WHT, line=GRN):
    """Bundle of rods with an axe (St. Gallen)."""
    rods = [rect(-10, -36, 20, 76, c, 3)] + [path(f"M{x}-34V38", stroke=line, sw=1.2) for x in (-5, 0, 5)]
    bands = [rect(-12, -24, 24, 5, c, 1.5), rect(-12, 24, 24, 5, c, 1.5),
             path("M-12-24h24M-12-19h24M-12 24h24M-12 29h24", stroke=line, sw=1),
             path("M-11-21.5L11-21.5M-11 26.5h22", stroke=line, sw=0.8)]
    axe = [path("M8-44h6v18h-6z", c), path("M14-50C30-50 34-36 30-24C26-30 20-30 14-30Z", c),
           path("M14-50C30-50 34-36 30-24C26-30 20-30 14-30Z", "none", line, 1)]
    return rods + bands + axe + [rect(-2, -44, 4, 10, c)]


def wave(y, h, fill, x0=0, x1=50, amp=4, n=3):
    step = (x1 - x0) / n
    top = f"M{f(x0)} {f(y)}" + "".join(f"q{f(step / 4)} {f(-amp)} {f(step / 2)} 0t{f(step / 2)} 0" for _ in range(n))
    bot = f"V{f(y + h)}" + "".join(f"q{f(-step / 4)} {f(amp)} {f(-step / 2)} 0t{f(-step / 2)} 0" for _ in range(n))
    return path(top + bot + "Z", fill)


A = {}
A["ZH"] = [rect(0, 0, W, H, LBLUE), path("M0 0H100V112Z", WHT)]
A["BE"] = [rect(0, 0, W, H, RED), path("M0 0L0 38L82 120L100 120L100 74L30 0Z", YEL), g(bear_walk(), 48, 57, 0.72, 45)]
A["LU"] = [rect(0, 0, 50, H, LBLUE), rect(50, 0, 50, H, WHT)]
A["UR"] = [rect(0, 0, W, H, YEL),
           path("M33 44C18 44 10 32 13 18C18 30 26 34 37 35Z", "#F4F1E6", BLK, 1.6),
           path("M67 44C82 44 90 32 87 18C82 30 74 34 63 35Z", "#F4F1E6", BLK, 1.6),
           ell(28, 48, 9, 5, BLK, 20), ell(72, 48, 9, 5, BLK, -20),
           path("M36 34C42 30 58 30 64 34C70 44 68 64 64 78C62 88 58 94 50 94C42 94 38 88 36 78C32 64 30 44 36 34Z", BLK),
           circ(42, 52, 3.4, WHT), circ(58, 52, 3.4, WHT), circ(42.6, 52.4, 1.6, BLK), circ(57.4, 52.4, 1.6, BLK),
           ell(45, 86, 2, 3, "#555"), ell(55, 86, 2, 3, "#555"),
           '<circle cx="50" cy="98" r="7" fill="none" stroke="#D8232A" stroke-width="3.2"/>',
           path("M44 92C40 96 38 102 41 106C44 102 45 98 46 93Z", RED)]
A["SZ"] = [rect(0, 0, W, H, RED), cross(24, 22, 22, WHT)]
A["OW"] = [rect(0, 0, W, 60, RED), rect(0, 60, W, 60, WHT),
           '<clipPath id="ow-t"><rect width="100" height="60"/></clipPath><clipPath id="ow-b"><rect y="60" width="100" height="60"/></clipPath>',
           f'<g clip-path="url(#ow-t)">{g(key(WHT, RED, True), 50, 18, 1.05)}</g>',
           f'<g clip-path="url(#ow-b)">{g(key(RED, WHT, True), 50, 18, 1.05)}</g>']
A["NW"] = [rect(0, 0, W, H, RED), g(key(WHT, RED, True), 50, 16, 1.1)]
A["GL"] = [rect(0, 0, W, H, RED), g(fridolin(), 54, 64, 1.05)]
A["ZG"] = [rect(0, 0, W, H, WHT), rect(0, 42, W, 36, LBLUE)]
A["FR"] = [rect(0, 0, W, 60, BLK), rect(0, 60, W, 60, WHT)]
A["SO"] = [rect(0, 0, W, 60, RED), rect(0, 60, W, 60, WHT)]
A["BS"] = [rect(0, 0, W, H, WHT), g(crozier(BLK, WHT), 56, 6, 0.98)]
A["BL"] = [rect(0, 0, W, H, WHT), g(crozier(RED, WHT, True), 44, 6, 0.98, flip=True)]
A["SH"] = [rect(0, 0, W, H, YEL), g(ram_rampant(), 52, 60, 1.05)]
A["AR"] = [rect(0, 0, W, H, WHT), g(bear_rampant(), 54, 60, 1.0),
           '<text x="16" y="96" font-family="Georgia,serif" font-weight="700" font-size="20" fill="#1B1B1B">V</text>'
           '<text x="72" y="96" font-family="Georgia,serif" font-weight="700" font-size="20" fill="#1B1B1B">R</text>']
A["AI"] = [rect(0, 0, W, H, WHT), g(bear_rampant(), 54, 60, 1.1)]
A["SG"] = [rect(0, 0, W, H, GRN), g(fasces(), 46, 62, 1.05)]
A["GR"] = [rect(0, 0, 25, 56, BLK), rect(25, 0, 25, 56, WHT),
           rect(50, 0, 25, 28, LBLUE), rect(75, 0, 25, 28, YEL), rect(50, 28, 25, 28, YEL), rect(75, 28, 25, 28, LBLUE),
           # the cross of the Ten Jurisdictions, counterchanged
           rect(72, 0, 3, 25, YEL), rect(75, 0, 3, 25, LBLUE), rect(50, 25, 25, 3, YEL), rect(50, 28, 25, 3, LBLUE),
           rect(75, 25, 25, 3, LBLUE), rect(75, 28, 25, 3, YEL), rect(72, 31, 3, 25, LBLUE), rect(75, 31, 3, 25, YEL),
           rect(0, 56, W, 64, WHT), g(ibex_rampant(), 50, 90, 0.7),
           path("M50 0V56M0 56H100", stroke=BLK, sw=1.2)]
A["AG"] = [rect(0, 0, 50, H, BLK), rect(50, 0, 50, H, LBLUE),
           wave(44, 9, WHT), wave(62, 9, WHT), wave(80, 9, WHT, amp=4),
           star(66, 34, 10, WHT), star(86, 34, 10, WHT), star(76, 60, 10, WHT)]
A["TG"] = [rect(0, 0, W, H, GRN), path("M0 0H100L0 112Z", WHT),
           g(lion_walk(), 30, 38, 0.68, -42), g(lion_walk(), 70, 82, 0.68, -42)]
A["TI"] = [rect(0, 0, 50, H, RED), rect(50, 0, 50, H, BLUE)]
A["VD"] = [rect(0, 0, W, 50, WHT), rect(0, 50, W, 70, GRN),
           '<text x="50" y="22" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="12.5" fill="#E0A800">LIBERTÉ</text>'
           '<text x="50" y="40" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="12.5" fill="#E0A800">ET PATRIE</text>']
A["VS"] = [rect(0, 0, 50, H, WHT), rect(50, 0, 50, H, RED)]
for i, (x, y) in enumerate([(16, 18), (34, 18), (66, 18), (84, 18), (16, 40), (34, 40), (66, 40), (84, 40),
                            (25, 62), (75, 62), (25, 84), (75, 84), (50, 104)]):
    if i == 12:  # the 13th star sits on the line: half red, half white
        A["VS"].append(f'<clipPath id="vs-l"><rect width="50" height="120"/></clipPath><clipPath id="vs-r"><rect x="50" width="50" height="120"/></clipPath>'
                       f'<g clip-path="url(#vs-l)">{star(x, y, 8, RED)}</g><g clip-path="url(#vs-r)">{star(x, y, 8, WHT)}</g>')
    else:
        A["VS"].append(star(x, y, 8, RED if x < 50 else WHT))
A["NE"] = [rect(0, 0, 34, H, GRN), rect(34, 0, 32, H, WHT), rect(66, 0, 34, H, RED), cross(83, 18, 18, WHT)]
A["GE"] = [rect(0, 0, 50, H, YEL), rect(50, 0, 50, H, RED), g(half_eagle(), 50, 56, 1.0),
           g(key(YEL, RED), 72, 22, 1.0)]
A["JU"] = [rect(0, 0, W, H, WHT), g(crozier(RED, WHT), 32, 8, 0.9),
           *[rect(52, y, 48, 120 / 7, RED) for y in [120 / 7 * i for i in (1, 3, 5)]], path("M51 0V120", stroke=WHT, sw=2)]

ORDER = ["ZH", "BE", "LU", "UR", "SZ", "OW", "NW", "GL", "ZG", "FR", "SO", "BS", "BL", "SH", "AR", "AI", "SG", "GR",
         "AG", "TG", "TI", "VD", "VS", "NE", "GE", "JU"]


def main():
    out = {"source": "own drawings (tools/build_arms.py)", "width": W, "height": H, "shield": SHIELD,
           "arms": {k: "".join(A[k]) for k in ORDER}}
    p = Path(__file__).resolve().parent.parent / "family_quest/app/web/geo/arms.json"
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(p, p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
