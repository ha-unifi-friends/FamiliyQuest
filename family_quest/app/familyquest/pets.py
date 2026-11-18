"""Pet care: the pets of the avatar shop (cat, dog, owl, parrot, degu) want to be fed, played with and washed.

Three bars (0–100) drop slowly: hunger and mood from full to empty in about 2 days, cleanliness in about 3 days.
The decay is computed lazily from `updated_at` on every read – no own background thread; the Home Assistant tick
calls `tick()` now and then so that warnings and death also happen while the child does not open the app.

While the parents pause pet care for a child («Ferienbetreuung») or the Family Planer has the child away on holiday
that day, the bars do not drop and the death timer stands still. If all three bars stay at 0 for 3 days (of
unpaused time), the pet dies: the unlock is removed, it is taken off the avatar and the child sees a gentle message
at the next login. It can be bought again in the shop – as a new baby.

Every pet starts as a baby; stages by age in days: baby 0–6, young 7–29, adult from 30.

Pet sitting: the owner gives a pet to a family member until a day – the sitter sees it in «Pets in my care» and can
feed (pays the food), play and wash; the bars keep dropping as usual. Or the pet goes to the Family Quest pet hotel for
some days (parents' setting `pet_hotel_cost` coins per day, paid at once): no decay, no death, and it comes back fed,
happy and clean. Fetched early, the unused full days are paid back.

More pets of one kind: a further pet of a kind the child has costs the shop price again (at most MAX_PER_KIND per
kind). Two pets of the same kind that are healthy (every bar at least 50) and at least BREED_AGE days old can have 1–2
babies; afterwards both rest BREED_PAUSE days. Babies are new pets (stage baby) like bought ones.

The hamster (special pet): while it is healthy (every bar at least 50) it runs in its wheel and mines coins for its
owner – `hamster_coins_per_day` (parents' setting) spread over the day, booked as whole coins. A baby hamster starts
mining when it is young (from 7 days).

Pet shop: outfits, houses and furniture (SHOP) are bought for one pet with coins or XP (parents' setting
`pet_shop_currency`: coins | xp | mixed). A pet wears one outfit, lives in one house and has up to 6 pieces of furniture
placed. The house makes the mood drop 25 % slower, each placed piece of furniture another 5 % (50 % at most); the first
time an outfit is worn the pet gets +20 mood. Everything is lost with the pet. XP spent here does not lower the level
(rewards.engine.SPEND_EVENTS).
"""
from __future__ import annotations

import functools
import json
import logging
import random
import threading
from datetime import datetime, timedelta
from typing import Callable

from .db import profile_settings
from .i18n import _t
from .rewards import avatar as av

log = logging.getLogger("familyquest.pets")

# kind: (emoji, default name, bot colour)
KINDS: dict[str, tuple[str, str, str]] = {
    "dog": ("🐶", "Bello", "#e8590c"),
    "cat": ("🐱", "Minka", "#f59f00"),
    "owl": ("🦉", "Eulalia", "#7048e8"),
    "parrot": ("🦜", "Coco", "#2f9e44"),
    "degu": ("🐭", "Krümel", "#8d7b68"),       # no degu emoji: the web app draws it (petIcon in avatar.js), 🐭 elsewhere
    "hamster": ("🐹", "Hamsti", "#d9822b"),    # special: mines coins in its wheel while healthy
    "dino": ("🦕", "Rexi", "#2f9e44"),          # starts as an egg (day 0) and hatches on day 1
    "goldfish": ("🐟", "Goldi", "#f76707"),     # the web app draws a goldfish (petIcon), 🐟 elsewhere
    "turtle": ("🐢", "Shelly", "#5c940d"),
}
EGG_KINDS = ("dino",)          # these start as an egg: no care and no decay on the day they come
BARS = ("hunger", "mood", "clean")
# points per hour: full → empty in 48 h (hunger, mood) and 72 h (cleanliness)
RATE = {"hunger": 100 / 48, "mood": 100 / 48, "clean": 100 / 72}
GAIN = {"feed": ("hunger", 40), "play": ("mood", 35), "wash": ("clean", 50)}
LOW = 25                       # below this a bar shows a warning on the start page
DEATH_SECONDS = 3 * 86400      # all bars at 0 for this long (unpaused time) → the pet dies
REBUY_COST = 120               # a pet that was only earned (badge) costs this much after it died
DEFAULT_FOOD_COST = 2
DEFAULT_HOTEL_COST = 10        # pet hotel: coins per day
HOTEL_MAX_DAYS = 30
SIT_MAX_DAYS = 60              # a family member looks after a pet at most this long
HEALTHY = 50                   # the hamster mines while every bar is at least this
MAX_PER_KIND = 6               # living pets of one kind per child
BREED_AGE = 3                  # days old before a pet can have babies
BREED_PAUSE = 14               # days a pair rests after babies
DEFAULT_HAMSTER_RATE = 15      # coins per day of healthy time – 5 more than a day in the pet hotel


# pet shop – id: (category, English name, emoji ('' = drawn in the web app, web/shared/avatar.js PET_SHOP_SVG), price,
# kinds the house fits best). One table: parents only choose the currency, not single prices.
SHOP: dict[str, tuple[str, str, str, int, tuple[str, ...]]] = {
    "bow": ("outfit", _t("Bow"), "🎀", 30, ()),
    "collar": ("outfit", _t("Collar"), "", 30, ()),
    "sweater": ("outfit", _t("Sweater"), "🧶", 50, ()),
    "raincoat": ("outfit", _t("Raincoat"), "", 55, ()),
    "dress": ("outfit", _t("Little dress"), "👗", 60, ()),
    "sunglasses": ("outfit", _t("Sunglasses"), "🕶️", 40, ()),
    "party_hat": ("outfit", _t("Party hat"), "🥳", 45, ()),
    "crown": ("outfit", _t("Crown"), "👑", 80, ()),
    "dog_house": ("house", _t("Dog house"), "", 120, ("dog",)),
    "cat_tree": ("house", _t("Cat basket with scratching tree"), "", 150, ("cat",)),
    "bird_cage": ("house", _t("Bird cage"), "", 140, ("owl", "parrot")),
    "degu_house": ("house", _t("Degu enclosure"), "", 160, ("degu",)),
    "hamster_cage": ("house", _t("Hamster cage"), "", 140, ("hamster",)),
    "aquarium": ("house", _t("Aquarium"), "", 120, ("goldfish",)),
    "terrarium": ("house", _t("Terrarium"), "", 140, ("turtle",)),
    "dino_nest": ("house", _t("Dino nest"), "", 180, ("dino",)),
    "castle": ("house", _t("Castle"), "🏰", 300, ("dog", "cat", "owl", "parrot", "degu", "hamster", "dino", "goldfish", "turtle")),
    "bed": ("furniture", _t("Bed"), "🛏️", 40, ()),
    "bowl": ("furniture", _t("Food bowl"), "🥣", 20, ()),
    "ball": ("furniture", _t("Toy ball"), "⚽", 25, ()),
    "wheel": ("furniture", _t("Play wheel"), "", 60, ()),
    "cushion": ("furniture", _t("Cushion"), "", 30, ()),
    "lamp": ("furniture", _t("Lamp"), "💡", 35, ()),
    "plant": ("furniture", _t("Plant"), "🪴", 30, ()),
    "rug": ("furniture", _t("Rug"), "", 45, ()),
}
OUTFITS = tuple(k for k, v in SHOP.items() if v[0] == "outfit")
CURRENCIES = ("coins", "xp", "mixed")
HOUSE_SLOW = 0.25              # a house: mood drops 25 % slower
FURNITURE_SLOW = 0.05          # each placed piece of furniture another 5 %
MAX_SLOW = 0.5                 # … at most 50 % slower in total
MAX_FURNITURE = 6
OUTFIT_BONUS = 20              # mood, the first time an outfit is worn
HAPPY_HOME = 3                 # a house and at least this many pieces of furniture: ✨ happy home


def slowdown(items: list[dict]) -> float:
    """How much slower the mood drops with the house and furniture in use (0 … MAX_SLOW)."""
    used = [SHOP[i["item"]][0] for i in items if i["used"] and i["item"] in SHOP]
    return min(MAX_SLOW, HOUSE_SLOW * ("house" in used) + FURNITURE_SLOW * used.count("furniture"))


class PetError(ValueError):
    pass


def now() -> datetime:
    """The clock of the pets (tests move it)."""
    return datetime.now().replace(microsecond=0)


def stage(age: int, kind: str = "") -> str:
    if kind in EGG_KINDS and age < 1:
        return "egg"
    return "baby" if age < 7 else "young" if age < 30 else "adult"


def _ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def active_seconds(start: datetime, end: datetime, away: set[str]) -> float:
    """Seconds between start and end that are not on an away day (ISO dates)."""
    if end <= start:
        return 0.0
    if not away:
        return (end - start).total_seconds()
    total, t = 0.0, start
    while t < end:
        nxt = min(end, datetime.combine(t.date() + timedelta(days=1), datetime.min.time()))
        if t.date().isoformat() not in away:
            total += (nxt - t).total_seconds()
        t = nxt
    return total


def serial(fn):
    """One pet change at a time (requests and the Home Assistant tick run in several threads): every read → compute →
    write of the bars, the hamster's coins and the hotel is done under one lock – no double bookings, no lost feeding."""
    @functools.wraps(fn)
    def run(self, *a, **kw):
        with self.lock:
            return fn(self, *a, **kw)
    return run


class Pets:
    def __init__(self, db, rewards):
        self.lock = threading.RLock()
        self.db = db
        self.rewards = rewards
        self.locked: Callable[[int], bool] = lambda pet_id: False     # promised in a deal (deals.py): no hotel, no sitter
        self.away: Callable[[int], set[str]] = lambda pid: set()     # holiday days of the Family Planer (set by services)
        self.on_zero: list[Callable[[dict, dict], None]] = []       # fn(profile, pet) – all bars at 0: tell the parents once
        self.on_change: list[Callable[[int], None]] = []

    # ---------------------------------------------------------------- settings
    def food_cost(self) -> int:
        v = self.db.get_setting("pet_food_cost")
        try:
            return max(0, min(100, int(DEFAULT_FOOD_COST if v is None else v)))
        except (TypeError, ValueError, OverflowError):
            return DEFAULT_FOOD_COST

    def _int_setting(self, key: str, default: int, hi: int) -> int:
        v = self.db.get_setting(key)
        try:
            return max(0, min(hi, int(default if v is None else v)))
        except (TypeError, ValueError, OverflowError):
            return default

    def hotel_cost(self) -> int:
        return self._int_setting("pet_hotel_cost", DEFAULT_HOTEL_COST, 1000)

    def hamster_rate(self) -> int:
        return self._int_setting("hamster_coins_per_day", DEFAULT_HAMSTER_RATE, 1000)

    def paused_by_parents(self, pid: int) -> bool:
        p = self.db.q1("SELECT settings FROM profile WHERE id=?", pid)
        return bool(p and profile_settings(p).get("pets_paused"))

    def _away(self, pid: int) -> set[str]:
        try:
            return set(self.away(pid) or ())
        except Exception:  # noqa: BLE001 – the planner must never break the pets
            log.exception("away days not readable")
            return set()

    @serial
    def set_paused(self, pid: int, on: bool) -> None:
        """Parents switch «Ferienbetreuung» on or off – the time so far is counted first."""
        p = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        if not p:
            raise PetError("Unknown profile")
        self.refresh(pid)
        st = json.loads(p["settings"] or "{}")
        if on:
            st["pets_paused"] = True
        else:
            st.pop("pets_paused", None)
        stamp = now().isoformat()
        with self.db.tx():
            self.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), pid)
            # the paused time does not count: the clock of every living pet restarts now
            self.db.x("UPDATE pet SET updated_at=? WHERE profile_id=? AND dead_at IS NULL", stamp, pid)
        self._changed(pid)

    # ---------------------------------------------------------------- records
    def _bought(self, pid: int) -> set[str]:
        return {r["item"] for r in self.db.q("SELECT item FROM unlock WHERE profile_id=?", pid)}

    @serial
    def sync(self, pid: int) -> None:
        """Every owned pet has a living record: bought ones (also from before pet care existed) and the badge owl."""
        bought = self._bought(pid)
        badges = None
        rows = self.db.q("SELECT kind, dead_at FROM pet WHERE profile_id=?", pid)
        alive = {r["kind"] for r in rows if not r["dead_at"]}
        ever = {r["kind"] for r in rows}
        for kind in KINDS:
            if kind in alive or kind not in av.ITEMS:
                continue
            rule = av.ITEMS[kind][2]
            owned = kind in bought
            if not owned and "badge" in rule and kind not in ever:
                # earned with a badge: the pet comes once – after it died it has to be bought
                if badges is None:
                    badges = {r["badge"] for r in self.db.q("SELECT badge FROM badge WHERE profile_id=?", pid)}
                owned = rule["badge"] in badges
                if owned:
                    self.db.x("INSERT OR IGNORE INTO unlock(profile_id,item) VALUES(?,?)", pid, kind)
            if owned:
                self.adopt(pid, kind)

    @serial
    def adopt(self, pid: int, kind: str) -> int:
        """A new pet (a baby) – unless this kind is alive already."""
        row = self.db.q1("SELECT id FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", pid, kind)
        if row:
            return row["id"]
        stamp = now().isoformat()
        return self.db.x("""INSERT INTO pet(profile_id, kind, name, born_at, updated_at) VALUES(?,?,?,?,?)""",
                         pid, kind, KINDS[kind][1], stamp, stamp)

    def lost_kinds(self, pid: int) -> set[str]:
        """Kinds whose pet died and that the child has not got again – they can be bought in the shop."""
        rows = self.db.q("SELECT kind, dead_at FROM pet WHERE profile_id=?", pid)
        alive = {r["kind"] for r in rows if not r["dead_at"]}
        return {r["kind"] for r in rows if r["dead_at"]} - alive - self._bought(pid)

    # ---------------------------------------------------------------- decay
    def _advance(self, pet: dict, t: datetime, paused: bool, away: set[str], slow: float = 0.0) -> dict:
        """Bring a pet to time t (in place) – returns the changed fields. `slow`: the mood drops this much slower (home)."""
        last = _ts(pet["updated_at"]) or t
        secs = 0.0 if paused else active_seconds(last, t, away)
        vals = {b: float(pet[b]) for b in BARS}
        if secs > 0:
            rate = {**RATE, "mood": RATE["mood"] * (1 - slow)}
            born = _ts(pet.get("born_at"))
            if pet.get("kind") == "hamster" and born and (t.date() - born.date()).days >= 7:
                # healthy until the first bar drops below HEALTHY – that time the wheel turns and mines coins
                healthy = min(max(0.0, (vals[b] - HEALTHY) / rate[b] * 3600) for b in BARS)
                pet["mined"] = float(pet.get("mined") or 0) + min(secs, healthy) / 86400 * self.hamster_rate()
            # how long until the last bar reaches 0 – everything after that is time «all at 0»
            to_zero = max(vals[b] / rate[b] * 3600 for b in BARS)
            for b in BARS:
                vals[b] = max(0.0, vals[b] - rate[b] * secs / 3600)
            if secs > to_zero:
                pet["zero_secs"] = float(pet["zero_secs"] or 0) + secs - to_zero
        pet.update(vals, updated_at=t.isoformat())
        return pet

    @serial
    def refresh(self, pid: int) -> list[dict]:
        """Update the bars of all living pets of a profile; pets that died now are handled. Returns the living pets."""
        self.sync(pid)
        t = now()
        paused = self.paused_by_parents(pid)
        away = self._away(pid)
        out, ended = [], set()
        items = self._items(pid)
        for pet in self.db.q("SELECT * FROM pet WHERE profile_id=? AND dead_at IS NULL ORDER BY born_at, id", pid):
            pet["_items"] = items.get(pet["id"], [])
            if pet["sit_until"] and t.date().isoformat() > pet["sit_until"]:
                ended.add(pet["sitter_id"])
                pet["sitter_id"] = pet["sit_until"] = None                # the sitting is over: back with the owner
            # with a sitter the pet is in their hands: the owner's holiday pause does not stop the bars (the sitter's does)
            p_paused, p_away = (False, self._away(pet["sitter_id"])) if pet["sitter_id"] else (paused, away)
            hotel = _ts(pet["hotel_until"])
            born = _ts(pet["born_at"]) or t
            if pet["kind"] in EGG_KINDS and t.date() == born.date():
                pet["updated_at"] = t.isoformat()                         # still an egg: nothing to care for yet
            elif hotel and t < hotel:
                pet["updated_at"] = t.isoformat()                         # in the pet hotel: well looked after
            else:
                if hotel:                                                 # back from the hotel: fed, happy and clean
                    pet.update(hunger=100.0, mood=100.0, clean=100.0, zero_secs=0.0, zero_since=None,
                               updated_at=hotel.isoformat(), hotel_until=None)
                self._advance(pet, t, p_paused, p_away, slowdown(pet["_items"]))
            all_zero = all(pet[b] <= 0 for b in BARS)
            if all_zero and pet["zero_secs"] >= DEATH_SECONDS:
                self._die(pid, pet, t)
                continue
            notify = False
            if all_zero and not pet["zero_since"]:
                pet["zero_since"] = t.isoformat()
                notify = True
            elif not all_zero:
                pet["zero_since"] = None
                pet["zero_secs"] = 0.0         # cared for again: the death timer starts from the beginning
            coins = int(pet["mined"] or 0)
            if coins >= 1:                                                # the hamster's coins, whole ones
                pet["mined"] = float(pet["mined"]) - coins
                pet["mined_total"] = int(pet["mined_total"] or 0) + coins
                self.rewards.book(pid, "coins", float(coins), "hamster", f"🐹 {pet['name']}", f"pet:{pet['id']}")
            self.db.x("""UPDATE pet SET hunger=?, mood=?, clean=?, updated_at=?, zero_secs=?, zero_since=?, sitter_id=?, sit_until=?,
                         hotel_until=?, mined=?, mined_total=? WHERE id=?""",
                      pet["hunger"], pet["mood"], pet["clean"], pet["updated_at"], pet["zero_secs"], pet["zero_since"],
                      pet["sitter_id"], pet["sit_until"], pet["hotel_until"], pet["mined"], pet["mined_total"], pet["id"])
            if notify:
                prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
                for fn in self.on_zero:
                    try:
                        fn(prof, pet)
                    except Exception:  # noqa: BLE001
                        log.exception("pet listener failed")
            out.append(pet)
        for sid in ended - {None}:                                         # their «Pets in my care» changed
            self._changed(sid)
        return out

    def _die(self, pid: int, pet: dict, t: datetime) -> None:
        kind = pet["kind"]
        with self.db.tx():
            self.db.x("UPDATE pet SET hunger=0, mood=0, clean=0, updated_at=?, dead_at=? WHERE id=?",
                      t.isoformat(), t.isoformat(), pet["id"])
            others = self.db.val("SELECT COUNT(*) FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", pid, kind, default=0)
            if not others:                     # the last of its kind: the unlock goes (another of the kind keeps it)
                spent = int(self.db.val("SELECT new_xp FROM unlock WHERE profile_id=? AND item=?", pid, kind, default=0) or 0)
                if spent > 0:                  # new XP paid for it stay spent (they do not come back with the death)
                    self.db.x("""INSERT INTO xp_spent(profile_id, n) VALUES(?,?)
                                 ON CONFLICT(profile_id) DO UPDATE SET n=n+excluded.n""", pid, spent)
                self.db.x("DELETE FROM unlock WHERE profile_id=? AND item=?", pid, kind)
            self.db.x("DELETE FROM pet_item WHERE pet_id=?", pet["id"])          # outfits, house, furniture go with it
            p = self.db.q1("SELECT avatar FROM profile WHERE id=?", pid)
            a = json.loads((p or {}).get("avatar") or "{}")
            if not others and (a.get("items") or {}).get("pet") == kind:
                a["items"].pop("pet", None)
                self.db.x("UPDATE profile SET avatar=? WHERE id=?", json.dumps(a), pid)
            # a note in the history of the account (amount 0)
            self.rewards.book(pid, "coins", 0.0, "pet_died", f"🕊️ {pet['name']}", f"pet:{pet['id']}")
        log.info("pet %s of profile %s died", pet["id"], pid)
        self._changed(pid)
        if pet.get("sitter_id"):
            self._changed(pet["sitter_id"])

    def tick(self) -> None:
        """All profiles with living pets – called from the periodic loop (warnings, parents' message, death)."""
        for r in self.db.q("""SELECT DISTINCT p.profile_id FROM pet p JOIN profile f ON f.id=p.profile_id
                              WHERE p.dead_at IS NULL AND f.archived=0"""):
            try:
                self.refresh(r["profile_id"])
            except Exception:  # noqa: BLE001
                log.exception("pet tick failed")

    # ---------------------------------------------------------------- read models
    def _view(self, pet: dict, paused: str | None, t: datetime) -> dict:
        born = _ts(pet["born_at"]) or t
        age = max(0, (t.date() - born.date()).days)
        all_zero = all(pet[b] <= 0 for b in BARS)
        left = max(0.0, DEATH_SECONDS - float(pet["zero_secs"] or 0)) / 86400
        hotel = pet.get("hotel_until") if _ts(pet.get("hotel_until")) and _ts(pet["hotel_until"]) > t else None
        sitter = self.db.q1("SELECT id, name FROM profile WHERE id=?", pet["sitter_id"]) if pet.get("sitter_id") else None
        out = {"id": pet["id"], "kind": pet["kind"], "emoji": KINDS[pet["kind"]][0], "name": pet["name"],
               "age": age, "stage": stage(age, pet["kind"]), "born_at": pet["born_at"],
               "hunger": round(pet["hunger"]), "mood": round(pet["mood"]), "clean": round(pet["clean"]),
               "low": [] if hotel else [b for b in BARS if pet[b] < LOW], "dying": all_zero and not hotel,
               "days_left": round(left, 1) if all_zero else None,
               "paused": paused or ("hotel" if hotel else None), "hotel_until": hotel,
               "sitter": {"id": sitter["id"], "name": sitter["name"]} if sitter else None, "sit_until": pet.get("sit_until") if sitter else None,
               **self._home_view(pet.get("_items") or [])}
        if pet["kind"] == "hamster":
            out["mining"] = {"on": not hotel and not paused and age >= 7 and all(pet[b] >= HEALTHY for b in BARS), "baby": age < 7,
                             "per_day": self.hamster_rate(), "total": int(pet.get("mined_total") or 0)}
        return out

    @staticmethod
    def _home_view(items: list[dict]) -> dict:
        used = [i["item"] for i in items if i["used"] and i["item"] in SHOP]
        house = next((i for i in used if SHOP[i][0] == "house"), None)
        furniture = [i for i in used if SHOP[i][0] == "furniture"]
        return {"outfit": next((i for i in used if SHOP[i][0] == "outfit"), None), "house": house, "furniture": furniture,
                "owned": sorted(i["item"] for i in items if i["item"] in SHOP),
                "slow": round(slowdown(items) * 100), "happy_home": bool(house) and len(furniture) >= HAPPY_HOME}

    def pause_reason(self, pid: int) -> str | None:
        if self.paused_by_parents(pid):
            return "parents"
        if now().date().isoformat() in self._away(pid):
            return "away"
        return None

    def list(self, pid: int) -> list[dict]:
        t = now()
        reason = self.pause_reason(pid)
        return [self._view(p, reason, t) for p in self.refresh(pid)]

    def sitting(self, pid: int) -> list[dict]:
        """Pets of other family members this profile looks after just now (with the owner's name)."""
        out, t = [], now()
        for owner in {r["profile_id"] for r in self.db.q("SELECT profile_id FROM pet WHERE sitter_id=? AND dead_at IS NULL", pid)}:
            reason = self.pause_reason(owner)
            name = self.db.val("SELECT name FROM profile WHERE id=?", owner)
            out += [{**self._view(p, reason, t), "owner": {"id": owner, "name": name}}
                    for p in self.refresh(owner) if p["sitter_id"] == pid]
        return out

    def summary(self, pid: int) -> dict:
        """For the start page: living pets and the ones that died since the child last looked."""
        dead = self.db.q("SELECT id, kind, name, dead_at FROM pet WHERE profile_id=? AND dead_at IS NOT NULL AND seen=0", pid)
        family = [{"id": r["id"], "name": r["name"]} for r in
                  self.db.q("SELECT id, name FROM profile WHERE archived=0 AND id!=? ORDER BY role DESC, name", pid)]
        pets = self.list(pid)
        kinds = sorted({p["kind"] for p in pets})
        more = [{"kind": k, "emoji": KINDS[k][0], "price": self.price(k), "count": self._count(pid, k),
                 "max": MAX_PER_KIND} for k in kinds]
        return {"pets": pets, "food_cost": self.food_cost(), "sitting": self.sitting(pid), "more": more,
                "breeding": self.breeding(pid, pets),
                "hotel_cost": self.hotel_cost(), "family": family,
                "died": [{"id": d["id"], "kind": d["kind"], "emoji": KINDS[d["kind"]][0], "name": d["name"]} for d in dead]}

    def seen(self, pid: int) -> None:
        self.db.x("UPDATE pet SET seen=1 WHERE profile_id=? AND dead_at IS NOT NULL", pid)

    def badge(self, pid: int, kind: str) -> dict | None:
        """What the avatar badge shows: kind, age in days, stage (no decay needed – cheap)."""
        if kind not in KINDS:
            return None
        sql = "SELECT id, born_at FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL ORDER BY born_at, id LIMIT 1"
        row = self.db.q1(sql, pid, kind)
        if not row:
            self.sync(pid)
            row = self.db.q1(sql, pid, kind)
            if not row:
                return None
        age = max(0, (now().date() - (_ts(row["born_at"]) or now()).date()).days)
        outfit = self.db.val("SELECT item FROM pet_item WHERE pet_id=? AND used=1 AND item IN (%s)" % ",".join("?" * len(OUTFITS)),
                             row["id"], *OUTFITS)
        return {"kind": kind, "age": age, "stage": stage(age, kind), "alive": True, **({"outfit": outfit} if outfit else {})}

    def bots(self, pid: int) -> list[dict]:
        """The living pets of a profile as bots for the games (only for their owner)."""
        rows = self.db.q("SELECT id, kind, name FROM pet WHERE profile_id=? AND dead_at IS NULL ORDER BY born_at, id", pid)
        return [{"id": f"pet:{r['id']}", "pet_id": r["id"], "owner_id": pid, "name": r["name"], "emoji": KINDS[r["kind"]][0],
                 "color": KINDS[r["kind"]][2], "level": "normal", "shared": 0, "pet": True, "kind": r["kind"]} for r in rows if r["kind"] in KINDS]

    # ---------------------------------------------------------------- actions
    def _mine(self, pid: int, pet_id: int) -> dict:
        p = self.db.q1("SELECT * FROM pet WHERE id=?", pet_id)
        if not p or p["profile_id"] != pid:
            raise PetError("That is not your pet")
        if p["dead_at"]:
            raise PetError("This pet is no longer here")
        return p

    def _carer(self, pid: int, pet_id: int) -> dict:
        """The owner – or the family member who looks after the pet just now."""
        p = self.db.q1("SELECT * FROM pet WHERE id=?", pet_id)
        if not p or (p["profile_id"] != pid and not (p["sitter_id"] == pid and (p["sit_until"] or "") >= now().date().isoformat())):
            raise PetError("That is not your pet")
        if p["dead_at"]:
            raise PetError("This pet is no longer here")
        return p

    @serial
    def act(self, pid: int, pet_id: int, action: str) -> dict:
        if action not in GAIN:
            raise PetError("Unknown action")
        owner = self._carer(pid, pet_id)["profile_id"]
        self.refresh(owner)
        pet = self._carer(pid, pet_id)         # it may have died just now
        if _ts(pet["hotel_until"]) and _ts(pet["hotel_until"]) > now():
            raise PetError("Your pet is in the pet hotel – it is well looked after there")
        if pet["kind"] in EGG_KINDS and (_ts(pet["born_at"]) or now()).date() == now().date():
            raise PetError("It is still an egg – it hatches tomorrow")
        bar, gain = GAIN[action]
        with self.db.tx():
            if action == "feed":
                if pet["hunger"] >= 95:
                    raise PetError("Your pet is full – feed it later")
                cost = self.food_cost()
                if cost:
                    if self.rewards.available(pid) < cost:
                        raise PetError("Not enough coins for pet food")
                    self.rewards.book(pid, "coins", -float(cost), "pet_food", _t("Pet food") + f" – {pet['name']}", f"pet:{pet_id}")
            val = min(100.0, float(pet[bar]) + gain)
            self.db.x(f"UPDATE pet SET {bar}=?, zero_since=NULL, zero_secs=0 WHERE id=?", val, pet_id)
        self._changed(pid)
        if owner != pid:                       # the sitter cared: the owner's app shows it too
            self._changed(owner)
            return next((p for p in self.sitting(pid) if p["id"] == pet_id), {})
        return self.get(pid, pet_id)

    # ---------------------------------------------------------------- more pets of one kind, babies
    def price(self, kind: str) -> int:
        rule = av.rule_of(kind) if kind in av.ITEMS else {}
        return int(rule.get("cost", REBUY_COST))

    def _count(self, pid: int, kind: str) -> int:
        return int(self.db.val("SELECT COUNT(*) FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", pid, kind, default=0))

    def _new_name(self, pid: int, kind: str) -> str:
        names = {r["name"] for r in self.db.q("SELECT name FROM pet WHERE profile_id=? AND kind=? AND dead_at IS NULL", pid, kind)}
        base, n = KINDS[kind][1], 2
        while f"{base} {n}" in names:
            n += 1
        return base if base not in names else f"{base} {n}"

    def _born(self, pid: int, kind: str) -> int:
        stamp = now().isoformat()
        return self.db.x("INSERT INTO pet(profile_id, kind, name, born_at, updated_at) VALUES(?,?,?,?,?)",
                         pid, kind, self._new_name(pid, kind), stamp, stamp)

    @serial
    def buy_another(self, pid: int, kind: str) -> dict:
        """One more pet of a kind the child already has – same price as in the shop."""
        if kind not in KINDS:
            raise PetError("Unknown pet")
        if not self._count(pid, kind):
            raise PetError("Buy this pet in the shop first")
        if self._count(pid, kind) >= MAX_PER_KIND:
            raise PetError("At most 6 pets of one kind")
        cost = self.price(kind)
        with self.db.tx():
            if self.rewards.available(pid) < cost:
                raise PetError("Not enough coins")
            self.rewards.book(pid, "coins", -float(cost), "avatar", av.ITEMS.get(kind, (kind,))[0], f"pet:more:{kind}")
            new = self._born(pid, kind)
        self._changed(pid)
        return self.get(pid, new)

    def _breed_check(self, pet: dict, t: datetime) -> str | None:
        """Why this pet cannot have babies now (None: it can)."""
        born = _ts(pet["born_at"]) or t
        if (t.date() - born.date()).days < BREED_AGE:
            return "too_young"
        if any(pet[b] < HEALTHY for b in BARS):
            return "not_healthy"
        if _ts(pet.get("hotel_until")) and _ts(pet["hotel_until"]) > t:
            return "away"
        bred = _ts(pet.get("bred_at"))
        if bred and t < bred + timedelta(days=BREED_PAUSE):
            return "resting"
        return None

    @serial
    def breed(self, pid: int, pet_id: int, partner_id: int) -> dict:
        """Two healthy pets of the same kind (at least 3 days old) have 1–2 babies; then the pair rests 14 days."""
        if pet_id == partner_id:
            raise PetError("Choose two different pets")
        self._mine(pid, pet_id)
        self._mine(pid, partner_id)
        self.refresh(pid)
        a, b = self._mine(pid, pet_id), self._mine(pid, partner_id)
        if a["kind"] != b["kind"]:
            raise PetError("Only pets of the same kind can have babies")
        t = now()
        why = self._breed_check(a, t) or self._breed_check(b, t)
        if why:
            raise PetError({"too_young": "Both must be at least 3 days old", "not_healthy": "Both must be healthy (every bar at least 50)",
                            "away": "Both must be at home", "resting": "They had babies not long ago – wait a little"}[why])
        room = MAX_PER_KIND - self._count(pid, a["kind"])
        if room <= 0:
            raise PetError("At most 6 pets of one kind")
        n = min(room, 1 + (random.random() < 0.5))
        with self.db.tx():
            babies = [self._born(pid, a["kind"]) for _ in range(n)]
            self.db.x("UPDATE pet SET bred_at=? WHERE id IN (?,?)", t.isoformat(), pet_id, partner_id)
        self._changed(pid)
        return {"babies": [self.get(pid, i) for i in babies]}

    def breeding(self, pid: int, pets: list[dict]) -> dict:
        """Per living pet: can it have babies now, and with which partners (for the app)."""
        t, out = now(), {}
        rows = {r["id"]: r for r in self.db.q("SELECT * FROM pet WHERE profile_id=? AND dead_at IS NULL", pid)}
        for p in pets:
            r = rows.get(p["id"])
            if not r:
                continue
            mates = [q for q in rows.values() if q["kind"] == r["kind"] and q["id"] != r["id"]]
            out[p["id"]] = {"why": self._breed_check(r, t), "partners": [q["id"] for q in mates],
                            "ready_partners": [q["id"] for q in mates if not self._breed_check(q, t)],
                            "room": self._count(pid, r["kind"]) < MAX_PER_KIND}
        return out

    # ---------------------------------------------------------------- pet sitting and pet hotel
    @serial
    def sit(self, pid: int, pet_id: int, sitter: int, until: str) -> dict:
        """Give the pet to a family member until a day (inclusive)."""
        self._mine(pid, pet_id)
        if sitter == pid or not self.db.q1("SELECT 1 FROM profile WHERE id=? AND archived=0", sitter):
            raise PetError("Choose somebody of the family")
        try:
            day = datetime.fromisoformat(str(until)).date()
        except ValueError:
            raise PetError("Choose until when") from None
        today = now().date()
        if day < today or day > today + timedelta(days=SIT_MAX_DAYS):
            raise PetError("Pet sitting is possible for up to 60 days")
        if self.locked(pet_id):
            raise PetError("This pet is part of a deal")
        self.refresh(pid)
        pet = self._mine(pid, pet_id)
        if _ts(pet["hotel_until"]) and _ts(pet["hotel_until"]) > now():
            raise PetError("Your pet is in the pet hotel – fetch it first")
        self.db.x("UPDATE pet SET sitter_id=?, sit_until=? WHERE id=?", sitter, day.isoformat(), pet_id)
        self._changed(pid)
        self._changed(sitter)
        return self.get(pid, pet_id)

    @serial
    def hotel(self, pid: int, pet_id: int, days: int) -> dict:
        """The Family Quest pet hotel for some days – paid at once."""
        self._mine(pid, pet_id)
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 0
        if not 1 <= days <= HOTEL_MAX_DAYS:
            raise PetError("The pet hotel takes pets for 1 to 30 days")
        if self.locked(pet_id):
            raise PetError("This pet is part of a deal")
        self.refresh(pid)
        pet = self._mine(pid, pet_id)
        if _ts(pet["hotel_until"]) and _ts(pet["hotel_until"]) > now():
            raise PetError("Your pet is in the pet hotel already")
        cost = days * self.hotel_cost()
        with self.db.tx():
            if cost:
                if self.rewards.available(pid) < cost:
                    raise PetError("Not enough coins for the pet hotel")
                self.rewards.book(pid, "coins", -float(cost), "pet_hotel", _t("Pet hotel") + f" – {pet['name']}", f"pet:{pet_id}")
            self.db.x("UPDATE pet SET hotel_until=?, hotel_cost=?, sitter_id=NULL, sit_until=NULL, updated_at=? WHERE id=?",
                      (now() + timedelta(days=days)).isoformat(), self.hotel_cost(), now().isoformat(), pet_id)
        self._changed(pid)
        if pet["sitter_id"]:
            self._changed(pet["sitter_id"])
        return self.get(pid, pet_id)

    @serial
    def fetch(self, pid: int, pet_id: int) -> dict:
        """Take the pet back – from the sitter or early from the hotel (unused full days are paid back)."""
        self._mine(pid, pet_id)
        self.refresh(pid)
        pet = self._mine(pid, pet_id)
        hotel, t = _ts(pet["hotel_until"]), now()
        with self.db.tx():
            if hotel and hotel > t:
                back = int((hotel - t).total_seconds() // 86400) * int(pet["hotel_cost"] or 0)   # the price that was paid
                if back:
                    self.rewards.book(pid, "coins", float(back), "pet_hotel", _t("Pet hotel") + f" – {pet['name']} ↩", f"pet:{pet_id}")
                self.db.x("""UPDATE pet SET hotel_until=NULL, hunger=100, mood=100, clean=100, zero_secs=0, zero_since=NULL,
                             updated_at=? WHERE id=?""", t.isoformat(), pet_id)
            self.db.x("UPDATE pet SET sitter_id=NULL, sit_until=NULL WHERE id=?", pet_id)
        self._changed(pid)
        if pet["sitter_id"]:
            self._changed(pet["sitter_id"])
        return self.get(pid, pet_id)

    @serial
    def rename(self, pid: int, pet_id: int, name: str) -> dict:
        self._mine(pid, pet_id)
        name = " ".join(str(name or "").split())[:24]
        if not name:
            raise PetError("Give your pet a name")
        self.db.x("UPDATE pet SET name=? WHERE id=?", name, pet_id)
        self._changed(pid)
        return self.get(pid, pet_id)

    # ---------------------------------------------------------------- pet shop: outfits, houses, furniture
    def _items(self, pid: int) -> dict[int, list[dict]]:
        out: dict[int, list[dict]] = {}
        for r in self.db.q("""SELECT i.* FROM pet_item i JOIN pet p ON p.id=i.pet_id
                              WHERE p.profile_id=? AND p.dead_at IS NULL ORDER BY i.id""", pid):
            out.setdefault(r["pet_id"], []).append(r)
        return out

    def currency(self) -> str:
        v = self.db.get_setting("pet_shop_currency")
        return v if v in CURRENCIES else "coins"

    def shop(self, pid: int) -> dict:
        """The catalog with prices, the currency mode, the balances and what each living pet owns and uses."""
        pets = [{k: p[k] for k in ("id", "kind", "name", "emoji", "mood", "outfit", "house", "furniture", "owned", "slow", "happy_home")}
                for p in self.list(pid)]
        return {"currency": self.currency(), "max_furniture": MAX_FURNITURE,
                "balance": {"coins": self.rewards.available(pid), "xp": self.rewards.balance(pid, "xp")},
                "items": [{"id": k, "cat": c, "name": n, "emoji": e, "price": price, "best": list(best)}
                          for k, (c, n, e, price, best) in SHOP.items()],
                "pets": pets}

    @serial
    def buy(self, pid: int, pet_id: int, item: str, pay: str | None = None) -> dict:
        """Buy an item for one pet – it is put on / moved in / placed right away (furniture while there is room)."""
        if item not in SHOP:
            raise PetError("Unknown item")
        self._mine(pid, pet_id)
        mode = self.currency()
        pay = pay or ("xp" if mode == "xp" else "coins")
        if pay not in ({"coins", "xp"} if mode == "mixed" else {mode}):
            raise PetError("Your parents chose another way to pay")
        cat, name, _e, price, _b = SHOP[item]
        self.refresh(pid)                      # the time so far counts with the old home
        pet = self._mine(pid, pet_id)
        with self.db.tx():                     # check and book in one step – a double tap cannot buy twice
            if self.db.q1("SELECT 1 FROM pet_item WHERE pet_id=? AND item=?", pet_id, item):
                raise PetError("Your pet has this already")
            if self.rewards.available(pid, pay) < price:
                raise PetError("Not enough coins" if pay == "coins" else "Not enough XP")
            self.rewards.book(pid, pay, -float(price), "pet_shop", f"{name} – {pet['name']}", f"pet:{pet_id}:{item}")
            self.db.x("INSERT INTO pet_item(pet_id, item, bought_at) VALUES(?,?,?)", pet_id, item, now().isoformat())
            if cat == "outfit":
                self._wear(pet, item)
            elif cat == "house":
                self._use(pet_id, "house", [item])
            elif self._placed(pet_id) < MAX_FURNITURE:
                self.db.x("UPDATE pet_item SET used=1 WHERE pet_id=? AND item=?", pet_id, item)
        self._changed(pid)
        return self.get(pid, pet_id)

    def _placed(self, pet_id: int) -> int:
        return sum(1 for r in self.db.q("SELECT item FROM pet_item WHERE pet_id=? AND used=1", pet_id)
                   if SHOP.get(r["item"], ("",))[0] == "furniture")

    def _owned(self, pet_id: int, cat: str) -> set[str]:
        return {r["item"] for r in self.db.q("SELECT item FROM pet_item WHERE pet_id=?", pet_id) if SHOP.get(r["item"], ("",))[0] == cat}

    def _use(self, pet_id: int, cat: str, chosen: list[str]) -> None:
        """Exactly the chosen items of a category are in use."""
        for it in self._owned(pet_id, cat):
            self.db.x("UPDATE pet_item SET used=? WHERE pet_id=? AND item=?", int(it in chosen), pet_id, it)

    def _wear(self, pet: dict, outfit: str | None) -> None:
        self._use(pet["id"], "outfit", [outfit] if outfit else [])
        if outfit and self.db.x("UPDATE pet_item SET worn_once=1 WHERE pet_id=? AND item=? AND worn_once=0", pet["id"], outfit):
            # a new outfit makes the pet happy – once per outfit
            self.db.x("UPDATE pet SET mood=?, zero_since=NULL, zero_secs=0 WHERE id=?",
                      min(100.0, float(pet["mood"]) + OUTFIT_BONUS), pet["id"])

    @serial
    def wear(self, pid: int, pet_id: int, outfit: str | None) -> dict:
        """Put on an outfit the pet owns ('' / None = take it off)."""
        self._mine(pid, pet_id)
        if outfit and outfit not in self._owned(pet_id, "outfit"):
            raise PetError("Buy this outfit first")
        self.refresh(pid)
        pet = self._mine(pid, pet_id)
        with self.db.tx():
            self._wear(pet, outfit or None)
        self._changed(pid)
        return self.get(pid, pet_id)

    @serial
    def home(self, pid: int, pet_id: int, house: str | None, furniture: list[str]) -> dict:
        """Choose the house (None = none) and the placed furniture (up to MAX_FURNITURE) among the owned ones."""
        self._mine(pid, pet_id)
        furniture = list(dict.fromkeys(furniture or []))
        if house and house not in self._owned(pet_id, "house"):
            raise PetError("Buy this house first")
        if set(furniture) - self._owned(pet_id, "furniture"):
            raise PetError("Buy this furniture first")
        if len(furniture) > MAX_FURNITURE:
            raise PetError("At most 6 pieces of furniture")
        self.refresh(pid)                      # the time so far counts with the old home
        with self.db.tx():
            self._use(pet_id, "house", [house] if house else [])
            self._use(pet_id, "furniture", furniture)
        self._changed(pid)
        return self.get(pid, pet_id)

    def get(self, pid: int, pet_id: int) -> dict:
        return next((p for p in self.list(pid) if p["id"] == pet_id), None) or {}

    def _changed(self, pid: int) -> None:
        for fn in self.on_change:
            try:
                fn(pid)
            except Exception:  # noqa: BLE001
                log.exception("listener failed")
