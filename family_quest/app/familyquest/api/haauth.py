"""«Sign in with Home Assistant» in the app on the direct port (haauth.py): start, finish, and the parent settings."""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .. import haauth, loginlog
from .auth import Parent, app_of, profile_of_ha_user, via_ingress

router = APIRouter()


class StartIn(BaseModel):
    base: str                        # the address of the app in the browser (becomes the client_id)


class FinishIn(BaseModel):
    code: str
    state: str
    nonce: str


class TestIn(BaseModel):
    url: str = ""


def _off(fq, request: Request) -> None:
    """Only on the direct port and only when the parents switched it on (inside Home Assistant the trusted user headers
    are used instead) – otherwise it does not exist."""
    if via_ingress(request) or not haauth.available(fq):
        raise HTTPException(404, "Not Found")


@router.post("/api/ha-auth/start")
async def start(body: StartIn, request: Request) -> dict:
    fq = app_of(request)
    _off(fq, request)
    try:
        client_id = haauth.app_base(body.base, request.headers.get("host"))
    except ValueError:
        raise HTTPException(400, "Unknown address") from None
    ha = await haauth.browser_base(fq, client_id)
    state, nonce = haauth.make_state(fq, client_id, ha)
    return {"url": haauth.authorize_url(ha, client_id, state), "nonce": nonce}


@router.get("/ha-auth/callback", include_in_schema=False)
def callback(request: Request):
    """Home Assistant sends the browser back here – on to the app, which finishes the sign-in with its nonce."""
    _off(app_of(request), request)
    q = {k: request.query_params[k][:500] for k in ("code", "state", "error") if k in request.query_params}
    return RedirectResponse("../#/ha-auth?" + urlencode(q), status_code=303, headers={"Cache-Control": "no-store"})


@router.post("/api/ha-auth/finish")
async def finish(body: FinishIn, request: Request) -> dict:
    fq = app_of(request)
    _off(fq, request)
    key = "ha-auth:" + loginlog.client_ip(request)
    fq.throttle.check(key)
    try:
        st = haauth.read_state(fq, body.state, body.nonce)
        user = await haauth.identify(await haauth.server_bases(fq, st["h"]), body.code, st["c"])
    except haauth.HAAuthError as e:
        loginlog.record(fq, request, "profile", None, False)
        raise HTTPException(403, str(e)) from None
    p = profile_of_ha_user(fq, user["id"])
    if not p:
        loginlog.record(fq, request, "profile", None, False)
        raise HTTPException(403, "Your Home Assistant user is not linked with a profile – ask your parents")
    fq.throttle.ok(key)
    loginlog.record(fq, request, "profile", p["id"], True)
    out = {"token": fq.tokens.make(p["id"], "kid"), "profile": fq.profile_public(p), "ha_user": user["name"]}
    # a parent: the same as a parent PIN login in the app – also the parent token unless the parent area is only
    # offered in Home Assistant (then the parent area stays closed on this port, as with the PIN)
    if p["role"] == "parent" and not fq.db.get_setting("parent_ha_only"):
        out["parent_token"] = fq.tokens.make(p["id"], "parent")
    return out


# ---------------------------------------------------------------- parent settings
@router.get("/api/parent/ha-app-login")
async def settings(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    host = request.headers.get("host") or "homeassistant.local"
    return {"on": bool(fq.db.get_setting("ha_app_login")), "url": fq.db.get_setting("ha_app_login_url") or "",
            "auto": await haauth.browser_base(fq, f"{request.url.scheme}://{host}/") if not fq.db.get_setting("ha_app_login_url")
            else None,
            "suggestions": await haauth.suggestions(fq),
            "linked": [{"id": p["id"], "name": p["name"], "role": p["role"]} for p in haauth.linked_profiles(fq)]}


@router.post("/api/parent/ha-app-login/test")
async def test(body: TestIn, request: Request, me: dict = Parent) -> dict:
    """Can Family Quest itself reach Home Assistant at this address (and inside Home Assistant)? The browser checks its
    own way there (parent.js)."""
    fq = app_of(request)
    try:
        url = haauth.clean_url(body.url) if body.url.strip() else \
            await haauth.browser_base(fq, f"{request.url.scheme}://{request.headers.get('host') or 'homeassistant.local'}/")
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    bases = await haauth.server_bases(fq, url)
    return {"url": url, "server": any([await haauth.probe(b) for b in bases])}
