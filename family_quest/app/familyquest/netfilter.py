"""Mini web application firewall: from which networks Family Quest may be used.

Two lists of networks (CIDR, e.g. 192.168.35.0/24, a single address or a range 192.168.35.10-192.168.35.50),
set in the parent area:
* allowed_networks – the whole app (learning app, planer, parent area)
* parent_networks  – additionally for the parent area (/eltern, /api/parent/…)
Empty list = no restriction. The client address is the one loginlog.client_ip() sees (X-Forwarded-For behind
Home Assistant ingress). Refused requests are logged (login_log, kind "blocked") at most once a minute per address.
Saving a list that would lock out the parent who saves it is refused.
"""
from __future__ import annotations

import ipaddress
import time

PARENT_PATHS = ("/eltern", "/api/parent/")
_last_logged: dict[str, float] = {}


def _range(v: str):
    a, b = (ipaddress.ip_address(x.strip()) for x in v.split("-", 1))
    if a.version != b.version or a > b:
        raise ValueError(v)
    return a, b


def parse(values) -> list[str]:
    """Validated, normalised list of networks – raises ValueError with the bad entry.
    A range that is exactly one network is stored as that network (10.0.0.0-10.0.0.255 → 10.0.0.0/24)."""
    out = []
    for v in values or []:
        v = str(v).strip()
        if not v:
            continue
        try:
            if "-" in v:
                a, b = _range(v)
                nets = list(ipaddress.summarize_address_range(a, b))
                out.append(str(nets[0]) if len(nets) == 1 else f"{a}-{b}")
            else:
                out.append(str(ipaddress.ip_network(v, strict=False)))
        except ValueError:
            raise ValueError(f"Not a network: {v}") from None
    return out


def allowed(ip: str, networks: list[str]) -> bool:
    if not networks:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for n in networks:
        if "-" in n:
            try:
                a, b = _range(n)
            except ValueError:
                continue
            x = addr.ipv4_mapped if addr.version == 6 and addr.ipv4_mapped and a.version == 4 else addr
            if x.version == a.version and a <= x <= b:
                return True
            continue
        try:
            net = ipaddress.ip_network(n, strict=False)
        except ValueError:
            continue
        if addr.version == net.version and addr in net:
            return True
        if addr.version == 6 and addr.ipv4_mapped and addr.ipv4_mapped in net:
            return True
    return False


def is_parent_path(path: str) -> bool:
    return path == "/eltern" or path.startswith(PARENT_PATHS)


# guest networks (e.g. the guest Wi-Fi): only the guest page and playing a game with an invitation
GUEST_API = ("/api/community/guest/", "/api/community/quiz", "/api/community/bingo", "/api/community/poker",
             "/api/community/cards/", "/api/community/domino", "/api/community/paarjagd",
             "/api/community/werbinich", "/api/community/kartenlauf", "/api/community/stadtland",
             "/api/community/zeichnen", "/api/community/wuerfel", "/api/community/heimwaerts", "/api/community/jump", "/api/community/verboten",
             "/api/community/jass", "/api/community/werwolf", "/api/community/dorfmarkt")
GUEST_API_DENY = ("/api/community/quiz/start", "/api/community/quiz/next", "/api/community/quiz/end", "/api/community/quiz/abort",
                  "/api/community/bingo/start", "/api/community/bingo/begin", "/api/community/bingo/pause", "/api/community/bingo/end",
                  "/api/community/bingo/rules", "/api/community/quizzes", "/api/community/poker/start",
                  "/api/community/poker/begin", "/api/community/poker/pause", "/api/community/poker/end",
                  "/api/community/poker/give", "/api/community/poker/rules")
GUEST_API_DENY_PARTS = ("/start", "/begin", "/end", "/rules")


def guest_only(fq, ip: str) -> bool:
    """A device in a guest network that is not also listed as a family network."""
    guests = fq.db.get_setting("guest_networks") or []
    if not guests or not allowed(ip, guests):
        return False
    family = fq.db.get_setting("allowed_networks") or []
    return not (family and allowed(ip, family))


def is_guest_path(path: str) -> bool:
    if path == "/gast" or path.startswith("/i18n/"):
        return True
    if path.startswith("/api/"):
        if path.startswith(("/api/community/cards/", "/api/community/domino/", "/api/community/paarjagd/",
                             "/api/community/werbinich/", "/api/community/kartenlauf/", "/api/community/stadtland/",
                             "/api/community/zeichnen/", "/api/community/wuerfel/", "/api/community/heimwaerts/", "/api/community/jump/", "/api/community/verboten/",
                             "/api/community/jass/", "/api/community/werwolf/", "/api/community/dorfmarkt/")) \
                and path.endswith(GUEST_API_DENY_PARTS + ("/skip", "/next", "/override", "/mix", "/pause")):
            return False
        return path.startswith(GUEST_API) and not path.startswith(GUEST_API_DENY)
    last = path.rsplit("/", 1)[-1]
    return "." in last and not path.startswith(("/eltern", "/media", "/family_planer_files"))   # scripts, styles, icons


def check(fq, ip: str, path: str) -> str | None:
    """None if the request may pass, else the reason ("app", "parent" or "guest")."""
    if guest_only(fq, ip):
        return None if is_guest_path(path) else "guest"
    nets = fq.db.get_setting("allowed_networks") or []
    if not allowed(ip, nets):
        return "app"
    if is_parent_path(path) and not allowed(ip, fq.db.get_setting("parent_networks") or []):
        return "parent"
    return None


def log_blocked(fq, ip: str, device: tuple[str | None, str | None]) -> None:
    now = time.time()
    if now - _last_logged.get(ip, 0) < 60:
        return
    _last_logged[ip] = now
    fq.db.x("INSERT INTO login_log(kind, profile_id, ok, ip, device, mac) VALUES('blocked', NULL, 0, ?, ?, ?)", ip or None, *device)
