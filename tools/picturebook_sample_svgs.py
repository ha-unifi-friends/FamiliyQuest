"""Draws the illustrations of the sample picture book «Klonk» (familyquest/picturebook_sample.json: "cover", "pics").

Every picture is a small flat SVG scene (viewBox 0 0 400 300, own background – fine on light and dark screens) built
from the same dwarf figure, so the family looks the same on every page:
Klonk (me, red hat, green tunic), Mama Tilda (purple scarf), Opa Brumbo (grey hat, white beard), Gorm (blue hat,
long brown beard), Pip (little sister, yellow hat). Run: python3 tools/picturebook_sample_svgs.py – it rewrites the
pictures in the JSON file and checks each one with the SVG cleaner of the app.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "family_quest" / "app"))
from familyquest.svgsafe import clean_svg  # noqa: E402

SKIN, NOSE, INK = "#f6c8a4", "#e9967a", "#3b2a20"
PEOPLE = {
    "klonk": {"hat": "#e03131", "tunic": "#2f9e44", "beard": "stubble", "s": 1.0},
    "pip": {"hat": "#f59f00", "tunic": "#e64980", "beard": None, "hair": "pigtails", "s": .78},
    "gorm": {"hat": "#1c7ed6", "tunic": "#5f3dc4", "beard": "long", "s": 1.12},
    "opa": {"hat": "#868e96", "tunic": "#8d5524", "beard": "white", "s": 1.05},
    "mama": {"hat": "#ae3ec9", "tunic": "#0c8599", "beard": None, "hair": "braids", "s": 1.05},
}


def f(v: float) -> str:
    return ("%.1f" % v).rstrip("0").rstrip(".")


def dwarf(who: str, x: float, y: float, eyes: str = "open", mouth: str = "smile", arms: str = "down", cheeks: str = "#ff8787",
          flip: bool = False, extra: str = "", scale: float = 1.0, rot: float = 0) -> str:
    """One dwarf standing with the feet at (x, y). eyes: open | closed | wink | wide | side; mouth: smile | grin | o |
    frown | laugh | flat; arms: down | up | hold | hips | ears."""
    p = PEOPLE[who]
    s = p["s"] * scale
    t, hat = p["tunic"], p["hat"]
    out = []
    # boots and tunic
    out.append(f'<ellipse cx="-12" cy="-5" rx="11" ry="6" fill="{INK}"/><ellipse cx="12" cy="-5" rx="11" ry="6" fill="{INK}"/>')
    out.append(f'<path d="M-23-9L-17-52Q0-58 17-52L23-9Z" fill="{t}"/><rect x="-21" y="-28" width="42" height="6" fill="{INK}"/>'
               f'<rect x="-4" y="-29" width="8" height="8" rx="1" fill="#fcc419"/>')
    # arms
    arm = {"down": [(-18, -46, -27, -20), (18, -46, 27, -20)], "up": [(-18, -46, -32, -78), (18, -46, 32, -78)],
           "hold": [(-18, -46, -10, -30), (18, -46, 10, -30)], "hips": [(-18, -46, -30, -34), (18, -46, 30, -34)],
           "ears": [(-18, -46, -20, -66), (18, -46, 20, -66)], "wave": [(-18, -46, -27, -20), (18, -46, 34, -76)]}[arms]
    for x1, y1, x2, y2 in arm:
        out.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{t}" stroke-width="10" stroke-linecap="round"/>'
                   f'<circle cx="{x2}" cy="{y2}" r="6" fill="{SKIN}"/>')
    # hair under the hat
    if p.get("hair") == "braids":
        out.append('<path d="M-17-64Q-30-40-22-22M17-64Q30-40 22-22" stroke="#c0792f" stroke-width="7" fill="none" stroke-linecap="round"/>')
    if p.get("hair") == "pigtails":
        out.append('<circle cx="-21" cy="-64" r="7" fill="#c0792f"/><circle cx="21" cy="-64" r="7" fill="#c0792f"/>')
    # head
    out.append(f'<circle cy="-66" r="17" fill="{SKIN}"/>')
    b = p["beard"]
    if b == "long":
        out.append('<path d="M-16-62Q-14-30 0-6Q14-30 16-62Q0-50-16-62Z" fill="#8a5a2b"/>')
    elif b == "white":
        out.append('<path d="M-17-62Q-16-34 0-26Q16-34 17-62Q0-52-17-62Z" fill="#f1f3f5" stroke="#ced4da" stroke-width="1.5"/>')
    elif b == "stubble":
        out.append('<path d="M-15-60Q-10-46 0-45Q10-46 15-60Q0-54-15-60Z" fill="#a0632e"/>')
    if cheeks:
        out.append(f'<circle cx="-10" cy="-61" r="4" fill="{cheeks}" opacity=".55"/><circle cx="10" cy="-61" r="4" fill="{cheeks}" opacity=".55"/>')
    # eyes
    if eyes == "open":
        out.append(f'<circle cx="-6" cy="-69" r="2.4" fill="{INK}"/><circle cx="6" cy="-69" r="2.4" fill="{INK}"/>')
    elif eyes == "wide":
        out.append(f'<circle cx="-6" cy="-70" r="4" fill="#fff" stroke="{INK}"/><circle cx="6" cy="-70" r="4" fill="#fff" stroke="{INK}"/>'
                   f'<circle cx="-6" cy="-70" r="1.8" fill="{INK}"/><circle cx="6" cy="-70" r="1.8" fill="{INK}"/>')
    elif eyes == "side":
        out.append(f'<circle cx="-4" cy="-69" r="2.4" fill="{INK}"/><circle cx="8" cy="-69" r="2.4" fill="{INK}"/>'
                   f'<path d="M-10-74L-2-73M2-73L10-74" stroke="{INK}" stroke-width="1.6"/>')
    elif eyes == "wink":
        out.append(f'<path d="M-9-69Q-6-72-3-69" stroke="{INK}" stroke-width="2" fill="none"/><circle cx="6" cy="-69" r="2.4" fill="{INK}"/>')
    else:                                                   # closed
        out.append(f'<path d="M-9-69Q-6-66-3-69M3-69Q6-66 9-69" stroke="{INK}" stroke-width="2" fill="none"/>')
    # nose and mouth
    out.append(f'<circle cy="-64" r="5" fill="{NOSE}"/>')
    m = {"smile": "M-6-56Q0-51 6-56", "grin": "M-8-57Q0-49 8-57Z", "o": None, "frown": "M-6-53Q0-58 6-53", "laugh": "M-9-58Q0-46 9-58Z",
         "flat": "M-5-55L5-55"}.get(mouth)
    if mouth == "o":
        out.append(f'<ellipse cy="-54" rx="4" ry="5" fill="{INK}"/>')
    elif m and m.endswith("Z"):
        out.append(f'<path d="{m}" fill="{INK}"/><path d="M-6-56L6-56" stroke="#fff" stroke-width="1.5"/>' if mouth == "grin"
                   else f'<path d="{m}" fill="{INK}"/>')
    elif m:
        out.append(f'<path d="{m}" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>')
    # hat (Mama: a scarf with a knot)
    if who == "mama":
        out.append(f'<path d="M-19-68Q0-94 19-68Q0-76-19-68Z" fill="{hat}"/><circle cx="17" cy="-70" r="4" fill="{hat}"/>')
    else:
        out.append(f'<path d="M-19-74Q0-82 19-74Q10-100 -2-122Q-4-100-19-74Z" fill="{hat}"/>'
                   f'<path d="M-20-75Q0-83 20-75" stroke="#00000033" stroke-width="5" fill="none"/>')
        if who == "klonk":                                  # the patch on Klonk's hat
            out.append('<rect x="-3" y="-98" width="8" height="8" fill="#ffd43b" transform="rotate(12 1 -94)"/>')
    out.append(extra)
    tr = f"translate({f(x)} {f(y)})" + (f" rotate({rot})" if rot else "") + f" scale({f(-s) if flip else f(s)} {f(s)})"
    return f'<g transform="{tr}">{"".join(out)}</g>'


def cave(wall: str = "#5c4033", floor: str = "#7a5a43", light: bool = True) -> str:
    """The family cave: wall, floor, a few stones; a warm lamp glow."""
    g = ('<defs><radialGradient id="glow"><stop offset="0" stop-color="#ffe066" stop-opacity=".55"/>'
         '<stop offset="1" stop-color="#ffe066" stop-opacity="0"/></radialGradient></defs>') if light else ""
    return (g + f'<rect width="400" height="300" fill="{wall}"/>'
            '<path d="M0 0H400V40Q350 70 300 38Q250 62 200 34Q140 66 90 36Q40 62 0 40Z" fill="#00000026"/>'
            f'<path d="M0 230Q100 215 200 228T400 222V300H0Z" fill="{floor}"/>'
            '<ellipse cx="60" cy="270" rx="22" ry="7" fill="#00000022"/><ellipse cx="340" cy="262" rx="16" ry="5" fill="#00000022"/>'
            + ('<circle cx="330" cy="70" r="70" fill="url(#glow)"/><path d="M330 40V58" stroke="#495057" stroke-width="3"/>'
               '<path d="M318 58H342L338 80H322Z" fill="#495057"/><circle cx="330" cy="70" r="7" fill="#ffd43b"/>' if light else ""))


def zzz(x: float, y: float, size: float = 18, col: str = "#e7f5ff") -> str:
    out = []
    for i, k in enumerate((1, .75, .55)):
        s = size * k
        xx, yy = x + i * size * .9, y - i * size * .9
        out.append(f'<path d="M{f(xx)} {f(yy)}h{f(s)}l{f(-s)} {f(s)}h{f(s)}" stroke="{col}" stroke-width="{f(3 * k + 1)}" fill="none" '
                   'stroke-linejoin="round" stroke-linecap="round"/>')
    return "".join(out)


def pick(x: float, y: float, rot: float = 0) -> str:
    return (f'<g transform="translate({x} {y}) rotate({rot})"><rect x="-3" y="0" width="6" height="58" rx="2" fill="#a9713d"/>'
            '<path d="M-26 6Q0-8 26 6L22 10Q0 0-22 10Z" fill="#adb5bd" stroke="#495057" stroke-width="1.5"/></g>')


def svg(*parts: str) -> str:
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">' + "".join(parts) + "</svg>"


def stalactites() -> str:
    return '<path d="M40 0L52 46L64 0M120 0L128 30L136 0M250 0L262 52L274 0M330 0L338 26L346 0" fill="#7d5f4a"/>'


# ---------------------------------------------------------------- the pages
def cover() -> str:
    return svg('<rect width="400" height="300" fill="#a5d8ff"/><circle cx="330" cy="62" r="30" fill="#fff3bf"/>',
               '<path d="M0 220L90 90L150 160L220 60L330 200L400 140V300H0Z" fill="#868e96"/>',
               '<path d="M220 60L245 95L230 92L215 105L200 88Z M90 90L108 116L92 112L80 122Z" fill="#f8f9fa"/>',
               '<path d="M150 300Q150 200 210 200Q270 200 270 300Z" fill="#343a40"/>',
               '<path d="M0 250Q200 228 400 252V300H0Z" fill="#69db7c"/>',
               dwarf("klonk", 210, 286, eyes="wink", mouth="grin", arms="hips", scale=1.25),
               '<rect x="246" y="228" width="44" height="28" rx="12" fill="#fff" stroke="#ced4da" stroke-width="2" transform="rotate(-14 268 242)"/>')


def p1_hammock() -> str:
    return svg(cave(), stalactites(),
               '<path d="M60 230V120M340 230V120" stroke="#6c4a32" stroke-width="12" stroke-linecap="round"/>',
               dwarf("klonk", 200, 186, eyes="closed", mouth="smile", arms="hold", rot=-88, scale=1.05),
               '<path d="M60 128Q200 236 340 128" stroke="#e8590c" stroke-width="8" fill="none"/>',
               '<path d="M66 134Q200 250 334 134Q200 214 66 134Z" fill="#ff922b"/>',
               '<path d="M100 160Q200 236 300 160" stroke="#ffd8a8" stroke-width="3" fill="none" stroke-dasharray="8 8"/>',
               zzz(250, 110, 20))


def p2_mama() -> str:
    return svg(cave(),
               '<rect x="24" y="210" width="170" height="34" rx="10" fill="#a9713d"/><rect x="28" y="190" width="50" height="28" rx="12" fill="#fff"/>',
               dwarf("klonk", 116, 210, eyes="wink", mouth="flat", arms="down", rot=-90, scale=.8),
               '<rect x="84" y="194" width="110" height="30" rx="10" fill="#4dabf7"/><path d="M96 204h86" stroke="#a5d8ff" stroke-width="3"/>',
               dwarf("mama", 250, 262, eyes="open", mouth="o", arms="hold",
                     extra='<path d="M10-30L44 6" stroke="#a9713d" stroke-width="5"/><path d="M36 -2L58 14L44 22Z" fill="#fab005"/>'),
               '<path d="M330 236h44v-30h-44z" fill="#495057"/><path d="M340 196q6-10 0-20M352 196q6-10 0-20M364 196q6-10 0-20" '
               'stroke="#f1f3f5" stroke-width="3" fill="none"/>',
               '<path d="M262 120h56a10 10 0 0 1 10 10v26a10 10 0 0 1-10 10h-30l-12 14v-14h-14a10 10 0 0 1-10-10v-26a10 10 0 0 1 10-10Z" fill="#fff"/>',
               '<text x="290" y="154" font-size="30" font-weight="bold" fill="#e03131" font-family="sans-serif" text-anchor="middle">!!</text>')


def p3_opa() -> str:
    return svg(cave(), stalactites(),
               '<path d="M44 28l16 4M126 20l12 4M254 30l18 6" stroke="#ffd43b" stroke-width="3" stroke-linecap="round"/>',
               '<rect x="40" y="150" width="140" height="100" rx="26" fill="#c92a2a"/><rect x="58" y="190" width="104" height="54" rx="12" fill="#e03131"/>',
               dwarf("opa", 110, 250, eyes="closed", mouth="o", arms="hold"),
               zzz(140, 150, 30, "#fff"),
               dwarf("klonk", 300, 262, eyes="closed", mouth="frown", arms="ears"))


def p4_gorm() -> str:
    sparkle = lambda x, y: f'<path d="M{x} {y - 9}L{x + 3} {y}L{x} {y + 9}L{x - 3} {y}Z M{x - 9} {y}L{x} {y + 3}L{x + 9} {y}L{x} {y - 3}Z" fill="#fff3bf"/>'
    return svg(cave(wall="#4c3a5a", floor="#6b5677"),
               dwarf("gorm", 170, 268, eyes="open", mouth="grin", arms="hold", scale=1.15),
               '<ellipse cx="290" cy="150" rx="40" ry="54" fill="#dee2e6" stroke="#fab005" stroke-width="8"/>',
               '<ellipse cx="290" cy="150" rx="28" ry="40" fill="#a5d8ff"/><path d="M276 132l18-14M280 156l22-18" stroke="#fff" stroke-width="4"/>',
               '<path d="M290 204v52" stroke="#fab005" stroke-width="8"/>',
               '<rect x="176" y="214" width="40" height="10" rx="3" fill="#fab005" transform="rotate(-35 196 219)"/>'
               '<path d="M180 222l4 7M187 218l4 7M194 214l4 7M201 210l4 7" stroke="#e67700" stroke-width="2" transform="rotate(-35 196 219)"/>',
               sparkle(120, 120), sparkle(232, 90), sparkle(196, 250))


def p5_yawn() -> str:
    return svg(cave(),
               dwarf("klonk", 150, 262, eyes="closed", mouth="o", arms="up"),
               dwarf("pip", 270, 262, eyes="closed", mouth="o", arms="up"),
               '<path d="M196 120q10-10 20 0M310 150q8-8 16 0" stroke="#e7f5ff" stroke-width="3" fill="none"/>')


def p6_glue() -> str:
    return svg(cave(), '<rect x="180" y="60" width="200" height="12" rx="4" fill="#a9713d"/>',
               pick(210, 72, 4), pick(260, 72, -3), pick(310, 72, 5), pick(356, 72, -2),
               '<path d="M196 122q14 10 4 26M246 120q10 16 0 30M300 124q12 12 6 26" stroke="#ffe066" stroke-width="5" fill="none" stroke-linecap="round"/>',
               dwarf("klonk", 110, 262, eyes="side", mouth="grin", arms="hold",
                     extra='<rect x="-6" y="-42" width="30" height="26" rx="5" fill="#fcc419" stroke="#e67700" stroke-width="2"/>'
                           '<path d="M2-42q8-8 16 0" fill="#ffe066"/><path d="M26-30l26-30" stroke="#a9713d" stroke-width="4"/>'
                           '<path d="M48-64l10-10 4 4-8 12Z" fill="#ffe066"/>'))


def p7_salt() -> str:
    jar = lambda x, lid, inside: (f'<rect x="{x}" y="74" width="54" height="66" rx="10" fill="#e7f5ff" stroke="#adb5bd" stroke-width="2"/>'
                                  f'<rect x="{x - 3}" y="66" width="60" height="12" rx="4" fill="{lid}"/>{inside}')
    salt = "".join(f'<circle cx="{x}" cy="{y}" r="2.5" fill="#868e96"/>' for x, y in ((92, 110), (104, 122), (116, 106), (100, 128), (112, 130), (122, 120)))
    sugar = "".join(f'<rect x="{x}" y="{y}" width="10" height="10" rx="1" fill="#fff" stroke="#ced4da"/>' for x, y in ((172, 104), (186, 116), (170, 122), (184, 98)))
    return svg(cave(wall="#6b4f3a"), '<rect x="60" y="140" width="190" height="10" rx="3" fill="#a9713d"/>',
               jar(80, "#1c7ed6", salt), jar(160, "#e64980", sugar),
               '<path d="M136 52q20-26 46 0" stroke="#ffd43b" stroke-width="4" fill="none"/><path d="M178 44l6 10-11 1Z" fill="#ffd43b"/>',
               '<path d="M182 52q-20 26-46 0" stroke="#ffd43b" stroke-width="4" fill="none" transform="translate(0 26)"/>',
               dwarf("mama", 300, 270, eyes="wide", mouth="frown", arms="hold",
                     extra='<ellipse cx="0" cy="-30" rx="24" ry="10" fill="#495057"/><path d="M14-46l12-22" stroke="#a9713d" stroke-width="4"/>'
                           '<path d="M24-80l4-10M34-76l8-6M14-82l-2-10" stroke="#fff" stroke-width="3" stroke-linecap="round"/>'),
               dwarf("klonk", 60, 290, eyes="side", mouth="grin", arms="down", scale=.8))


def p8_slippers() -> str:
    return svg(cave(),
               '<path d="M290 236l8-50h56l8 50Z" fill="#343a40"/><ellipse cx="326" cy="188" rx="28" ry="7" fill="#212529"/>',
               '<path d="M308 186q4-24 22-22t14 22Z" fill="#e64980"/><path d="M322 180q8-18 22-12" stroke="#fff" stroke-width="3" fill="none"/>',
               dwarf("opa", 170, 262, eyes="side", mouth="frown", arms="hips",
                     extra='<rect x="-24" y="-12" width="22" height="10" rx="4" fill="#fff"/><rect x="2" y="-12" width="22" height="10" rx="4" fill="#fff"/>'
                           '<path d="M-20-12v10M-12-12v10M6-12v10M14-12v10" stroke="#e03131" stroke-width="3"/>'),
               '<text x="190" y="100" font-size="44" font-weight="bold" fill="#ffd43b" font-family="sans-serif">?!</text>',
               '<path d="M10 256q30-80 80-60q20 30 0 60Z" fill="#868e96"/>',
               dwarf("klonk", 50, 262, eyes="wink", mouth="laugh", arms="ears", scale=.85))


def p9_sausage() -> str:
    return svg(cave(), stalactites(),
               '<path d="M60 230V110M340 230V110" stroke="#6c4a32" stroke-width="12" stroke-linecap="round"/>',
               '<path d="M60 116Q200 150 340 116" stroke="#e8590c" stroke-width="6" fill="none"/>',
               dwarf("klonk", 150, 156, eyes="wide", mouth="o", arms="hold", rot=-90, scale=.95),
               '<rect x="104" y="126" width="222" height="62" rx="31" fill="#ff922b"/>',
               '<path d="M150 128q-6 30 0 58M210 128q-6 30 0 58M270 128q-6 30 0 58" stroke="#ffe066" stroke-width="6" fill="none"/>',
               dwarf("pip", 290, 268, eyes="wink", mouth="grin", arms="wave",
                     extra='<path d="M34-76l18-30" stroke="#a9713d" stroke-width="4"/><path d="M48-112l10-6 3 8-9 6Z" fill="#ffe066"/>'),
               '<rect x="226" y="236" width="30" height="24" rx="5" fill="#fcc419" stroke="#e67700" stroke-width="2"/>')


def p10_family() -> str:
    return svg(cave(),
               dwarf("opa", 50, 270, eyes="closed", mouth="laugh", arms="hips", scale=.9),
               dwarf("mama", 125, 270, eyes="closed", mouth="laugh", arms="hips", scale=.9),
               dwarf("klonk", 205, 262, eyes="side", mouth="flat", arms="hold", cheeks="#fa5252", scale=1.05,
                     extra='<circle cx="-10" cy="-61" r="6" fill="#fa5252"/><circle cx="10" cy="-61" r="6" fill="#fa5252"/>'),
               dwarf("gorm", 288, 272, eyes="closed", mouth="laugh", arms="up", scale=.85),
               dwarf("pip", 362, 270, eyes="closed", mouth="laugh", arms="up"),
               '<path d="M20 120q10-10 20 0M86 110q10-10 20 0M270 100q10-10 20 0M340 140q10-10 20 0" stroke="#ffd43b" stroke-width="3" fill="none"/>')


def p11_help() -> str:
    broom = '<path d="M14-36L44 18" stroke="#a9713d" stroke-width="4"/><path d="M36 8L58 22L44 30Z" fill="#fab005"/>'
    return svg(cave(),
               '<path d="M250 250q30-6 60 0" stroke="#ced4da" stroke-width="3" fill="none" stroke-dasharray="4 6"/>',
               dwarf("klonk", 110, 262, eyes="open", mouth="smile", arms="hold", extra=broom),
               dwarf("pip", 200, 262, eyes="open", mouth="smile", arms="hold", extra=broom),
               dwarf("opa", 320, 262, eyes="closed", mouth="smile", arms="hips",
                     extra='<ellipse cx="-12" cy="-6" rx="14" ry="7" fill="#e64980"/><ellipse cx="12" cy="-6" rx="14" ry="7" fill="#e64980"/>'),
               '<path d="M300 150l6-12 6 12-12-6h12Z M346 130l5-10 5 10-10-5h10Z" fill="#ffd43b"/>')


def p12_night() -> str:
    return svg('<rect width="400" height="300" fill="#2b2140"/><path d="M0 0H400V36Q300 60 200 30T0 36Z" fill="#00000033"/>',
               '<circle cx="330" cy="70" r="34" fill="#1b1530"/><circle cx="330" cy="70" r="20" fill="#fff3bf"/><circle cx="338" cy="64" r="16" fill="#1b1530"/>',
               '<circle cx="306" cy="52" r="2" fill="#fff"/><circle cx="354" cy="90" r="1.6" fill="#fff"/>',
               '<path d="M0 236Q200 222 400 236V300H0Z" fill="#3f3157"/>',
               '<path d="M18 70V236M202 70V236" stroke="#8d5524" stroke-width="8" stroke-linecap="round"/>',
               '<rect x="20" y="110" width="180" height="16" rx="5" fill="#a9713d"/><rect x="20" y="200" width="180" height="16" rx="5" fill="#a9713d"/>',
               '<rect x="20" y="96" width="180" height="16" rx="6" fill="#4dabf7"/><rect x="20" y="186" width="180" height="16" rx="6" fill="#74c0fc"/>',
               '<rect x="24" y="86" width="30" height="14" rx="6" fill="#fff"/><rect x="24" y="176" width="30" height="14" rx="6" fill="#fff"/>',
               '<circle cx="46" cy="86" r="11" fill="#f6c8a4"/><path d="M38 76l8-22 8 22Z" fill="#868e96"/><path d="M36 88q10 14 20 0Z" fill="#f1f3f5"/>',
               '<circle cx="46" cy="176" r="11" fill="#f6c8a4"/><path d="M38 166l8-22 8 22Z" fill="#1c7ed6"/><path d="M36 178q10 30 20 0Z" fill="#8a5a2b"/>',
               zzz(70, 70, 14), zzz(70, 160, 14),
               dwarf("klonk", 270, 262, eyes="wink", mouth="grin", arms="hold",
                     extra='<rect x="-6" y="-42" width="12" height="16" rx="2" fill="#f8f9fa"/><path d="M0-50q5 4 0 8q-5-4 0-8Z" fill="#ffd43b"/>'))


PAGES = [p1_hammock, p2_mama, p3_opa, p4_gorm, p5_yawn, p6_glue, p7_salt, p8_slippers, p9_sausage, p10_family, p11_help, p12_night]
LAYOUTS = ["full", "top", "top", "top", "top", "full", "top", "top", "top", "top", "top", "full"]


def main() -> None:
    path = ROOT / "family_quest" / "app" / "familyquest" / "picturebook_sample.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    book = data.setdefault("dwarf", {"emoji": "⛏️", "color": 6, "texts": {}})
    book["cover"] = cover()
    book["pics"] = [fn() for fn in PAGES]
    book["layouts"] = LAYOUTS
    for s in [book["cover"], *book["pics"]]:
        assert clean_svg(s) == s, "the cleaner changes a picture"
        assert len(s) < 10000, len(s)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("pictures:", len(book["pics"]), "largest:", max(len(s) for s in [book["cover"], *book["pics"]]))


if __name__ == "__main__":
    main()
