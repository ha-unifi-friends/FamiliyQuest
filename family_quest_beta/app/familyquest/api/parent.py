"""API for the parent UI. Every call needs the parent PIN token (X-FQ-Parent)."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import os
import re
import time
import zipfile
from typing import Any

import httpx
import yaml
from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ..weather import WeatherError
from ..dashboard import DashboardError
from ..calendar import CalendarError
from ..translations import BUILTIN, TranslationError, source_keys
from .. import generators
from ..chores import ChoreError
from ..db import DEFAULT_PROFILE_SETTINGS, DEFAULT_SETTINGS, profile_settings
from ..importers import ai_draft, table, yaml_zip
from ..packs.loader import PackError, media_refs, parse_doc
from ..packs.registry import SUBJECTS, subject_meta
from .. import loginlog, netfilter, symbols
from ..rewards.engine import BADGES, EVENTS
from ..rewards.shop import KINDS, ShopError
from .auth import INGRESS_IP, Parent, PARENT_MAX_AGE, app_of, check_pin, hash_pin, valid_pin

router = APIRouter(prefix="/api/parent")


class PinIn(BaseModel):
    pin: str
    profile_id: int | None = None      # picture PIN: the parent who logs in (the symbols belong to a profile)


class ProfileIn(BaseModel):
    name: str
    role: str = "kid"
    color: str = "#4f8cff"
    pin: str | None = None            # "" removes the PIN, None keeps it
    pin_symbols: list[str] | None = None   # children: picture PIN – 4 symbol ids in order (instead of digits)
    symbol_set: list[str] | None = None    # the 12 symbols the 4 were chosen from
    settings: dict = {}
    planer_person_id: str | None = None
    ha_user_id: str | None = None          # parents: the Home Assistant user that opens the parent area ("" = none, None = keep)
    ha_user_name: str = ""


class ActivateIn(BaseModel):
    profile_id: int
    pack_id: str
    on: bool = True


class StatusIn(BaseModel):
    status: str


class RawIn(BaseModel):
    data: dict | None = None
    yaml: str | None = None


class AccountIn(BaseModel):
    key: str
    name: str
    unit: str = ""
    icon: str = ""
    spendable: bool = True
    active: bool = True
    sort: int = 0


class RuleIn(BaseModel):
    event: str
    account: str
    amount: float
    daily_limit: float | None = None
    condition: dict = {}
    label: str = ""
    active: bool = True


class RewardIn(BaseModel):
    name: str
    kind: str = "voucher"
    account: str = "coins"
    cost: float
    approval: bool = True
    weekly_limit: int | None = None
    icon: str = "🎁"
    config: dict = {}
    active: bool = True
    sort: int = 0


class DecideIn(BaseModel):
    approve: bool
    note: str = ""


class GoalIn(BaseModel):
    profile_id: int | None = None
    kind: str = "unit"
    title: str = ""
    target: float = 5
    account: str | None = None
    pack_id: str | None = None
    unit_id: str | None = None
    active: bool = True


class BookIn(BaseModel):
    profile_id: int
    account: str
    amount: float
    reason: str = ""


class TableIn(BaseModel):
    upload_id: str
    meta: dict
    columns: dict


class UrlIn(BaseModel):
    url: str


# ---------------------------------------------------------------- login
def ha_user(request: Request) -> dict | None:
    """The Home Assistant user – only trusted when the request really comes through Home Assistant ingress
    (the Supervisor proxy sets these headers; on the direct port anybody could send them)."""
    if not request.client or request.client.host != INGRESS_IP:
        return None
    uid = request.headers.get("x-remote-user-id")
    if not uid:
        return None
    return {"id": uid, "name": request.headers.get("x-remote-user-display-name") or request.headers.get("x-remote-user-name") or "",
            "user": request.headers.get("x-remote-user-name") or ""}


def _parent_of_ha_user(fq, uid: str) -> dict | None:
    for p in fq.db.q("SELECT * FROM profile WHERE role='parent' AND archived=0"):
        if profile_settings(p).get("ha_user_id") == uid:
            return p
    return None


@router.post("/ha-login")
def ha_login(request: Request) -> dict:
    """Parent area without PIN for parents whose Home Assistant user is linked to their profile."""
    fq = app_of(request)
    u = ha_user(request)
    if not u:
        return {"ha_user": None}
    p = _parent_of_ha_user(fq, u["id"])
    if not p:
        return {"ha_user": u, "linked": False}
    loginlog.record(fq, request, "parent", p["id"], True)
    return {"parent_token": fq.tokens.make(p["id"], "parent"), "profile": fq.profile_public(p), "max_age": PARENT_MAX_AGE,
            "ha_user": u, "linked": True}


class HaLinkIn(BaseModel):
    on: bool = True


@router.post("/ha-link")
def ha_link(body: HaLinkIn, request: Request, me: dict = Parent) -> dict:
    """Link (or unlink) the Home Assistant user of this request with my parent profile."""
    fq = app_of(request)
    u = ha_user(request)
    if body.on:
        if not u:
            raise HTTPException(400, "Open the parent area through Home Assistant to link your user")
        for p in fq.db.q("SELECT * FROM profile WHERE role='parent'"):
            st = profile_settings(p)
            if st.get("ha_user_id") == u["id"] and p["id"] != me["id"]:
                st.pop("ha_user_id", None); st.pop("ha_user_name", None)
                fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), p["id"])
    st = profile_settings(me)
    if body.on:
        st.update(ha_user_id=u["id"], ha_user_name=u["name"] or u["user"])
    else:
        st.pop("ha_user_id", None); st.pop("ha_user_name", None)
        if fq.db.get_setting("parent_ha_only") and not any(profile_settings(p).get("ha_user_id")
                for p in fq.db.q("SELECT * FROM profile WHERE role='parent' AND archived=0 AND id<>?", me["id"])):
            fq.db.set_setting("parent_ha_only", False)       # nobody could log in any more
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), me["id"])
    return {"ha_user_name": st.get("ha_user_name", ""), "linked": body.on}


@router.post("/login")
def login(body: PinIn, request: Request) -> dict:
    fq = app_of(request)
    if fq.db.get_setting("parent_ha_only"):
        raise HTTPException(403, "The parent area opens only through Home Assistant")
    key = "parent:" + loginlog.client_ip(request)        # per device: a child cannot lock all parents out
    fq.throttle.check(key)
    parents = fq.db.q("SELECT * FROM profile WHERE role='parent' AND archived=0" + (" AND id=?" if body.profile_id else ""),
                      *([body.profile_id] if body.profile_id else []))
    for p in parents:
        if check_pin(body.pin, p["pin_hash"]):
            fq.throttle.ok(key)
            loginlog.record(fq, request, "parent", p["id"], True)
            return {"parent_token": fq.tokens.make(p["id"], "parent"), "profile": fq.profile_public(p),
                    "max_age": PARENT_MAX_AGE}
    fq.throttle.fail(key)
    loginlog.record(fq, request, "parent", None, False)
    raise HTTPException(403, "Wrong PIN")


@router.post("/refresh")
def refresh(request: Request, me: dict = Parent) -> dict:
    return {"parent_token": app_of(request).tokens.make(me["id"], "parent")}


# ---------------------------------------------------------------- meta
def _ha_status(fq) -> str:
    """Why Home Assistant is (not) connected – in plain words for the parent area."""
    st = fq.settings
    if fq.ha and fq.ha.connected:
        return "connected"
    if not st.ha_token:
        return "no SUPERVISOR_TOKEN – the app runs outside Home Assistant (or homeassistant_api is off)"
    if not st.ha_enabled:
        return "switched off (FQ_HA_DISABLED)"
    err = getattr(fq.ha.client, "last_error", "") if fq.ha else ""
    return f"not connected to {st.ha_url}" + (f": {err}" if err else " (connecting …)")


@router.get("/themes")
def themes_get(request: Request, me: dict = Parent) -> dict:
    from .. import themes
    cfg = app_of(request).db.get_setting("themes")
    return {"designs": themes.designs(cfg), "active": themes.active(cfg), "visuals": list(themes.VISUALS)}


@router.put("/themes")
def themes_put(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    from .. import themes
    try:
        cfg = themes.clean(body)
    except themes.ThemeError as e:
        raise HTTPException(400, str(e)) from None
    app_of(request).db.set_setting("themes", cfg)
    return {"designs": themes.designs(cfg), "active": themes.active(cfg), "visuals": list(themes.VISUALS)}


@router.get("/update-info")
async def update_info(request: Request, me: dict = Parent) -> dict:
    from ..netinfo import update_info as info
    return await info(app_of(request).settings)


@router.get("/changelog")
def changelog(me: dict = Parent) -> dict:
    """Release notes: CHANGELOG.md of the add-on (in the image next to the app, in development one folder up)."""
    from pathlib import Path
    here = Path(__file__).resolve().parents
    for f in (here[2] / "CHANGELOG.md", here[3] / "CHANGELOG.md"):
        if f.is_file():
            return {"text": f.read_text(encoding="utf-8")[:200_000]}
    return {"text": ""}


@router.get("/meta")
def meta(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    return {"events": EVENTS, "badges": {k: {"name": v[0], "icon": v[1], "description": v[2]} for k, v in BADGES.items()},
            "reward_kinds": KINDS, "generators": {k: g.title for k, g in generators.GENERATORS.items()},
            "subjects": [subject_meta(k) for k in SUBJECTS], "profile_defaults": DEFAULT_PROFILE_SETTINGS,
            "ha": bool(fq.ha and fq.ha.connected), "planer": bool(fq.ha and fq.ha.planer_available),
            "ha_status": _ha_status(fq),
            "ai": ai_draft.available(fq), "version": fq.settings.version, "me": fq.profile_public(me),
            "ha_user": ha_user(request), "my_ha_user": profile_settings(me).get("ha_user_name") if profile_settings(me).get("ha_user_id") else None,
            "parent_ha_only": bool(fq.db.get_setting("parent_ha_only"))}


@router.get("/overview")
def overview(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    return {"kids": fq.overview(), "pending": fq.shop.list("pending"), "family_goal": fq.family_goal(),
            "chores_pending": fq.chores.pending()}


# ---------------------------------------------------------------- profiles
@router.get("/profiles")
def profiles(request: Request, me: dict = Parent) -> list[dict]:
    fq = app_of(request)
    out = []
    for p in fq.db.q("SELECT * FROM profile WHERE archived=0 ORDER BY role='parent', id"):
        d = fq.profile_public(p)
        d.update(settings=profile_settings(p), planer_person_id=p["planer_person_id"],
                 packs=sorted(fq.packs.activated(p["id"])))
        out.append(d)
    return out


def _parents(fq) -> int:
    return int(fq.db.val("SELECT COUNT(*) FROM profile WHERE role='parent' AND archived=0", default=0))


def _check_profile(body: ProfileIn) -> None:
    if not body.name.strip():
        raise HTTPException(400, "Name is required")
    if body.role not in ("kid", "parent"):
        raise HTTPException(400, "Unknown role")
    if body.pin and body.role == "kid" and not valid_pin(body.pin, 4, 4):
        raise HTTPException(400, "Children's PIN: 4 digits")
    if body.pin and not valid_pin(body.pin, 4, 8):
        raise HTTPException(400, "PIN: 4–8 digits")
    if body.pin_symbols is not None:
        try:
            symbols.secret(body.pin_symbols, symbols.check_set(body.symbol_set or []))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    devs = body.settings.get("devices")
    if devs is not None:
        from ..devices import DOMAINS
        if not isinstance(devs, list) or any(not isinstance(d, str) or d.split(".", 1)[0] not in (*DOMAINS, "area")
                                             or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", d) for d in devs) or len(devs) > 30:
            raise HTTPException(400, "Devices: lights, switches, fans, covers, scenes or scripts")
    rule = str(body.settings.get("internet_rule") or "").strip()
    if rule and not re.fullmatch(r"(switch|input_boolean)\.[a-z0-9_]+", rule):
        raise HTTPException(400, "Firewall rule: a switch, e.g. switch.unifi_rule_internet_mia")
    if body.settings.get("internet_plan") is not None:
        from ..internet import InternetError, clean_plan
        try:
            body.settings["internet_plan"] = clean_plan(body.settings["internet_plan"])
        except InternetError as e:
            raise HTTPException(400, str(e)) from None
    svc = str(body.settings.get("notify_service") or "").strip()
    if svc and not re.fullmatch(r"notify\.[a-z0-9_]+", svc):
        raise HTTPException(400, "Notify service: e.g. notify.mobile_app_phone")


def _pin_hash(body: ProfileIn, settings: dict, current: str | None) -> str | None:
    """New PIN hash from the request: picture PIN, digit PIN, "" = remove, nothing = keep (settings updated in place)."""
    if body.pin_symbols is not None:
        settings.update(pin_kind="symbols", symbol_set=symbols.check_set(body.symbol_set or []))
        return hash_pin(symbols.secret(body.pin_symbols, settings["symbol_set"]))
    if body.pin == "":
        settings.update(pin_kind="", symbol_set=[])
        return None
    if body.pin:
        settings.update(pin_kind="digits", symbol_set=[])
        return hash_pin(body.pin)
    return current


def _set_ha_user(fq, body: ProfileIn, settings: dict, pid: int | None) -> None:
    """Link the parent profile with a Home Assistant user (only one profile per user)."""
    if body.ha_user_id is None or body.role != "parent":
        return
    if not body.ha_user_id:
        settings.pop("ha_user_id", None); settings.pop("ha_user_name", None)
        return
    for p in fq.db.q("SELECT * FROM profile WHERE role='parent'"):
        st = profile_settings(p)
        if st.get("ha_user_id") == body.ha_user_id and p["id"] != pid:
            st.pop("ha_user_id", None); st.pop("ha_user_name", None)
            fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), p["id"])
    settings.update(ha_user_id=body.ha_user_id, ha_user_name=(body.ha_user_name or "")[:60])


def _planer_sync(fq) -> None:
    """Profiles are Planer persons: tell the Planer bridge (name, colour, role, new or removed profile)."""
    bridge = getattr(fq.planer_host, "bridge", None)
    if bridge:
        bridge.request()


@router.post("/profiles")
def create_profile(body: ProfileIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    _check_profile(body)
    if body.role == "parent" and not body.pin and body.pin_symbols is None and not body.ha_user_id:
        raise HTTPException(400, "Parents need a Home Assistant user or a PIN")
    settings = {k: v for k, v in body.settings.items() if k in DEFAULT_PROFILE_SETTINGS and k not in ("pin_kind", "symbol_set")}
    pin_hash = _pin_hash(body, settings, None)
    _set_ha_user(fq, body, settings, None)
    pid = fq.db.x("INSERT INTO profile(name,role,color,pin_hash,settings,planer_person_id) VALUES(?,?,?,?,?,?)",
                  body.name.strip()[:40], body.role, body.color, pin_hash,
                  json.dumps(settings), body.planer_person_id)
    if body.role == "kid":
        fq.packs.activate_defaults(pid)
    if settings.get("internet_rule"):
        fq.internet.ensure_account()
    if fq.ha:
        fq.ha.profile_changed(pid)
    _planer_sync(fq)
    return fq.profile_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid))


@router.put("/profiles/{pid}")
def update_profile(pid: int, body: ProfileIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    p = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
    if not p:
        raise HTTPException(404, "Unknown profile")
    _check_profile(body)
    if p["role"] == "parent" and body.role != "parent" and _parents(fq) <= 1:
        raise HTTPException(400, "At least one parent profile is needed")
    settings = profile_settings(p)
    settings.update({k: v for k, v in body.settings.items() if k in DEFAULT_PROFILE_SETTINGS and k not in ("pin_kind", "symbol_set")})
    pin_hash = _pin_hash(body, settings, p["pin_hash"])
    _set_ha_user(fq, body, settings, pid)
    if body.role == "parent" and not pin_hash and not settings.get("ha_user_id"):
        raise HTTPException(400, "Parents need a Home Assistant user or a PIN")
    fq.db.x("UPDATE profile SET name=?, role=?, color=?, pin_hash=?, settings=?, planer_person_id=? WHERE id=?",
            body.name.strip()[:40], body.role, body.color, pin_hash, json.dumps(settings), body.planer_person_id, pid)
    if settings.get("internet_rule"):
        fq.internet.ensure_account()
    if fq.ha:
        fq.ha.profile_changed(pid)
    _planer_sync(fq)
    out = fq.profile_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid))
    if pid == me["id"]:                                  # an own new PIN ends the logins – this parent stays in
        out["parent_token"] = fq.tokens.make(pid, "parent")
    return out


@router.get("/profiles/{pid}/avatar")
def profile_avatar(pid: int, request: Request, me: dict = Parent) -> dict:
    """The avatar of any profile with the parts and the items this profile has unlocked (for the profile dialog)."""
    from ..rewards import avatar as av
    fq = app_of(request)
    p = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
    if not p:
        raise HTTPException(404, "Unknown profile")
    level, badges, bought = fq.avatar_state(pid)
    return {"avatar": json.loads(p["avatar"] or "{}") or av.DEFAULT_AVATAR, **av.catalog(level, badges, bought)}


class AvatarIn(BaseModel):
    avatar: dict


@router.put("/profiles/{pid}/avatar")
def profile_avatar_save(pid: int, body: AvatarIn, request: Request, me: dict = Parent) -> dict:
    from ..rewards import avatar as av
    fq = app_of(request)
    if not fq.db.q1("SELECT 1 FROM profile WHERE id=? AND archived=0", pid):
        raise HTTPException(404, "Unknown profile")
    level, badges, bought = fq.avatar_state(pid)
    a = av.clean(body.avatar, level, badges, bought)
    fq.db.x("UPDATE profile SET avatar=? WHERE id=?", json.dumps(a), pid)
    _planer_sync(fq)
    return {"avatar": a}


class CrownIn(BaseModel):
    on: bool = True


@router.post("/profiles/{pid}/crown")
def crown(pid: int, body: CrownIn, request: Request, me: dict = Parent) -> dict:
    """👑 for today (e.g. Epiphany – but any day): everybody sees the profile with the crown until midnight."""
    from datetime import date
    fq = app_of(request)
    p = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
    if not p:
        raise HTTPException(404, "Unknown profile")
    st = profile_settings(p)
    if body.on:
        st["crown_until"] = date.today().isoformat()
    else:
        st.pop("crown_until", None)
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), pid)
    return fq.profile_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid))


class PetPauseIn(BaseModel):
    on: bool = True


@router.put("/profiles/{pid}/pet-pause")
def pet_pause(pid: int, body: PetPauseIn, request: Request, me: dict = Parent) -> dict:
    """«Ferienbetreuung»: the pets of this child do not get hungry, sad or dirty while it is switched on."""
    fq = app_of(request)
    if not fq.db.q1("SELECT 1 FROM profile WHERE id=? AND archived=0", pid):
        raise HTTPException(404, "Unknown profile")
    fq.pets.set_paused(pid, body.on)
    return {"paused": fq.pets.paused_by_parents(pid), "pets": fq.pets.list(pid)}


@router.delete("/profiles/{pid}")
def delete_profile(pid: int, request: Request, name: str = "", mode: str = "archive", me: dict = Parent) -> dict:
    """Remove a profile – only with its name typed in again.
    mode "archive": inactive (hidden, history kept, can be restored); "delete": really gone with all its data."""
    fq = app_of(request)
    if mode not in ("archive", "delete"):
        raise HTTPException(400, "Unknown setting")
    if pid == me["id"]:
        raise HTTPException(400, "You cannot remove your own profile")
    p = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    if not p:
        raise HTTPException(404, "Unknown profile")
    if name.strip().casefold() != p["name"].strip().casefold():
        raise HTTPException(400, "Type the name of the profile to confirm")
    if p["role"] == "parent" and not p["archived"] and _parents(fq) <= 1:
        raise HTTPException(400, "At least one parent profile is needed")
    if mode == "archive":
        fq.db.x("UPDATE profile SET archived=1 WHERE id=?", pid)
    else:
        for t in fq.db.q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            cols = {c["name"] for c in fq.db.q(f"PRAGMA table_info({t['name']})")}
            if "profile_id" in cols and t["name"] != "profile":
                fq.db.x(f"DELETE FROM {t['name']} WHERE profile_id=?", pid)
        fq.db.x("DELETE FROM deck_card WHERE deck_id NOT IN (SELECT id FROM deck)")    # the cards of its own decks
        fq.db.x("DELETE FROM profile WHERE id=?", pid)
    _planer_sync(fq)
    return {"ok": True, "mode": mode}


@router.get("/profiles/archived")
def archived_profiles(request: Request, me: dict = Parent) -> list[dict]:
    fq = app_of(request)
    return [fq.profile_public(p) for p in fq.db.q("SELECT * FROM profile WHERE archived=1 ORDER BY name")]


@router.post("/profiles/{pid}/restore")
def restore_profile(pid: int, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if not fq.db.x("UPDATE profile SET archived=0 WHERE id=? AND archived=1", pid):
        raise HTTPException(404, "Unknown profile")
    _planer_sync(fq)
    return {"ok": True}


# ---------------------------------------------------------------- packs
@router.get("/packs")
def packs(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    act: dict[str, list[int]] = {}
    for r in fq.db.q("SELECT pack_id, profile_id FROM pack_profile"):
        act.setdefault(r["pack_id"], []).append(r["profile_id"])
    out = []
    for p in fq.packs.all():
        s = p.summary()
        s["profiles"] = act.get(p.id, [])
        out.append(s)
    return {"packs": out}


@router.post("/packs/activate")
def activate(body: ActivateIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if not fq.packs.get(body.pack_id):
        raise HTTPException(404, "Unknown pack")
    fq.packs.activate(body.profile_id, body.pack_id, body.on)
    return {"ok": True}


@router.post("/packs/{pack_id}/status")
def pack_status(pack_id: str, body: StatusIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if body.status not in ("active", "draft", "disabled"):
        raise HTTPException(400, "Unknown status")
    fq.packs.set_status(pack_id, body.status)
    return {"ok": True}


@router.delete("/packs/{pack_id}")
def delete_pack(pack_id: str, request: Request, me: dict = Parent) -> dict:
    app_of(request).packs.delete(pack_id)
    return {"ok": True}


@router.get("/packs/{pack_id}/raw")
def pack_raw(pack_id: str, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    data = fq.packs.raw(pack_id)
    if data is None:
        raise HTTPException(404, "Unknown pack")
    info = fq.packs.get(pack_id)
    return {"data": data, "yaml": yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            "summary": info.summary() if info else None}


@router.put("/packs/{pack_id}/raw")
def pack_save(pack_id: str, body: RawIn, request: Request, me: dict = Parent) -> dict:
    """Save an edited pack (cards edited in the editor or YAML)."""
    fq = app_of(request)
    try:
        data = body.data if body.data is not None else yaml.safe_load(body.yaml or "")
        p = parse_doc(data)
    except (PackError, yaml.YAMLError) as e:
        raise HTTPException(400, str(e)) from None
    if p.id != pack_id:
        raise HTTPException(400, "The id cannot be changed here")
    row = fq.db.q1("SELECT status FROM pack WHERE id=?", pack_id)
    fq.packs.upsert(p, "edited", status=row["status"] if row else "draft", force=True)
    # photos uploaded in the editor but no longer used by any card
    folder = fq.settings.media_dir / pack_id
    if folder.is_dir():
        used = media_refs(p)
        for f in folder.glob("foto-*"):
            if f.name not in used:
                f.unlink(missing_ok=True)
    return {"ok": True, "summary": fq.packs.get(pack_id).summary()}


PHOTO_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
PHOTO_MAX = 5 * 1024 * 1024
IMPORT_MAX = 30 * 1024 * 1024
BACKUP_MAX = 500 * 1024 * 1024


async def _read_photo(file: UploadFile) -> tuple[bytes, str]:
    """The uploaded bytes and the file extension – only real photos (checked by their first bytes), max. 5 MB."""
    raw = await file.read(PHOTO_MAX + 1)
    if raw[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        ext = ".webp"
    elif raw[:4] == b"GIF8":
        ext = ".gif"
    else:
        ext = None
    if not ext:
        raise HTTPException(400, "Only photos (JPEG, PNG, WebP, GIF) can be uploaded")
    if len(raw) > PHOTO_MAX:
        raise HTTPException(400, "The photo is too large (max. 5 MB)")
    return raw, ext


@router.post("/packs/{pack_id}/media")
async def pack_photo(pack_id: str, request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    """Upload an own photo for a card (e.g. «Paare finden» with family photos). Returns the name for `bild`."""
    fq = app_of(request)
    if fq.packs.raw(pack_id) is None:
        raise HTTPException(404, "Unknown pack")
    raw, ext = await _read_photo(file)
    name = "foto-" + hashlib.sha1(raw).hexdigest()[:12] + ext
    folder = fq.settings.media_dir / pack_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(raw)
    return {"name": name, "url": f"media/{pack_id}/{name}"}


@router.get("/packs/export")
def packs_export_all(request: Request, status: str | None = None, me: dict = Parent) -> Response:
    """All packs and level packs as one JSON file ({"pakete": [...]}) – importable again as a whole."""
    fq = app_of(request)
    data = [fq.packs.raw(p.id) for p in fq.packs.all(status=status)]
    body = json.dumps({"format": "family-quest-packs", "version": 1, "pakete": data}, ensure_ascii=False, indent=1)
    return Response(body, media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="family-quest-packs.json"'})


@router.get("/packs/{pack_id}/export")
def pack_export(pack_id: str, request: Request, format: str = "zip", me: dict = Parent) -> Response:
    """Export a pack as zip (YAML + pictures/audio), json or yaml."""
    fq = app_of(request)
    data = fq.packs.raw(pack_id)
    if data is None:
        raise HTTPException(404, "Unknown pack")
    if format == "json":
        return Response(json.dumps(data, ensure_ascii=False, indent=1), media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{pack_id}.json"'})
    if format == "yaml":
        return Response(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), media_type="application/yaml; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{pack_id}.yaml"'})
    if format != "zip":
        raise HTTPException(400, "format: zip, json or yaml")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{pack_id}.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        media = fq.settings.media_dir / pack_id
        if media.is_dir():
            for f in media.iterdir():
                z.write(f, f.name)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{pack_id}.zip"'})


# ---------------------------------------------------------------- import
@router.post("/import/file")
async def import_file(request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    fq = app_of(request)
    raw = await file.read(IMPORT_MAX + 1)
    if len(raw) > IMPORT_MAX:
        raise HTTPException(400, "The file is too large (max. 30 MB)")
    name = file.filename or "upload"

    def work() -> dict:            # parsing and the AI call take long: off the event loop, the app stays responsive
        if table.is_table(name):
            return {"table": table.stage(fq, name, raw)}
        if ai_draft.is_document(name):
            return {"drafts": ai_draft.draft_from_document(fq, name, raw)}
        return {"drafts": yaml_zip.import_bytes(fq, name, raw)}
    try:
        return await asyncio.to_thread(work)
    except PackError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/import/json")
def import_json(request: Request, body: Any = Body(...), me: dict = Parent) -> dict:
    """Packs as JSON in the request body: one pack, a level pack, a list, or {"pakete": [...]}. Result: drafts."""
    fq = app_of(request)
    try:
        return {"drafts": yaml_zip.import_data(fq, body)}
    except PackError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/import/table")
def import_table(body: TableIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    try:
        return {"drafts": table.build(fq, body.upload_id, body.meta, body.columns)}
    except PackError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/import/url")
def import_url(body: UrlIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    try:
        return {"drafts": yaml_zip.import_url(fq, body.url)}
    except PackError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/import/suggest")
def import_suggest(request: Request, name: str = Form(""), me: dict = Parent) -> dict:
    return table.suggest_meta(name)


# ---------------------------------------------------------------- accounts, rules, rewards
@router.get("/accounts")
def accounts(request: Request, me: dict = Parent) -> list[dict]:
    return app_of(request).rewards.accounts(active_only=False)


@router.put("/accounts")
def save_account(body: AccountIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    key = body.key.strip().lower()
    if not key.replace("_", "").isalnum():
        raise HTTPException(400, "Key: letters, digits and _ only")
    if key == "xp" and (body.spendable or not body.active):
        raise HTTPException(400, "XP always stays active and cannot be spent")
    fq.db.x("""INSERT INTO account(key,name,unit,icon,spendable,active,sort) VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET name=excluded.name,unit=excluded.unit,icon=excluded.icon,
               spendable=excluded.spendable,active=excluded.active,sort=excluded.sort""",
            key, body.name, body.unit, body.icon, int(body.spendable), int(body.active), body.sort)
    if fq.ha:
        fq.ha.all_changed()
    return {"ok": True}


@router.get("/rules")
def rules(request: Request, me: dict = Parent) -> list[dict]:
    rows = app_of(request).db.q("SELECT * FROM rule ORDER BY event, account")
    for r in rows:
        r["condition"] = json.loads(r["condition"] or "{}")
    return rows


@router.post("/rules")
def create_rule(body: RuleIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    rid = fq.db.x("INSERT INTO rule(event,account,amount,daily_limit,condition,label,active) VALUES(?,?,?,?,?,?,?)",
                  body.event, body.account, body.amount, body.daily_limit, json.dumps(body.condition), body.label,
                  int(body.active))
    return {"id": rid}


@router.put("/rules/{rid}")
def update_rule(rid: int, body: RuleIn, request: Request, me: dict = Parent) -> dict:
    app_of(request).db.x("UPDATE rule SET event=?,account=?,amount=?,daily_limit=?,condition=?,label=?,active=? WHERE id=?",
                         body.event, body.account, body.amount, body.daily_limit, json.dumps(body.condition),
                         body.label, int(body.active), rid)
    return {"ok": True}


@router.delete("/rules/{rid}")
def delete_rule(rid: int, request: Request, me: dict = Parent) -> dict:
    app_of(request).db.x("DELETE FROM rule WHERE id=?", rid)
    return {"ok": True}


@router.get("/rewards")
def rewards(request: Request, me: dict = Parent) -> list[dict]:
    return app_of(request).rewards.rewards(active_only=False)


def _check_reward(body: RewardIn) -> None:
    if body.kind not in KINDS:
        raise HTTPException(400, "Unknown reward type")
    if body.cost < 0:
        raise HTTPException(400, "Price must not be negative")


@router.post("/rewards")
def create_reward(body: RewardIn, request: Request, me: dict = Parent) -> dict:
    _check_reward(body)
    rid = app_of(request).db.x(
        "INSERT INTO reward(name,kind,account,cost,approval,weekly_limit,icon,config,active,sort) VALUES(?,?,?,?,?,?,?,?,?,?)",
        body.name, body.kind, body.account, body.cost, int(body.approval), body.weekly_limit, body.icon,
        json.dumps(body.config), int(body.active), body.sort)
    return {"id": rid}


@router.put("/rewards/{rid}")
def update_reward(rid: int, body: RewardIn, request: Request, me: dict = Parent) -> dict:
    _check_reward(body)
    app_of(request).db.x(
        "UPDATE reward SET name=?,kind=?,account=?,cost=?,approval=?,weekly_limit=?,icon=?,config=?,active=?,sort=? WHERE id=?",
        body.name, body.kind, body.account, body.cost, int(body.approval), body.weekly_limit, body.icon,
        json.dumps(body.config), int(body.active), body.sort, rid)
    return {"ok": True}


@router.delete("/rewards/{rid}")
def delete_reward(rid: int, request: Request, me: dict = Parent) -> dict:
    app_of(request).db.x("UPDATE reward SET active=0 WHERE id=?", rid)
    return {"ok": True}


@router.get("/redemptions")
def redemptions(request: Request, status: str | None = None, me: dict = Parent) -> list[dict]:
    return app_of(request).shop.list(status)


@router.post("/redemptions/{rid}")
def decide(rid: int, body: DecideIn, request: Request, me: dict = Parent) -> dict:
    try:
        return app_of(request).shop.decide(rid, body.approve, note=body.note)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/book")
def book(body: BookIn, request: Request, me: dict = Parent) -> dict:
    """Manual correction or bonus by a parent."""
    fq = app_of(request)
    if not fq.db.q1("SELECT 1 FROM account WHERE key=?", body.account):
        raise HTTPException(400, "Unknown account")
    b = fq.rewards.book(body.profile_id, body.account, body.amount, "manual", body.reason or "Parent", f"parent:{me['id']}")
    if fq.ha:
        fq.ha.profile_changed(body.profile_id)
    return b


@router.get("/ledger/{pid}")
def ledger(pid: int, request: Request, me: dict = Parent) -> list[dict]:
    return app_of(request).db.q("SELECT * FROM ledger WHERE profile_id=? ORDER BY id DESC LIMIT 100", pid)


# ---------------------------------------------------------------- chore plan (Ämtliplan)
class ChoreIn(BaseModel):
    name: str
    icon: str = "🧹"
    points: float = 10
    account: str = "coins"
    frequency: str = "daily"
    weekdays: list[int] = []
    date: str | None = None
    assign: str = "fixed"
    rotate_every: str = "week"
    profiles: list[int] = []
    kind: str = "bonus"
    confirm: bool = True
    active: bool = True
    sort: int = 0


class ChoreDecideIn(BaseModel):
    ok: bool


@router.get("/chores")
def chores(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    return {"chores": fq.chores.list(), "week": fq.chores.week(), "today": fq.chores.tasks(),
            "pending": fq.chores.pending()}


@router.post("/chores")
def create_chore(body: ChoreIn, request: Request, me: dict = Parent) -> dict:
    try:
        return {"id": app_of(request).chores.save(body.model_dump())}
    except ChoreError as e:
        raise HTTPException(400, str(e)) from None


@router.put("/chores/{cid}")
def update_chore(cid: int, body: ChoreIn, request: Request, me: dict = Parent) -> dict:
    try:
        return {"id": app_of(request).chores.save(body.model_dump(), cid)}
    except ChoreError as e:
        raise HTTPException(400, str(e)) from None


@router.delete("/chores/{cid}")
def delete_chore(cid: int, request: Request, me: dict = Parent) -> dict:
    app_of(request).chores.delete(cid)
    return {"ok": True}


@router.post("/chores/tasks/{tid}")
def decide_chore(tid: int, body: ChoreDecideIn, request: Request, me: dict = Parent) -> dict:
    try:
        return app_of(request).chores.decide(tid, body.ok)
    except ChoreError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- goals
@router.get("/goals")
def goals(request: Request, me: dict = Parent) -> list[dict]:
    return app_of(request).db.q("SELECT * FROM goal WHERE active=1 ORDER BY profile_id, id")


@router.post("/goals")
def create_goal(body: GoalIn, request: Request, me: dict = Parent) -> dict:
    if body.kind not in ("unit", "family"):
        raise HTTPException(400, "Unknown goal type")
    gid = app_of(request).db.x(
        "INSERT INTO goal(profile_id,kind,title,target,account,pack_id,unit_id,active) VALUES(?,?,?,?,?,?,?,?)",
        None if body.kind == "family" else body.profile_id, body.kind, body.title, body.target, body.account,
        body.pack_id, body.unit_id, int(body.active))
    return {"id": gid}


@router.delete("/goals/{gid}")
def delete_goal(gid: int, request: Request, me: dict = Parent) -> dict:
    app_of(request).db.x("UPDATE goal SET active=0 WHERE id=?", gid)
    return {"ok": True}


# ---------------------------------------------------------------- settings
@router.get("/settings")
def settings(request: Request, me: dict = Parent) -> dict:
    return app_of(request).db.all_settings()


@router.put("/settings")
def save_settings(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    nets = {}
    for k in ("allowed_networks", "parent_networks", "guest_networks"):
        if k in body:
            try:
                nets[k] = netfilter.parse(body[k])
            except ValueError as e:
                raise HTTPException(400, str(e)) from None
    if nets:
        # never lock out the parent who is saving
        ip = loginlog.client_ip(request)
        for k in ("allowed_networks", "parent_networks"):
            if not netfilter.allowed(ip, nets.get(k, fq.db.get_setting(k) or [])):
                raise HTTPException(400, f"This would lock you out – your device ({ip}) is not in these networks")
        guests = nets.get("guest_networks", fq.db.get_setting("guest_networks") or [])
        family = nets.get("allowed_networks", fq.db.get_setting("allowed_networks") or [])
        if guests and netfilter.allowed(ip, guests) and not (family and netfilter.allowed(ip, family)):
            raise HTTPException(400, f"This would lock you out – your device ({ip}) would only be a guest")
        body = {**body, **nets}
    if body.get("parent_ha_only"):
        u = ha_user(request)
        if not u or profile_settings(me).get("ha_user_id") != u["id"]:
            raise HTTPException(400, "Link your Home Assistant user first and open the parent area through Home Assistant")
    def finite(v) -> bool:                       # JSON may carry Infinity / NaN – such a number would break the readers
        if isinstance(v, float):
            return math.isfinite(v)
        if isinstance(v, dict):
            return all(finite(x) for x in v.values())
        if isinstance(v, list):
            return all(finite(x) for x in v)
        return True
    for k, v in body.items():
        if k in DEFAULT_SETTINGS and not finite(v):
            raise HTTPException(400, "Invalid number")
    for k, v in body.items():
        if k in DEFAULT_SETTINGS:
            fq.db.set_setting(k, v)
    return fq.db.all_settings()


# ---------------------------------------------------------------- behaviour weather
class WeatherIn(BaseModel):
    level: str


@router.get("/weather")
def weather(request: Request, me: dict = Parent) -> dict:
    """All children with their weather of today and the last 30 days – only parents see this list."""
    fq = app_of(request)
    return {"config": fq.weather.config(),
            "kids": [{"profile": fq.profile_public(k), "current": fq.weather.current(k["id"]),
                      "days": fq.weather.history(k["id"])} for k in fq.kids()]}


@router.post("/weather/{pid}")
def set_weather(pid: int, body: WeatherIn, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if not fq.db.q1("SELECT 1 FROM profile WHERE id=? AND role='kid' AND archived=0", pid):
        raise HTTPException(404, "Unknown profile")
    try:
        cur = fq.weather.set(pid, body.level, me["id"])
    except WeatherError as e:
        raise HTTPException(400, str(e)) from None
    if fq.ha:
        fq.ha.profile_changed(pid)
    return {"current": cur, "days": fq.weather.history(pid), "balances": fq.rewards.balances(pid)}


@router.put("/weather/config")
def weather_config(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    try:
        return app_of(request).weather.save_config(body)
    except WeatherError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- own translations
class LanguageIn(BaseModel):
    name: str = ""
    base: str = "de-DE"
    flag: str = ""


class TextsIn(BaseModel):
    texts: dict[str, str | None]
    merge: bool = True


class CsvIn(BaseModel):
    csv: str


def _tr(fn):
    try:
        return fn()
    except TranslationError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/translations")
def translations(request: Request, me: dict = Parent) -> dict:
    t = app_of(request).translations
    return {"builtin": BUILTIN, "languages": t.languages(),
            "counts": {l: len(t.overrides(l)) for l in BUILTIN + [x["code"] for x in t.languages()]}}


@router.post("/translations/languages")
def add_language(body: LanguageIn, request: Request, me: dict = Parent) -> dict:
    return _tr(lambda: app_of(request).translations.add_language(body.name, body.base, body.flag))


@router.put("/translations/languages/{code}")
def update_language(code: str, body: LanguageIn, request: Request, me: dict = Parent) -> dict:
    return _tr(lambda: app_of(request).translations.update_language(code, body.name, body.flag, body.base))


@router.delete("/translations/languages/{code}")
def delete_language(code: str, request: Request, me: dict = Parent) -> dict:
    app_of(request).translations.delete_language(code)
    return {"ok": True}


@router.get("/translations/{lang}")
def translation_texts(lang: str, request: Request, me: dict = Parent) -> dict:
    t = app_of(request).translations
    return _tr(lambda: {"keys": source_keys(), "standard": t.standard(lang), "own": t.overrides(lang)})


@router.put("/translations/{lang}")
def save_texts(lang: str, body: TextsIn, request: Request, me: dict = Parent) -> dict:
    return {"own": _tr(lambda: app_of(request).translations.set_overrides(lang, body.texts, merge=body.merge))}


@router.get("/translations/{lang}/csv")
def export_texts(lang: str, request: Request, me: dict = Parent) -> Response:
    body = _tr(lambda: app_of(request).translations.export_csv(lang))
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="family-quest-{lang}.csv"'})


@router.post("/translations/{lang}/csv")
def import_texts(lang: str, body: CsvIn, request: Request, me: dict = Parent) -> dict:
    t = app_of(request).translations
    n = _tr(lambda: t.import_csv(lang, body.csv))
    return {"imported": n, "own": t.overrides(lang)}


# ---------------------------------------------------------------- kiosk dashboard
@router.get("/dashboard")
def dashboard_config(request: Request, me: dict = Parent) -> dict:
    return app_of(request).kiosk.config()


@router.put("/dashboard")
def dashboard_save(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    try:
        return app_of(request).kiosk.save(body)
    except (DashboardError, ValueError, TypeError) as e:
        raise HTTPException(400, str(e)) from None


@router.post("/dashboard/key")
def dashboard_key(request: Request, me: dict = Parent) -> dict:
    """A new key – kiosk browsers with the old link stop working."""
    return app_of(request).kiosk.new_key()


# ---------------------------------------------------------------- family calendar
class EventIn(BaseModel):
    title: str
    start: str
    end: str = ""
    icon: str = ""
    color: str = ""
    kind: str = "event"                  # event | familytime | offlinetime | …
    note: str = ""
    options: dict = {}                   # offlinetime: {"internet": bool, "games": bool, "profiles": [ids]}


class EventsIn(BaseModel):
    events: list[dict[str, Any]]
    source: str = "import"


class FileTextIn(BaseModel):
    name: str = ""
    text: str


def _cal(fn):
    try:
        return fn()
    except CalendarError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/calendar")
def calendar_events(start: str, end: str, request: Request, me: dict = Parent) -> dict:
    """Own events and the chosen Home Assistant calendars (read-only) between start and end (ISO dates)."""
    cal = app_of(request).calendar
    return {"events": _cal(lambda: cal.range(start, end)), "settings": cal.settings(), "sources": cal.sources()}


@router.post("/calendar")
def calendar_add(body: EventIn, request: Request, me: dict = Parent) -> dict:
    return {"id": _cal(lambda: app_of(request).calendar.add(body.model_dump()))}


@router.put("/calendar/settings")
def calendar_settings(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    return _cal(lambda: app_of(request).calendar.save_settings(body))


@router.put("/calendar/{eid}")
def calendar_update(eid: int, body: EventIn, request: Request, me: dict = Parent) -> dict:
    _cal(lambda: app_of(request).calendar.update(eid, body.model_dump()))
    return {"ok": True}


@router.delete("/calendar/{eid}")
def calendar_delete(eid: int, request: Request, me: dict = Parent) -> dict:
    app_of(request).calendar.delete(eid)
    return {"ok": True}


@router.get("/calendar/cantons")
def calendar_cantons(request: Request, me: dict = Parent) -> dict:
    from ..calendar import CANTONS
    return CANTONS


@router.get("/calendar/holidays")
def calendar_holidays(canton: str, year: int, request: Request, school: bool = True, public: bool = True,
                      lang: str = "DE", me: dict = Parent) -> list[dict]:
    """Preview of a template: school and public holidays of a canton, each marked if it is already in the calendar."""
    cal = app_of(request).calendar
    return _cal(lambda: cal.check(cal.holidays(canton, year, school, public, lang.upper()[:2])))


@router.post("/calendar/parse")
def calendar_parse(body: FileTextIn, request: Request, me: dict = Parent) -> list[dict]:
    """Preview of a file: CSV (title;start;end) or iCal (.ics) – duplicates marked."""
    from ..calendar import parse_csv, parse_ics
    cal = app_of(request).calendar
    ics = "BEGIN:VCALENDAR" in body.text[:2000].upper() or body.name.lower().endswith((".ics", ".ical"))
    return _cal(lambda: cal.check(parse_ics(body.text) if ics else parse_csv(body.text)))


@router.post("/calendar/import")
def calendar_import(body: EventsIn, request: Request, me: dict = Parent) -> dict:
    return _cal(lambda: app_of(request).calendar.import_events(body.events, body.source[:80] or "import"))


@router.delete("/calendar/source/{source:path}")
def calendar_delete_source(source: str, request: Request, me: dict = Parent) -> dict:
    """Remove a whole import (e.g. the school holidays of a canton) again."""
    return {"deleted": app_of(request).calendar.delete_source(source)}


# ---------------------------------------------------------------- family games on / off
class GamesIn(BaseModel):
    mode: str | None = None         # older form: one switch for all games – all | some | off
    profiles: list[int] = []
    access: dict | None = None      # per game: {"bingo": {"mode": "some", "profiles": [2, 3]}, …}


@router.get("/games")
def games_get(request: Request, me: dict = Parent) -> dict:
    return {"access": app_of(request).games_access()}


@router.put("/games")
def games(body: GamesIn, request: Request, me: dict = Parent) -> dict:
    """Which games are open – for everybody, for chosen children or for nobody; parents can always play."""
    fq = app_of(request)
    if body.access is None:
        if body.mode not in ("all", "some", "off"):
            raise HTTPException(400, "Unknown setting")
        body.access = {g: {"mode": body.mode, "profiles": body.profiles} for g in fq.GAMES}
    acc = fq.games_access()
    for g, a in body.access.items():
        if g not in fq.GAMES or not isinstance(a, dict) or a.get("mode") not in ("all", "some", "off"):
            raise HTTPException(400, "Unknown setting")
        acc[g] = {"mode": a["mode"], "profiles": sorted({int(x) for x in a.get("profiles") or []})}
    fq.db.set_setting("games_access", acc)
    return {"access": acc}


REWARD_GAMES = ("paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "verboten", "jass", "werwolf")       # live games with coins for places 1–3 (game_rewards)


@router.get("/game-rewards")
def game_rewards_get(request: Request, me: dict = Parent) -> dict:
    """Coins for places 1, 2, 3 of the live games (Paarjagd, «Wer bin ich?», Kartenlauf, Stadt-Land-Fluss, «Zeichnen & Raten», «Fünf Würfel», «Heimwärts», «Verbotene Wörter», «Jass», «Werwölfe») – only family tables with at least two people."""
    from ..pairhunt import rewards_of
    db = app_of(request).db
    return {k: rewards_of(db, k) for k in REWARD_GAMES}


@router.put("/game-rewards")
def game_rewards_put(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    from ..pairhunt import rewards_of
    fq = app_of(request)
    out = dict(fq.db.get_setting("game_rewards") or {})
    for k, v in body.items():
        if k not in REWARD_GAMES:
            raise HTTPException(400, "Unknown game")
        if not isinstance(v, list) or len(v) != 3 or not all(type(x) is int and 0 <= x <= 1000 for x in v):
            raise HTTPException(400, "Three numbers of coins (0 to 1000) are needed")
        out[k] = v
    fq.db.set_setting("game_rewards", out)
    return {k: rewards_of(fq.db, k) for k in REWARD_GAMES}


# ---------------------------------------------------------------- failed logins, network filter
@router.get("/my-address")
def my_address(request: Request, me: dict = Parent) -> dict:
    """The address this device is seen with (for the network filter)."""
    fq = app_of(request)
    ip = loginlog.client_ip(request)
    name, mac = loginlog.device(fq, ip)
    return {"ip": ip, "device": name, "mac": mac}



@router.get("/logins/failed")
def failed_logins(request: Request, days: int = 30, me: dict = Parent) -> list[dict]:
    """Wrong PINs with IP, MAC, device name and who normally logs in from that address."""
    return loginlog.failures(app_of(request), max(1, min(days, 180)))


# ---------------------------------------------------------------- link for tablets (direct access, QR code)
@router.get("/direct-access")
async def direct_access(request: Request, me: dict = Parent) -> dict:
    """Is direct access on, which host port is mapped to 8099 and which IP has Home Assistant (Supervisor API)."""
    from ..netinfo import home_access
    return await home_access(app_of(request).settings)


# ---------------------------------------------------------------- Home Assistant / Family Planer
@router.get("/ha/persons")
def planer_persons(request: Request, me: dict = Parent) -> list[dict]:
    fq = app_of(request)
    return fq.ha.planer_persons() if fq.ha else []


@router.post("/ha/import_persons")
def import_persons(request: Request, me: dict = Parent) -> dict:
    """Create a child profile for every Family Planer person that is not linked yet."""
    fq = app_of(request)
    if not fq.ha:
        raise HTTPException(400, "Home Assistant is not connected")
    linked = {r["planer_person_id"] for r in fq.db.q("SELECT planer_person_id FROM profile WHERE planer_person_id IS NOT NULL AND archived=0")}
    created = []
    for p in fq.ha.planer_persons():
        if p["id"] in linked or p.get("role") == "adult":
            continue
        pid = fq.db.x("INSERT INTO profile(name,role,color,planer_person_id) VALUES(?,?,?,?)",
                      p["name"], "kid", p.get("color") or "#4f8cff", p["id"])
        fq.packs.activate_defaults(pid)
        created.append(p["name"])
    if created:
        fq.ha.all_changed()
    return {"created": created}


@router.get("/ha/entities")
def ha_entities(request: Request, domain: str = "input_number", me: dict = Parent) -> list[dict]:
    fq = app_of(request)
    return fq.ha.entities(domain) if fq.ha else []


class HelperIn(BaseModel):
    name: str


@router.get("/ha/areas")
def ha_areas(request: Request, me: dict = Parent) -> list[dict]:
    """Areas (rooms) of Home Assistant – a child may get a whole room instead of single devices."""
    fq = app_of(request)
    if not fq.ha or not fq.ha.connected:
        return []
    try:
        return [{**a, "count": len(fq.ha.area_entities(a["area_id"]))} for a in fq.ha.areas()]
    except Exception:  # noqa: BLE001
        return []


@router.post("/ha/input_number")
def ha_create_input_number(body: HelperIn, request: Request, me: dict = Parent) -> dict:
    """Create the budget entity for a child's internet minutes in Home Assistant."""
    fq = app_of(request)
    if not fq.ha or not fq.ha.connected:
        raise HTTPException(400, "Home Assistant is not connected")
    try:
        return {"entity_id": fq.ha.create_input_number(body.name.strip() or "Internet minutes")}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Home Assistant: {e}") from None


# ---------------------------------------------------------------- internet time
@router.post("/internet/{pid}/stop")
def internet_stop(pid: int, request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
    if not prof:
        raise HTTPException(404, "Unknown profile")
    return {"internet": fq.internet.stop(prof)}


# ---------------------------------------------------------------- backup & restore
@router.get("/backup")
async def backup_download(request: Request, me: dict = Parent) -> Response:
    """Everything in one ZIP file."""
    from .. import backup
    fq = app_of(request)
    if fq.planer_host:
        await fq.planer_host.save_now()
    data, name = await asyncio.to_thread(backup.create, fq)
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/backup/sizes")
def backup_sizes(request: Request, me: dict = Parent) -> dict:
    """What takes how much room in a backup."""
    from .. import backup
    return backup.sizes(app_of(request))


@router.post("/backup/inspect")
async def backup_inspect(request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    from .. import backup
    try:
        return {"manifest": backup.inspect(await file.read())}
    except backup.BackupError as e:
        raise HTTPException(400, str(e)) from None


# Uploads through Home Assistant (ingress) may be at most about 16 MB («HTTP 413») – a backup with photos is bigger.
# The parent area therefore sends the file in pieces (CHUNK), they are put together here, then inspected and restored.
UPLOAD_RE = re.compile(r"[a-z0-9]{8,40}")


def _upload_path(request: Request, upload: str):
    if not UPLOAD_RE.fullmatch(upload or ""):
        raise HTTPException(400, "Unknown upload")
    folder = app_of(request).settings.data_dir / "restore_upload"
    folder.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for f in folder.iterdir():                    # leftovers of uploads that were not finished
        try:
            if now - f.stat().st_mtime > 3600:
                f.unlink()
        except OSError:
            pass
    return folder / (upload + ".zip")


@router.post("/backup/chunk")
async def backup_chunk(request: Request, upload: str, index: int, me: dict = Parent) -> dict:
    """One piece of a backup file (raw bytes, in order: index 0, 1, 2 …)."""
    path = _upload_path(request, upload)
    data = await request.body()
    if index == 0:
        path.write_bytes(b"")
    elif not path.exists():
        raise HTTPException(400, "Unknown upload")
    size = path.stat().st_size + len(data)
    if size > BACKUP_MAX:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "The backup is too large (max. 500 MB)")
    with path.open("ab") as f:
        f.write(data)
    return {"size": size}


def _uploaded(request: Request, body: dict) -> tuple:
    path = _upload_path(request, str(body.get("upload") or ""))
    if not path.exists():
        raise HTTPException(400, "Unknown upload")
    return path, path.read_bytes()


@router.post("/backup/inspect-upload")
async def backup_inspect_upload(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    from .. import backup
    _path, raw = _uploaded(request, body)
    try:
        return {"manifest": backup.inspect(raw)}
    except backup.BackupError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/restore-upload")
async def backup_restore_upload(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    """Replace all data with a backup that was sent in pieces."""
    from .. import backup
    fq = app_of(request)
    path, raw = _uploaded(request, body)
    try:
        backup.inspect(raw)
        if fq.planer_host:
            fq.planer_host.freeze()              # the old planner must not save into the restored database
        manifest = await asyncio.to_thread(backup.restore, fq, raw)
    except backup.BackupError as e:
        raise HTTPException(400, str(e)) from None
    finally:
        path.unlink(missing_ok=True)
    if fq.planer_host:
        await fq.planer_host.reload()
    if fq.ha:
        fq.ha.all_changed()
    return {"ok": True, "manifest": manifest}


@router.post("/restore")
async def backup_restore(request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    """Replace all data with a backup file."""
    from .. import backup
    fq = app_of(request)
    raw = await file.read(BACKUP_MAX + 1)
    if len(raw) > BACKUP_MAX:
        raise HTTPException(400, "The backup is too large (max. 500 MB)")
    try:
        backup.inspect(raw)
        if fq.planer_host:
            fq.planer_host.freeze()              # the old planner must not save into the restored database
        manifest = await asyncio.to_thread(backup.restore, fq, raw)
    except backup.BackupError as e:
        raise HTTPException(400, str(e)) from None
    if fq.planer_host:
        await fq.planer_host.reload()
    if fq.ha:
        fq.ha.all_changed()
    return {"ok": True, "manifest": manifest}


# ---------------------------------------------------------------- pairs game: own photo sets and the family crest
@router.get("/memory")
def memory_get(request: Request, me: dict = Parent) -> dict:
    from .. import memorygame
    return memorygame.get(app_of(request))


@router.put("/memory")
def memory_put(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    from .. import memorygame
    try:
        return memorygame.save(app_of(request), body)
    except memorygame.MemoryError_ as e:
        raise HTTPException(400, str(e)) from None


@router.post("/memory/photo")
async def memory_photo(request: Request, file: UploadFile = File(...), me: dict = Parent) -> dict:
    from .. import memorygame
    raw, ext = await _read_photo(file)
    name = "foto-" + hashlib.sha1(raw).hexdigest()[:12] + ext
    folder = app_of(request).settings.media_dir / memorygame.FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(raw)
    return {"name": name, "url": f"media/{memorygame.FOLDER}/{name}"}


# ---------------------------------------------------------------- running games: end one or all (running.py)
@router.get("/games/running")
def games_running(request: Request, me: dict = Parent) -> list[dict]:
    from .. import running
    return running.running(app_of(request))


@router.post("/games/end")
def games_end(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    """{"key": "<key>"} ends one game, {"all": true} every running game."""
    from .. import running
    fq = app_of(request)
    if body.get("all"):
        n = running.end_all(fq)
    else:
        try:
            running.end(fq, str(body.get("key") or ""))
        except ValueError:
            raise HTTPException(400, "Unknown game") from None
        n = 1
    return {"ended": n, "running": running.running(fq)}


@router.get("/ha-media")
def ha_media(request: Request, path: str = "", me: dict = Parent) -> dict:
    """Browse Home Assistant Media (My media, mapped read-only as /media): folders and pictures."""
    from .. import memorygame
    try:
        return memorygame.ha_media_list(app_of(request).settings.ha_media_dir, path)
    except memorygame.MemoryError_ as e:
        raise HTTPException(404, str(e)) from None


@router.get("/ha-media/file")
def ha_media_file(request: Request, path: str, me: dict = Parent):
    """One picture of Home Assistant Media – for the preview in the parent area."""
    from .. import memorygame
    try:
        f = memorygame.ha_media_path(app_of(request).settings.ha_media_dir, path)
    except memorygame.MemoryError_:
        raise HTTPException(404) from None
    if not f.is_file() or f.suffix.lower() not in memorygame.PICTURE_EXT:
        raise HTTPException(404)
    return FileResponse(f, headers={"Cache-Control": "private, max-age=3600"})


@router.post("/memory/ha-media")
def memory_ha_media(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    """Take pictures from Home Assistant Media for photo sets or the crest (copied into the photo folder)."""
    from .. import memorygame
    fq = app_of(request)
    try:
        return {"names": memorygame.ha_media_copy(fq, fq.settings.ha_media_dir, body.get("paths"))}
    except memorygame.MemoryError_ as e:
        raise HTTPException(400, str(e)) from None


@router.get("/ha/users")
def ha_users(request: Request, me: dict = Parent) -> list[dict]:
    """Home Assistant users (persons with a login) to link with parent profiles, and which profile has them."""
    fq = app_of(request)
    if not (fq.ha and fq.ha.connected):
        return []
    linked = {profile_settings(p).get("ha_user_id"): p["name"] for p in fq.db.q("SELECT * FROM profile WHERE role='parent' AND archived=0")}
    return [{**u, "linked_to": linked.get(u["id"])} for u in fq.ha.users()]


@router.post("/app-token")
def app_token(request: Request, me: dict = Parent) -> dict:
    """«Open in the app»: the parent plays in the app (new tab) without logging in again – a learning-app login of
    this parent, handed over in the address fragment (it never reaches a server log)."""
    return {"token": app_of(request).tokens.make(me["id"], "kid", ttl=12 * 3600)}      # «open in the app»: half a day
