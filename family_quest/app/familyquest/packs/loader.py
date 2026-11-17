"""Reading packs from YAML text, folders and ZIP files; syncing them into the database."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import ValidationError

from .schema import Bundle, Pack

log = logging.getLogger("familyquest.packs")
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp3", ".ogg", ".wav", ".m4a"}
MAX_ZIP_BYTES = 50 * 1024 * 1024


class PackError(ValueError):
    pass


def _fmt_validation(e: ValidationError) -> str:
    parts = []
    for err in e.errors()[:6]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return "; ".join(parts)


def parse_doc(doc: dict) -> Pack | Bundle:
    if not isinstance(doc, dict):
        raise PackError("a pack must be a YAML mapping")
    try:
        if "stufenpaket" in doc:
            return Bundle.model_validate(doc)
        return Pack.model_validate(doc)
    except ValidationError as e:
        raise PackError(_fmt_validation(e)) from None


def parse_yaml(text: str) -> list[Pack | Bundle]:
    try:
        docs = [d for d in yaml.safe_load_all(text) if d]
    except yaml.YAMLError as e:
        raise PackError(f"YAML: {e}") from None
    if not docs:
        raise PackError("empty file")
    out = []
    for d in docs:
        if isinstance(d, list):          # a file that is a list of packs
            out.extend(parse_doc(x) for x in d)
        else:
            out.append(parse_doc(d))
    return out


def parse_json(text: str) -> list[Pack | Bundle]:
    """A pack, a level pack, a list of them, or {"pakete": [...]} as JSON."""
    from ..jsonish import loads             # also JSON as AIs write it (code fence, comments, trailing commas)
    try:
        data = loads(text)
    except ValueError as e:
        raise PackError(f"JSON: {e}") from None
    from ..ai_format import strip_meta
    data = strip_meta(data)                 # the explanations of a template / export ("_…" keys)
    if isinstance(data, dict) and isinstance(data.get("pakete"), list) and "stufenpaket" not in data and "id" not in data:
        data = data["pakete"]
    docs = data if isinstance(data, list) else [data]
    if not docs:
        raise PackError("empty file")
    return [parse_doc(d) for d in docs]


def parse_text(name: str, text: str) -> list[Pack | Bundle]:
    low = name.lower()
    if low.endswith(".json") or (low.endswith((".txt", ".md")) and text.lstrip().startswith(("{", "[", "```"))):
        return parse_json(text)
    return parse_yaml(text)


def parse_zip(data: bytes) -> tuple[list[Pack | Bundle], dict[str, bytes]]:
    """Packs from a ZIP plus its media files (path inside the zip → bytes)."""
    if len(data) > MAX_ZIP_BYTES:
        raise PackError("ZIP file too large")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PackError("not a valid ZIP file") from None
    packs: list[Pack | Bundle] = []
    media: dict[str, bytes] = {}
    total = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if name.startswith("/") or ".." in Path(name).parts or name.startswith("__MACOSX"):
            continue
        total += info.file_size
        if total > MAX_ZIP_BYTES * 4:
            raise PackError("ZIP content too large")
        ext = Path(name).suffix.lower()
        if ext in (".yaml", ".yml", ".json"):
            packs.extend(parse_text(name, zf.read(info).decode("utf-8-sig")))
        elif ext in MEDIA_EXT:
            media[Path(name).name] = zf.read(info)
    if not packs:
        raise PackError("no pack (.yaml or .json) found in the ZIP")
    return packs, media


def pack_dict(p: Pack | Bundle) -> dict:
    return p.model_dump(mode="json", exclude_none=True)


def content_hash(p: Pack | Bundle) -> str:
    return hashlib.sha1(json.dumps(pack_dict(p), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def iter_dir(folder: Path) -> Iterable[tuple[Pack | Bundle, dict[str, Path | bytes]]]:
    """Packs below a folder: *.yaml files, sub-folders with YAML + media, *.zip files."""
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        try:
            if ext in (".yaml", ".yml", ".json"):
                media = {m.name: m for m in path.parent.iterdir() if m.suffix.lower() in MEDIA_EXT}
                for p in parse_text(path.name, path.read_text(encoding="utf-8-sig")):
                    yield p, media
            elif ext == ".zip":
                packs, media_b = parse_zip(path.read_bytes())
                for p in packs:
                    yield p, dict(media_b)
        except (PackError, OSError, UnicodeDecodeError) as e:
            log.warning("skipping %s: %s", path, e)


def store_media(media_dir: Path, pack_id: str, media: dict[str, Path | bytes], used: set[str] | None = None) -> None:
    if not media:
        return
    target = media_dir / pack_id
    target.mkdir(parents=True, exist_ok=True)
    for name, src in media.items():
        if used is not None and name not in used:
            continue
        safe = Path(name).name
        if isinstance(src, Path):
            shutil.copyfile(src, target / safe)
        else:
            (target / safe).write_bytes(src)


def media_refs(p: Pack | Bundle) -> set[str]:
    out: set[str] = set()
    if isinstance(p, Pack):
        for u in p.einheiten:
            for c in u.karten:
                for k in ("bild", "audio"):
                    v = c.get(k)
                    if isinstance(v, str) and "." in v and ":" not in v:
                        out.add(Path(v).name)
    return out
