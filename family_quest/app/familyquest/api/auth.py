"""Profiles, PINs and tokens.

Tokens are signed (itsdangerous) and sent as header X-FQ-Token (child/learner) or
X-FQ-Parent (parent actions). Headers instead of cookies work the same through
Home Assistant ingress and on the direct port.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

KID_MAX_AGE = 60 * 60 * 24 * 30
PARENT_MAX_AGE = 60 * 30
INGRESS_IP = "172.30.32.2"


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
    return isinstance(pin, str) and pin.isdigit() and min_len <= len(pin) <= max_len


class Throttle:
    """At most 5 PIN attempts per key (profile and device) per minute.

    Every attempt is counted *before* the PIN is checked – atomically – so parallel requests cannot slip past the
    limit while the slow hash runs; a right PIN clears the count again."""

    def __init__(self):
        self.fails: dict[str, list[float]] = defaultdict(list)
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


class Tokens:
    """Signed logins. A login of a profile carries a fingerprint of the profile (when it was made, its PIN, whether it
    is archived): changing the PIN, archiving or deleting the profile ends all its logins – and a new profile that
    gets the id of a deleted one cannot use the old logins."""

    def __init__(self, secret: bytes):
        self.s = URLSafeTimedSerializer(secret, salt="familyquest")
        self.fingerprint: Callable[[int], str | None] | None = None      # set by FamilyQuest (services.py)

    def make(self, pid: int, kind: str, ttl: int | None = None) -> str:
        d = {"p": pid, "k": kind}
        if self.fingerprint and kind in ("kid", "parent"):
            d["f"] = self.fingerprint(pid)
        if ttl:
            d["x"] = int(time.time()) + ttl                              # shorter than the usual max age
        return self.s.dumps(d)

    def read(self, token: str | None, kind: str, max_age: int) -> int | None:
        if not token:
            return None
        try:
            d = self.s.loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        if d.get("k") != kind or ("x" in d and time.time() > d["x"]):
            return None
        pid = int(d["p"])
        if self.fingerprint and kind in ("kid", "parent") and d.get("f") != self.fingerprint(pid):
            return None
        return pid


def app_of(request: Request):
    return request.app.state.fq


def learner(request: Request, x_fq_token: str | None = Header(default=None),
            x_fq_parent: str | None = Header(default=None)) -> dict:
    """The profile that is learning: a child, or a parent who learns along."""
    fq = app_of(request)
    pid = fq.tokens.read(x_fq_token, "kid", KID_MAX_AGE)
    if pid is None:
        pid = fq.tokens.read(x_fq_parent, "parent", PARENT_MAX_AGE)
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
    """The (not archived) profile linked with this Home Assistant user – one profile per user."""
    from ..db import profile_settings
    if not uid:
        return None
    for p in fq.db.q("SELECT * FROM profile WHERE archived=0" + (" AND role=?" if role else "") + " ORDER BY id", *([role] if role else [])):
        if profile_settings(p).get("ha_user_id") == uid:
            return p
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
    pid = fq.tokens.read(x_fq_parent, "parent", PARENT_MAX_AGE)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=? AND role='parent' AND archived=0", pid) if pid else None
    if not prof:
        raise HTTPException(401, "Parent PIN required")
    return prof


Learner = Depends(learner)
Parent = Depends(parent)
