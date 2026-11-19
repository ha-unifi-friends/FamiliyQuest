"""API of the privacy page (privacy.py): retention periods, the clean-up runs (preview, single entries, run) and the
past runs. Parents only."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, HTTPException, Request

from .. import privacy
from .auth import Parent, app_of

router = APIRouter(prefix="/api/parent/privacy")


@router.get("")
def overview(request: Request, me: dict = Parent) -> dict:
    """Everything of the page: kinds with their period and what is past due (the dry run), what is kept, the switch, the runs."""
    return privacy.preview(app_of(request))


@router.get("/badge")
def badge(request: Request, me: dict = Parent) -> dict:
    """The light count for the red badge on the menu item (cached a few minutes on the server)."""
    return privacy.badge(app_of(request))


@router.put("/settings")
def save(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    fq = app_of(request)
    privacy.save_settings(fq.db, body)
    return privacy.preview(fq)


@router.get("/entries/{kind}")
def entries(kind: str, request: Request, me: dict = Parent) -> list[dict]:
    if kind not in privacy.BY_KEY:
        raise HTTPException(404, "Unknown kind of data")
    return privacy.entries(app_of(request), kind)


@router.post("/run")
async def run(request: Request, body: dict = Body(...), me: dict = Parent) -> dict:
    """Delete what is past due of the chosen kinds (a snapshot first). Body: {"kinds": [...], "entries": {kind: [ids]}}."""
    fq = app_of(request)
    kinds = [k for k in body.get("kinds") or [] if isinstance(k, str)]
    picks = body.get("entries") if isinstance(body.get("entries"), dict) else {}
    if not kinds or any(k not in privacy.BY_KEY for k in kinds):
        raise HTTPException(400, "Choose what to delete")
    try:
        res = await asyncio.to_thread(privacy.run, fq, kinds, picks, {"id": me["id"], "name": me["name"]})
    except privacy.PrivacyOff:
        raise HTTPException(409, "Privacy is switched off – switch it on to run a clean-up") from None
    except OSError:
        raise HTTPException(500, "The backup before the clean-up could not be written – nothing was deleted") from None
    return {**res, **privacy.preview(fq)}
