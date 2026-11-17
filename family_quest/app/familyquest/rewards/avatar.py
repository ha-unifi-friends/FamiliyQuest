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
    "degu": (_t("Degu"), "pet", {"cost": 120}),
    "hamster": (_t("Hamster"), "pet", {"cost": 300}),
    # back, costumes and more fun things (shop)
    "jetpack": (_t("Jetpack"), "back", {"cost": 500}),
    "lightsaber": (_t("Laser sword"), "hand", {"cost": 1500}),
    "dark_helmet": (_t("Dark knight helmet"), "hat", {"cost": 2500}),
    "bat_mask": (_t("Bat mask"), "hat", {"cost": 500}),
    "devil_horns": (_t("Devil horns"), "hat", {"cost": 600}),
    "pirate_apprentice": (_t("Pirate apprentice"), "suit", {"cost": 3500}),
    "wings": (_t("Wings"), "back", {"cost": 100}),
    "chicken_suit": (_t("Chicken suit"), "suit", {"cost": 150}),
    "camo_sweater": (_t("Camo sweater"), "suit", {"cost": 20}),
    "helmet": (_t("Helmet"), "hat", {"cost": 50}),
    "mouse_ears": (_t("Mouse ears hat"), "hat", {"cost": 5}),
    "drink_helmet": (_t("Drinking helmet with straws"), "hat", {"cost": 30}),
    "earbuds": (_t("White wireless earbuds"), "ear", {"cost": 750}),
    "pants_head": (_t("White underpants on the head"), "hat", {"cost": 20}),
    "tshirt_pets": (_t("T-shirt «I love my pets»"), "suit", {"cost": 35}),
    "round_belly": (_t("Round belly"), "figure", {"cost": 50}),
    "pyjamas": (_t("Pyjamas"), "suit", {"cost": 40}),
    "sleep_mask": (_t("Sleep mask"), "eyewear", {"cost": 15}),
    "sleep_cap": (_t("Nightcap"), "hat", {"cost": 15}),
    "bg_rainbow": (_t("Rainbow"), "background", {"cost": 60}),
    "monocle": (_t("Monocle"), "eyewear", {"cost": 40}),
    "dino": (_t("Dinosaur"), "pet", {"cost": 400}),        # starts as an egg and hatches on day 1 (pets.py)
    "goldfish": (_t("Goldfish"), "pet", {"cost": 60}),
    "turtle": (_t("Turtle"), "pet", {"cost": 120}),     # special: mines coins on its wheel while it is healthy (pets.py)
    # backgrounds for new XP: every 500 XP earned from now on unlock one – the XP account itself stays as it is
    "bg_sunset": (_t("Sunset beach"), "background", {"xp": 500}),
    "bg_forest": (_t("Forest"), "background", {"xp": 500}),
    "bg_desert": (_t("Desert"), "background", {"xp": 500}),
    "bg_ocean": (_t("Under the sea"), "background", {"xp": 500}),
    "bg_space": (_t("Space"), "background", {"xp": 500}),
    "bg_snow": (_t("Snowy hills"), "background", {"xp": 500}),
    "bg_city": (_t("City at night"), "background", {"xp": 500}),
    "bg_volcano": (_t("Volcano"), "background", {"xp": 500}),
    "bg_aurora": (_t("Northern lights"), "background", {"xp": 500}),
    "bg_meadow": (_t("Flower meadow"), "background", {"xp": 500}),
    "bg_candy": (_t("Candy land"), "background", {"xp": 500}),
    "bg_castle": (_t("Castle"), "background", {"xp": 500}),
    "bg_balloons": (_t("Hot-air balloons"), "background", {"xp": 500}),
    "bg_autumn": (_t("Autumn leaves"), "background", {"xp": 500}),
    "bg_savanna": (_t("Savanna"), "background", {"xp": 500}),
}

XP_ITEMS_FROM = "xp_items_from"      # setting: the ledger id from which XP count for the XP backgrounds («new» XP)


def xp_used(bought: set[str]) -> int:
    """New XP already used for XP items (the XP account is not touched)."""
    return sum(int(ITEMS[i][2]["xp"]) for i in bought if i in ITEMS and "xp" in ITEMS[i][2])

# given by the parents for one day (parent area › Overview › 👑) – cannot be chosen or bought
ROYAL = "royal"
# won the last family game: the «No. 1» hat until the next family game (community.family_result) – cannot be bought
CHAMPION = "champion"

SLOTS = ["background", "hat", "hairclip", "eyewear", "face", "teeth", "ear", "neck", "suit", "figure", "back", "hand", "pet"]

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
    elif "cost" in rule or "xp" in rule:
        unlocked = item_id in bought
    elif "season" in rule:
        unlocked = t.month in rule["season"]
    if slot == "pet":
        # pets live in the table «pet» (pets.py): owned only while unlocked – a badge brings the pet once, a pet that
        # died is gone until it is bought again
        unlocked = False
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


def with_crown(avatar: dict, crown_until: str | None, today: date | None = None, champion: bool = False) -> dict:
    """The avatar as everybody sees it: with the crown of the day if the parents gave it, else with the «No. 1» hat
    of the last family game won."""
    t = (today or date.today()).isoformat()
    if crown_until and crown_until >= t:
        return {**avatar, "items": {**(avatar.get("items") or {}), "hat": ROYAL}}
    if champion:
        return {**avatar, "items": {**(avatar.get("items") or {}), "hat": CHAMPION}}
    return avatar
