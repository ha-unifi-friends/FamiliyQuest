"""«Sign in with Home Assistant» in the app outside Home Assistant (direct port: tablets, phones).

Home Assistant's own OAuth2 / IndieAuth login: the browser goes to <HA>/auth/authorize with client_id = the address of
the app (a URL, as Home Assistant requires) and redirect_uri = <app>/ha-auth/callback (same host as the client_id).
Home Assistant shows its login page (password, two-factor – whatever the user has), then sends the browser back with a
code. The add-on exchanges that code itself (server side) at <HA>/auth/token, asks Home Assistant who the user is
(websocket «auth/current_user» with the user's own access token) and revokes the Home Assistant tokens right away:
Family Quest keeps only the identity, never a Home Assistant token. The Home Assistant user is then mapped to the
profile linked with it (profile setting ha_user_id): a child (only with «kid_ha_login»), or a parent – both get the same
login a PIN login in the app gives.

State: a short-lived signed state carries a hash of a random nonce that only the starting browser tab knows
(sessionStorage) – a code from somebody else's login flow cannot be pushed into another device, and every state is
used once.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

log = logging.getLogger("familyquest.haauth")

STATE_MAX_AGE = 600                  # 10 minutes for Home Assistant's login page (two-factor included)
CALLBACK = "ha-auth/callback"
_TRANSPORT: httpx.AsyncBaseTransport | None = None      # tests: a mock transport for Home Assistant's endpoints


class HAAuthError(Exception):
    """A failed sign-in – the message is for the user (translated by the app)."""


# ---------------------------------------------------------------- who may use it
def linked_profiles(fq) -> list[dict]:
    """The profiles that can sign in with Home Assistant: linked parents, linked children when «kid_ha_login» is on."""
    from .db import profile_settings
    kids = bool(fq.db.get_setting("kid_ha_login"))
    return [p for p in fq.db.q("SELECT * FROM profile WHERE archived=0 ORDER BY id")
            if profile_settings(p).get("ha_user_id") and (p["role"] == "parent" or kids)]


def available(fq) -> bool:
    return bool(fq.db.get_setting("ha_app_login")) and bool(linked_profiles(fq))


# ---------------------------------------------------------------- addresses
def clean_url(url: str) -> str:
    """http(s)://host[:port] – no user, path, query or fragment. ValueError otherwise."""
    url = str(url or "").strip().rstrip("/")
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.path or p.query or p.fragment:
        raise ValueError("Address: e.g. http://192.168.1.10:8123")
    p.port                                                    # noqa: B018 – raises ValueError for a broken port
    return f"{p.scheme}://{p.netloc}"


def app_base(url: str, host_header: str | None) -> str:
    """The address of the app as the browser sees it (client_id): http(s)://host[:port]/path/ – the host must be the one
    the request came to (Host header)."""
    p = urlsplit(str(url or ""))
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query or p.fragment \
            or not p.path.startswith("/") or not p.path.endswith("/") or "/." in p.path or len(url) > 300:
        raise ValueError("bad app address")
    if host_header and urlsplit("//" + host_header).hostname != p.hostname:
        raise ValueError("bad app address")
    return f"{p.scheme}://{p.netloc}{p.path}"


async def _panel(fq) -> dict:
    from .netinfo import ha_panel
    try:
        return await ha_panel(fq.settings)
    except Exception:  # noqa: BLE001
        return {}


async def browser_base(fq, app: str) -> str:
    """Where the browser reaches Home Assistant: the address the parents entered, else the host of the app (the add-on
    runs on the Home Assistant machine) with Home Assistant's port and https from the Supervisor (default 8123, http)."""
    if (url := fq.db.get_setting("ha_app_login_url")):
        return url
    panel = await _panel(fq)
    host = urlsplit(app).hostname or "homeassistant.local"
    host = f"[{host}]" if ":" in host else host
    return f"{'https' if panel.get('ssl') else 'http'}://{host}:{int(panel.get('port') or 8123)}"


async def server_bases(fq, browser: str) -> list[str]:
    """Where the add-on itself reaches Home Assistant for the code exchange: inside Home Assistant directly on the
    Supervisor network (http://homeassistant:<port>, not when Home Assistant itself does https – its certificate is not
    for that name), then the browser's address."""
    out = []
    if (env := os.environ.get("FQ_HA_AUTH_INTERNAL")):
        out.append(env.rstrip("/"))
    elif fq.settings.ha_token:
        panel = await _panel(fq)
        if panel and not panel.get("ssl"):
            out.append(f"http://homeassistant:{int(panel.get('port') or 8123)}")
    if browser not in out:
        out.append(browser)
    return out


async def suggestions(fq) -> list[str]:
    """internal_url / external_url from Home Assistant's configuration – offered in the settings."""
    out = []
    if fq.ha and fq.ha.connected:
        try:
            cfg = await fq.ha.client.config()
        except Exception:  # noqa: BLE001
            cfg = {}
        for k in ("internal_url", "external_url"):
            try:
                if cfg.get(k) and (u := clean_url(cfg[k])) not in out:
                    out.append(u)
            except ValueError:
                pass
    return out


# ---------------------------------------------------------------- state
_used: dict[str, float] = {}
_used_lock = threading.Lock()


def _serializer(fq) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(fq.tokens.s.secret_key, salt="familyquest-ha-auth")


def _h(nonce: str) -> str:
    return hashlib.sha256(nonce.encode()).hexdigest()


def make_state(fq, client_id: str, ha: str) -> tuple[str, str]:
    """(state, nonce): the nonce stays in the browser tab, the state goes through Home Assistant."""
    nonce = secrets.token_urlsafe(24)
    return _serializer(fq).dumps({"n": _h(nonce), "c": client_id, "h": ha, "r": secrets.token_hex(4)}), nonce


def read_state(fq, state: str, nonce: str) -> dict:
    try:
        d = _serializer(fq).loads(str(state or ""), max_age=STATE_MAX_AGE)
    except SignatureExpired:
        raise HAAuthError("The sign-in took too long – please try again") from None
    except BadSignature:
        raise HAAuthError("The sign-in could not be checked – please try again") from None
    if not isinstance(d, dict) or not nonce or not secrets.compare_digest(d.get("n", ""), _h(str(nonce))):
        raise HAAuthError("The sign-in could not be checked – please try again")
    now = time.time()
    with _used_lock:
        for k in [k for k, t in _used.items() if now - t > STATE_MAX_AGE]:
            del _used[k]
        if d["n"] in _used:
            raise HAAuthError("The sign-in could not be checked – please try again")
        _used[d["n"]] = now
    return d


def authorize_url(ha: str, client_id: str, state: str) -> str:
    return f"{ha}/auth/authorize?" + urlencode({"response_type": "code", "client_id": client_id,
                                                 "redirect_uri": client_id + CALLBACK, "state": state})


# ---------------------------------------------------------------- talking to Home Assistant
async def current_user(base: str, access_token: str) -> dict:
    """{id, name, is_admin} of the access token's user – websocket «auth/current_user» (there is no REST call for it)."""
    import websockets
    url = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/api/websocket"
    async with websockets.connect(url, open_timeout=8, close_timeout=2, max_size=1024 * 1024) as ws:
        msg = json.loads(await ws.recv())
        if msg.get("type") == "auth_required":
            await ws.send(json.dumps({"type": "auth", "access_token": access_token}))
            msg = json.loads(await ws.recv())
        if msg.get("type") != "auth_ok":
            raise HAAuthError("Home Assistant did not accept the sign-in")
        await ws.send(json.dumps({"id": 1, "type": "auth/current_user"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                break
    if not msg.get("success") or not (msg.get("result") or {}).get("id"):
        raise HAAuthError("Home Assistant did not accept the sign-in")
    r = msg["result"]
    return {"id": str(r["id"]), "name": str(r.get("name") or ""), "is_admin": bool(r.get("is_admin"))}


async def _revoke(c: httpx.AsyncClient, refresh_token: str | None) -> None:
    """End the Home Assistant login right away – Family Quest needs only the identity."""
    if not refresh_token:
        return
    try:
        r = await c.post("/auth/revoke", data={"token": refresh_token})
        if r.status_code in (404, 405):                        # older Home Assistant
            await c.post("/auth/token", data={"token": refresh_token, "action": "revoke"})
    except httpx.HTTPError:
        log.warning("Could not revoke the Home Assistant token of a sign-in")


async def identify(bases: list[str], code: str, client_id: str) -> dict:
    """Exchange the code (server side), read the user, revoke the tokens. The tokens are never stored or logged."""
    if not code or len(code) > 200:
        raise HAAuthError("Home Assistant did not accept the sign-in")
    last = None
    for base in bases:
        async with httpx.AsyncClient(base_url=base, timeout=10, transport=_TRANSPORT) as c:
            try:
                r = await c.post("/auth/token", data={"grant_type": "authorization_code", "code": code, "client_id": client_id})
            except httpx.HTTPError as e:
                last = e
                log.info("Home Assistant not reachable at %s for the sign-in: %s", base, type(e).__name__)
                continue                                       # the next address
            if r.status_code != 200:
                log.info("Home Assistant refused the sign-in code (%s)", r.status_code)
                raise HAAuthError("Home Assistant did not accept the sign-in")
            try:
                tok = r.json()
            except ValueError:
                raise HAAuthError("Home Assistant did not accept the sign-in") from None
            if not isinstance(tok, dict):
                raise HAAuthError("Home Assistant did not accept the sign-in")
            try:
                if not tok.get("access_token"):
                    raise HAAuthError("Home Assistant did not accept the sign-in")
                try:
                    return await current_user(base, tok["access_token"])
                except HAAuthError:
                    raise
                except Exception as e:  # noqa: BLE001
                    log.info("Home Assistant user could not be read: %s", type(e).__name__)
                    raise HAAuthError("Home Assistant did not accept the sign-in") from None
            finally:
                await _revoke(c, tok.get("refresh_token"))
    raise HAAuthError("Family Quest cannot reach Home Assistant") from last


async def probe(base: str) -> bool:
    """Is Home Assistant there (its public list of login providers)?"""
    try:
        async with httpx.AsyncClient(base_url=base, timeout=5, transport=_TRANSPORT) as c:
            r = await c.get("/auth/providers")
            return r.status_code == 200 and isinstance(r.json(), (list, dict))
    except (httpx.HTTPError, ValueError):
        return False
