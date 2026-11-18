"""Family Quest HA integration: the API of the custom component and its settings in the parent area.

/api/integration/state, /api/integration/action – `Authorization: Bearer <integration token>` (not a parent or kid
login). Refused with 403 while the setting is off. Wrong tokens count like wrong PINs (5 per minute and address).
/api/parent/integration/… – switch on/off, new token, install / remove the component (parent login).
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel

from .. import integration
from .auth import Parent, app_of

router = APIRouter(prefix="/api/integration")
parent_router = APIRouter(prefix="/api/parent/integration")


def _auth(request: Request, authorization: str | None) -> Any:
    fq = app_of(request)
    if not integration.enabled(fq):
        raise HTTPException(403, "The Family Quest HA integration is switched off")
    token = (authorization or "").removeprefix("Bearer ").strip()
    key = "integration:" + (request.client.host if request.client else "")
    fq.throttle.check(key)
    if not integration.check_token(fq, token):
        raise HTTPException(401, "Wrong integration token")
    fq.throttle.ok(key)
    integration.polled(fq)
    return fq


@router.get("/state")
def state(request: Request, authorization: str | None = Header(default=None)) -> dict:
    return integration.state(_auth(request, authorization))


@router.post("/action")
def action(request: Request, body: dict[str, Any] = Body(...), authorization: str | None = Header(default=None)) -> dict:
    fq = _auth(request, authorization)
    try:
        return integration.action(fq, body)
    except integration.IntegrationError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- parent area
class EnableIn(BaseModel):
    enabled: bool


@parent_router.get("")
def status(request: Request, me: dict = Parent) -> dict:
    return integration.status(app_of(request))


@parent_router.put("")
async def switch(body: EnableIn, request: Request, me: dict = Parent) -> dict:
    """On: a token (first time), the component copied to /config. Off: the token is refused from now on."""
    fq = app_of(request)
    token = await asyncio.to_thread(integration.set_enabled, fq, body.enabled)
    out: dict = {}
    if body.enabled:
        try:
            out["install"] = await asyncio.to_thread(integration.install, fq.settings.version)
        except (integration.IntegrationError, OSError) as e:
            out["install_error"] = str(e)
    return {**integration.status(fq), **out, "token": token}


@parent_router.post("/token")
def token(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if not integration.enabled(fq):
        raise HTTPException(400, "Switch the Family Quest HA integration on first")
    return {**integration.status(fq), "token": integration.new_token(fq)}


@parent_router.post("/install")
def install(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    try:
        r = integration.install(fq.settings.version)
    except (integration.IntegrationError, OSError) as e:
        raise HTTPException(400, str(e)) from None
    return {**integration.status(fq), "install": r}


@parent_router.delete("/component")
def remove(request: Request, me: dict = Parent) -> dict:
    fq = app_of(request)
    if integration.enabled(fq):
        raise HTTPException(400, "Switch the Family Quest HA integration off first")
    try:
        removed = integration.remove()
    except OSError as e:
        raise HTTPException(400, str(e)) from None
    return {**integration.status(fq), "removed": removed}
