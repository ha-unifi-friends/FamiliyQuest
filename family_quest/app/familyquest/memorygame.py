"""Pairs game (game corner): own photo sets and the family crest.

The game itself runs in the browser (web/minigames.js). Here only what parents set up is kept, in the setting
`memory`: {"sets": [{"id", "name", "photos": [file names]}], "crest": {...}}. The photos lie in
<media>/_memory/ and are served as media/_memory/<name>. Pictures taken from Home Assistant Media are not copied:
they are kept as a reference «ha:<path in /media>» and served as hamedia/<path> (only referenced ones) – so they are
not in the Family Quest backup (Home Assistant's own backup has them).
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
from pathlib import Path

FOLDER = "_memory"
PATTERNS = ("plain", "split", "quarter", "band", "chevron")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_CREST = {"name": "", "icon": "🏠", "colors": ["#5b5bd6", "#fcc419"], "pattern": "split", "motto": ""}
MAX_SETS, MAX_PHOTOS = 20, 40
PICTURE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
HA_MEDIA_MAX = 15 * 1024 * 1024        # pictures from Home Assistant Media are often original photos
HA = "ha:"                              # a photo that stays in Home Assistant Media (reference instead of a copy)


class MemoryError_(ValueError):
    pass


def _never(_name: str) -> bool:
    return False


def clean_crest(c, existing_files: set[str] | None = None, ha_ok=_never) -> dict | None:
    if not c:
        return None
    if not isinstance(c, dict):
        raise MemoryError_("Invalid family crest")
    colors = [x for x in (c.get("colors") or []) if isinstance(x, str) and COLOR.match(x)][:2]
    while len(colors) < 2:
        colors.append(DEFAULT_CREST["colors"][len(colors)])
    return {"name": str(c.get("name") or "")[:40], "icon": str(c.get("icon") or "🏠")[:8], "colors": colors,
            "pattern": c.get("pattern") if c.get("pattern") in PATTERNS else "split", "motto": str(c.get("motto") or "")[:60],
            # own picture as crest (uploaded or from Home Assistant Media) – must lie in the photo folder
            "image": c.get("image") if isinstance(c.get("image"), str) and existing_files is not None
            and (c.get("image") in existing_files or ha_ok(c.get("image"))) else None}


def clean(data: dict, existing_files: set[str], ha_ok=_never) -> dict:
    """Check what the parent area sends; photos must have been uploaded before."""
    sets = []
    for s in (data.get("sets") or [])[:MAX_SETS]:
        name = str(s.get("name") or "").strip()[:60]
        if not name:
            raise MemoryError_("Every photo set needs a name")
        photos = [p for p in dict.fromkeys(s.get("photos") or []) if isinstance(p, str) and (p in existing_files or ha_ok(p))][:MAX_PHOTOS]
        sid = str(s.get("id") or "")
        sets.append({"id": sid if re.fullmatch(r"[a-z0-9]{6,16}", sid) else secrets.token_hex(4), "name": name, "photos": photos})
    return {"sets": sets, "crest": clean_crest(data.get("crest"), existing_files, ha_ok)}


def photo_url(name: str) -> str:
    """Address of a photo for the browser: the photo folder, or Home Assistant Media for a reference."""
    from urllib.parse import quote
    return "hamedia/" + quote(name[len(HA):]) if name.startswith(HA) else f"media/{FOLDER}/{name}"


def ha_ref_ok(fq, name: str) -> bool:
    """A reference «ha:<path>» to an existing picture in Home Assistant Media."""
    if not isinstance(name, str) or not name.startswith(HA):
        return False
    try:
        p = ha_media_path(fq.settings.ha_media_dir, name[len(HA):])
    except MemoryError_:
        return False
    return p.is_file() and p.suffix.lower() in PICTURE_EXT


def referenced(fq, name: str) -> bool:
    """Is this reference used by a photo set or the crest (only those are served to the players)?"""
    d = get(fq)
    return any(name in s.get("photos", []) for s in d.get("sets") or []) or (d.get("crest") or {}).get("image") == name


def get(fq) -> dict:
    return fq.db.get_setting("memory") or {"sets": [], "crest": None}


def save(fq, data: dict) -> dict:
    """Photo sets and / or the crest – what is not sent stays as it is (the crest has its own section in the settings)."""
    data = {**get(fq), **{k: v for k, v in data.items() if k in ("sets", "crest")}}
    folder = fq.settings.media_dir / FOLDER
    files = {f.name for f in folder.iterdir()} if folder.is_dir() else set()
    out = clean(data, files, lambda n: ha_ref_ok(fq, n))
    fq.db.set_setting("memory", out)
    used = {p for s in out["sets"] for p in s["photos"]} | ({out["crest"]["image"]} if out["crest"] and out["crest"].get("image") else set())
    old = time.time() - 3600
    for name in files - used:                 # photos no set uses any more – not the fresh ones of an upload still running
        f = folder / name
        try:
            if f.stat().st_mtime < old:
                f.unlink()
        except OSError:
            pass
    return out


def public(fq) -> dict:
    """For the players: sets with at least 3 photos (fewer give no game), photo addresses and the crest."""
    d = get(fq)
    return {"sets": [{"id": s["id"], "name": s["name"], "photos": [photo_url(p) for p in s["photos"]]}
                     for s in d["sets"] if len(s["photos"]) >= 3],
            "crest": d.get("crest")}


# ---------------------------------------------------------------- pictures from Home Assistant Media (/media, read-only)
def picture_kind(raw: bytes) -> str | None:
    """File extension from the first bytes – only real pictures."""
    if raw[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    if raw[:4] == b"GIF8":
        return ".gif"
    return None


def ha_media_path(root: Path, rel: str) -> Path:
    """A path inside Home Assistant's media folder – never outside of it, no hidden names."""
    rel = str(rel or "").strip("/")
    if any(part.startswith(".") for part in rel.split("/") if part):
        raise MemoryError_("Unknown folder")
    base = root.resolve()
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        raise MemoryError_("Unknown folder")
    return p


def ha_media_list(root: Path, rel: str = "") -> dict:
    """Folders and pictures in a folder of Home Assistant Media."""
    if not root.is_dir():
        return {"available": False, "path": "", "folders": [], "images": []}
    p = ha_media_path(root, rel)
    if not p.is_dir():
        raise MemoryError_("Unknown folder")
    folders, images = [], []
    for e in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        if e.name.startswith("."):
            continue
        if e.is_dir():
            folders.append(e.name)
        elif e.is_file() and e.suffix.lower() in PICTURE_EXT:
            images.append({"name": e.name, "size": e.stat().st_size})
    rel = str(p.relative_to(root.resolve())).replace("\\", "/")
    return {"available": True, "path": "" if rel == "." else rel, "folders": folders[:500], "images": images[:500]}


def ha_media_copy(fq, root: Path, paths: list) -> list[str]:
    """Take pictures from Home Assistant Media: checked, but NOT copied – a reference «ha:<path>» each
    (the name a set or the crest keeps, like the file name after an upload)."""
    if not isinstance(paths, list) or not paths:
        raise MemoryError_("No pictures chosen")
    base = root.resolve()
    names = []
    for rel in paths[:MAX_PHOTOS]:
        p = ha_media_path(root, str(rel))
        if not p.is_file() or p.suffix.lower() not in PICTURE_EXT:
            raise MemoryError_("Unknown picture")
        if p.stat().st_size > HA_MEDIA_MAX:
            raise MemoryError_(f"The picture «{p.name}» is too large (max. 15 MB)")
        with p.open("rb") as f:
            head = f.read(16)
        if not picture_kind(head):
            raise MemoryError_(f"«{p.name}» is not a picture (JPEG, PNG, WebP, GIF)")
        names.append(HA + p.relative_to(base).as_posix())
    return names


def relink_ha_copies(fq) -> int:
    """Earlier versions (until 0.4.0-beta.19) COPIED pictures from Home Assistant Media into the photo folder – they made
    the backup big. A copy is byte for byte the original: find it in Home Assistant Media (same size, same SHA-1),
    use the reference «ha:<path>» instead and delete the copy. Returns how many photos were linked."""
    root = fq.settings.ha_media_dir
    folder = fq.settings.media_dir / FOLDER
    if not root or not Path(root).is_dir() or not folder.is_dir():
        return 0
    d = get(fq)
    used = {p for s in d.get("sets") or [] for p in s.get("photos", [])}
    crest = (d.get("crest") or {}).get("image")
    if crest:
        used.add(crest)
    copies: dict[int, list[Path]] = {}                       # size -> local photos (no references)
    for name in used:
        if name.startswith(HA):
            continue
        f = folder / name
        if f.is_file():
            copies.setdefault(f.stat().st_size, []).append(f)
    if not copies:
        return 0
    def sha(p: Path) -> str:
        h = hashlib.sha1()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    base = Path(root).resolve()
    wanted = {sha(f): f.name for fs in copies.values() for f in fs}
    found: dict[str, str] = {}                               # local name -> reference
    for p in base.rglob("*"):
        if len(found) == len(wanted):
            break
        try:
            if any(part.startswith(".") for part in p.relative_to(base).parts) or not p.is_file() \
                    or p.suffix.lower() not in PICTURE_EXT or p.stat().st_size not in copies:
                continue
            h = sha(p)
        except OSError:
            continue
        if h in wanted and wanted[h] not in found:
            found[wanted[h]] = HA + p.relative_to(base).as_posix()
    if not found:
        return 0
    d = get(fq)                                              # read again: a save may have happened meanwhile
    for st in d.get("sets") or []:
        st["photos"] = [found.get(n, n) for n in st.get("photos", [])]
    if d.get("crest") and d["crest"].get("image") in found:
        d["crest"]["image"] = found[d["crest"]["image"]]
    fq.db.set_setting("memory", d)
    still = {p for s in d.get("sets") or [] for p in s.get("photos", [])} | ({d["crest"]["image"]} if d.get("crest") and d["crest"].get("image") else set())
    for name in found:
        if name not in still:
            try:
                (folder / name).unlink()
            except OSError:
                pass
    return len(found)
