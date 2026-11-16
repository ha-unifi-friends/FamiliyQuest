"""Season designs of the app: the header shows the animated scene of the Family Planer for the active design.

Built in and scheduled every year: the four seasons, Halloween and Christmas (events win over seasons). Parents can
switch them off, move their dates and add own designs (name, icon, accent colour, scene, from – to; own designs win).
Setting «themes»: {"builtin": {id: {"on": bool, "from": "MM-DD", "to": "MM-DD"}}, "own": [design, …]}.
"""
from __future__ import annotations

import re
import secrets
from datetime import date

from .i18n import _t

# id, name, icon, scene, from, to, kind – the scene names are the Family Planer visuals (+ halloween)
BUILTIN = [
    {"id": "spring", "name": _t("Spring"), "icon": "🌷", "vis": "fruehling", "from": "03-21", "to": "06-20", "kind": "season"},
    {"id": "summer", "name": _t("Summer"), "icon": "☀️", "vis": "sommer", "from": "06-21", "to": "09-22", "kind": "season"},
    {"id": "autumn", "name": _t("Autumn"), "icon": "🍂", "vis": "herbst", "from": "09-23", "to": "12-20", "kind": "season"},
    {"id": "winter", "name": _t("Winter"), "icon": "❄️", "vis": "winter", "from": "12-21", "to": "03-20", "kind": "season"},
    {"id": "halloween", "name": _t("Halloween"), "icon": "🎃", "vis": "halloween", "from": "10-20", "to": "11-01", "kind": "event"},
    {"id": "christmas", "name": _t("Christmas"), "icon": "🎄", "vis": "weihnachten", "from": "12-01", "to": "12-26", "kind": "event"},
]
VISUALS = ("alltag", "fruehling", "sommer", "herbst", "winter", "halloween", "weihnachten", "silvester", "fasnacht", "ostern",
           "liebe", "pfingsten", "august", "schule", "geburtstag", "sport")
JZ = {"spring": "fruehling", "summer": "sommer", "autumn": "herbst", "winter": "winter"}
_MD = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


class ThemeError(ValueError):
    pass


def _md(v, default: str | None = None) -> str | None:
    v = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})[.-](\d{1,2})\.?", v)          # also «24.12.» or «12-24»
    if m and "." in v:
        v = f"{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    elif m:
        v = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return v if _MD.match(v) else default


def clean(t) -> dict:
    t = t if isinstance(t, dict) else {}
    builtin = {}
    for b in BUILTIN:
        cur = (t.get("builtin") or {}).get(b["id"]) or {}
        builtin[b["id"]] = {"on": cur.get("on", True) is not False, "from": _md(cur.get("from"), b["from"]), "to": _md(cur.get("to"), b["to"])}
    own = []
    for o in (t.get("own") or [])[:30]:
        if not isinstance(o, dict):
            continue
        name = str(o.get("name") or "").strip()[:40]
        f, to = _md(o.get("from")), _md(o.get("to"))
        if not name or not f or not to:
            raise ThemeError("A design needs a name and a date from – to")
        acc = str(o.get("accent") or "")
        own.append({"id": str(o.get("id") or secrets.token_hex(4))[:16], "name": name, "icon": str(o.get("icon") or "🎨")[:8],
                    "vis": o.get("vis") if o.get("vis") in VISUALS else "alltag", "accent": acc if re.fullmatch(r"#[0-9a-fA-F]{6}", acc) else "",
                    "from": f, "to": to, "on": o.get("on", True) is not False})
    return {"builtin": builtin, "own": own}


def _inside(md: str, f: str, t: str) -> bool:
    return f <= md <= t if f <= t else (md >= f or md <= t)      # over new year, e.g. 12-21 – 03-20


def designs(cfg) -> list[dict]:
    c = clean(cfg)
    return ([{**b, **c["builtin"][b["id"]], "builtin": True} for b in BUILTIN] + [{**o, "kind": "own", "builtin": False} for o in c["own"]])


def active(cfg, today: date | None = None) -> dict | None:
    """The design of today: own designs before events (Halloween, Christmas) before seasons."""
    md = (today or date.today()).strftime("%m-%d")
    all_ = designs(cfg)
    jz = next((JZ[b["id"]] for b in BUILTIN if b["kind"] == "season" and _inside(md, b["from"], b["to"])), "sommer")
    for kind in ("own", "event", "season"):
        hit = next((d for d in all_ if d["kind"] == kind and d["on"] and _inside(md, d["from"], d["to"])), None)
        if hit:
            return {"id": hit["id"], "name": hit["name"], "icon": hit["icon"], "vis": hit["vis"], "jz": jz,
                    "accent": hit.get("accent", ""), "builtin": hit["builtin"]}
    return None
