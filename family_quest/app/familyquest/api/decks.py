"""Own flash card decks of the logged-in person (/api/me/decks…)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..decks import DeckError
from ..learning.lesson import LearnError
from .auth import Learner, app_of

router = APIRouter(prefix="/api/me/decks")


def _run(fn, *args):
    try:
        return fn(*args)
    except (DeckError, LearnError) as e:
        raise HTTPException(400, str(e)) from None


class DeckIn(BaseModel):
    name: str
    icon: str = "📇"


class CardIn(BaseModel):
    front: str
    back: str


class GradeIn(BaseModel):
    result: str


class FromSessionIn(BaseModel):
    session: str
    step: int
    deck: int | None = None


class FromUnitIn(BaseModel):
    pack: str
    unit: str
    deck: int | None = None


@router.get("")
def decks(request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    return {"decks": fq.decks.list(prof["id"]), "due": fq.decks.due_total(prof["id"])}


@router.post("")
def create(body: DeckIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).decks.create, prof["id"], body.name, body.icon)}


@router.post("/from-session")
def from_session(body: FromSessionIn, request: Request, prof: dict = Learner) -> dict:
    """The card(s) of an answered lesson step – only what this person was just shown."""
    fq = app_of(request)
    row, data = _run(fq.learning._load, body.session, prof["id"])
    if not 0 <= body.step < len(data["steps"]) or str(body.step) not in data["answered"]:
        raise HTTPException(400, "Answer first")
    step = data["steps"][body.step]
    pack = fq.packs.get(step["pack"])
    items = fq.decks.pack_items(pack, step["unit"], step["keys"]) if pack else []
    if not items:
        raise HTTPException(400, "This task cannot go into a deck")
    return _run(fq.decks.add_items, prof["id"], pack, items, body.deck)


@router.post("/from-unit")
def from_unit(body: FromUnitIn, request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    pack = fq.packs.get(body.pack)
    if not pack or body.pack not in {x.id for x in fq.packs.for_profile(prof["id"])}:
        raise HTTPException(404, "Pack not available")
    items = fq.decks.pack_items(pack, body.unit)
    if not items:
        raise HTTPException(400, "This task cannot go into a deck")
    return _run(fq.decks.add_items, prof["id"], pack, items, body.deck)


@router.get("/{did}")
def cards(did: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).decks.cards, prof["id"], did)


@router.put("/{did}")
def update(did: int, body: DeckIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).decks.update, prof["id"], did, body.name, body.icon)
    return {"ok": True}


@router.delete("/{did}")
def delete(did: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).decks.delete, prof["id"], did)
    return {"ok": True}


@router.post("/{did}/cards")
def add_card(did: int, body: CardIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).decks.add_card, prof["id"], did, body.front, body.back)}


@router.put("/cards/{cid}")
def edit_card(cid: int, body: CardIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).decks.edit_card, prof["id"], cid, body.front, body.back)
    return {"ok": True}


@router.delete("/cards/{cid}")
def delete_card(cid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).decks.delete_card, prof["id"], cid)
    return {"ok": True}


@router.get("/{did}/study")
def study(did: int, request: Request, mode: str = "due", prof: dict = Learner) -> dict:
    return {"cards": _run(app_of(request).decks.study, prof["id"], did, mode)}


@router.post("/cards/{cid}/grade")
def grade(cid: int, body: GradeIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).decks.grade, prof["id"], cid, body.result)
