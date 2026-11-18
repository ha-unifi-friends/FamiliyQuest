"""Adventure books API (familyquest/stories.py): the family only – children and parents with their login, never guests.

Writing, reading and the shelf take the learning-app login (or the parent login); the settings need the parent PIN.
Who may change a book (author or a parent) is decided in stories.py.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field

from ..community import CommunityError
from .auth import Learner, Parent, app_of

router = APIRouter(prefix="/api/stories")


def _run(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except CommunityError as e:
        raise HTTPException(400, str(e)) from None


def _oversee(request: Request, prof: dict) -> bool:
    """The parent area (parent login, no app login): parents open every book that is not private."""
    return prof["role"] == "parent" and not request.headers.get("x-fq-token")


class BookIn(BaseModel):
    visibility: str = Field(default="family", max_length=16)     # new books: the whole family (approval still applies)
    title: str = Field(default="", max_length=400)
    emoji: str = Field(default="📖", max_length=64)
    color: int = 0
    lang: str = Field(default="en", max_length=16)
    template: str | None = Field(default=None, max_length=32)
    type: str = Field(default="adventure", max_length=16)


class BookEditIn(BaseModel):
    title: str | None = Field(default=None, max_length=400)
    emoji: str | None = Field(default=None, max_length=64)
    color: int | None = None
    lang: str | None = Field(default=None, max_length=16)
    visibility: str | None = Field(default=None, max_length=16)
    data: dict[str, Any] | None = None


class ChoiceIn(BaseModel):
    i: int


class RateIn(BaseModel):
    stars: int


class TurnIn(BaseModel):
    page: int


class SvgIn(BaseModel):
    svg: str = Field(max_length=40_000)


class SampleIn(BaseModel):
    hidden: bool


class MoveIn(BaseModel):
    """One move in an adventure game: look / take / talk / go / use (with an item or without) / combine / answer / leave."""
    verb: str = Field(max_length=16)
    spot: int | None = None
    item: int | None = None
    item2: int | None = None
    answer: int | None = None


class TryIn(BaseModel):
    """▶ in the editor: the state so far (None: start – in `room`, or the start room) and the move."""
    state: dict[str, Any] | None = None
    move: MoveIn | None = None
    room: int | None = None
    pending: bool = False


@router.get("")
def shelf(request: Request, lang: str = "en", prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.shelf, prof, _oversee(request, prof), lang[:16])


@router.get("/templates")
def templates(request: Request, lang: str = "en", type: str = "adventure", prof: dict = Learner) -> list[dict]:
    if type == "game":
        from ..adventuregame import templates as game_tpl
        return game_tpl(lang[:16])
    from ..stories import templates as tpl
    return tpl(lang)


@router.get("/ai-template")
def ai_template(type: str = "adventure") -> Response:
    """The template for an AI: self-describing JSON (instructions, field guide, backgrounds, an example book).
    `type=picture`: the picture book format (family-quest-picturebook/1, with the rules for SVG pictures);
    `type=game`: the adventure game format (family-quest-adventuregame/1, with the assets and a full example game)."""
    if type == "game":
        from ..adventuregame import document as game_doc
        doc, name = game_doc([], example=True), "family-quest-adventuregame-template.json"
    elif type == "picture":
        from ..picturebooks import document
        doc, name = document([], example=True), "family-quest-picturebook-template.json"
    else:
        from ..stories import story_document
        doc, name = story_document([], example=True), "family-quest-story-template.json"
    return Response(json.dumps(doc, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


class ImportIn(BaseModel):
    text: str = Field(max_length=1_000_000)


@router.post("/import")
def import_(body: ImportIn, request: Request, prof: dict = Learner) -> dict:
    return {"ids": _run(app_of(request).stories.import_, prof, body.text)}


@router.get("/settings")
def settings_get(request: Request, me: dict = Parent) -> dict:
    return app_of(request).stories.settings()


@router.put("/settings")
def settings_put(body: dict[str, Any], request: Request, me: dict = Parent) -> dict:
    return app_of(request).stories.save_settings(body)


@router.post("/svg")
def svg(body: SvgIn, request: Request, prof: dict = Learner) -> dict:
    """An own SVG picture for a picture book: cleaned (what the book will show) – or 400 with the reason."""
    return {"svg": _run(app_of(request).stories.check_svg, prof, body.svg)}


@router.put("/samples/{key}")
def sample_hidden(key: str, body: SampleIn, request: Request, prof: dict = Learner) -> dict:
    """Parents: take a sample book off the shelf (for the whole family) or put it back."""
    _run(app_of(request).stories.sample_hidden, prof, key, body.hidden)
    return {"ok": True}


@router.post("/image")
async def image(request: Request, file: UploadFile = File(...), prof: dict = Learner) -> dict:
    from ..memorygame import picture_kind
    from ..stories import IMAGE_MAX
    raw = await file.read(IMAGE_MAX + 1)
    return _run(app_of(request).stories.save_image, prof, raw, picture_kind(raw))


@router.post("")
def create(body: BookIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).stories.create, prof, body.title, body.emoji, body.color, body.lang, body.template, body.visibility,
                       body.type)}


@router.get("/{sid}")
def get(sid: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.get, prof, sid)


@router.get("/{sid}/export")
def export(sid: int, request: Request, prof: dict = Learner) -> Response:
    doc = _run(app_of(request).stories.export, prof, sid)
    return Response(json.dumps(doc, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="family-quest-book-{sid}.json"'})


@router.put("/{sid}")
def save(sid: int, body: BookEditIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.save, prof, sid, body.data, body.title, body.emoji, body.color, body.lang, body.visibility)


@router.delete("/{sid}")
def delete(sid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).stories.delete, prof, sid)
    return {"ok": True}


@router.post("/{sid}/publish")
def publish(sid: int, request: Request, prof: dict = Learner) -> dict:
    return {"status": _run(app_of(request).stories.publish, prof, sid)}


@router.post("/{sid}/unpublish")
def unpublish(sid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).stories.unpublish, prof, sid)
    return {"ok": True}


@router.post("/{sid}/approve")
def approve(sid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).stories.approve, prof, sid)
    return {"ok": True}


@router.post("/{sid}/reject")
def reject(sid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).stories.reject, prof, sid)
    return {"ok": True}


@router.get("/{sid}/read")
def read(sid: int, request: Request, lang: str = "en", prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.read, prof, sid, _oversee(request, prof), lang[:16])


@router.post("/{sid}/read/restart")
def restart(sid: int, request: Request, lang: str = "en", prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.restart, prof, sid, _oversee(request, prof), lang[:16])


@router.post("/{sid}/read/page")
def turn(sid: int, body: TurnIn, request: Request, prof: dict = Learner) -> dict:
    """A picture book: the reader is on this page now (0 = the cover) – the last page reads it to the end."""
    return _run(app_of(request).stories.turn, prof, sid, body.page, _oversee(request, prof))


@router.post("/{sid}/read/choose")
def choose(sid: int, body: ChoiceIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).stories.choose, prof, sid, body.i, _oversee(request, prof))


@router.post("/{sid}/read/act")
def act(sid: int, body: MoveIn, request: Request, prof: dict = Learner) -> dict:
    """An adventure game: one move – the server plays it and saves the state of this player."""
    return _run(app_of(request).stories.play, prof, sid, body.model_dump(), _oversee(request, prof))


@router.post("/{sid}/try")
def try_game(sid: int, body: TryIn, request: Request, prof: dict = Learner) -> dict:
    """An adventure game: ▶ the working copy from any room (author and parents) – nothing is saved."""
    return _run(app_of(request).stories.try_game, prof, sid, body.state, body.move.model_dump() if body.move else None, body.room,
                body.pending)


@router.post("/{sid}/rate")
def rate(sid: int, body: RateIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).stories.rate, prof, sid, body.stars, _oversee(request, prof))
    return {"ok": True}
