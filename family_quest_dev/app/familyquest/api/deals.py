"""API of the deals (deals.py): children – and parents in the app or the parent area – trade; parents manage them."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..deals import DealError
from .auth import Learner, Parent, app_of

router = APIRouter(prefix="/api/me/deals")
parent_router = APIRouter(prefix="/api/parent/deals")


class OfferIn(BaseModel):
    to: int
    give: list[Any] = []
    get: list[Any] = []
    text: str = ""


class CounterIn(BaseModel):
    give: list[Any] = []
    get: list[Any] = []
    text: str = ""
    version: int | None = None


class AcceptIn(BaseModel):
    version: int


class TextIn(BaseModel):
    text: str = ""


class OkIn(BaseModel):
    ok: bool = True


class CouncilIn(BaseModel):
    lang: str = ""


class SeenIn(BaseModel):
    msg: int


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except DealError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- everybody who trades (children, parents)
@router.get("")
def my_deals(request: Request, ended: bool = False, prof: dict = Learner) -> dict:
    d = app_of(request).deals
    return {"deals": d.list(prof, ended), "on": d.can_trade(prof), "partners": d.partners(prof) if d.can_trade(prof) else [],
            "summary": d.summary(prof)}


@router.get("/assets/{other}")
def assets(other: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.assets, prof, other)


@router.post("")
def offer(body: OfferIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.offer, prof, body.to, body.give, body.get, body.text)


@router.get("/{deal_id}")
def deal(deal_id: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.get, prof, deal_id)


@router.post("/{deal_id}/counter")
def counter(deal_id: int, body: CounterIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.counter, prof, deal_id, body.give, body.get, body.text, body.version)


@router.post("/{deal_id}/accept")
def accept(deal_id: int, body: AcceptIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.accept, prof, deal_id, body.version)


@router.post("/{deal_id}/reject")
def reject(deal_id: int, body: TextIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.reject, prof, deal_id, body.text)


@router.post("/{deal_id}/withdraw")
def withdraw(deal_id: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.withdraw, prof, deal_id)


@router.post("/{deal_id}/confirm")
def confirm(deal_id: int, body: OkIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.confirm, prof, deal_id, body.ok)


@router.post("/{deal_id}/council")
def council(deal_id: int, body: CouncilIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).deals.to_council, prof, deal_id, body.lang)


@router.post("/{deal_id}/seen")
def seen(deal_id: int, body: SeenIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).deals.seen, prof, deal_id, body.msg)
    return {"ok": True}


# ---------------------------------------------------------------- parents: overview, settings, approve, settle, cancel
@parent_router.get("")
def overview(request: Request, me: dict = Parent) -> dict:
    return app_of(request).deals.overview()


@parent_router.put("/settings")
def save_settings(body: dict, request: Request, me: dict = Parent) -> dict:
    return {"settings": app_of(request).deals.save_settings(body)}


@parent_router.get("/{deal_id}")
def thread(deal_id: int, request: Request, me: dict = Parent) -> dict:
    return _run(app_of(request).deals.thread, deal_id)


@parent_router.post("/{deal_id}/approve")
def approve(deal_id: int, body: OkIn, request: Request, me: dict = Parent) -> dict:
    return _run(app_of(request).deals.approve, me, deal_id, body.ok)


@parent_router.post("/{deal_id}/settle")
def settle(deal_id: int, body: OkIn, request: Request, me: dict = Parent) -> dict:
    return _run(app_of(request).deals.settle, me, deal_id, body.ok)


@parent_router.post("/{deal_id}/cancel")
def cancel(deal_id: int, request: Request, me: dict = Parent) -> dict:
    return _run(app_of(request).deals.cancel, me, deal_id)
