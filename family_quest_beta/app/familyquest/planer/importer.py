"""Etappe F: take over an existing Family Planer (Home Assistant integration) into Family Quest.

The integration keeps everything in /config/.storage/family_planer.<entry id> (Home Assistant Store format:
{"version", "key", "data": {...}}) and the persons' photos in /config/family_planer/. The app sees the Home Assistant
configuration under /homeassistant (map homeassistant_config; read-only except custom_components/familyquest). A parent can also upload the file.

Import = the planner data replaces the built-in planner (the previous state is kept in the kv document
fq.planer_before_import), photos are copied, then the bridge links the persons to the Family Quest profiles
by name (unknown persons become profiles) and adds up the points.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import rewards as prew
from .const import FILES_DIR
from .hacompat import StoreBackend

log = logging.getLogger("familyquest.planer.import")
HA_CONFIG = Path(os.environ.get("FQ_HA_CONFIG", "/homeassistant"))   # env: for development
BEFORE_KEY = "fq.planer_before_import"
NAME_RE = re.compile(r"^family_planer\.[A-Za-z0-9_]+$")


class ImportError_(ValueError):
    pass


def unwrap(doc: Any) -> dict:
    """Planner data from a Home Assistant store file (or the bare data)."""
    if isinstance(doc, dict) and isinstance(doc.get("data"), dict) and str(doc.get("key", "")).startswith("family_planer"):
        doc = doc["data"]
    if not isinstance(doc, dict) or not isinstance(doc.get("persons"), dict) or not isinstance(doc.get("chores", {}), dict):
        raise ImportError_("This is not a Family Planer file")
    return doc


def summary(data: dict) -> dict:
    ledger = data.get("ledger") or []
    return {
        "persons": [{"id": k, "name": v.get("name", k), "role": v.get("role", "kid"),
                     "points": prew.balance(ledger, k)} for k, v in (data.get("persons") or {}).items()],
        "chores": len(data.get("chores") or {}),
        "lists": len(data.get("lists") or {}),
        "rewards": len(data.get("rewards") or {}),
        "todos": len(data.get("todos") or {}),
    }


def sources(base: Path | None = None) -> list[dict]:
    """Family Planer store files in the Home Assistant configuration."""
    base = base or HA_CONFIG
    out = []
    storage = base / ".storage"
    if not storage.is_dir():
        return out
    for f in sorted(storage.iterdir()):
        if not NAME_RE.match(f.name) or not f.is_file():
            continue
        try:
            data = unwrap(json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
        out.append({"id": f.name, "modified": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(),
                    **summary(data)})
    return out


def read_source(name: str, base: Path | None = None) -> dict:
    base = base or HA_CONFIG
    if not NAME_RE.match(name):
        raise ImportError_("Unknown Family Planer file")
    f = base / ".storage" / name
    if not f.is_file():
        raise ImportError_("Unknown Family Planer file")
    return unwrap(json.loads(f.read_text(encoding="utf-8")))


async def run(fq, data: dict, photos: Path | None = None) -> dict:
    """Replace the built-in planner with `data`, then link persons and points."""
    host = fq.planer_host
    if host is None:
        raise ImportError_("Planer is not running")
    kv = StoreBackend(fq.db)
    planner = host.planner
    await host.save_now()
    key = planner._store.key
    kv.save(BEFORE_KEY, kv.load(key))
    kv.save(key, data)
    # photos of the persons
    if photos and photos.is_dir():
        target = Path(host.hass.config.path(FILES_DIR))
        for f in photos.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                out = target / f.relative_to(photos)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out)
    # new persons, new ledger: the bridge starts over (links by name, both balances added up)
    bridge = getattr(host, "bridge", None)
    if bridge:
        st = bridge.state()
        st["links"], st["seen"] = {}, {}
        st.pop("account", None)
        bridge.kv.save("fq.planer_bridge", st)
    await host.reload()
    if bridge:
        await bridge.sync()
    log.info("Family Planer imported: %s", summary(data))
    return summary(host.planner.data)

