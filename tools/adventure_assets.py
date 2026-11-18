#!/usr/bin/env python3
"""Write the own SVG pictures of the adventure games (familyquest/adventuregame.py ASSETS and ROOMS) to web/img/adventure.

    python3 tools/adventure_assets.py

All pictures are drawn by hand here: flat shapes with a dark outline, so they read on light and dark room pictures.
Objects and characters have a viewBox that fits the shape (the play screen shows them «contain» in the hotspot);
rooms are 400×300 like the scenes of the books (web/img/stories).
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web" / "img" / "adventure"
INK = "#2a2330"


def svg(vb: str, body: str, ink: bool = True) -> str:
    g = f'<g stroke="{INK}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round">{body}</g>' if ink else body
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{g}</svg>'


def room(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice">{body}</svg>'


EYES = '<circle cx="{0}" cy="{2}" r="3" fill="{3}" stroke="none"/><circle cx="{1}" cy="{2}" r="3" fill="{3}" stroke="none"/>'

ASSETS = {
    # ---------------------------------------------------------------- doors and passages
    "door": svg("0 0 60 100", '<path d="M6 98V22Q6 4 30 4T54 22V98Z" fill="#8a5a2b"/><path d="M14 94V26Q14 12 30 12T46 26V94" fill="#a9733c"/>'
                '<path d="M22 14V94M30 12V94M38 14V94" fill="none" stroke-width="1.5"/><circle cx="42" cy="58" r="3.5" fill="#f2c94c"/>'),
    "door_arch": svg("0 0 64 100", '<path d="M2 98V30Q2 2 32 2T62 30V98Z" fill="#8d8a99"/><path d="M12 98V34Q12 12 32 12T52 34V98Z" fill="#3a3346"/>'
                     '<path d="M2 40H12M52 40H62M2 70H12M52 70H62M20 6L24 15M44 6L40 15" fill="none" stroke-width="2"/>'),
    "door_metal": svg("0 0 60 100", '<rect x="4" y="4" width="52" height="94" rx="8" fill="#9aa7b8"/><rect x="11" y="12" width="38" height="80" rx="5" fill="#c9d3e0"/>'
                      '<path d="M30 12V92" fill="none"/><rect x="40" y="46" width="12" height="10" rx="2" fill="#4dabf7"/><circle cx="46" cy="51" r="2" fill="#fff" stroke="none"/>'
                      '<path d="M14 22L46 22M14 82L46 82" stroke="#f59f00" stroke-width="4"/>'),
    "hatch": svg("0 0 100 60", '<rect x="4" y="6" width="92" height="48" rx="4" fill="#8a5a2b"/><path d="M4 22H96M4 38H96" fill="none" stroke-width="1.5"/>'
                 '<rect x="44" y="24" width="12" height="12" rx="2" fill="#f2c94c"/><circle cx="50" cy="30" r="2" fill="' + INK + '" stroke="none"/>'),
    "window": svg("0 0 80 80", '<rect x="4" y="4" width="72" height="72" rx="6" fill="#d9e6f2"/><rect x="11" y="11" width="58" height="58" rx="3" fill="#7cc4f2"/>'
                  '<path d="M40 11V69M11 40H69" fill="none" stroke-width="4" stroke="#d9e6f2"/><rect x="11" y="11" width="58" height="58" rx="3" fill="none"/>'
                  '<path d="M18 22l8-6M50 50l10-8" stroke="#fff" stroke-width="2.5" fill="none"/>'),
    # ---------------------------------------------------------------- things to take, use and combine
    "key": svg("0 0 100 50", '<circle cx="22" cy="25" r="17" fill="#f2c94c"/><circle cx="22" cy="25" r="7" fill="#fff8db"/>'
               '<path d="M38 21H94V29H86V40H78V29H70V37H62V29H38Z" fill="#f2c94c"/>'),
    "chest": svg("0 0 100 80", '<path d="M8 34H92V76H8Z" fill="#a9733c"/><path d="M8 34Q8 6 50 6T92 34Z" fill="#8a5a2b"/>'
                 '<path d="M8 34H92M24 10V76M76 10V76" fill="none" stroke-width="5" stroke="#f2c94c"/><path d="M8 34H92" fill="none"/>'
                 '<rect x="42" y="30" width="16" height="18" rx="3" fill="#f2c94c"/><circle cx="50" cy="38" r="2.5" fill="' + INK + '" stroke="none"/>'),
    "lever": svg("0 0 70 100", '<path d="M33 70L54 10" fill="none" stroke-width="7" stroke="' + INK + '"/><path d="M33 70L54 10" fill="none" stroke-width="3.5" stroke="#adb5bd"/>'
                 '<circle cx="55" cy="9" r="8" fill="#e03131"/><path d="M8 96V74Q8 62 20 62H50Q62 62 62 74V96Z" fill="#868e96"/>'),
    "lamp": svg("0 0 60 100", '<path d="M30 6V20" fill="none"/><path d="M14 20H46L40 58H20Z" fill="#ffd43b"/><path d="M20 58H40V66H20Z" fill="#a9733c"/>'
                '<path d="M26 66V88M18 96H42L38 88H22Z" fill="#8a5a2b"/><circle cx="30" cy="38" r="7" fill="#fff3bf" stroke="none"/>'),
    "candle": svg("0 0 40 100", '<path d="M20 4Q30 18 20 30Q10 18 20 4Z" fill="#ff922b"/><path d="M20 14Q24 21 20 27Q16 21 20 14Z" fill="#ffe066" stroke="none"/>'
                  '<path d="M20 30V36" fill="none"/><rect x="10" y="36" width="20" height="50" rx="3" fill="#fff4e0"/><path d="M4 86H36L32 96H8Z" fill="#c9a227"/>'),
    "book": svg("0 0 90 70", '<path d="M45 14Q26 4 6 10V64Q26 58 45 66Q64 58 84 64V10Q64 4 45 14Z" fill="#fff8e7"/><path d="M45 14V66" fill="none"/>'
                '<path d="M14 22Q26 18 38 22M14 32Q26 28 38 32M52 22Q64 18 76 22M52 32Q64 28 76 32M14 42Q26 38 38 42" fill="none" stroke-width="1.5"/>'),
    "potion": svg("0 0 60 100", '<rect x="22" y="4" width="16" height="12" rx="2" fill="#a9733c"/><path d="M24 16V36Q6 48 6 70Q6 96 30 96T54 70Q54 48 36 36V16Z" fill="#e7f5ff"/>'
                  '<path d="M8 66Q30 56 52 66Q54 94 30 94T8 66Z" fill="#9775fa"/><circle cx="22" cy="78" r="4" fill="#e5dbff" stroke="none"/><circle cx="36" cy="72" r="2.5" fill="#e5dbff" stroke="none"/>'),
    "rope": svg("0 0 100 80", '<ellipse cx="50" cy="44" rx="40" ry="28" fill="#d9a35b"/><ellipse cx="50" cy="44" rx="28" ry="18" fill="none"/>'
                '<ellipse cx="50" cy="44" rx="15" ry="9" fill="#a9733c"/><path d="M84 58Q96 70 90 78" fill="none" stroke-width="5" stroke="#d9a35b"/>'),
    "stick": svg("0 0 100 30", '<path d="M4 18L92 8Q98 10 94 15L6 26Q2 22 4 18Z" fill="#a9733c"/><path d="M40 13L36 6" fill="none" stroke-width="3" stroke="#8a5a2b"/>'),
    "ladder": svg("0 0 50 100", '<path d="M10 2V98M40 2V98" fill="none" stroke-width="6" stroke="' + INK + '"/><path d="M10 2V98M40 2V98" fill="none" stroke-width="3" stroke="#d9a35b"/>'
                  '<path d="M10 16H40M10 36H40M10 56H40M10 76H40M10 94H40" fill="none" stroke-width="3"/>'),
    "crystal": svg("0 0 60 80", '<path d="M30 4L54 30L30 76L6 30Z" fill="#74c0fc"/><path d="M6 30H54M30 4L20 30L30 76L40 30Z" fill="none" stroke-width="1.5"/>'
                   '<path d="M14 26L22 16" stroke="#fff" stroke-width="2.5" fill="none"/>'),
    "magnet": svg("0 0 80 80", '<path d="M8 40A32 32 0 0 1 72 40V72H52V40A12 12 0 0 0 28 40V72H8Z" fill="#e03131"/>'
                  '<path d="M8 60H28V72H8ZM52 60H72V72H52Z" fill="#dee2e6"/>'),
    "battery": svg("0 0 60 100", '<rect x="22" y="4" width="16" height="10" rx="2" fill="#adb5bd"/><rect x="8" y="12" width="44" height="84" rx="6" fill="#40c057"/>'
                   '<rect x="8" y="12" width="44" height="22" rx="6" fill="#2f9e44"/><path d="M34 44L22 66H32L26 86L42 60H32L38 44Z" fill="#fff3bf"/>'),
    "cable": svg("0 0 100 60", '<path d="M8 40Q26 6 50 30T92 20" fill="none" stroke-width="9" stroke="' + INK + '"/><path d="M8 40Q26 6 50 30T92 20" fill="none" stroke-width="5" stroke="#fd7e14"/>'
                 '<rect x="80" y="10" width="16" height="18" rx="3" fill="#868e96"/><path d="M96 14H100M96 24H100" fill="none"/><path d="M4 36L12 46" stroke-width="3"/>'),
    "card": svg("0 0 100 66", '<rect x="4" y="4" width="92" height="58" rx="8" fill="#4dabf7"/><rect x="14" y="18" width="20" height="16" rx="3" fill="#f2c94c"/>'
                '<path d="M44 22H84M44 32H72M14 48H86" fill="none" stroke="#e7f5ff" stroke-width="3"/>'),
    "button": svg("0 0 80 60", '<rect x="4" y="30" width="72" height="26" rx="6" fill="#868e96"/><path d="M14 34Q14 10 40 10T66 34Z" fill="#e03131"/>'
                  '<path d="M24 22Q30 16 38 15" stroke="#ffc9c9" stroke-width="3" fill="none"/>'),
    "screen": svg("0 0 100 80", '<rect x="4" y="4" width="92" height="60" rx="6" fill="#495057"/><rect x="12" y="11" width="76" height="46" rx="3" fill="#0b7285"/>'
                  '<path d="M18 40L30 28L40 36L54 20L66 32L82 18" fill="none" stroke="#63e6be" stroke-width="2.5"/><path d="M40 64V72H60V64M30 76H70" fill="none"/>'),
    "cauldron": svg("0 0 100 90", '<ellipse cx="50" cy="26" rx="44" ry="10" fill="#69db7c"/><path d="M8 28Q4 80 50 82Q96 80 92 28Q80 36 50 36T8 28Z" fill="#343a40"/>'
                    '<circle cx="36" cy="16" r="5" fill="#8ce99a"/><circle cx="58" cy="12" r="4" fill="#8ce99a"/><path d="M26 82L20 90M74 82L80 90" fill="none" stroke-width="4"/>'),
    "bookshelf": svg("0 0 90 120", '<rect x="4" y="4" width="82" height="112" rx="3" fill="#8a5a2b"/><path d="M4 40H86M4 78H86" fill="none" stroke-width="3"/>'
                     '<path d="M12 14h8v24h-8zM22 18h7v20h-7zM31 12h9v26h-9zM52 16h8v22h-8zM62 20h12v18h-12z" fill="#e03131"/>'
                     '<path d="M12 52h10v24h-10zM26 56h7v20h-7zM44 50h9v26h-9zM56 54h8v22h-8zM68 58h10v18h-10z" fill="#4dabf7"/>'
                     '<path d="M12 90h8v24h-8zM22 94h12v20h-12zM50 88h9v26h-9zM62 92h7v22h-7z" fill="#40c057"/>'),
    "table": svg("0 0 100 70", '<path d="M4 20H96V30H4Z" fill="#a9733c"/><path d="M12 30V68M88 30V68" fill="none" stroke-width="6" stroke="' + INK + '"/>'
                 '<path d="M12 30V68M88 30V68" fill="none" stroke-width="3" stroke="#a9733c"/><rect x="30" y="30" width="40" height="14" fill="#8a5a2b"/><circle cx="50" cy="37" r="2.5" fill="#f2c94c"/>'),
    "bed": svg("0 0 120 70", '<rect x="6" y="20" width="16" height="46" rx="3" fill="#8a5a2b"/><rect x="22" y="34" width="94" height="22" rx="3" fill="#a9733c"/>'
               '<rect x="24" y="22" width="22" height="14" rx="6" fill="#fff"/><path d="M46 28H114V40H46Z" fill="#748ffc"/><path d="M28 56V66M110 56V66" fill="none" stroke-width="4"/>'),
    "box": svg("0 0 100 80", '<rect x="6" y="14" width="88" height="62" rx="3" fill="#d9a35b"/><path d="M6 14L20 4H80L94 14" fill="#e8c088"/>'
               '<path d="M6 30H94M50 14V76" fill="none" stroke-width="1.8"/>'),
    "plant": svg("0 0 70 100", '<path d="M35 64Q20 40 8 34Q22 30 35 50M35 60Q48 34 62 30Q56 46 36 62M35 64V30Q30 16 35 6Q42 18 35 30" fill="#51cf66"/>'
                 '<path d="M14 64H56L50 96H20Z" fill="#e8590c"/>'),
    "well": svg("0 0 100 110", '<path d="M8 30L50 4L92 30Z" fill="#c92a2a"/><path d="M16 30V70M84 30V70" fill="none" stroke-width="5" stroke="' + INK + '"/>'
                '<path d="M16 30V70M84 30V70" fill="none" stroke-width="2.5" stroke="#8a5a2b"/><path d="M50 30V52" fill="none"/><rect x="44" y="52" width="12" height="10" fill="#adb5bd"/>'
                '<path d="M6 70H94V106H6Z" fill="#adb5bd"/><path d="M6 82H94M6 94H94M30 70V82M60 70V82M45 82V94M75 82V94M20 94V106M58 94V106" fill="none" stroke-width="1.5"/>'),
    "wand": svg("0 0 100 100", '<path d="M10 92L62 40" fill="none" stroke-width="9" stroke="' + INK + '"/><path d="M10 92L62 40" fill="none" stroke-width="5" stroke="#8a5a2b"/>'
                '<path d="M74 8L79 22L94 22L82 31L87 46L74 37L61 46L66 31L54 22L69 22Z" fill="#74c0fc"/><path d="M40 20l4 4M90 56l4 4M22 50l3-3" stroke="#fcc419" stroke-width="3"/>'),
    # ---------------------------------------------------------------- characters
    "wizard": svg("0 0 80 120", '<path d="M40 2L62 44H18Z" fill="#5f3dc4"/><circle cx="44" cy="22" r="3" fill="#ffd43b" stroke="none"/><path d="M8 46H72" stroke-width="6" stroke="' + INK + '"/>'
                  '<path d="M8 46H72" stroke-width="3" stroke="#7048e8"/><circle cx="40" cy="58" r="13" fill="#ffd8a8"/>'
                  '<path d="M26 64Q40 100 54 64Q48 74 40 74T26 64Z" fill="#f1f3f5"/><path d="M18 118L26 74H54L62 118Z" fill="#7048e8"/>'
                  + EYES.format(35, 45, 56, INK)),
    "robot": svg("0 0 80 120", '<path d="M40 4V16" fill="none"/><circle cx="40" cy="4" r="3.5" fill="#e03131"/><rect x="14" y="16" width="52" height="38" rx="10" fill="#ced4da"/>'
                 '<rect x="22" y="26" width="36" height="16" rx="6" fill="#343a40"/><circle cx="32" cy="34" r="4" fill="#4dabf7" stroke="none"/><circle cx="48" cy="34" r="4" fill="#4dabf7" stroke="none"/>'
                 '<rect x="18" y="58" width="44" height="40" rx="8" fill="#adb5bd"/><circle cx="40" cy="74" r="7" fill="#ffd43b"/>'
                 '<path d="M18 66L6 82M62 66L74 82M28 98V116M52 98V116" fill="none" stroke-width="5"/>'),
    "cat": svg("0 0 100 90", '<path d="M70 70Q96 70 92 40" fill="none" stroke-width="7" stroke="' + INK + '"/><path d="M70 70Q96 70 92 40" fill="none" stroke-width="3.5" stroke="#495057"/>'
               '<ellipse cx="50" cy="68" rx="28" ry="20" fill="#495057"/><path d="M18 30L20 6L36 20Q46 16 56 20L72 6L74 30Q78 52 46 52T18 30Z" fill="#495057"/>'
               '<ellipse cx="36" cy="32" rx="4" ry="5" fill="#ffd43b" stroke="none"/><ellipse cx="58" cy="32" rx="4" ry="5" fill="#ffd43b" stroke="none"/>'
               '<path d="M44 40L48 44L52 40" fill="#ffa8a8" stroke-width="1.5"/>'),
    "dragon": svg("0 0 120 100", '<path d="M44 48L20 14L58 36Z" fill="#94d82d"/><ellipse cx="60" cy="68" rx="34" ry="24" fill="#40c057"/>'
                  '<path d="M90 70Q116 70 112 48L104 58" fill="none" stroke-width="6"/><path d="M8 44Q8 26 30 26Q48 26 46 46Q44 60 26 58Q8 58 8 44Z" fill="#40c057"/>'
                  '<path d="M44 76Q60 86 76 76" fill="#d8f5a2"/><circle cx="24" cy="38" r="4" fill="' + INK + '" stroke="none"/><path d="M12 48L6 50" fill="none"/>'
                  '<path d="M40 90V98M78 90V98" stroke-width="5"/><path d="M30 26L34 16L38 26M44 34L50 26" fill="#fab005" stroke-width="2"/>'),
    "ghost": svg("0 0 80 100", '<path d="M8 96V44Q8 6 40 6T72 44V96L62 88L52 96L40 88L28 96L18 88Z" fill="#f8f9fa"/>'
                 + EYES.format(30, 50, 40, INK) + '<ellipse cx="40" cy="56" rx="6" ry="8" fill="' + INK + '" stroke="none"/>'
                 '<circle cx="22" cy="50" r="4" fill="#ffc9c9" stroke="none"/><circle cx="58" cy="50" r="4" fill="#ffc9c9" stroke="none"/>'),
    "knight": svg("0 0 80 120", '<path d="M40 2Q54 2 54 14" fill="none" stroke="#e03131" stroke-width="5"/><path d="M20 22Q20 4 40 4T60 22V48H20Z" fill="#ced4da"/>'
                  '<path d="M24 26H56V34H24Z" fill="#343a40"/><path d="M40 34V48" fill="none"/><path d="M16 118L22 50H58L64 118Z" fill="#adb5bd"/>'
                  '<path d="M4 60H28V88Q16 98 4 88Z" fill="#1c7ed6"/><path d="M16 64V92M6 72H26" stroke="#ffd43b" stroke-width="3"/><path d="M70 40V100" stroke-width="5"/>'),
    "pirate": svg("0 0 80 120", '<path d="M10 30Q40 0 70 30Z" fill="#212529"/><path d="M36 14l8 8M44 14l-8 8" stroke="#fff" stroke-width="2"/><circle cx="40" cy="42" r="14" fill="#ffd8a8"/>'
                  '<path d="M26 36L54 36" fill="none" stroke-width="2"/><circle cx="46" cy="40" r="5" fill="' + INK + '"/><circle cx="33" cy="41" r="2.5" fill="' + INK + '" stroke="none"/>'
                  '<path d="M30 50Q40 64 50 50" fill="#8a5a2b"/><path d="M18 118L22 58H58L62 118Z" fill="#e03131"/><path d="M22 70H58M22 84H58M22 98H58" stroke="#fff" stroke-width="4"/>'),
    "alien": svg("0 0 80 120", '<path d="M28 18L22 4M52 18L58 4" fill="none"/><circle cx="22" cy="4" r="3" fill="#fcc419"/><circle cx="58" cy="4" r="3" fill="#fcc419"/>'
                 '<ellipse cx="40" cy="38" rx="26" ry="24" fill="#8ce99a"/><circle cx="28" cy="34" r="6" fill="#fff"/><circle cx="40" cy="28" r="6" fill="#fff"/><circle cx="52" cy="34" r="6" fill="#fff"/>'
                 '<circle cx="28" cy="35" r="2.5" fill="' + INK + '" stroke="none"/><circle cx="40" cy="29" r="2.5" fill="' + INK + '" stroke="none"/><circle cx="52" cy="35" r="2.5" fill="' + INK + '" stroke="none"/>'
                 '<path d="M30 48Q40 56 50 48" fill="none"/><path d="M20 118L26 62H54L60 118Z" fill="#69db7c"/><path d="M26 70L10 56M54 70L70 56" fill="none" stroke-width="4"/>'),
    "owl": svg("0 0 80 100", '<path d="M14 18L22 30M66 18L58 30" fill="none" stroke-width="4"/><ellipse cx="40" cy="56" rx="28" ry="38" fill="#a9733c"/>'
               '<ellipse cx="40" cy="70" rx="16" ry="20" fill="#e8c088"/><circle cx="28" cy="40" r="11" fill="#fff"/><circle cx="52" cy="40" r="11" fill="#fff"/>'
               '<circle cx="28" cy="40" r="5" fill="#f59f00"/><circle cx="52" cy="40" r="5" fill="#f59f00"/><path d="M36 50L40 58L44 50Z" fill="#f59f00"/>'
               '<path d="M28 94L24 98M52 94L56 98" fill="none" stroke-width="3"/>'),
}

STONE = '<path d="{0}" fill="none" stroke="#00000033" stroke-width="2"/>'
ROOMS = {
    "tower": room('<rect width="400" height="300" fill="#6c6a7e"/><rect y="215" width="400" height="85" fill="#7c5a3c"/>'
                  '<path d="M0 230H400M0 252H400M0 276H400M70 215V300M170 215V300M260 215V300M340 215V300" stroke="#00000030" stroke-width="2"/>'
                  + STONE.format("M0 40H400M0 80H400M0 120H400M0 160H400M0 200H400M40 0V40M120 0V40M200 0V40M280 0V40M360 0V40M80 40V80M160 40V80M240 40V80M320 40V80"
                                 "M40 80V120M120 80V120M200 80V120M280 80V120M360 80V120M80 120V160M160 120V160M240 120V160M320 120V160M40 160V200M120 160V200M200 160V200M280 160V200M360 160V200")
                  + '<path d="M196 40Q196 24 210 24T224 40V112H196Z" fill="#1c2a6b" stroke="#3a3346" stroke-width="4"/><circle cx="212" cy="54" r="2" fill="#fff"/><circle cx="204" cy="80" r="1.5" fill="#fff"/>'
                  '<ellipse cx="200" cy="262" rx="120" ry="22" fill="#c92a2a" opacity=".55"/>'),
    "library": room('<rect width="400" height="300" fill="#4a3322"/><rect y="220" width="400" height="80" fill="#6b4c33"/><path d="M0 220H400" stroke="#2e2014" stroke-width="6"/>'
                    '<path d="M0 60H400M0 140H400" stroke="#3a281a" stroke-width="10"/><path d="M180 0V220M260 0V220" stroke="#3a281a" stroke-width="8"/>'
                    '<rect x="190" y="160" width="60" height="58" fill="#7c5a3c" stroke="#2e2014" stroke-width="4"/>'
                    '<ellipse cx="220" cy="262" rx="130" ry="20" fill="#5c7cfa" opacity=".35"/><path d="M290 40l6 14 14 2-10 10 2 14-12-7-12 7 2-14-10-10 14-2z" fill="#fcc41955"/>'),
    "hall": room('<rect width="400" height="300" fill="#868e96"/><rect y="230" width="400" height="70" fill="#5c5f66"/>'
                 + STONE.format("M0 50H400M0 100H400M0 150H400M0 200H400M60 0V50M160 0V50M260 0V50M360 0V50M110 50V100M210 50V100M310 50V100M60 100V150M160 100V150M260 100V150M360 100V150"
                                "M110 150V200M210 150V200M310 150V200M0 255H400M50 230V300M130 230V300M210 230V300M290 230V300M370 230V300")
                 + '<path d="M196 68h8v30h-8z" fill="#5c3d2e"/><path d="M200 46q12 14 0 24q-12-10 0-24z" fill="#ff922b"/><path d="M200 54q5 8 0 13q-5-5 0-13z" fill="#ffe066"/>'
                 '<path d="M0 230H400" stroke="#3a3346" stroke-width="4"/>'),
    "hallway": room('<rect width="400" height="300" fill="#f3d9a4"/><path d="M0 0H400V40H0Z" fill="#fff4e0"/><path d="M0 40H400" stroke="#c9a227" stroke-width="4"/>'
                    '<path d="M20 40V230M60 40V230M100 40V230M140 40V230M180 40V230M220 40V230M260 40V230M300 40V230M340 40V230M380 40V230" stroke="#e8c08855" stroke-width="10"/>'
                    '<rect x="96" y="80" width="44" height="54" fill="#74c0fc" stroke="#8a5a2b" stroke-width="6"/><rect x="250" y="76" width="56" height="44" fill="#ffa8a8" stroke="#8a5a2b" stroke-width="6"/>'
                    '<rect y="230" width="400" height="70" fill="#a9733c"/><path d="M0 230H400" stroke="#6b4c33" stroke-width="5"/>'
                    '<path d="M0 250H400M0 272H400" stroke="#8a5a2b" stroke-width="2"/><rect x="120" y="244" width="170" height="44" rx="8" fill="#c92a2a" opacity=".7"/>'),
    "cabin": room('<rect width="400" height="300" fill="#dee6ee"/><rect y="236" width="400" height="64" fill="#9aa7b8"/>'
                  '<path d="M0 236H400M0 60H400M100 0V236M300 0V236" stroke="#b8c4d2" stroke-width="4"/><path d="M0 268H400" stroke="#868e96" stroke-width="2"/>'
                  '<circle cx="230" cy="74" r="58" fill="#1c2a6b" stroke="#adb5bd" stroke-width="10"/><circle cx="210" cy="60" r="2" fill="#fff"/><circle cx="250" cy="90" r="1.5" fill="#fff"/>'
                  '<circle cx="246" cy="52" r="10" fill="#4dabf7"/><path d="M20 20h40v10h-40z" fill="#e03131"/><circle cx="30" cy="25" r="3" fill="#ffc9c9"/>'),
    "corridor": room('<rect width="400" height="300" fill="#e9eef3"/><path d="M0 0L130 90V200L0 300Z" fill="#cfd8e3"/><path d="M400 0L270 90V200L400 300Z" fill="#cfd8e3"/>'
                     '<path d="M0 300L130 200H270L400 300Z" fill="#9aa7b8"/><rect x="130" y="90" width="140" height="110" fill="#dfe6ee"/>'
                     '<path d="M130 90L0 0M270 90L400 0M130 200L0 300M270 200L400 300" stroke="#adb5bd" stroke-width="3"/>'
                     '<path d="M150 0L175 90M250 0L225 90" stroke="#4dabf7" stroke-width="5" opacity=".7"/><path d="M180 250H220" stroke="#f59f00" stroke-width="6"/>'),
    "bridge": room('<rect width="400" height="300" fill="#343a40"/><path d="M20 20H380L350 170H50Z" fill="#0b1a40" stroke="#868e96" stroke-width="8"/>'
                   '<circle cx="290" cy="80" r="34" fill="#339af0"/><path d="M270 66q14 6 10 22q16-4 22 8" fill="none" stroke="#51cf66" stroke-width="10"/>'
                   '<circle cx="90" cy="50" r="2" fill="#fff"/><circle cx="140" cy="110" r="1.5" fill="#fff"/><circle cx="200" cy="60" r="2" fill="#fff"/><circle cx="330" cy="140" r="1.5" fill="#fff"/>'
                   '<path d="M0 200L60 170H340L400 200V300H0Z" fill="#495057"/><path d="M60 200H340" stroke="#adb5bd" stroke-width="3"/>'
                   '<rect x="90" y="210" width="40" height="18" rx="3" fill="#63e6be"/><rect x="270" y="210" width="40" height="18" rx="3" fill="#ffd43b"/>'),
    "engine": room('<rect width="400" height="300" fill="#2b3036"/><rect y="236" width="400" height="64" fill="#495057"/>'
                   '<path d="M0 236H400M0 256H400" stroke="#343a40" stroke-width="3"/><path d="M0 30H400M0 50H400" stroke="#868e96" stroke-width="8"/>'
                   '<path d="M40 50V236M360 50V236" stroke="#5c636a" stroke-width="16"/><path d="M40 120H100M300 160H360" stroke="#f08c00" stroke-width="8"/>'
                   '<circle cx="80" cy="200" r="6" fill="#e03131"/><circle cx="320" cy="200" r="6" fill="#40c057"/>'),
    "storage": room('<rect width="400" height="300" fill="#ced4da"/><rect y="240" width="400" height="60" fill="#868e96"/>'
                    '<path d="M0 240H400" stroke="#495057" stroke-width="4"/><path d="M250 40V240M390 40V240" stroke="#495057" stroke-width="6"/>'
                    '<path d="M250 100H390M250 170H390" stroke="#495057" stroke-width="6"/><rect x="262" y="66" width="40" height="32" fill="#d9a35b" stroke="#2a2330" stroke-width="2"/>'
                    '<rect x="320" y="72" width="54" height="26" fill="#74c0fc" stroke="#2a2330" stroke-width="2"/><rect x="270" y="136" width="60" height="32" fill="#d9a35b" stroke="#2a2330" stroke-width="2"/>'
                    '<rect x="270" y="206" width="90" height="32" fill="#adb5bd" stroke="#2a2330" stroke-width="2"/><path d="M40 20h120v12h-120z" fill="#ffd43b"/>'),
    "dark": room('<rect width="400" height="300" fill="#141018"/><rect y="220" width="400" height="80" fill="#1d1820"/>'
                 '<path d="M0 220H400M0 60H400M0 140H400M180 0V220M260 0V220" stroke="#241d28" stroke-width="6"/>'
                 '<circle cx="80" cy="90" r="2" fill="#ffd43b" opacity=".5"/><circle cx="92" cy="90" r="2" fill="#ffd43b" opacity=".5"/>'
                 '<ellipse cx="200" cy="262" rx="130" ry="20" fill="#221c27"/>'),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in {**ASSETS, **ROOMS}.items():
        (OUT / f"{name}.svg").write_text(body + "\n", encoding="utf-8")
    print(f"{len(ASSETS)} assets and {len(ROOMS)} rooms written to {OUT}")


if __name__ == "__main__":
    main()
