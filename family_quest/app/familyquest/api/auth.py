"""Profiles, PINs and tokens.

Tokens are signed (itsdangerous) and sent as header X-FQ-Token (child/learner) or
X-FQ-Parent (parent actions). Headers instead of cookies work the same through
Home Assistant ingress and on the direct port.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

KID_MAX_AGE = 60 * 60 * 24 * 30
PARENT_MAX_AGE = 60 * 30                 # one parent token – /api/parent/refresh hands out the next one …
PARENT_SESSION_MAX = 60 * 60 * 12        # … but a parent session never lasts longer than this without the PIN again
PARENT_SESSION_MAX_HA = 60 * 60 * 24 * 30  # … through Home Assistant ingress (Home Assistant's own login stands behind it)
PARENT_APP_TTL = 60 * 60 * 12            # the app login (learning app, planner admin) of a parent profile
INGRESS_IP = "172.30.32.2"
PIN_BACKOFF_AFTER = 5                    # wrong PINs in a row for one profile – then a growing wait (Throttle.guard)
PIN_BACKOFF_MAX = 60 * 60

log = logging.getLogger("familyquest.auth")


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pin.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


# scrypt takes ~16 MB and real CPU per call: never more than two at a time (a burst of guesses waits instead)
_SCRYPT = threading.BoundedSemaphore(2)


def check_pin(pin: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt, h = stored.split("$")
        with _SCRYPT:
            calc = hashlib.scrypt(str(pin).encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


def valid_pin(pin: str, min_len: int = 4, max_len: int = 8) -> bool:
    return isinstance(pin, str) and pin.isascii() and pin.isdigit() and min_len <= len(pin) <= max_len


class Throttle:
    """At most 5 PIN attempts per key (profile and device) per minute.

    Every attempt is counted *before* the PIN is checked – atomically – so parallel requests cannot slip past the
    limit while the slow hash runs; a right PIN clears the count again."""

    def __init__(self):
        self.fails: dict[str, list[float]] = defaultdict(list)
        self.streak: dict[str, tuple[int, float]] = {}       # per profile: (wrong PINs in a row, locked until)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            self.fails[key] = [t for t in self.fails[key] if now - t < 60]
            if len(self.fails[key]) >= 5:
                raise HTTPException(429, "Too many attempts – wait a minute")
            self.fails[key].append(now)                     # counted now; ok() forgives it

    def fail(self, key: str) -> None:
        """Already counted in check() – kept so the callers read clearly."""

    def ok(self, key: str) -> None:
        with self.lock:
            self.fails.pop(key, None)

    # ---- per profile, from every device: wrong PINs in a row (a child changing addresses or devices gets no more
    # tries) – after PIN_BACKOFF_AFTER a wait of 1 minute, doubling with every further wrong PIN (at most an hour)
    def guard(self, target: str) -> None:
        with self.lock:
            n, until = self.streak.get(target, (0, 0.0))
        if until > time.time():
            raise HTTPException(429, "Too many wrong PINs – wait a while")

    def bad(self, target: str) -> None:
        with self.lock:
            n = self.streak.get(target, (0, 0.0))[0] + 1
            until = 0.0
            if n >= PIN_BACKOFF_AFTER:
                until = time.time() + min(PIN_BACKOFF_MAX, 60 * 2 ** (n - PIN_BACKOFF_AFTER))
            self.streak[target] = (n, until)
        if until:
            log.warning("%d wrong PINs in a row for %s – the next try in %d s", n, target, int(until - time.time()))

    def good(self, target: str) -> None:
        with self.lock:
            self.streak.pop(target, None)


class Tokens:
    """Signed logins. A login of a profile carries a fingerprint of the profile (when it was made, its PIN, whether it
    is archived, its session counter): changing the PIN, archiving or deleting the profile, or «log out everywhere»
    (the counter) ends all its logins – and a new profile that gets the id of a deleted one cannot use the old logins.
    A parent login also carries when the session began (`i`, kept by /refresh): it ends PARENT_SESSION_MAX later
    (PARENT_SESSION_MAX_HA when it began through Home Assistant ingress, `h`)."""

    def __init__(self, secret: bytes):
        self.s = URLSafeTimedSerializer(secret, salt="familyquest")
        self.fingerprint: Callable[[int], str | None] | None = None      # set by FamilyQuest (services.py)

    def make(self, pid: int, kind: str, ttl: int | None = None, since: float | None = None, ha: bool = False) -> str:
        d = {"p": pid, "k": kind}
        if self.fingerprint and kind in ("kid", "parent"):
            d["f"] = self.fingerprint(pid)
        if ttl:
            d["x"] = int(time.time()) + ttl                              # shorter than the usual max age
        if kind == "parent":
            d["i"] = int(since if since is not None else time.time())
            if ha:
                d["h"] = 1
        return self.s.dumps(d)

    def _load(self, token: str | None, kind: str, max_age: int, ha: bool = True) -> dict | None:
        if not token:
            return None
        try:
            d, ts = self.s.loads(token, max_age=max_age, return_timestamp=True)
        except (BadSignature, SignatureExpired):
            return None
        if not isinstance(d, dict) or d.get("k") != kind or ("x" in d and time.time() > d["x"]):
            return None
        if kind == "parent":
            d.setdefault("i", ts.timestamp())                            # a token from before: its own time
            if time.time() - float(d["i"]) > (PARENT_SESSION_MAX_HA if d.get("h") and ha else PARENT_SESSION_MAX):
                return None
        pid = int(d["p"])
        if self.fingerprint and kind in ("kid", "parent") and d.get("f") != self.fingerprint(pid):
            return None
        return d

    def read(self, token: str | None, kind: str, max_age: int, ha: bool = True) -> int | None:
        """The profile id of a valid token. ha=False: the request did not come through Home Assistant ingress – a
        parent session begun there gets only PARENT_SESSION_MAX here."""
        d = self._load(token, kind, max_age, ha)
        return int(d["p"]) if d else None

    def session(self, token: str | None, ha: bool = True) -> tuple[float, bool] | None:
        """(when the parent session began, through Home Assistant) of a valid parent token."""
        d = self._load(token, "parent", PARENT_MAX_AGE, ha)
        return (float(d["i"]), bool(d.get("h"))) if d else None


def kid_token(fq, p: dict) -> str:
    """The app login of a profile – a parent profile's is short (it is also a planner admin: api/planer.py)."""
    return fq.tokens.make(p["id"], "kid", ttl=PARENT_APP_TTL if p.get("role") == "parent" else None)


def parent_token(fq, pid: int, request: Request, keep: bool = False) -> str:
    """A parent token. keep: the next token of the running session (refresh, an own new PIN) – the session keeps
    its start, so refreshing never makes it longer than PARENT_SESSION_MAX."""
    via_ha = via_ingress(request)
    if keep and (cur := fq.tokens.session(request.headers.get("x-fq-parent"), via_ha)):
        return fq.tokens.make(pid, "parent", since=cur[0], ha=cur[1] and via_ha)
    return fq.tokens.make(pid, "parent", ha=via_ha)


def pin_target(p: dict | None) -> str:
    """The key of the per-profile PIN backoff (Throttle.guard): the parent PIN is tried against every parent profile,
    so all parents share one."""
    return "pin:parents" if not p or p.get("role") == "parent" else f"pin:{p['id']}"


def end_sessions(fq, pid: int) -> None:
    """«Log out everywhere»: every login (app and parent area) of this profile ends."""
    fq.db.x("UPDATE profile SET sessions=sessions+1 WHERE id=?", pid)


def parent_network_ok(fq, request: Request) -> bool:
    """The request comes from where the parent area may be opened (parent networks, «only in Home Assistant»)."""
    from .. import loginlog, netfilter
    if fq.db.get_setting("parent_ha_only") and not via_ingress(request):
        return False
    return not netfilter.check(fq, loginlog.client_ip(request), "/api/parent/")


def app_of(request: Request):
    return request.app.state.fq


def learner(request: Request, x_fq_token: str | None = Header(default=None),
            x_fq_parent: str | None = Header(default=None)) -> dict:
    """The profile that is learning: a child, or a parent who learns along."""
    fq = app_of(request)
    pid = fq.tokens.read(x_fq_token, "kid", KID_MAX_AGE)
    if pid is None:
        pid = fq.tokens.read(x_fq_parent, "parent", PARENT_MAX_AGE, via_ingress(request))
    if pid is None:
        raise HTTPException(401, "Please choose your profile")
    prof = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
    if not prof:
        raise HTTPException(401, "Please choose your profile")
    # block time «only a message»: a child can only see that it is OfflineTime (and log out) – also enforced here,
    # not just on the screen (a second device or an old tab)
    if prof["role"] != "parent" and request.url.path not in LOCK_OPEN:
        blk = fq.internet.block(prof)
        if blk and blk["mode"] == "app":
            raise HTTPException(423, "It is OfflineTime – Family Quest is back later")
    return prof


LOCK_OPEN = {"/api/me", "/api/me/logout", "/api/logout", "/api/info"}


def via_ingress(request: Request) -> bool:
    """The request really comes through Home Assistant ingress (the Supervisor proxy)."""
    return bool(request.client and request.client.host == INGRESS_IP)


def ha_user(request: Request) -> dict | None:
    """The Home Assistant user – only trusted when the request really comes through Home Assistant ingress
    (the Supervisor proxy sets these headers; on the direct port anybody could send them)."""
    if not via_ingress(request):
        return None
    uid = request.headers.get("x-remote-user-id")
    if not uid:
        return None
    return {"id": uid, "name": request.headers.get("x-remote-user-display-name") or request.headers.get("x-remote-user-name") or "",
            "user": request.headers.get("x-remote-user-name") or ""}


def profile_of_ha_user(fq, uid: str | None, role: str | None = None) -> dict | None:
    """The (not archived) profile linked with this Home Assistant user – one profile per user – that may sign in with
    it (sign-in «Home Assistant only» or «PIN or Home Assistant»; db.login_ha_ok)."""
    from ..db import login_ha_ok, profile_settings
    if not uid:
        return None
    for p in fq.db.q("SELECT * FROM profile WHERE archived=0" + (" AND role=?" if role else "") + " ORDER BY id", *([role] if role else [])):
        if profile_settings(p).get("ha_user_id") == uid:
            return p if login_ha_ok(p) else None
    return None


def ha_kid(fq, request: Request) -> dict | None:
    """The child whose Home Assistant user opened the app through ingress (linked in its profile – the link is the
    permission, there is no extra switch). Gives the children's app, never the parent area."""
    u = ha_user(request)
    return profile_of_ha_user(fq, u["id"], "kid") if u else None


def parent(request: Request, x_fq_parent: str | None = Header(default=None)) -> dict:
    fq = app_of(request)
    if fq.db.get_setting("parent_ha_only") and not via_ingress(request):
        raise HTTPException(403, "The parent area opens only through Home Assistant")
    # the parent networks for every route with a parent token – not only below /api/parent/ (main.py checks paths)
    from .. import loginlog, netfilter
    if netfilter.check(fq, loginlog.client_ip(request), "/api/parent/"):
        raise HTTPException(403, "The parent area cannot be opened from this network")
    pid = fq.tokens.read(x_fq_parent, "parent", PARENT_MAX_AGE, via_ingress(request))
    prof = fq.db.q1("SELECT * FROM profile WHERE id=? AND role='parent' AND archived=0", pid) if pid else None
    if not prof:
        raise HTTPException(401, "Parent PIN required")
    return prof


Learner = Depends(learner)
Parent = Depends(parent)
