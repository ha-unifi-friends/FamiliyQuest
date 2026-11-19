"""API for the learning app (children, and parents who learn along)."""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import haauth, loginlog, symbols, themes
from ..chores import ChoreError
from ..internet import InternetError
from ..db import profile_settings
from ..channel import feature_visible
from ..learning.lesson import LearnError
from ..packs import i18n as pack_i18n
from ..rewards import avatar as av
from ..rewards.shop import ShopError
from ..pets import KINDS as PET_KINDS, REBUY_COST, PetError
from .auth import KID_MAX_AGE, Learner, app_of, check_pin, ha_kid, ha_user, hash_pin, valid_pin, via_ingress

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    profile_id: int
    pin: str = ""


class SetupIn(BaseModel):
    name: str
    pin: str = ""                    # optional only through Home Assistant with a known user (the profile is linked)


class SessionIn(BaseModel):
    mode: str
    pack: str | None = None
    unit: str | None = None


class AnswerIn(BaseModel):
    step: int
    answer: Any = None
    ms: int | None = None


class AvatarIn(BaseModel):
    avatar: dict
    mood_text: str | None = None      # «today I feel …» – only parents see it
    mood: str | None = None           # the emoji the child picked (😊 😴 🤢 …)


class BuyIn(BaseModel):
    item: str


class RedeemIn(BaseModel):
    reward_id: int


@router.get("/info")
def info(request: Request) -> dict:
    fq = app_of(request)
    s = fq.db.all_settings()
    return {"version": fq.settings.version,
            "setup_needed": (setup := not fq.db.val("SELECT COUNT(*) FROM profile WHERE role='parent' AND archived=0", default=0)),
            # first start through Home Assistant: the name of the HA user – the first parent is linked with it
            "setup_ha_user": (u["name"] or u["user"]) if setup and (u := ha_user(request)) else None,
            "ha": bool(fq.ha and fq.ha.connected), "planer": bool(fq.ha and fq.ha.planer_available),
            "ai": False, "sound": s.get("sound", True),
            "family_visibility": s.get("family_visibility"), "kid_max_age": KID_MAX_AGE,
            # parent area only in Home Assistant: on the app port (tablets) it is not offered at all
            "parent_ha_only": bool(s.get("parent_ha_only")),
            "via_ha": via_ingress(request),
            # a child opened the app with its own Home Assistant user (ingress, parents allow it): log in without PIN
            "ha_kid": {"id": kid["id"], "name": kid["name"]} if (kid := ha_kid(fq, request)) else None,
            # outside Home Assistant (tablets): «Sign in with Home Assistant» (haauth.py) when switched on and somebody is linked
            "ha_app_login": not via_ingress(request) and haauth.available(fq),
            "season": themes.active(s.get("themes")),
            "codelab": feature_visible("codelab")}           # 💡 Code Workshop: only in the dev channel (channel.DEV_FEATURES)


@router.get("/app-link")
async def app_link(request: Request) -> dict:
    """Where the app is reached directly in the home network (port of the direct access, IPs of Home Assistant): links
    from the parent area in Home Assistant open the app there – an ingress address opened outside of Home Assistant
    (e.g. Safari from the companion app) only answers «401: Unauthorized»."""
    from ..netinfo import home_access
    acc = await home_access(app_of(request).settings)
    return {"port": acc.get("port") if acc.get("enabled") else None, "ips": acc.get("ips") or []}


@router.get("/ha-panel")
async def ha_panel(request: Request) -> dict:
    """Link target for «open in Home Assistant» when the parent area is only offered there."""
    from ..netinfo import ha_panel as panel
    return await panel(app_of(request).settings)


@router.get("/profiles")
def profiles(request: Request) -> list[dict]:
    fq = app_of(request)
    # parents only with a PIN: the PIN is their login in the app (e.g. to join a game on another device) – or, on the
    # direct port with «Sign in with Home Assistant» on, with a linked Home Assistant user (tap = Home Assistant login)
    rows = fq.db.q("SELECT * FROM profile WHERE archived=0 ORDER BY role='parent', id")
    ha = {p["id"] for p in haauth.linked_profiles(fq)} if not via_ingress(request) and fq.db.get_setting("ha_app_login") else set()
    out = []
    for p in rows:
        if p["role"] == "parent" and not p["pin_hash"] and p["id"] not in ha:
            continue
        d = fq.profile_public(p)
        if p["id"] in ha:
            d["ha_login"] = True
        out.append(d)
    return out


@router.post("/login")
def login(body: LoginIn, request: Request) -> dict:
    fq = app_of(request)
    p = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", body.profile_id)
    if not p:
        raise HTTPException(404, "Unknown profile")
    # per profile and device – a child cannot lock out a sibling; parent profiles share the parent counter of the device
    ip = loginlog.client_ip(request)
    key = f"parent:{ip}" if p["role"] == "parent" else f"login:{p['id']}:{ip}"
    fq.throttle.check(key)
    if p["pin_hash"] and not check_pin(body.pin, p["pin_hash"]):
        fq.throttle.fail(key)
        loginlog.record(fq, request, "profile", p["id"], False)
        raise HTTPException(403, "Wrong PIN")
    if p["role"] == "parent" and not p["pin_hash"]:
        raise HTTPException(403, "Parent profile needs a PIN")
    # no PIN, but linked with a Home Assistant user while «Sign in with Home Assistant» is on: only that way (tablets)
    if not p["pin_hash"] and not via_ingress(request) and fq.db.get_setting("ha_app_login") \
            and any(x["id"] == p["id"] for x in haauth.linked_profiles(fq)):
        raise HTTPException(403, "Sign in with Home Assistant")
    fq.throttle.ok(key)
    loginlog.record(fq, request, "profile", p["id"], True)
    out = {"token": fq.tokens.make(p["id"], "kid"), "profile": fq.profile_public(p)}
    if p["role"] == "parent" and not fq.db.get_setting("parent_ha_only"):
        out["parent_token"] = fq.tokens.make(p["id"], "parent")
    return out


@router.post("/ha-login")
def ha_login(request: Request) -> dict:
    """Children's app without PIN for a child whose Home Assistant user is linked with its profile – only through Home
    Assistant ingress and only when the parents switched it on. Only the learning-app login, never the parent area."""
    fq = app_of(request)
    p = ha_kid(fq, request)
    if not p:
        return {"linked": False}
    loginlog.record(fq, request, "profile", p["id"], True)
    return {"linked": True, "token": fq.tokens.make(p["id"], "kid"), "profile": fq.profile_public(p)}


@router.post("/setup")
def setup(body: SetupIn, request: Request) -> dict:
    """First start: create the parent profile (PIN required)."""
    fq = app_of(request)
    if fq.db.val("SELECT COUNT(*) FROM profile WHERE role='parent' AND archived=0", default=0):
        raise HTTPException(409, "Already set up")
    # opened through Home Assistant: the first parent is linked with that Home Assistant user right away – the parent
    # area then opens without PIN, and the PIN is optional (the tablets: «Sign in with Home Assistant», or a PIN set
    # later in the profile). Without a Home Assistant user the PIN is the only login and stays required.
    u = ha_user(request)
    if not body.name.strip() or (body.pin and not valid_pin(body.pin)) or (not body.pin and not u):
        raise HTTPException(400, "Name and a PIN with 4–8 digits are required")
    st = {"ha_user_id": u["id"], "ha_user_name": u["name"] or u["user"]} if u else {}
    pid = fq.db.x("INSERT INTO profile(name, role, color, pin_hash, settings) VALUES(?, 'parent', '#495057', ?, ?)",
                  body.name.strip()[:40], hash_pin(body.pin) if body.pin else None, json.dumps(st))
    return {"parent_token": fq.tokens.make(pid, "parent"), "token": fq.tokens.make(pid, "kid"),
            "profile": fq.profile_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid))}


# ---------------------------------------------------------------- learner
@router.get("/me/community")
def my_community(request: Request, prof: dict = Learner) -> dict:
    """Only the running games and open votes – the start page asks for it every few seconds to update itself."""
    return app_of(request)._community_summary(prof)


@router.get("/me")
def me(request: Request, prof: dict = Learner) -> dict:
    return app_of(request).dashboard(prof)


# ---------------------------------------------------------------- Home Assistant devices of this profile
def _devices(prof: dict, fq=None) -> list[str]:
    """The entities a profile may control – an area («area.kinderzimmer») stands for all its lights, switches …"""
    out = []
    for d in profile_settings(prof).get("devices") or []:
        if not isinstance(d, str):
            continue
        if d.startswith("area."):
            if fq and fq.ha and fq.ha.connected:
                try:
                    out += fq.ha.area_entities(d[5:])
                except Exception:  # noqa: BLE001
                    pass
        else:
            out.append(d)
    return list(dict.fromkeys(out))


@router.get("/me/devices")
def my_devices(request: Request, prof: dict = Learner) -> list[dict]:
    fq = app_of(request)
    devs = _devices(prof, fq)
    if not devs or not fq.ha or not fq.ha.connected:
        return []
    return fq.ha.device_states(devs)


class DeviceIn(BaseModel):
    action: str                      # on | off | brightness | open | close | stop | run
    value: int | None = None         # brightness in %


@router.post("/me/devices/{entity_id}")
def my_device_control(entity_id: str, body: DeviceIn, request: Request, prof: dict = Learner) -> dict:
    from ..devices import DeviceError
    fq = app_of(request)
    if entity_id not in _devices(prof, fq):
        raise HTTPException(403, "This device is not yours")
    if not fq.ha or not fq.ha.connected:
        raise HTTPException(400, "Home Assistant is not connected")
    try:
        fq.ha.control(entity_id, body.action, body.value)
    except DeviceError as e:
        raise HTTPException(400, str(e)) from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Home Assistant: {e}") from None
    return {"ok": True, "devices": fq.ha.device_states(_devices(prof, fq))}


@router.get("/me/courses")
def courses(request: Request, prof: dict = Learner) -> list[dict]:
    """Packs learners switch on themselves (language courses, general knowledge) and whether they are on for me."""
    fq = app_of(request)
    mine = {r["pack_id"] for r in fq.db.q("SELECT pack_id FROM pack_profile WHERE profile_id=?", prof["id"])}
    out = []
    viewer = pack_i18n.viewer()
    for p in fq.packs.all(status="active", kind="pack"):
        s = p.summary()
        if s.get("self_service"):
            if viewer and p.lang == viewer and p.id not in mine:
                continue                     # a course of the learner's own language (the French course for French speakers)
            out.append({k: s.get(k) for k in ("id", "title", "subject", "level", "lang", "src_lang", "src_langs", "icon", "color",
                                               "description", "descriptions", "content_langs")}
                       | {"units": len(s.get("units") or []), "cards": sum(u["count"] for u in s.get("units") or []), "on": p.id in mine})
    return out


class CourseIn(BaseModel):
    on: bool = True


@router.post("/me/courses/{pack_id}")
def course_switch(pack_id: str, body: CourseIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    p = fq.packs.get(pack_id)
    if not p or p.status != "active" or not p.summary().get("self_service"):
        raise HTTPException(404, "Unknown course")
    if body.on:
        fq.db.x("INSERT OR IGNORE INTO pack_profile(pack_id, profile_id) VALUES(?,?)", pack_id, prof["id"])
    else:
        fq.db.x("DELETE FROM pack_profile WHERE pack_id=? AND profile_id=?", pack_id, prof["id"])
    return {"ok": True, "on": body.on}


@router.get("/me/packs/{pack_id}")
def pack(pack_id: str, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    p = fq.packs.get(pack_id)
    if not p or pack_id not in {x.id for x in fq.packs.for_profile(prof["id"])}:
        raise HTTPException(404, "Pack not available")
    return {"pack": p.summary(), "progress": fq.learning.pack_progress(prof["id"], p)}


@router.post("/me/session")
def new_session(body: SessionIn, request: Request, prof: dict = Learner) -> dict:
    try:
        return app_of(request).learning.build(prof["id"], body.mode, body.pack, body.unit)
    except LearnError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/me/session/{sid}/answer")
def answer(sid: str, body: AnswerIn, request: Request, prof: dict = Learner) -> dict:
    try:
        return app_of(request).learning.answer(sid, prof["id"], body.step, body.answer, body.ms)
    except LearnError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/me/session/{sid}/finish")
def finish(sid: str, request: Request, prof: dict = Learner) -> dict:
    try:
        return app_of(request).learning.finish(sid, prof["id"])
    except LearnError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- shop
@router.get("/me/shop")
def shop(request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    return {"offers": fq.shop.offers(prof["id"]), "balances": fq.rewards.balances(prof["id"]),
            "accounts": fq.rewards.accounts(), "history": fq.shop.list(pid=prof["id"], limit=20)}


@router.post("/me/redeem")
def redeem(body: RedeemIn, request: Request, prof: dict = Learner) -> dict:
    try:
        return app_of(request).shop.redeem(prof["id"], body.reward_id)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- avatar
def new_xp_left(fq, pid: int) -> int:
    """New XP not yet used for XP items (backgrounds …) – the XP account itself is never touched by them."""
    used = int(fq.db.val("SELECT SUM(new_xp) FROM unlock WHERE profile_id=?", pid, default=0) or 0) \
        + int(fq.db.val("SELECT n FROM xp_spent WHERE profile_id=?", pid, default=0) or 0)     # also for unlocks gone again
    return max(0, int(fq.rewards.new_xp(pid)) - used)


@router.get("/me/avatar")
def avatar(request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    level, badges, bought = fq.avatar_state(prof["id"])
    cat = av.catalog(level, badges, bought)
    lost = fq.pets.lost_kinds(prof["id"])
    for i in cat["items"]:
        if i["id"] in lost and "cost" not in i["rule"]:
            i["rule"] = {"cost": REBUY_COST}          # an earned pet that died: buy it again as a baby
    a = json.loads(prof["avatar"] or "{}") or av.DEFAULT_AVATAR
    kind = (a.get("items") or {}).get("pet")
    pet = fq.pets.badge(prof["id"], kind) if kind else None
    return {"avatar": {**a, "pet": pet} if pet else a, **cat,
            "mood_text": json.loads(prof["settings"] or "{}").get("mood_text") or "",
            "mood": json.loads(prof["settings"] or "{}").get("mood") or "",
            "coins": fq.rewards.available(prof["id"]), "level": level,
            "new_xp": new_xp_left(fq, prof["id"])}


@router.get("/dashboard")
def kiosk_dashboard(key: str, request: Request) -> dict:
    """Data of the kiosk dashboard – no login, the dashboard key is the password."""
    from ..dashboard import DashboardError
    try:
        return app_of(request).kiosk.data(key)
    except DashboardError as e:
        raise HTTPException(403, str(e)) from None


class PinChangeIn(BaseModel):
    old_pin: str = ""                      # the current PIN ("sym:a,b,c,d" for a picture PIN)
    pin: str | None = None                 # new digit PIN …
    pin_symbols: list[str] | None = None   # … or new picture PIN: 4 symbols out of symbol_set
    symbol_set: list[str] | None = None


@router.post("/me/pin")
def change_pin(body: PinChangeIn, request: Request, prof: dict = Learner) -> dict:
    """Children (and parents) change their own PIN – with the current one. Removing the PIN stays with the parents."""
    fq = app_of(request)
    p = fq.db.q1("SELECT * FROM profile WHERE id=?", prof["id"])
    key = f"login:{p['id']}"
    fq.throttle.check(key)
    if p["pin_hash"] and not check_pin(body.old_pin, p["pin_hash"]):
        fq.throttle.fail(key)
        raise HTTPException(403, "Wrong PIN")
    fq.throttle.ok(key)
    st = profile_settings(p)
    if body.pin_symbols is not None:
        try:
            sset = symbols.check_set(body.symbol_set or [])
            new = hash_pin(symbols.secret(body.pin_symbols, sset))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        st.update(pin_kind="symbols", symbol_set=sset)
    elif body.pin:
        lo, hi = (4, 4) if p["role"] == "kid" else (4, 8)
        if not valid_pin(body.pin, lo, hi):
            raise HTTPException(400, "Children's PIN: 4 digits" if p["role"] == "kid" else "PIN: 4–8 digits")
        new = hash_pin(body.pin)
        st.update(pin_kind="digits", symbol_set=[])
    else:
        raise HTTPException(400, "Choose a new PIN")
    fq.db.x("UPDATE profile SET pin_hash=?, settings=? WHERE id=?", new, json.dumps(st), p["id"])
    # a new PIN ends every other login of this profile – this device gets a fresh one
    return {"profile": fq.profile_public(fq.db.q1("SELECT * FROM profile WHERE id=?", p["id"])), "token": fq.tokens.make(p["id"], "kid")}


@router.post("/me/avatar")
def save_avatar(body: AvatarIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    level, badges, bought = fq.avatar_state(prof["id"])
    a = av.clean(body.avatar, level, badges, bought)
    fq.db.x("UPDATE profile SET avatar=? WHERE id=?", json.dumps(a), prof["id"])
    if prof["role"] == "kid":
        fq.mood_changed(prof, json.loads(prof["avatar"] or "{}"), a, body.mood_text, body.mood)
    return {"avatar": a}


@router.post("/me/avatar/buy")
def buy_item(body: BuyIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    rule = av.rule_of(body.item) if body.item in av.ITEMS else {}
    if rule.get("off"):
        raise HTTPException(400, "This item is not in the shop")
    if "cost" not in rule and body.item in fq.pets.lost_kinds(prof["id"]):
        rule = {"cost": REBUY_COST}
    if "xp" in rule:                                   # XP backgrounds: paid with new XP, the XP account stays as it is
        with fq.db.tx():
            if fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item=?", prof["id"], body.item):
                return {"ok": True}
            if new_xp_left(fq, prof["id"]) < rule["xp"]:
                raise HTTPException(400, "Not enough yet")
            fq.db.x("INSERT INTO unlock(profile_id,item,new_xp) VALUES(?,?,?)", prof["id"], body.item, int(rule["xp"]))
        if body.item in PET_KINDS:
            fq.pets.adopt(prof["id"], body.item)
        if fq.ha:
            fq.ha.profile_changed(prof["id"])
        return {"ok": True}
    if "cost" not in rule:
        raise HTTPException(400, "This item cannot be bought")
    cost = float(rule["cost"])
    with fq.db.tx():
        if fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item=?", prof["id"], body.item):
            return {"ok": True}
        if fq.rewards.available(prof["id"]) < cost:
            raise HTTPException(400, "Not enough yet")
        if cost > 0:                                   # price 0 (parent area › Shop): free – nothing to book
            fq.rewards.book(prof["id"], "coins", -cost, "avatar", av.ITEMS[body.item][0], f"avatar:{body.item}")
        fq.db.x("INSERT INTO unlock(profile_id,item) VALUES(?,?)", prof["id"], body.item)
    if body.item in PET_KINDS:
        fq.pets.adopt(prof["id"], body.item)           # a new pet: a baby from today
    if fq.ha:
        fq.ha.profile_changed(prof["id"])
    return {"ok": True}


# ---------------------------------------------------------------- family and chores
@router.get("/family")
def family(request: Request, prof: dict = Learner) -> dict:
    return app_of(request).family()


@router.post("/me/chores/{uid}/done")
def chore_done(uid: str, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    if uid.startswith("fq:"):
        try:
            t = fq.chores.mark_done(prof["id"], int(uid[3:]))
        except (ChoreError, ValueError) as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True, "status": t["status"], "chores": fq.all_chores(prof)}
    if uid.startswith("fp:"):           # built-in Family Planer
        if not fq.planer_host or not fq.planer_host.set_item(prof["id"], uid[3:]):
            raise HTTPException(400, "Could not tick off the chore")
        return {"ok": True, "status": "done", "chores": fq.all_chores(prof)}
    if not fq.ha:
        raise HTTPException(400, "Home Assistant is not connected")
    ok = fq.ha.complete_chore(prof, uid)
    if not ok:
        raise HTTPException(400, "Could not tick off the chore")
    return {"ok": True, "status": "done", "chores": fq.all_chores(prof)}


@router.get("/me/settings")
def my_settings(request: Request, prof: dict = Learner) -> dict:
    return {"settings": profile_settings(prof)}


# ---------------------------------------------------------------- internet time
@router.get("/me/internet")
def internet_state(request: Request, prof: dict = Learner) -> dict:
    return {"internet": app_of(request).internet.state(prof)}


@router.post("/me/internet/start")
def internet_start(request: Request, prof: dict = Learner) -> dict:
    try:
        return {"internet": app_of(request).internet.start(prof)}
    except InternetError as e:
        raise HTTPException(400, str(e)) from None
    except Exception as e:  # noqa: BLE001 – Home Assistant call failed
        raise HTTPException(502, f"Home Assistant: {e}") from None


@router.post("/me/internet/stop")
def internet_stop(request: Request, prof: dict = Learner) -> dict:
    return {"internet": app_of(request).internet.stop(prof)}


@router.get("/me/badges")
def my_badges(request: Request, prof: dict = Learner) -> dict:
    return {"badges": app_of(request).badge_overview(prof["id"])}


# ---------------------------------------------------------------- pet care (pets.py)
class PetNameIn(BaseModel):
    name: str


def _pet(fn, *args):
    try:
        return fn(*args)
    except PetError as e:
        raise HTTPException(403 if str(e) == "That is not your pet" else 400, str(e)) from None


@router.get("/me/pets")
def my_pets(request: Request, prof: dict = Learner) -> dict:
    return app_of(request).pets.summary(prof["id"])


@router.post("/me/pets/seen")
def pets_seen(request: Request, prof: dict = Learner) -> dict:
    """The child saw the message that a pet died."""
    app_of(request).pets.seen(prof["id"])
    return {"ok": True}


class PetBuyIn(BaseModel):
    item: str
    pay: Literal["coins", "xp"] | None = None     # None: what the parents chose (coins in «mixed»)


class PetWearIn(BaseModel):
    outfit: str | None = None                     # None / "": take it off


class PetHomeIn(BaseModel):
    house: str | None = None
    furniture: list[str] = []


@router.get("/me/pets/shop")
def pet_shop(request: Request, prof: dict = Learner) -> dict:
    """Pet shop: outfits, houses and furniture with prices, how to pay, and what each pet owns."""
    return app_of(request).pets.shop(prof["id"])


@router.post("/me/pets/{pet_id}/buy")
def pet_buy(pet_id: int, body: PetBuyIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    pet = _pet(fq.pets.buy, prof["id"], pet_id, body.item, body.pay)
    if fq.ha:
        fq.ha.profile_changed(prof["id"])
    return {"pet": pet, "shop": fq.pets.shop(prof["id"])}


@router.put("/me/pets/{pet_id}/wear")
def pet_wear(pet_id: int, body: PetWearIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    pet = _pet(fq.pets.wear, prof["id"], pet_id, body.outfit)
    if fq.ha:
        fq.ha.profile_changed(prof["id"])           # the outfit shows on the avatar badge
    return {"pet": pet, "shop": fq.pets.shop(prof["id"])}


@router.put("/me/pets/{pet_id}/home")
def pet_home(pet_id: int, body: PetHomeIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    return {"pet": _pet(fq.pets.home, prof["id"], pet_id, body.house, body.furniture), "shop": fq.pets.shop(prof["id"])}


# ---------------------------------------------------------------- daily game time (timelimits.py)
@router.post("/me/playtime")
def playtime(request: Request, prof: dict = Learner) -> dict:
    """Heartbeat of the game corner (games on this device only) every minute: counts the minute as game time.
    ok False: no game may be played now (switched off, OfflineTime, game time of today used up) – the corner closes."""
    from .. import timelimits
    from ..gamepasses import ARCADE
    fq = app_of(request)
    ok = fq.games_allowed(prof) or any((fq.game_trial(prof, g, time=True) or {}).get("active") for g in ARCADE)  # a free try
    if ok and prof.get("role") == "kid" and not fq.party_lifts(prof):           # a party that lifts the limits: not counted
        timelimits.touch(fq.db, prof["id"])
    return {"ok": ok, "time_left": fq.time_left(prof)}


# ---------------------------------------------------------------- games with a price (gamepasses.py): kid shop «Unlock games»
GAME_TITLES = {"quiz": "Family quiz", "bingo": "Bingo", "song": "Guess the song", "poker": "Texas Hold'em", "ttt": "Tic-Tac-Toe",
               "sudoku": "Sudoku", "patience": "Patience", "pingpong": "Ping-Pong", "slots": "One-armed bandit", "cube": "Cube solver"}


def _game_title(game: str) -> str:
    from ..running import TITLES
    return GAME_TITLES.get(game) or TITLES.get(game) or game


class GamePassIn(BaseModel):
    game: str
    kind: Literal["buy", "rent"]
    until: str | None = None          # rent: the end the app showed («» = none) – a second tap does not book twice


@router.get("/me/games/shop")
def games_shop(request: Request, prof: dict = Learner) -> dict:
    """The priced games this child may play once bought or rented – with what it has (bought, rented until)."""
    fq = app_of(request)
    return {"games": fq.game_offers(prof), "coins": fq.rewards.available(prof["id"])}


@router.post("/me/games/buy")
def games_buy(body: GamePassIn, request: Request, prof: dict = Learner) -> dict:
    from ..gamepasses import PassError
    fq = app_of(request)
    if prof.get("role") != "kid":
        raise HTTPException(400, "Parents always play for free")
    if body.game not in fq.GAMES or body.game not in fq.games_open_to(prof, party=False):   # a party does not last
        raise HTTPException(403, "This game is switched off for you")
    a = fq.games_access()[body.game]
    try:
        if body.kind == "buy":
            fq.passes.buy(prof["id"], body.game, a, _game_title(body.game))
        else:
            fq.passes.rent(prof["id"], body.game, a, _game_title(body.game), body.until if body.until is not None else None)
    except PassError as e:
        raise HTTPException(400, str(e)) from None
    return games_shop(request, prof)


class GameTryIn(BaseModel):
    game: str
    join: bool = False                # opened to answer a duel / doubles invitation of somebody else: no battery segment


EMPTY = "Your game battery is empty – recharge it or join a table of somebody else"


def _corner_charge(fq, prof: dict, body: GameTryIn) -> tuple[str | None, int | None]:
    """Opening a game of the game corner costs a battery segment (battery.py) – not when the child answers an
    invitation (a duel or a doubles table of somebody else waiting for it)."""
    if body.join and body.game in ("ttt", "pingpong"):
        duel = fq.duels.state(prof["id"])
        if (duel and {"ttt": "ttt", "pong": "pingpong"}.get(duel.get("kind") or "ttt") == body.game) or \
                (body.game == "pingpong" and fq.pong4.busy(prof["id"])):
            return "free", None
    used = fq.use_charge(prof, body.game)
    if not used[0]:
        raise HTTPException(403, EMPTY)
    return used


@router.post("/me/games/try")
def games_try(body: GameTryIn, request: Request, prof: dict = Learner) -> dict:
    """Opening a game of the game corner. It costs a segment of the game battery (battery.py; a second call right after
    – double tap, another device – is the same start). A locked game (gamepasses.py `preview`): a free try – the app
    opens the game once; the one-armed bandit counts each spin instead (nothing used here). Family games use a try and
    a segment when the child starts a table (api/community.py)."""
    from ..gamepasses import ARCADE
    fq = app_of(request)
    if body.game not in ARCADE:
        raise HTTPException(400, "Start or join a table to use a free try")
    t = fq.game_trial(prof, body.game, time=True)
    if not t:
        if fq.games_allowed(prof, body.game):
            _corner_charge(fq, prof, body)
            return {"ok": True, "tries_left": 0, "open": True, "battery": fq.battery.state(prof)}
        raise HTTPException(403, "This game is switched off for you")
    used = _corner_charge(fq, prof, body)
    if (t["left"] <= 0 if body.game == "slots" else not fq.use_game_try(prof, body.game)):
        if used[0] == "new":
            fq.battery.give_back(prof["id"], used[1])
        raise HTTPException(403, "No free tries left – buy or rent the game")
    return {"ok": True, "tries_left": fq.passes.tries_left(prof["id"], body.game, fq.games_access()[body.game]), "open": False,
            "battery": fq.battery.state(prof)}


# ---------------------------------------------------------------- game battery (battery.py)
@router.get("/me/battery")
def battery_state(request: Request, prof: dict = Learner) -> dict | None:
    return app_of(request).battery.state(prof)


@router.post("/me/battery/recharge")
def battery_recharge(request: Request, prof: dict = Learner) -> dict:
    """Recharge the game battery to full for coins (one transaction; a double tap finds it full and books nothing)."""
    from ..battery import BatteryError
    fq = app_of(request)
    try:
        st = fq.battery.recharge(prof)
    except BatteryError as e:
        raise HTTPException(400, str(e)) from None
    if fq.ha:
        fq.ha.profile_changed(prof["id"])
    return {"battery": st, "coins": fq.rewards.available(prof["id"])}


# ---------------------------------------------------------------- game corner: one-armed bandit (slots.py)
def _slots(request: Request, prof: dict, fn, *args, paid: bool = True):
    from ..slots import SlotError
    fq = app_of(request)
    # not paid: the machine before buying it – switched on for the child, no block time, game time not used up
    unpaid_ok = "slots" in fq.games_open_to(prof) and (prof.get("role") == "parent" or not fq._games_blocked(prof))
    if not (fq.games_allowed(prof, "slots") if paid else unpaid_ok):
        raise HTTPException(403, "This game is switched off")
    try:
        return fn(*args)
    except SlotError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/me/slots")
def slots_state(request: Request, prof: dict = Learner) -> dict:
    return _slots(request, prof, app_of(request).slots.state, prof["id"], paid=False)


@router.post("/me/slots/buy")
def slots_buy(request: Request, prof: dict = Learner) -> dict:
    """Older apps: buying the machine – now the standard purchase (gamepasses.py)."""
    games_buy(GamePassIn(game="slots", kind="buy"), request, prof)
    return app_of(request).slots.state(prof["id"])


@router.post("/me/slots/spin")
def slots_spin(request: Request, prof: dict = Learner) -> dict:
    return _slots(request, prof, app_of(request).slots.spin, prof["id"], paid=False)     # not bought: 400 «buy first»


class PetMoreIn(BaseModel):
    kind: str


class PetBreedIn(BaseModel):
    partner: int


@router.post("/me/pets/more")
def pet_more(body: PetMoreIn, request: Request, prof: dict = Learner) -> dict:
    """One more pet of a kind the child already has (same price as in the shop)."""
    fq = app_of(request)
    pet = _pet(fq.pets.buy_another, prof["id"], body.kind)
    return {"pet": pet, "coins": fq.rewards.available(prof["id"])}


@router.post("/me/pets/{pet_id}/breed")
def pet_breed(pet_id: int, body: PetBreedIn, request: Request, prof: dict = Learner) -> dict:
    """Two healthy pets of the same kind have babies."""
    return _pet(app_of(request).pets.breed, prof["id"], pet_id, body.partner)


class PetSitIn(BaseModel):
    sitter: int                                   # profile of the family member
    until: str                                    # ISO date (inclusive)


class PetHotelIn(BaseModel):
    days: int


@router.post("/me/pets/{pet_id}/sit")
def pet_sit(pet_id: int, body: PetSitIn, request: Request, prof: dict = Learner) -> dict:
    """Give the pet to a family member for pet sitting."""
    return {"pet": _pet(app_of(request).pets.sit, prof["id"], pet_id, body.sitter, body.until)}


@router.post("/me/pets/{pet_id}/hotel")
def pet_hotel(pet_id: int, body: PetHotelIn, request: Request, prof: dict = Learner) -> dict:
    """The Family Quest pet hotel: paid per day at once."""
    fq = app_of(request)
    pet = _pet(fq.pets.hotel, prof["id"], pet_id, body.days)
    return {"pet": pet, "coins": fq.rewards.available(prof["id"])}


@router.post("/me/pets/{pet_id}/fetch")
def pet_fetch(pet_id: int, request: Request, prof: dict = Learner) -> dict:
    """Take the pet back from the sitter or from the hotel."""
    fq = app_of(request)
    pet = _pet(fq.pets.fetch, prof["id"], pet_id)
    return {"pet": pet, "coins": fq.rewards.available(prof["id"])}


@router.post("/me/pets/{pet_id}/{action}")
def pet_action(pet_id: int, action: str, request: Request, prof: dict = Learner) -> dict:
    if action not in ("feed", "play", "wash"):
        raise HTTPException(404, "Unknown action")
    fq = app_of(request)
    pet = _pet(fq.pets.act, prof["id"], pet_id, action)
    return {"pet": pet, "coins": fq.rewards.available(prof["id"])}


@router.put("/me/pets/{pet_id}")
def pet_rename(pet_id: int, body: PetNameIn, request: Request, prof: dict = Learner) -> dict:
    return {"pet": _pet(app_of(request).pets.rename, prof["id"], pet_id, body.name)}


# ---------------------------------------------------------------- shop: pranks (pranks.py) – the ink bomb
class PrankThrowIn(BaseModel):
    targets: list[int]


def _prank(fn, *args):
    from ..pranks import PrankError
    try:
        return fn(*args)
    except PrankError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/me/pranks")
def pranks_state(request: Request, prof: dict = Learner) -> dict:
    return app_of(request).pranks.state(prof["id"])


class PrankBuyIn(BaseModel):
    kind: str = "ink"


@router.post("/me/pranks/buy")
def pranks_buy(request: Request, body: PrankBuyIn | None = None, prof: dict = Learner) -> dict:
    return _prank(app_of(request).pranks.buy, prof["id"], (body.kind if body else "ink"))


@router.post("/me/pranks/fart")
def pranks_fart(request: Request, prof: dict = Learner) -> dict:
    return _prank(app_of(request).pranks.fart, prof["id"])


@router.post("/me/pranks/throw")
def pranks_throw(body: PrankThrowIn, request: Request, prof: dict = Learner) -> dict:
    return _prank(app_of(request).pranks.throw, prof["id"], body.targets)


@router.get("/me/pranks/pending")
def pranks_pending(request: Request, prof: dict = Learner) -> dict:
    return {"prank": app_of(request).pranks.pending(prof["id"])}


@router.post("/me/pranks/{prank_id}/clean")
def pranks_clean(prank_id: int, request: Request, prof: dict = Learner) -> dict:
    return app_of(request).pranks.cleaned(prof["id"], prank_id)


# ---------------------------------------------------------------- templates for an AI (learning packs, quizzes)
@router.get("/ai-template/{kind}")
def ai_template(kind: str) -> Response:
    """The template for an AI: self-describing JSON (instructions, field guide, example) – ai_format.py."""
    import json as _json
    from .. import ai_format
    if kind not in ("pack", "quiz"):
        raise HTTPException(404)
    doc = ai_format.quiz_document([], template=True) if kind == "quiz" else ai_format.pack_document([], template=True)
    return Response(_json.dumps(doc, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="family-quest-{kind}-template.json"'})
