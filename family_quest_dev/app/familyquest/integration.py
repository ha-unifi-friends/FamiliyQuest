"""Family Quest HA integration: the add-on side of the custom component `familyquest` (app/ha_integration/).

Parent area › Settings › «Family Quest HA integration» (off by default):
* on: an integration token is made (shown once, stored as a SHA-256 hash – it is 256 random bits, so a fast hash is
  enough) and the component is copied to /config/custom_components/familyquest (map homeassistant_config:rw).
  It is copied again at every start of the app while the setting is on (an update of the app updates the component).
* off: the token stops working (the API answers 403); the component can be removed with a button.

The component polls GET /api/integration/state every 30 s and sends the few whitelisted actions to
POST /api/integration/action – both with `Authorization: Bearer <token>` (api/integration.py). Only the Supervisor
network (Home Assistant Core) may call these paths inside the add-on (main.py access check).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import shutil
import socket
from datetime import datetime
from pathlib import Path

from .db import profile_settings
from .rewards.engine import today
from .settings import APP_DIR
from . import timelimits

log = logging.getLogger("familyquest.integration")

KEY = "ha_integration"                    # setting: {"enabled", "token_hash", "token_at", "instance"}
DOMAIN = "familyquest"
SOURCE = APP_DIR / "ha_integration" / DOMAIN
HA_CONFIG = Path(os.environ.get("FQ_HA_CONFIG", "/homeassistant"))     # Home Assistant's /config inside the add-on
PORT = 8099                              # the port inside the container (ingress port) – not the host port
MAX_AMOUNT = 10000


class IntegrationError(ValueError):
    pass


# ---------------------------------------------------------------- setting and token
def config(fq) -> dict:
    c = fq.db.get_setting(KEY) or {}
    return c if isinstance(c, dict) else {}


def _save(fq, c: dict) -> None:
    fq.db.set_setting(KEY, c)


def enabled(fq) -> bool:
    return bool(config(fq).get("enabled"))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def instance_id(fq) -> str:
    """Stable id of this Family Quest (unique ids of the entities in Home Assistant)."""
    c = config(fq)
    if not c.get("instance"):
        c["instance"] = secrets.token_hex(6)
        _save(fq, c)
    return c["instance"]


def new_token(fq) -> str:
    """A new token – the old one stops working. Returned once, only the hash is kept."""
    token = "fqi_" + secrets.token_urlsafe(32)
    c = config(fq)
    c.update(token_hash=_hash(token), token_at=datetime.now().isoformat(timespec="minutes"))
    c.setdefault("instance", secrets.token_hex(6))
    _save(fq, c)
    return token


def check_token(fq, token: str | None) -> bool:
    c = config(fq)
    if not c.get("enabled") or not c.get("token_hash") or not token:
        return False
    return hmac.compare_digest(_hash(token), c["token_hash"])


def set_enabled(fq, on: bool) -> str | None:
    """Switch on (returns a new token the first time) or off (the token is kept but refused while off)."""
    c = config(fq)
    c["enabled"] = bool(on)
    _save(fq, c)
    if on and not c.get("token_hash"):
        return new_token(fq)
    return None


def addon_url() -> str:
    """Address of the app on the Supervisor network: http://<add-on hostname>:8099 (e.g. a0d7b954-family-quest)."""
    host = os.environ.get("FQ_ADDON_HOST") or socket.gethostname() or "local-family-quest"
    return f"http://{host}:{PORT}"


def status(fq) -> dict:
    c = config(fq)
    return {"enabled": bool(c.get("enabled")), "has_token": bool(c.get("token_hash")), "token_at": c.get("token_at"),
            "url": addon_url(), "component": component_status(), "config_writable": _writable(HA_CONFIG),
            "last_poll": c.get("last_poll")}


def polled(fq) -> None:
    """Remember (at most every 10 minutes) when Home Assistant last asked – shown in the parent area."""
    c = config(fq)
    now = datetime.now().isoformat(timespec="minutes")
    if (c.get("last_poll") or "")[:15] != now[:15]:
        c["last_poll"] = now
        _save(fq, c)


# ---------------------------------------------------------------- the custom component in /config
def _writable(p: Path) -> bool:
    return p.is_dir() and os.access(p, os.W_OK)


def _version_of(folder: Path) -> str | None:
    try:
        return json.loads((folder / "manifest.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def component_status(base: Path | None = None) -> dict:
    dst = (base or HA_CONFIG) / "custom_components" / DOMAIN
    return {"installed": dst.is_dir(), "version": _version_of(dst) if dst.is_dir() else None, "path": "/config/custom_components/" + DOMAIN}


def install(version: str, base: Path | None = None, url: str | None = None) -> dict:
    """Copy the component into <config>/custom_components/familyquest (replacing an older copy).
    The manifest gets the app version; addon.json holds the address the config flow suggests."""
    base = base or HA_CONFIG
    if not _writable(base):
        raise IntegrationError("The Home Assistant configuration folder is not writable (map homeassistant_config:rw)")
    dst = base / "custom_components" / DOMAIN
    before = _version_of(dst)
    tmp = base / "custom_components" / f".{DOMAIN}.new"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(SOURCE, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    man = json.loads((tmp / "manifest.json").read_text(encoding="utf-8"))
    man["version"] = _manifest_version(version)
    (tmp / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    (tmp / "addon.json").write_text(json.dumps({"url": url or addon_url(), "version": version}, indent=2) + "\n", encoding="utf-8")
    if dst.exists():
        shutil.rmtree(dst)
    tmp.rename(dst)
    return {"installed": True, "version": man["version"], "previous": before, "changed": before != man["version"]}


def _manifest_version(v: str) -> str:
    """Home Assistant wants a valid version (AwesomeVersion): «dev» or «test» become 0.0.0."""
    return v if v and v[0].isdigit() else "0.0.0"


def remove(base: Path | None = None) -> bool:
    dst = (base or HA_CONFIG) / "custom_components" / DOMAIN
    if not dst.is_dir():
        return False
    shutil.rmtree(dst)
    return True


def install_on_start(fq) -> None:
    """At start: while the setting is on, bring the component in /config up to date (never fails the start)."""
    if not enabled(fq):
        return
    try:
        r = install(fq.settings.version)
        if r["changed"]:
            log.info("Family Quest HA integration %s installed in /config/custom_components – restart Home Assistant", r["version"])
    except Exception as e:  # noqa: BLE001
        log.warning("Family Quest HA integration not installed: %s", e)


# ---------------------------------------------------------------- state (all KPIs)
def _num(v) -> float | int:
    v = float(v or 0)
    if not math.isfinite(v):
        return 0
    return int(v) if v == int(v) else round(v, 1)


def _child(fq, prof: dict, accounts: list[dict], now: datetime) -> dict:
    r = fq.rewards
    pid = prof["id"]
    ps = profile_settings(prof)
    goal = int(ps["daily_goal"])
    xp = r.xp_today(pid)
    lvl = r.level(pid)
    day = fq.db.q1("SELECT * FROM daily WHERE profile_id=? AND day=?", pid, today().isoformat()) or {}
    tasks = fq.chores.tasks(pid=pid)
    bal = r.balances(pid)
    net = fq.internet.state(prof)
    internet = None
    if net is not None:
        budget = net.get("budget") or {}
        blk = net.get("block")
        internet = {"running": net["running"], "minutes": None if budget.get("unlimited") else net["minutes"],
                    "unlimited": bool(budget.get("unlimited")), "can_start": bool(net["can_start"]),
                    "blocked": not net["running"], "block_until": blk["until"] if blk else None,
                    "reset_at": budget.get("reset_at")}
    game_left = timelimits.left(fq.db, prof, "game", now)
    learn_left = timelimits.left(fq.db, prof, "learn", now)
    off_net = fq.calendar.blocks(pid, "internet", now)
    off_games = fq.calendar.blocks(pid, "games", now)
    plan_block = fq.internet.block(prof, now)
    offline = off_net or off_games
    return {
        "id": pid, "name": prof["name"], "color": prof.get("color"),
        "xp_today": _num(xp), "daily_goal": goal, "goal_met": bool(day.get("goal_met")) or xp >= goal,
        "goal_percent": min(100, round(100 * xp / max(1, goal))),
        "total_xp": _num(lvl["xp"]), "level": lvl["level"], "next_level_at": lvl.get("next"),
        "streak": r.streak(pid),
        "balances": {a["key"]: _num(bal.get(a["key"], 0)) for a in accounts},
        "chores_open": sum(1 for t in tasks if t["status"] != "done"),
        "chores_open_list": [t["name"] for t in tasks if t["status"] != "done"],
        "chores_pending": sum(1 for t in tasks if t["status"] == "pending"),
        "lessons_today": int(day.get("lessons") or 0), "learn_minutes_today": int(day.get("seconds") or 0) // 60,
        "internet": internet,
        "game_left": game_left, "game_unlimited": game_left is None, "game_used_up": game_left == 0,
        "game_minutes_today": timelimits.used(fq.db, pid, "game", now),
        "learn_left": learn_left, "learn_unlimited": learn_left is None,
        "offline_time": bool(offline or plan_block),
        "offline_title": (offline or {}).get("title") or ("" if not plan_block else "block time"),
    }


def state(fq, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    accounts = [{"key": a["key"], "name": a["name"], "unit": a["unit"] or "", "icon": a["icon"] or ""}
                for a in fq.rewards.accounts() if a["spendable"]]
    children = [_child(fq, k, accounts, now) for k in fq.kids()]
    try:
        from . import running
        games = len(running.running(fq))
    except Exception:  # noqa: BLE001
        log.exception("running games")
        games = 0
    fq.community._close_due()
    polls = int(fq.db.val("SELECT COUNT(*) FROM poll WHERE status='open'", default=0) or 0)
    council = int(fq.db.val("SELECT COUNT(*) FROM council_topic WHERE status='vote'", default=0) or 0)
    pending_chores = [{"task_id": t["id"], "child": t["profile_name"], "child_id": t["profile_id"], "chore": t["name"]}
                      for t in fq.chores.pending()]
    pending_rewards = [{"redemption_id": x["id"], "child": x["profile_name"], "child_id": x["profile_id"], "reward": x["name"]}
                       for x in fq.shop.list("pending")]
    return {
        "instance": instance_id(fq), "version": fq.settings.version, "accounts": accounts, "children": children,
        "family": {"total_xp": _num(sum(c["total_xp"] for c in children)), "xp_today": _num(sum(c["xp_today"] for c in children)),
                   "running_games": games, "open_polls": polls, "open_votes": polls + council,
                   "pending_approvals": len(pending_chores) + len(pending_rewards)},
        "pending_chores": pending_chores, "pending_rewards": pending_rewards,
    }


# ---------------------------------------------------------------- actions (whitelist)
ACTIONS = ("add_points", "approve_chore", "approve_reward", "internet_start", "internet_stop")


def _kid(fq, ref) -> dict:
    """A child by id or by name (case-insensitive)."""
    kids = fq.kids()
    for k in kids:
        if str(k["id"]) == str(ref).strip() or k["name"].casefold() == str(ref).strip().casefold():
            return k
    raise IntegrationError("Unknown child")


def _bool(v, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(v)


def action(fq, body: dict) -> dict:
    from .chores import ChoreError
    from .internet import InternetError
    from .rewards.shop import ShopError
    if not isinstance(body, dict) or body.get("action") not in ACTIONS:
        raise IntegrationError("Unknown action")
    act = body["action"]
    try:
        if act == "add_points":
            kid = _kid(fq, body.get("child"))
            acc = str(body.get("account") or "coins")
            if not fq.db.q1("SELECT 1 FROM account WHERE key=? AND active=1", acc):
                raise IntegrationError("Unknown account")
            try:
                amount = float(body.get("amount"))
            except (TypeError, ValueError):
                raise IntegrationError("Amount: a number") from None
            if not math.isfinite(amount) or amount == 0 or abs(amount) > MAX_AMOUNT:
                raise IntegrationError(f"Amount: a number between -{MAX_AMOUNT} and {MAX_AMOUNT}, not 0")
            reason = str(body.get("reason") or "Home Assistant").strip()[:80] or "Home Assistant"
            b = fq.rewards.book(kid["id"], acc, amount, "manual", reason, "ha_integration")
            if fq.ha:
                fq.ha.profile_changed(kid["id"])
            return {"ok": True, "booking": b}
        if act == "approve_chore":
            try:
                tid = int(body.get("task_id"))
            except (TypeError, ValueError):
                raise IntegrationError("Unknown chore") from None
            t = fq.chores.decide(tid, _bool(body.get("approve")))
            return {"ok": True, "status": t["status"]}
        if act == "approve_reward":
            try:
                rid = int(body.get("redemption_id"))
            except (TypeError, ValueError):
                raise IntegrationError("Unknown redemption") from None
            r = fq.shop.decide(rid, _bool(body.get("approve")), note="Home Assistant")
            return {"ok": True, "status": r["status"]}
        kid = _kid(fq, body.get("child"))
        if not fq.internet.managed(kid):
            raise IntegrationError("Internet time is not set up for this child")
        st = fq.internet.start(kid) if act == "internet_start" else fq.internet.stop(kid)
        return {"ok": True, "internet": st}
    except (ChoreError, InternetError, ShopError) as e:
        raise IntegrationError(str(e)) from None
