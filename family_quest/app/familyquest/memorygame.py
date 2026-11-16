"""Pairs game (game corner): own photo sets and the family crest.

The game itself runs in the browser (web/minigames.js). Here only what parents set up is kept, in the setting
`memory`: {"sets": [{"id", "name", "photos": [file names]}], "crest": {...}}. The photos lie in
<media>/_memory/ and are served as media/_memory/<name>.
"""
from __future__ import annotations

import re
import secrets

FOLDER = "_memory"
PATTERNS = ("plain", "split", "quarter", "band", "chevron")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_CREST = {"name": "", "icon": "🏠", "colors": ["#5b5bd6", "#fcc419"], "pattern": "split", "motto": ""}
MAX_SETS, MAX_PHOTOS = 20, 40


class MemoryError_(ValueError):
    pass


def clean_crest(c) -> dict | None:
    if not c:
        return None
    if not isinstance(c, dict):
        raise MemoryError_("Invalid family crest")
    colors = [x for x in (c.get("colors") or []) if isinstance(x, str) and COLOR.match(x)][:2]
    while len(colors) < 2:
        colors.append(DEFAULT_CREST["colors"][len(colors)])
    return {"name": str(c.get("name") or "")[:40], "icon": str(c.get("icon") or "🏠")[:8], "colors": colors,
            "pattern": c.get("pattern") if c.get("pattern") in PATTERNS else "split", "motto": str(c.get("motto") or "")[:60]}


def clean(data: dict, existing_files: set[str]) -> dict:
    """Check what the parent area sends; photos must have been uploaded before."""
    sets = []
    for s in (data.get("sets") or [])[:MAX_SETS]:
        name = str(s.get("name") or "").strip()[:60]
        if not name:
            raise MemoryError_("Every photo set needs a name")
        photos = [p for p in dict.fromkeys(s.get("photos") or []) if isinstance(p, str) and p in existing_files][:MAX_PHOTOS]
        sid = str(s.get("id") or "")
        sets.append({"id": sid if re.fullmatch(r"[a-z0-9]{6,16}", sid) else secrets.token_hex(4), "name": name, "photos": photos})
    return {"sets": sets, "crest": clean_crest(data.get("crest"))}


def get(fq) -> dict:
    return fq.db.get_setting("memory") or {"sets": [], "crest": None}


def save(fq, data: dict) -> dict:
    folder = fq.settings.media_dir / FOLDER
    files = {f.name for f in folder.iterdir()} if folder.is_dir() else set()
    out = clean(data, files)
    fq.db.set_setting("memory", out)
    used = {p for s in out["sets"] for p in s["photos"]}
    for name in files - used:                 # photos no set uses any more
        (folder / name).unlink(missing_ok=True)
    return out


def public(fq) -> dict:
    """For the players: sets with at least 3 photos (fewer give no game), photo addresses and the crest."""
    d = get(fq)
    return {"sets": [{"id": s["id"], "name": s["name"], "photos": [f"media/{FOLDER}/{p}" for p in s["photos"]]}
                     for s in d["sets"] if len(s["photos"]) >= 3],
            "crest": d.get("crest")}
