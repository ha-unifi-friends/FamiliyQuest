"""Avatar: parts every child can pick freely, plus items that are unlocked.

The SVG is drawn in the browser (web/shared/avatar.js) from the same ids, so the
server only checks that a chosen item is really unlocked.
"""
from __future__ import annotations

from datetime import date

from ..i18n import _t

FREE_PARTS = {
    "skin": ["#ffe0bd", "#f1c27d", "#e0ac69", "#c68642", "#8d5524", "#5c3a21"],
    "hair": ["short", "long", "curly", "bun", "spiky", "ponytail", "bald"],
    "hairColor": ["#2b1b0e", "#6b3e1f", "#b5651d", "#e6be8a", "#d94f2b", "#111111", "#9aa0a6", "#7b4fd6", "#f06595"],
    "eyes": ["round", "happy", "wink", "big", "sad", "sleepy", "dizzy", "angry"],
    "mouth": ["smile", "grin", "open", "neutral", "sad", "wavy"],
    "outfit": ["tshirt", "hoodie", "dress", "sweater", "overall"],
    "outfitColor": ["#4f8cff", "#ff6b6b", "#51cf66", "#fcc419", "#845ef7", "#20c997", "#ff922b", "#495057", "#f783ac"],
}

# id: (English name, slot, unlock rule)
ITEMS: dict[str, tuple[str, str, dict]] = {
    # free for everybody from the start: glasses, braces and hair clips (children who have them want them on the avatar)
    "glasses": (_t("Glasses"), "eyewear", {"free": True}),
    "glasses_square": (_t("Square glasses"), "eyewear", {"free": True}),
    "glasses_pink": (_t("Pink glasses"), "eyewear", {"free": True}),
    "braces": (_t("Braces"), "teeth", {"free": True}),
    "braces_color": (_t("Colourful braces"), "teeth", {"free": True}),
    "clip_bow": (_t("Hair bow"), "hairclip", {"free": True}),
    "clip_star": (_t("Star hair clip"), "hairclip", {"free": True}),
    "clip_heart": (_t("Heart hair clip"), "hairclip", {"free": True}),
    "cap": (_t("Cap"), "hat", {"cost": 40}),
    "earrings": (_t("Earrings"), "ear", {"cost": 30}),
    "sunglasses": (_t("Sunglasses"), "eyewear", {"cost": 50}),
    "headphones": (_t("Headphones"), "ear", {"cost": 60}),
    "hat": (_t("Hat"), "hat", {"level": 5}),
    "beret": (_t("Beret"), "hat", {"badge": "french_star"}),
    "hardhat": (_t("Hard hat"), "hat", {"badge": "chores_50"}),
    "medal": (_t("Medal"), "neck", {"badge": "streak_30"}),
    "scarf": (_t("Scarf"), "neck", {"cost": 45}),
    "crown": (_t("Crown"), "hat", {"level": 20}),
    "wizard": (_t("Wizard hat"), "hat", {"level": 10}),
    "cat": (_t("Cat"), "pet", {"cost": 120}),
    "dog": (_t("Dog"), "pet", {"cost": 120}),
    "owl": (_t("Owl"), "pet", {"badge": "ten_lessons"}),
    "bg_stars": (_t("Starry sky"), "background", {"cost": 80}),
    "bg_mountains": (_t("Mountains"), "background", {"level": 4}),
    "bg_lake": (_t("Lake Constance"), "background", {"badge": "geo_thurgau"}),
    "santa": (_t("Santa hat"), "hat", {"season": [12]}),
    "mask": (_t("Carnival mask"), "eyewear", {"season": [2]}),
    # fun specials – only to earn (buy with coins in the shop)
    "pirate_patch": (_t("Pirate eye patch"), "eyewear", {"cost": 70}),
    "pirate_hat": (_t("Pirate hat"), "hat", {"cost": 90}),
    "viking": (_t("Viking helmet"), "hat", {"cost": 110}),
    "unicorn": (_t("Unicorn horn"), "hat", {"cost": 100}),
    "party_hat": (_t("Party hat"), "hat", {"cost": 50}),
    "antennae": (_t("Alien antennae"), "hat", {"cost": 80}),
    "clown_nose": (_t("Clown nose"), "face", {"cost": 40}),
    "mustache": (_t("Moustache"), "face", {"cost": 45}),
    "mustache_curl": (_t("Twirled moustache"), "face", {"cost": 1000}),
    "bowtie": (_t("Bow tie"), "neck", {"cost": 35}),
    "parrot": (_t("Parrot"), "pet", {"cost": 150}),
}

# given by the parents for one day (parent area › Overview › 👑) – cannot be chosen or bought
ROYAL = "royal"

SLOTS = ["background", "hat", "hairclip", "eyewear", "face", "teeth", "ear", "neck", "pet"]

DEFAULT_AVATAR = {"skin": "#f1c27d", "hair": "short", "hairColor": "#6b3e1f", "eyes": "round", "mouth": "smile",
                  "outfit": "tshirt", "outfitColor": "#4f8cff", "items": {}}


def item_status(item_id: str, level: int, badges: set[str], bought: set[str], today: date | None = None) -> dict:
    name, slot, rule = ITEMS[item_id]
    t = today or date.today()
    unlocked = False
    if rule.get("free"):
        unlocked = True
    elif "level" in rule:
        unlocked = level >= rule["level"]
    elif "badge" in rule:
        unlocked = rule["badge"] in badges
    elif "cost" in rule:
        unlocked = item_id in bought
    elif "season" in rule:
        unlocked = t.month in rule["season"]
    return {"id": item_id, "name": name, "slot": slot, "rule": rule, "unlocked": unlocked or item_id in bought}


def catalog(level: int, badges: set[str], bought: set[str]) -> dict:
    return {"parts": FREE_PARTS, "slots": SLOTS,
            "items": [item_status(i, level, badges, bought) for i in ITEMS]}


def clean(avatar: dict, level: int, badges: set[str], bought: set[str]) -> dict:
    """Keep only valid parts and unlocked items."""
    out = dict(DEFAULT_AVATAR)
    for k, allowed in FREE_PARTS.items():
        if avatar.get(k) in allowed:
            out[k] = avatar[k]
    items = {}
    for slot, iid in (avatar.get("items") or {}).items():
        if iid in ITEMS and ITEMS[iid][1] == slot and item_status(iid, level, badges, bought)["unlocked"]:
            items[slot] = iid
    out["items"] = items
    return out


def with_crown(avatar: dict, crown_until: str | None, today: date | None = None) -> dict:
    """The avatar as everybody sees it: with the crown of the day if the parents gave it."""
    t = (today or date.today()).isoformat()
    if crown_until and crown_until >= t:
        return {**avatar, "items": {**(avatar.get("items") or {}), "hat": ROYAL}}
    return avatar
