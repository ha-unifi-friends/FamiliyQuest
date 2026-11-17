"""Import of YAML packs, ZIP packs/bundles (with media) and the same from a URL."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from ..packs.loader import MAX_ZIP_BYTES, PackError, pack_dict, parse_doc, parse_text, parse_zip
from .common import draft_from_dict


def import_bytes(fq, name: str, raw: bytes) -> list[dict]:
    low = name.lower()
    if low.endswith(".zip") or raw[:2] == b"PK":
        packs, media = parse_zip(raw)
    elif low.endswith((".yaml", ".yml", ".json", ".txt", ".md")) or "." not in low:
        try:
            packs, media = parse_text(low, raw.decode("utf-8-sig")), {}
        except UnicodeDecodeError:
            raise PackError("the file is not UTF-8 text") from None
    else:
        raise PackError("unsupported file type – use YAML, JSON, ZIP, CSV, XLSX, PDF or a photo")
    return [draft_from_dict(fq, pack_dict(p), "upload", media) for p in packs]


def import_data(fq, data) -> list[dict]:
    """Packs given as JSON data (API body): one pack, a level pack or a list."""
    if isinstance(data, dict) and isinstance(data.get("pakete"), list) and "id" not in data and "stufenpaket" not in data:
        data = data["pakete"]
    docs = data if isinstance(data, list) else [data]
    if not docs:
        raise PackError("no pack in the data")
    return [draft_from_dict(fq, pack_dict(parse_doc(d)), "upload") for d in docs]


def _public_host(host: str) -> bool:
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def import_url(fq, url: str) -> list[dict]:
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise PackError("only http(s) links")
    if not _public_host(u.hostname):
        raise PackError("only public addresses are allowed")
    # GitHub page links → raw file
    if u.hostname == "github.com" and "/blob/" in u.path:
        url = url.replace("github.com", "raw.githubusercontent.com", 1).replace("/blob/", "/", 1)
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.content
    except httpx.HTTPError as e:
        raise PackError(f"download failed: {e}") from None
    if len(data) > MAX_ZIP_BYTES:
        raise PackError("file too large")
    name = u.path.rsplit("/", 1)[-1] or "download.yaml"
    return import_bytes(fq, name, data)
