"""Etappe H – community API: family quiz, family council, personal history (see familyquest/community.py).

Everybody (children and parents) makes quizzes, plays and votes with the learning-app token (or the parent token).
A game is led by whoever started it; a parent may always lead.
"""
from __future__ import annotations

import random
from contextlib import contextmanager

from typing import Any

import logging

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from .. import timelimits
from ..community import CommunityError
from ..guests import GUEST, GUEST_HOURS, GuestError
from .auth import Learner, app_of, learner

log = logging.getLogger("familyquest.api.community")

# daily game time (timelimits.py): these requests start or join a game – refused once a child's game time is used up;
# everything else (state, moves) stays open, so a game the child is already in can be played to the end
STARTS = {"start", "join", "again", "duel", "pong4", "accept", "seat"}
NOT_PLAYING = {"quizzes", "templates", "memory"}      # making quizzes and photo sets is no playing time


class _PlayRoute(APIRoute):
    """Counts a minute of game time for a child whose request answered with a game (not «null»: not in a game)."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def run(request: Request):
            response = await handler(request)
            pid = request.scope.get("fq_play")
            if pid and response.status_code < 400 and getattr(response, "body", b"null") not in (b"null", b""):
                try:
                    timelimits.touch(app_of(request).db, pid)
                except Exception:  # noqa: BLE001
                    log.exception("counting game time failed")
            return response
        return run


router = APIRouter(prefix="/api/community", route_class=_PlayRoute)


def game_of(path: str) -> str | None:
    """Which game an address of the community API belongs to (None: council, polls, history – always open)."""
    part = path.split("/api/community/", 1)[-1].split("/")
    head = part[0]
    if head in ("quiz", "quizzes", "templates"):
        return "quiz"
    if head in ("bingo", "poker", "song", "domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "klatsch", "verboten", "jass", "werwolf", "schach", "dorfmarkt", "escape"):
        return head
    if head == "cards" and len(part) > 1:
        return part[1]
    # duels: Tic-Tac-Toe or Ping-Pong – checked per game where a duel starts (duel_invite)
    return {"memory": "paarjagd", "pong4": "pingpong"}.get(head)     # photo sets: Paarjagd; pong4: Ping-Pong doubles


def Player(request: Request, prof: dict = Learner) -> dict:      # noqa: N802 – used like Learner
    """A learner who may play this game (parent area › Games, per game and person)."""
    fq = app_of(request)
    game = game_of(request.url.path)
    if not fq.games_allowed(prof, game, time=False) and not _parent_table(fq, prof, game, request):
        if game:
            raise HTTPException(403, "This game is switched off for you")
        raise HTTPException(403, "Games are switched off for you")
    if prof.get("role") == "kid":
        part = request.url.path.split("/api/community/", 1)[-1].split("/")
        if request.method == "POST" and part[-1] in STARTS and timelimits.used_up(fq.db, prof, "game"):
            raise HTTPException(403, "Game time for today is used up – see you tomorrow!")
        if (game or part[0] == "duel") and part[0] not in NOT_PLAYING:
            request.scope["fq_play"] = prof["id"]
    return prof


Gamer = Depends(Player)

# a locked game (switched off, not bought / rented) at a family table a PARENT opened: the child may look, join and
# play that table – but nothing that opens an own table (alone, a new family table, a rematch)
OWN_TABLE = {"start", "again", "rematch", "solo", "duel", "accept", "seat", "delete", "resume"}


def _parent_table(fq, prof: dict, game: str | None, request: Request) -> bool:
    if not game or prof.get("role") != "kid":
        return False
    part = request.url.path.split("/api/community/", 1)[-1].strip("/").split("/")
    if part[0] in NOT_PLAYING or part[-1] in OWN_TABLE:
        return False
    t = fq.parent_tables(prof, time=False).get(game)
    if not t:
        return False
    if request.method == "GET" or t["member"]:
        return True
    return part[-1] == "join" and t["joinable"]


def PlayerOrGuest(request: Request, x_fq_token: str | None = Header(default=None),        # noqa: N802
                  x_fq_parent: str | None = Header(default=None)) -> dict:
    """Playing a running game: family members, or a guest who came with the invitation (token kind «guest»)."""
    fq = app_of(request)
    gid = fq.tokens.read(x_fq_token, "guest", GUEST_HOURS * 3600)
    if gid is not None:
        prof = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=?", gid, GUEST)
        if not prof:
            raise HTTPException(401, "This guest visit is over")
        return prof
    from .. import loginlog, netfilter
    if netfilter.guest_only(fq, loginlog.client_ip(request)):
        raise HTTPException(403, "Guest network: only games with an invitation (QR code) are open")
    return Player(request, learner(request, x_fq_token, x_fq_parent))


Playing = Depends(PlayerOrGuest)


def _no_bots(fq, prof: dict, game: str, wanted) -> bool:
    """Parent area › Games: «active without bots» – a start that asks for bots is refused; True: play without bots."""
    off = not fq.bots_allowed(prof, game)
    if off and wanted:
        raise HTTPException(403, "Playing with bots is switched off for this game")
    return off


@contextmanager
def _bots_not_remembered(fq, kind: str, forced: bool):
    """A start without bots forced by «active without bots» (Parent area › Games) must not become the remembered
    number of bots (setting game_rules.<kind>) – once bots are switched on again, the old default is back."""
    key = f"game_rules.{kind}"
    before = fq.db.get_setting(key)
    try:
        yield
    finally:
        after = fq.db.get_setting(key)
        if forced and isinstance(after, dict):
            if isinstance(before, dict) and "bots" in before:
                after["bots"] = before["bots"]
            else:
                after.pop("bots", None)
            fq.db.set_setting(key, after)


def _run(fn, *args):
    try:
        return fn(*args)
    except CommunityError as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- quiz: playing
class AnswerIn(BaseModel):
    idx: int
    choice: int | None = None
    value: float | None = None           # estimation question
    lat: float | None = None             # map question
    lon: float | None = None


@router.get("/quiz")
def quiz_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).community.state(prof["id"])


@router.post("/quiz/join")
def quiz_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.community.join, prof["id"])
    return fq.community.state(prof["id"])


@router.post("/quiz/leave")
def quiz_leave(request: Request, prof: dict = Playing) -> dict:
    app_of(request).community.leave(prof["id"])
    return {"ok": True}


@router.post("/quiz/answer")
def quiz_answer(body: AnswerIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.community.answer, prof["id"], body.idx, body.choice, body.value, body.lat, body.lon)
    return fq.community.state(prof["id"])


# ---------------------------------------------------------------- quiz: making and leading (everybody)
class QuizIn(BaseModel):
    title: str
    questions: list[dict[str, Any]] = []
    langs: dict[str, Any] | None = None     # multilingual: {"base", "more", "title"} (community.clean_langs)


class StartIn(BaseModel):
    quiz_id: int
    count: int | None = None        # play only this many questions
    shuffle: bool = True


class TemplateIn(BaseModel):
    template: str


@router.get("/quizzes")
def quizzes(request: Request, prof: dict = Gamer) -> list[dict]:
    return app_of(request).community.quizzes()


@router.get("/tables")
def open_tables(request: Request, prof: dict = Gamer) -> list[dict]:
    """Family tables somebody else opened just now – the app shows a note in its header (web/kid.js)."""
    from .. import running
    return running.open_tables(app_of(request), prof)


@router.get("/templates")
def templates(request: Request, prof: dict = Gamer) -> list[dict]:
    from ..quiz_templates import TEMPLATES
    from ..community import template_translations
    return [{"id": k, "title": t["title"], "icon": t["icon"], "questions": len(t["questions"]), "region": t["region"],
             "titles": {lang: v["title"] for lang, v in template_translations(k).items()},
             "examples": {lang: v["items"][0]["q"] for lang, v in template_translations(k).items()},
             "example": t["questions"][0]["q"] if isinstance(t["questions"][0], dict) else t["questions"][0][0]}
            for k, t in TEMPLATES.items()]


@router.post("/quizzes")
def quiz_create(body: QuizIn, request: Request, prof: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).community.save_quiz, body.model_dump(), prof)}


# ---------------------------------------------------------------- who begins a turn-based game (cardgames.apply_starter)
class BeginIn(BaseModel):
    starter: str | None = None       # with the setting «choose»: the player the leader picked


@router.get("/starter")
def game_starter(request: Request, prof: dict = Gamer) -> dict:
    from ..cardgames import starter_mode
    return {"mode": starter_mode(app_of(request).db)}


class QuizImportIn(BaseModel):
    text: str                        # the file: a quiz (or a list) in the Family Quest quiz format


@router.post("/quizzes/import")
def quiz_import(body: QuizImportIn, request: Request, prof: dict = Gamer) -> dict:
    if prof["role"] == "guest":
        raise HTTPException(403, "Guests cannot add quizzes")
    if len(body.text) > 1_000_000:
        raise HTTPException(400, "The file is too large")
    return {"ids": _run(app_of(request).community.import_quizzes, prof, body.text)}


def _quiz_file(doc: dict, name: str) -> Response:
    import json as _json
    return Response(_json.dumps(doc, ensure_ascii=False, indent=2), media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/quizzes/export")
def quiz_export_all(request: Request, prof: dict = Gamer) -> Response:
    if prof["role"] == "guest":
        raise HTTPException(403, "Guests cannot export quizzes")
    return _quiz_file(app_of(request).community.export_quizzes(), "family-quest-quizzes.json")


@router.get("/quizzes/{quiz_id}/export")
def quiz_export(quiz_id: int, request: Request, prof: dict = Gamer) -> Response:
    if prof["role"] == "guest":
        raise HTTPException(403, "Guests cannot export quizzes")
    doc = _run(app_of(request).community.export_quizzes, quiz_id)
    return _quiz_file(doc, f"family-quest-quiz-{quiz_id}.json")


@router.post("/quizzes/from-template")
def quiz_from_template(body: TemplateIn, request: Request, prof: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).community.from_template, prof, body.template)}


@router.put("/quizzes/{quiz_id}")
def quiz_update(quiz_id: int, body: QuizIn, request: Request, prof: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).community.save_quiz, body.model_dump(), prof, quiz_id)}


@router.delete("/quizzes/{quiz_id}")
def quiz_delete(quiz_id: int, request: Request, prof: dict = Gamer) -> dict:
    _run(app_of(request).community.delete_quiz, prof, quiz_id)
    return {"ok": True}


@router.post("/quiz/start")
def quiz_start(body: StartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.community.start, body.quiz_id, prof["id"], body.count, body.shuffle)
    return fq.community.state(prof["id"])


class FactsIn(BaseModel):
    count: int = 10                  # number of questions
    focus: str = "mixed"            # week | all | mixed
    lang: str | None = None         # the starter's app language (de-CH / de-DE … – the base language of the questions)


@router.get("/quizzes/facts")
def quiz_facts_info(request: Request, prof: dict = Gamer) -> dict:
    """The special quiz «Family Quest Facts» (facts.py): on or off, the choices of the start dialog."""
    from .. import facts
    return facts.info(app_of(request))


@router.post("/quiz/facts/start")
def quiz_facts_start(body: FactsIn, request: Request, prof: dict = Gamer) -> dict | None:
    """Start «Family Quest Facts»: questions made now from the family's data (fresh every game)."""
    from .. import facts
    fq = app_of(request)
    if prof.get("role") not in ("kid", "parent"):
        raise HTTPException(403, "Only the family can start this quiz")
    if not facts.enabled(fq.db):
        raise HTTPException(403, "The quiz «Family Quest Facts» is switched off")
    _run(facts.start, fq, prof["id"], body.count, body.focus, body.lang)
    return fq.community.state(prof["id"])


def _lead(fq, prof: dict) -> None:
    if not fq.community.may_lead(prof):
        raise HTTPException(403, "Only who started the quiz (or a parent) leads it")


@router.post("/quiz/next")
def quiz_next(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead(fq, prof)
    _run(fq.community.next)
    return fq.community.state(prof["id"])


@router.post("/quiz/end")
def quiz_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead(fq, prof)
    _run(fq.community.finish)
    return fq.community.state(prof["id"])


@router.post("/quiz/abort")
def quiz_abort(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead(fq, prof)
    fq.community.abort()
    return fq.community.state(prof["id"])          # like every action: the state (after the abort: none)


# ---------------------------------------------------------------- bingo
class BingoStartIn(BaseModel):
    interval: float | None = None
    win: str | None = None          # line | two_lines | full


class MarkIn(BaseModel):
    cell: int


class PauseIn(BaseModel):
    on: bool = True


def _bingo_lead(fq, prof: dict) -> None:
    if not fq.bingo.may_lead(prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/bingo")
def bingo_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).bingo.state(prof["id"])


@router.get("/bingo/rules")
def bingo_rules(request: Request, prof: dict = Gamer) -> dict:
    """The rules used last – the default for the next game."""
    return app_of(request).bingo.default_rules()


@router.post("/bingo/start")
def bingo_start(body: BingoStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.bingo.start, prof["id"], body.model_dump())
    return fq.bingo.state(prof["id"])


@router.post("/bingo/join")
def bingo_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.bingo.join, prof["id"])
    return fq.bingo.state(prof["id"])


@router.post("/bingo/begin")
def bingo_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _bingo_lead(fq, prof)
    _run(fq.bingo.begin)
    return fq.bingo.state(prof["id"])


@router.post("/bingo/pause")
def bingo_pause(body: PauseIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _bingo_lead(fq, prof)
    _run(fq.bingo.pause, body.on)
    return fq.bingo.state(prof["id"])


@router.post("/bingo/end")
def bingo_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _bingo_lead(fq, prof)
    fq.bingo.end()
    return fq.bingo.state(prof["id"])


@router.post("/bingo/mark")
def bingo_mark(body: MarkIn, request: Request, prof: dict = Playing) -> dict:
    return {"marks": _run(app_of(request).bingo.mark, prof["id"], body.cell)}


@router.post("/bingo/claim")
def bingo_claim(request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    res = _run(fq.bingo.claim, prof["id"])
    return {**res, "state": fq.bingo.state(prof["id"])}


# ---------------------------------------------------------------- Texas Hold'em (play chips only)
class PokerStartIn(BaseModel):
    start_chips: int | None = None
    small_blind: int | None = None
    big_blind: int | None = None
    ante: int | None = None
    blind_minutes: int | None = None
    turn_seconds: int | None = None
    pause_seconds: int | None = None
    mode: str | None = None              # equal | bank
    rebuys: int | None = None
    max_players: int | None = None
    solo: bool = False                   # alone against bots
    bots: int = 3
    level: str = "normal"                # easy | normal | hard
    bot_ids: list[int | str] = []
    bot_ms: int | None = None            # reaction time of the bots (0 = at once)


class PokerActIn(BaseModel):
    kind: str                            # fold | check | call | raise | allin
    amount: int | None = None            # raise: the total bet of this round


class PokerGiveIn(BaseModel):
    profile_id: int
    ok: bool = True
    amount: int | None = None


def _poker_lead(fq, prof: dict) -> None:
    if not fq.poker.may_lead(prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/poker")
def poker_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).poker.state(prof["id"])


@router.get("/poker/rules")
def poker_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).poker.default_rules()


@router.post("/poker/start")
def poker_start(body: PokerStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _no_bots(fq, prof, "poker", body.solo)
    rules = body.model_dump(exclude={"solo", "bots", "level", "bot_ids"})
    bots = None
    if body.solo:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1, min(5, body.bots)), body.level, BOTS)
    _run(fq.poker.start, prof["id"], rules, body.solo, bots)
    return fq.poker.state(prof["id"])


@router.post("/poker/join")
def poker_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.poker.join, prof["id"])
    return fq.poker.state(prof["id"])


@router.post("/poker/begin")
def poker_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _poker_lead(fq, prof)
    _run(fq.poker.begin, prof["id"], (body or BeginIn()).starter)
    return fq.poker.state(prof["id"])


@router.post("/poker/act")
def poker_act(body: PokerActIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.poker.act, prof["id"], body.kind, body.amount)
    return fq.poker.state(prof["id"])


@router.post("/poker/pause")
def poker_pause(body: PauseIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _poker_lead(fq, prof)
    _run(fq.poker.pause, body.on, prof["id"])
    return fq.poker.state(prof["id"])


@router.post("/poker/end")
def poker_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _poker_lead(fq, prof)
    fq.poker.end(prof["id"])
    return fq.poker.state(prof["id"])


@router.post("/poker/ask")
def poker_ask(request: Request, prof: dict = Playing) -> dict | None:
    """The bank: ask the game leader for chips."""
    fq = app_of(request)
    _run(fq.poker.ask_chips, prof["id"])
    return fq.poker.state(prof["id"])


@router.post("/poker/give")
def poker_give(body: PokerGiveIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    if not fq.poker.may_lead(prof, family=True):         # the bank belongs to the family table
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    _run(fq.poker.give_chips, body.profile_id, body.ok, body.amount)
    return fq.poker.state(prof["id"])


# ---------------------------------------------------------------- card games: Tschau Sepp, Kartenkarussell
class CardStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    deck: str | None = None              # tschau: swiss | french
    hand: int | None = None
    rounds: int | None = None
    draw2: bool | None = None
    skip: bool | None = None
    wish: bool | None = None
    again: bool | None = None
    reverse: bool | None = None
    stack: bool | None = None
    penalty: int | None = None
    bots: int | None = None
    level: str | None = None             # easy | normal
    back: str | None = None              # card back
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    bot_ids: list[int | str] = []        # own / shared bots of the children (bots.py) – the rest are animal bots


class CardPlayIn(BaseModel):
    card: str
    wish: str | None = None
    say: bool = False                    # «Tschau» / «Sepp» (Kartenkarussell: «Letzte!» / «Fertig!»)


def _kind(kind: str) -> str:
    from ..cardgames import GAMES
    if kind not in GAMES:
        raise HTTPException(404, "Unknown game")
    return kind


@router.get("/cards/{kind}")
def cards_state(kind: str, request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).cards.state(_kind(kind), prof["id"])


@router.get("/cards/{kind}/rules")
def cards_rules(kind: str, request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).cards.default_rules(_kind(kind))


@router.post("/cards/{kind}/start")
def cards_start(kind: str, body: CardStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, _kind(kind), body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        n = body.bots if body.bots is not None else fq.cards.default_rules(_kind(kind)).get("bots", 2)
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1 if body.solo else 0, min(5, n)), body.level or "normal", BOTS)
    with _bots_not_remembered(fq, _kind(kind), forced):
        _run(fq.cards.start, _kind(kind), prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/join")
def cards_join(kind: str, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.cards.join, _kind(kind), prof["id"])
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/begin")
def cards_begin(kind: str, request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    if not fq.cards.may_lead(_kind(kind), prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    _run(fq.cards.begin, kind, prof["id"], (body or BeginIn()).starter)
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/play")
def cards_play(kind: str, body: CardPlayIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.cards.play, _kind(kind), prof["id"], body.card, body.wish, body.say)
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/draw")
def cards_draw(kind: str, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.cards.draw, _kind(kind), prof["id"])
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/pass")
def cards_pass(kind: str, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.cards.pass_turn, _kind(kind), prof["id"])
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/end")
def cards_end(kind: str, request: Request, prof: dict = Gamer) -> dict:
    fq = app_of(request)
    if not fq.cards.may_lead(_kind(kind), prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    fq.cards.end(kind, prof["id"])
    return fq.cards.state(kind, prof["id"])


# ---------------------------------------------------------------- Domino (familyquest/domino.py)
class DominoStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    mode: str | None = None              # cuban | simple
    set: int | None = None               # 6 | 9 (double-6 / double-9)
    teams: bool | None = None
    draw: bool | None = None             # simple: draw from the boneyard when nothing fits
    target: int | None = None            # 100 | 150 | 200
    bots: int | None = None
    level: str | None = None             # easy | normal
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    bot_ids: list[int | str] = []


class DominoPlayIn(BaseModel):
    tile: str
    end: str | None = None               # left | right (only needed when the tile fits on both ends)


def _lead_domino(fq, prof: dict) -> None:
    if not fq.domino.may_lead("domino", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/domino")
def domino_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).domino.state("domino", prof["id"])


@router.get("/domino/rules")
def domino_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).domino.default_rules()


@router.post("/domino/start")
def domino_start(body: DominoStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "domino", body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        n = body.bots if body.bots is not None else fq.domino.default_rules().get("bots", 3)
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1 if body.solo else 0, min(5, n)), body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "domino", forced):
        _run(fq.domino.start, "domino", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/join")
def domino_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.domino.join, "domino", prof["id"])
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/begin")
def domino_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_domino(fq, prof)
    _run(fq.domino.begin, "domino", prof["id"])
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/play")
def domino_play(body: DominoPlayIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.domino.play, "domino", prof["id"], body.tile, body.end)
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/draw")
def domino_draw(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.domino.draw, "domino", prof["id"])
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/pass")
def domino_pass(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.domino.pass_turn, "domino", prof["id"])
    return fq.domino.state("domino", prof["id"])


@router.post("/domino/end")
def domino_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_domino(fq, prof)
    fq.domino.end("domino", prof["id"])
    return fq.domino.state("domino", prof["id"])


# ---------------------------------------------------------------- Paarjagd (familyquest/pairhunt.py)
class PairhuntStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    set: str | None = None               # emoji set key or photo:<id>
    pairs: int | None = None             # 6 | 8 | 12 | 18
    bots: int | None = None
    level: str | None = None             # easy | normal | hard
    back: str | None = None              # classic | stars | waves | checks | crest
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    bot_ids: list[int | str] = []


class PairhuntFlipIn(BaseModel):
    idx: int


def _lead_pairhunt(fq, prof: dict) -> None:
    if not fq.paarjagd.may_lead("paarjagd", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/paarjagd")
def pairhunt_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).paarjagd.state("paarjagd", prof["id"])


@router.get("/paarjagd/rules")
def pairhunt_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).paarjagd.rules_info()


@router.post("/paarjagd/start")
def pairhunt_start(body: PairhuntStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "paarjagd", body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        n = body.bots if body.bots is not None else fq.paarjagd.default_rules().get("bots", 2)
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1 if body.solo else 0, min(5, n)), body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "paarjagd", forced):
        _run(fq.paarjagd.start, "paarjagd", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.paarjagd.state("paarjagd", prof["id"])


@router.post("/paarjagd/join")
def pairhunt_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.paarjagd.join, "paarjagd", prof["id"])
    return fq.paarjagd.state("paarjagd", prof["id"])


@router.post("/paarjagd/begin")
def pairhunt_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_pairhunt(fq, prof)
    _run(fq.paarjagd.begin, "paarjagd", prof["id"], (body or BeginIn()).starter)
    return fq.paarjagd.state("paarjagd", prof["id"])


@router.post("/paarjagd/flip")
def pairhunt_flip(body: PairhuntFlipIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.paarjagd.flip, "paarjagd", prof["id"], body.idx)
    return fq.paarjagd.state("paarjagd", prof["id"])


@router.post("/paarjagd/end")
def pairhunt_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_pairhunt(fq, prof)
    fq.paarjagd.end("paarjagd", prof["id"])
    return fq.paarjagd.state("paarjagd", prof["id"])


# ---------------------------------------------------------------- «Wer bin ich?» (familyquest/whoami.py)
class WhoamiStartIn(BaseModel):
    category: str | None = None          # whoami_data.CATEGORIES key


class WhoamiTextIn(BaseModel):
    text: str = ""


class WhoamiVoteIn(BaseModel):
    vote: str                            # yes | no | unknown


def _lead_whoami(fq, prof: dict) -> None:
    if not fq.werbinich.may_lead("werbinich", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/werbinich")
def whoami_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).werbinich.state("werbinich", prof["id"])


@router.get("/werbinich/rules")
def whoami_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).werbinich.rules_info()


@router.post("/werbinich/start")
def whoami_start(body: WhoamiStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.start, "werbinich", prof["id"], body.model_dump())
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/join")
def whoami_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.join, "werbinich", prof["id"])
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/begin")
def whoami_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_whoami(fq, prof)
    _run(fq.werbinich.begin, "werbinich", prof["id"], (body or BeginIn()).starter)
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/ask")
def whoami_ask(body: WhoamiTextIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.ask, prof["id"], body.text)
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/answer")
def whoami_answer(body: WhoamiVoteIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.answer, prof["id"], body.vote)
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/close")
def whoami_close(request: Request, prof: dict = Playing) -> dict | None:
    """The asker closes their question early – or who leads the game."""
    fq = app_of(request)
    _run(fq.werbinich.close, prof["id"], prof["role"] != "guest" and fq.werbinich.may_lead("werbinich", prof))
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/guess")
def whoami_guess(body: WhoamiTextIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.guess, prof["id"], body.text)
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/giveup")
def whoami_give_up(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werbinich.give_up, prof["id"])
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/skip")
def whoami_skip(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads passes the turn on (e.g. somebody left the table)."""
    fq = app_of(request)
    _lead_whoami(fq, prof)
    _run(fq.werbinich.skip, prof["id"])
    return fq.werbinich.state("werbinich", prof["id"])


@router.post("/werbinich/end")
def whoami_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_whoami(fq, prof)
    fq.werbinich.end("werbinich", prof["id"])
    return fq.werbinich.state("werbinich", prof["id"])


# ---------------------------------------------------------------- Kartenlauf (familyquest/kartenlauf.py)
class KartenlaufStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    seats: int | None = None             # 2 | 3 | 4 (bots fill the free seats)
    teams: bool | None = None            # 4 players: teams of two (partners opposite)
    seven_partner: bool | None = None    # a 7 may move the partner's marbles too
    joker_last: bool | None = None       # the joker may be the card that wins
    level: str | None = None             # easy | normal | hard
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    bot_ids: list[int | str] = []


class KartenlaufPlayIn(BaseModel):
    card: str
    kind: str | None = None              # out | move | back | swap | seven (empty: from the card)
    marble: str | None = None            # "<player id>:<0-3>"
    steps: int | None = None             # ace: 1 or 11
    home: bool | None = None             # into the home (True), on along the ring (False), empty: into the home if it can
    target: str | None = None            # jack: the other marble
    split: list[list[Any]] | None = None  # 7: [[marble, steps, home?], …]
    as_: str | None = Field(default=None, alias="as")   # joker: the card it stands for

    model_config = {"populate_by_name": True}

    def move(self) -> dict:
        d = self.model_dump(exclude={"as_"})
        d["as"] = self.as_
        return d


class KartenlaufGiveIn(BaseModel):
    card: str


def _lead_kartenlauf(fq, prof: dict) -> None:
    if not fq.kartenlauf.may_lead("kartenlauf", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/kartenlauf")
def kartenlauf_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).kartenlauf.state("kartenlauf", prof["id"])


@router.get("/kartenlauf/rules")
def kartenlauf_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).kartenlauf.rules_info()


@router.post("/kartenlauf/start")
def kartenlauf_start(body: KartenlaufStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _no_bots(fq, prof, "kartenlauf", body.solo or body.bot_ids)
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 3, body.level or "normal", BOTS)
    _run(fq.kartenlauf.start, "kartenlauf", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.kartenlauf.state("kartenlauf", prof["id"])


@router.post("/kartenlauf/join")
def kartenlauf_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.kartenlauf.join, "kartenlauf", prof["id"])
    return fq.kartenlauf.state("kartenlauf", prof["id"])


@router.post("/kartenlauf/begin")
def kartenlauf_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_kartenlauf(fq, prof)
    _run(fq.kartenlauf.begin, "kartenlauf", prof["id"], (body or BeginIn()).starter)
    return fq.kartenlauf.state("kartenlauf", prof["id"])


@router.post("/kartenlauf/give")
def kartenlauf_give(body: KartenlaufGiveIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.kartenlauf.give, "kartenlauf", prof["id"], body.card)
    return fq.kartenlauf.state("kartenlauf", prof["id"])


@router.post("/kartenlauf/play")
def kartenlauf_play(body: KartenlaufPlayIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.kartenlauf.play, "kartenlauf", prof["id"], body.move())
    return fq.kartenlauf.state("kartenlauf", prof["id"])


@router.post("/kartenlauf/end")
def kartenlauf_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_kartenlauf(fq, prof)
    fq.kartenlauf.end("kartenlauf", prof["id"])
    return fq.kartenlauf.state("kartenlauf", prof["id"])


# ---------------------------------------------------------------- «Stadt-Land-Fluss» (familyquest/stadtland.py)
class StadtlandStartIn(BaseModel):
    cats: list[str] | None = None        # built-in category keys (stadtland.CATS)
    own: list[str] | None = None         # up to 2 own categories
    rounds: int | None = None            # 3 | 5 | 8 | 10
    time: int | None = None              # seconds per round: 60 | 90 | 120 | 180 – 0: until «Stopp!»
    stopp: bool | None = None            # «Stopp!» gives the others 10 more seconds
    hard: bool | None = None             # also C, Q, X, Y


class StadtlandAnswersIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict, max_length=12)


class StadtlandVoteIn(BaseModel):
    target: str                          # the player whose answer
    cat: str                             # the category key
    reject: bool = True


class StadtlandOverrideIn(BaseModel):
    target: str
    cat: str
    valid: bool | None = None            # None: the votes decide again


class StadtlandReadyIn(BaseModel):
    ready: bool = True


def _lead_stadtland(fq, prof: dict) -> None:
    if not fq.stadtland.may_lead("stadtland", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/stadtland")
def stadtland_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).stadtland.state("stadtland", prof["id"])


@router.get("/stadtland/rules")
def stadtland_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).stadtland.rules_info()


@router.post("/stadtland/start")
def stadtland_start(body: StadtlandStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.stadtland.start, "stadtland", prof["id"], body.model_dump())
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/join")
def stadtland_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.stadtland.join, "stadtland", prof["id"])
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/begin")
def stadtland_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_stadtland(fq, prof)
    _run(fq.stadtland.begin, "stadtland", prof["id"])
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/answers")
def stadtland_answers(body: StadtlandAnswersIn, request: Request, prof: dict = Playing) -> dict | None:
    """Autosave while typing (debounced by the app) – accepted until shortly after the time is up."""
    fq = app_of(request)
    _run(fq.stadtland.save, prof["id"], body.answers)
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/stopp")
def stadtland_stopp(request: Request, body: StadtlandAnswersIn | None = None, prof: dict = Playing) -> dict | None:
    """«Stopp!»: the last answers come along, then the others get a few more seconds."""
    fq = app_of(request)
    if body and body.answers:
        _run(fq.stadtland.save, prof["id"], body.answers)
    _run(fq.stadtland.stopp, prof["id"])
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/vote")
def stadtland_vote(body: StadtlandVoteIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.stadtland.vote, prof["id"], body.target, body.cat, body.reject)
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/ready")
def stadtland_ready(request: Request, body: StadtlandReadyIn | None = None, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.stadtland.ready, prof["id"], body.ready if body else True)
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/override")
def stadtland_override(body: StadtlandOverrideIn, request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads decides an answer – wins over the votes."""
    fq = app_of(request)
    _lead_stadtland(fq, prof)
    _run(fq.stadtland.override, prof["id"], body.target, body.cat, body.valid)
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/next")
def stadtland_next(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads goes on: closes the writing, the review, or starts the next round."""
    fq = app_of(request)
    _lead_stadtland(fq, prof)
    _run(fq.stadtland.next, prof["id"])
    return fq.stadtland.state("stadtland", prof["id"])


@router.post("/stadtland/end")
def stadtland_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_stadtland(fq, prof)
    fq.stadtland.end("stadtland", prof["id"])
    return fq.stadtland.state("stadtland", prof["id"])


# ---------------------------------------------------------------- «Fünf Würfel» (familyquest/wuerfel.py)
class WuerfelStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    bots: int | None = None              # 0–5 bots at the table (alone: at least 1)
    level: str | None = None             # easy | normal | hard
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    extra: bool | None = None            # +50 for every further «Fünfling»
    bot_ids: list[int | str] = []


class WuerfelRollIn(BaseModel):
    held: list[bool] | None = Field(default=None, max_length=5)     # the dice to keep (from the 2nd roll on)


class WuerfelHoldIn(BaseModel):
    held: list[bool] = Field(max_length=5)


class WuerfelChooseIn(BaseModel):
    cat: str = Field(max_length=30)


def _lead_wuerfel(fq, prof: dict) -> None:
    if not fq.wuerfel.may_lead("wuerfel", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/wuerfel")
def wuerfel_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).wuerfel.state("wuerfel", prof["id"])


@router.get("/wuerfel/rules")
def wuerfel_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).wuerfel.rules_info()


@router.post("/wuerfel/start")
def wuerfel_start(body: WuerfelStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "wuerfel", body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 5, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "wuerfel", forced):
        _run(fq.wuerfel.start, "wuerfel", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/join")
def wuerfel_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.wuerfel.join, "wuerfel", prof["id"])
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/begin")
def wuerfel_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_wuerfel(fq, prof)
    _run(fq.wuerfel.begin, "wuerfel", prof["id"])
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/roll")
def wuerfel_roll(request: Request, body: WuerfelRollIn | None = None, prof: dict = Playing) -> dict | None:
    """Roll the dice that are not held (the server rolls – the app only animates)."""
    fq = app_of(request)
    _run(fq.wuerfel.roll, prof["id"], body.held if body else None)
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/hold")
def wuerfel_hold(body: WuerfelHoldIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.wuerfel.hold, prof["id"], body.held)
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/choose")
def wuerfel_choose(body: WuerfelChooseIn, request: Request, prof: dict = Playing) -> dict | None:
    """Fill (or cross out) a free box of the own sheet with the current dice."""
    fq = app_of(request)
    _run(fq.wuerfel.choose, prof["id"], body.cat)
    return fq.wuerfel.state("wuerfel", prof["id"])


@router.post("/wuerfel/end")
def wuerfel_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_wuerfel(fq, prof)
    fq.wuerfel.end("wuerfel", prof["id"])
    return fq.wuerfel.state("wuerfel", prof["id"])


# ---------------------------------------------------------------- «Heimwärts» (familyquest/heimwaerts.py)
class HeimwaertsStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    bots: int | None = None              # 0–3 bots at the table (alone: at least 1)
    level: str | None = None             # easy | normal | hard
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    bench: bool | None = None            # «Eile-mit-Weile-Bänkli»: safe fields nobody may hit or pass
    exact: bool | None = None            # the exact number is needed to go into the home
    play_on: bool | None = None          # after the winner the others play on for the places
    bot_ids: list[int | str] = []


class HeimwaertsMoveIn(BaseModel):
    piece: int = Field(ge=0, le=3)


def _lead_heimwaerts(fq, prof: dict) -> None:
    if not fq.heimwaerts.may_lead("heimwaerts", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/heimwaerts")
def heimwaerts_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).heimwaerts.state("heimwaerts", prof["id"])


@router.get("/heimwaerts/rules")
def heimwaerts_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).heimwaerts.rules_info()


@router.post("/heimwaerts/start")
def heimwaerts_start(body: HeimwaertsStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "heimwaerts", body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 3, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "heimwaerts", forced):
        _run(fq.heimwaerts.start, "heimwaerts", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.heimwaerts.state("heimwaerts", prof["id"])


@router.post("/heimwaerts/join")
def heimwaerts_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.heimwaerts.join, "heimwaerts", prof["id"])
    return fq.heimwaerts.state("heimwaerts", prof["id"])


@router.post("/heimwaerts/begin")
def heimwaerts_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_heimwaerts(fq, prof)
    _run(fq.heimwaerts.begin, "heimwaerts", prof["id"], (body or BeginIn()).starter)
    return fq.heimwaerts.state("heimwaerts", prof["id"])


@router.post("/heimwaerts/roll")
def heimwaerts_roll(request: Request, prof: dict = Playing) -> dict | None:
    """Roll the die (the server rolls – the app only animates)."""
    fq = app_of(request)
    _run(fq.heimwaerts.roll, prof["id"])
    return fq.heimwaerts.state("heimwaerts", prof["id"])


@router.post("/heimwaerts/move")
def heimwaerts_move(body: HeimwaertsMoveIn, request: Request, prof: dict = Playing) -> dict | None:
    """Move one of the own pieces by the number rolled (only legal moves)."""
    fq = app_of(request)
    _run(fq.heimwaerts.move, prof["id"], body.piece)
    return fq.heimwaerts.state("heimwaerts", prof["id"])


@router.post("/heimwaerts/end")
def heimwaerts_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_heimwaerts(fq, prof)
    fq.heimwaerts.end("heimwaerts", prof["id"])
    return fq.heimwaerts.state("heimwaerts", prof["id"])


# ---------------------------------------------------------------- «Jump» (familyquest/jump.py)
class JumpStartIn(BaseModel):
    solo: bool = False                   # alone (private) – optionally with practice bots
    bots: int | None = None              # 0–5 bots
    level: str | None = None             # easy | normal | hard
    lives: int | None = None             # 1 | 3 | 5
    bot_ids: list[int | str] = []


class JumpSyncIn(BaseModel):
    t: float | None = None                                   # the game time of the app (seconds)
    jumps: list[float] = Field(default_factory=list, max_length=40)   # new jumps (game times)
    hits: list[list[float]] = Field(default_factory=list, max_length=20)   # new hits: [obstacle index, game time]


def _lead_jump(fq, prof: dict) -> None:
    if not fq.jump.may_lead("jump", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/jump")
def jump_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).jump.state("jump", prof["id"])


@router.get("/jump/rules")
def jump_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).jump.rules_info()


@router.post("/jump/start")
def jump_start(body: JumpStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "jump", body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 5, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "jump", forced):
        _run(fq.jump.start, "jump", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.jump.state("jump", prof["id"])


@router.post("/jump/join")
def jump_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.jump.join, "jump", prof["id"])
    return fq.jump.state("jump", prof["id"])


@router.post("/jump/begin")
def jump_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_jump(fq, prof)
    _run(fq.jump.begin, "jump", prof["id"])
    return fq.jump.state("jump", prof["id"])


@router.post("/jump/sync")
def jump_sync(body: JumpSyncIn, request: Request, prof: dict = Playing) -> dict | None:
    """The app reports its own jumps and hits (only its own player) and gets the others' lanes back."""
    fq = app_of(request)
    return _run(fq.jump.report, prof["id"], body.t, body.jumps, body.hits)


@router.post("/jump/end")
def jump_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_jump(fq, prof)
    fq.jump.end("jump", prof["id"])
    return fq.jump.state("jump", prof["id"])


# ---------------------------------------------------------------- «Star Runner» (familyquest/sternlauf.py)
class SternlaufStartIn(BaseModel):
    solo: bool = False                   # alone (private) – optionally with practice bots
    bots: int | None = None              # 0–7 bots
    level: str | None = None             # easy | normal | hard
    lives: int | None = None             # 1 | 3 | 5
    minutes: int | None = None           # 2 | 3 | 5
    bot_ids: list[int | str] = []


class SternlaufSyncIn(BaseModel):
    # the app's own new inputs: [game time (s), "l" | "r" | "u" | "d"] – the server replays them on the course
    inputs: list[tuple[float, str]] = Field(default_factory=list, max_length=40)


def _lead_sternlauf(fq, prof: dict) -> None:
    if not fq.sternlauf.may_lead("sternlauf", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/sternlauf")
def sternlauf_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).sternlauf.state("sternlauf", prof["id"])


@router.get("/sternlauf/rules")
def sternlauf_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).sternlauf.rules_info()


@router.post("/sternlauf/start")
def sternlauf_start(body: SternlaufStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    if _no_bots(fq, prof, "sternlauf", body.bot_ids or (body.bots or 0) > 0):
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 7, body.level or "normal", BOTS)
    _run(fq.sternlauf.start, "sternlauf", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.sternlauf.state("sternlauf", prof["id"])


@router.post("/sternlauf/join")
def sternlauf_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.sternlauf.join, "sternlauf", prof["id"])
    return fq.sternlauf.state("sternlauf", prof["id"])


@router.post("/sternlauf/begin")
def sternlauf_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_sternlauf(fq, prof)
    _run(fq.sternlauf.begin, "sternlauf", prof["id"])
    return fq.sternlauf.state("sternlauf", prof["id"])


@router.post("/sternlauf/sync")
def sternlauf_sync(body: SternlaufSyncIn, request: Request, prof: dict = Playing) -> dict | None:
    """The app reports its own inputs (only its own runner) and gets everybody's progress back."""
    fq = app_of(request)
    return _run(fq.sternlauf.report, prof["id"], body.inputs)


@router.post("/sternlauf/end")
def sternlauf_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_sternlauf(fq, prof)
    fq.sternlauf.end("sternlauf", prof["id"])
    return fq.sternlauf.state("sternlauf", prof["id"])


# ---------------------------------------------------------------- «Snack Rush» (familyquest/snack.py)
class SnackStartIn(BaseModel):
    solo: bool = False                   # alone (private) – optionally with practice bots
    bots: int | None = None              # 0–5 bots
    level: str | None = None             # easy | normal | hard
    mode: str | None = None              # t3 | t5 | t8 (minutes)
    limit: int | None = None             # 0 (off) | 3 | 5 | 8 angry customers: out
    foods: str | None = Field(default=None, max_length=200)    # "burger,fries,…"
    bot_ids: list[int | str] = []


class SnackSyncIn(BaseModel):
    t: float | None = None                                               # the game time of the app (seconds)
    serves: list[list[float]] = Field(default_factory=list, max_length=30)   # [customer index, game time]
    angry: list[int] = Field(default_factory=list, max_length=30)            # customers that left angry
    spent: float | None = None                                           # money spent on ingredients so far


def _lead_snack(fq, prof: dict) -> None:
    if not fq.snack.may_lead("snack", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/snack")
def snack_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).snack.state("snack", prof["id"])


@router.get("/snack/rules")
def snack_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).snack.rules_info()


@router.post("/snack/start")
def snack_start(body: SnackStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "snack", body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 5, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "snack", forced):
        _run(fq.snack.start, "snack", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.snack.state("snack", prof["id"])


@router.post("/snack/join")
def snack_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.snack.join, "snack", prof["id"])
    return fq.snack.state("snack", prof["id"])


@router.post("/snack/begin")
def snack_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_snack(fq, prof)
    _run(fq.snack.begin, "snack", prof["id"])
    return fq.snack.state("snack", prof["id"])


@router.post("/snack/sync")
def snack_sync(body: SnackSyncIn, request: Request, prof: dict = Playing) -> dict | None:
    """The app reports its own serves, angry customers and spent money (only its own stand) and gets the others back."""
    fq = app_of(request)
    return _run(fq.snack.report, prof["id"], body.t, body.serves, body.angry, body.spent)


@router.post("/snack/end")
def snack_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_snack(fq, prof)
    fq.snack.end("snack", prof["id"])
    return fq.snack.state("snack", prof["id"])


# ---------------------------------------------------------------- «Traffic Cadet» (familyquest/verkehr.py)
class VerkehrStartIn(BaseModel):
    solo: bool = False                   # alone (private) – optionally with practice bots
    bots: int | None = None              # 0–5 bots
    level: str | None = None             # the bots: easy | normal | hard
    difficulty: str | None = None        # the traffic: easy | normal | hard
    worlds: int | None = None            # 1–5
    bot_ids: list[int | str] = []


class VerkehrSyncIn(BaseModel):
    t: float | None = None                                   # the game time of the app (seconds)
    events: list[list[int]] = Field(default_factory=list, max_length=40)   # new switches: [global tick, group, 1 green / 0 red]


def _lead_verkehr(fq, prof: dict) -> None:
    if not fq.verkehr.may_lead("verkehr", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/verkehr")
def verkehr_state(request: Request, mine: bool = False, prof: dict = Playing) -> dict | None:
    """The table – with mine=1 also my map as the server has it (the app starts its own map from it)."""
    return app_of(request).verkehr.state("verkehr", prof["id"], mine=mine)


@router.get("/verkehr/worlds")
def verkehr_worlds(request: Request, prof: dict = Playing) -> dict | None:
    """The worlds of my game: street layouts and cars (the same for everybody)."""
    return app_of(request).verkehr.worlds(prof["id"])


@router.get("/verkehr/rules")
def verkehr_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).verkehr.rules_info()


@router.post("/verkehr/start")
def verkehr_start(body: VerkehrStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "verkehr", body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 5, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "verkehr", forced):
        _run(fq.verkehr.start, "verkehr", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.verkehr.state("verkehr", prof["id"], mine=True)


@router.post("/verkehr/join")
def verkehr_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.verkehr.join, "verkehr", prof["id"])
    return fq.verkehr.state("verkehr", prof["id"])


@router.post("/verkehr/begin")
def verkehr_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_verkehr(fq, prof)
    _run(fq.verkehr.begin, "verkehr", prof["id"])
    return fq.verkehr.state("verkehr", prof["id"], mine=True)


@router.post("/verkehr/sync")
def verkehr_sync(body: VerkehrSyncIn, request: Request, mine: bool = False, prof: dict = Playing) -> dict | None:
    """The app reports its own light switches (only its own map) and gets everybody's stats back – rejected switches
    («rej») come with my map as the server has it."""
    fq = app_of(request)
    out = _run(fq.verkehr.report, prof["id"], body.t, body.events)
    if mine and out and out.get("phase") == "play" and "my" not in out:
        out = {**fq.verkehr.state("verkehr", prof["id"], mine=True), "rej": out.get("rej", [])}
    return out


@router.post("/verkehr/end")
def verkehr_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_verkehr(fq, prof)
    fq.verkehr.end("verkehr", prof["id"])
    return fq.verkehr.state("verkehr", prof["id"])


# ---------------------------------------------------------------- «Klatsch den Beat» (familyquest/klatsch.py)
class KlatschStartIn(BaseModel):
    solo: bool = False                   # alone (private) – optionally with practice bots
    bots: int | None = None              # 0–7 bots
    level: str | None = None             # easy | normal | hard
    rounds: int | None = None            # 5–8
    bot_ids: list[int | str] = []


class KlatschSyncIn(BaseModel):
    round: int | None = None                                       # the round of these taps
    taps: list[float] = Field(default_factory=list, max_length=64)  # the taps of this round (game times, delay subtracted)


def _lead_klatsch(fq, prof: dict) -> None:
    if not fq.klatsch.may_lead("klatsch", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/klatsch")
def klatsch_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).klatsch.state("klatsch", prof["id"])


@router.get("/klatsch/rules")
def klatsch_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).klatsch.rules_info()


@router.post("/klatsch/start")
def klatsch_start(body: KlatschStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "klatsch", body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 7, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "klatsch", forced):
        _run(fq.klatsch.start, "klatsch", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.klatsch.state("klatsch", prof["id"])


@router.post("/klatsch/join")
def klatsch_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.klatsch.join, "klatsch", prof["id"])
    return fq.klatsch.state("klatsch", prof["id"])


@router.post("/klatsch/begin")
def klatsch_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_klatsch(fq, prof)
    _run(fq.klatsch.begin, "klatsch", prof["id"])
    return fq.klatsch.state("klatsch", prof["id"])


@router.post("/klatsch/sync")
def klatsch_sync(body: KlatschSyncIn, request: Request, prof: dict = Playing) -> dict | None:
    """The app reports the taps of its own player for a round and gets the state back (scores, ranking)."""
    fq = app_of(request)
    return _run(fq.klatsch.report, prof["id"], body.round, body.taps)


@router.post("/klatsch/end")
def klatsch_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_klatsch(fq, prof)
    fq.klatsch.end("klatsch", prof["id"])
    return fq.klatsch.state("klatsch", prof["id"])


# ---------------------------------------------------------------- «Zeichnen & Raten» (familyquest/zeichnen.py)
class ZeichnenStartIn(BaseModel):
    category: str | None = None          # zeichnen_data.CATEGORIES
    rounds: int | None = None            # 1 | 2 | 3 – everybody draws that many times
    time: int | None = None              # seconds per drawing: 60 | 80 | 120
    hints: bool | None = None            # letters shown at 50 % and 75 % of the time


class ZeichnenChooseIn(BaseModel):
    idx: int


class ZeichnenDrawIn(BaseModel):
    turn: int | None = None              # the turn the strokes belong to (late batches of the last turn are refused)
    ops: list[dict[str, Any]] = Field(default_factory=list, max_length=60)


class ZeichnenGuessIn(BaseModel):
    text: str = Field(max_length=200)


def _lead_zeichnen(fq, prof: dict) -> None:
    if not fq.zeichnen.may_lead("zeichnen", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/zeichnen")
def zeichnen_state(request: Request, n: int | None = None, pl: int = 0, t: int | None = None, prof: dict = Playing) -> dict | None:
    """The view; with the cursor n (events the app has), pl (points of its last event) and t (the turn) only the new
    strokes of the drawing come along."""
    return app_of(request).zeichnen.state("zeichnen", prof["id"], n, pl, t)


@router.get("/zeichnen/rules")
def zeichnen_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).zeichnen.rules_info()


@router.post("/zeichnen/start")
def zeichnen_start(body: ZeichnenStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.zeichnen.start, "zeichnen", prof["id"], body.model_dump())
    return fq.zeichnen.state("zeichnen", prof["id"])


@router.post("/zeichnen/join")
def zeichnen_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.zeichnen.join, "zeichnen", prof["id"])
    return fq.zeichnen.state("zeichnen", prof["id"])


@router.post("/zeichnen/begin")
def zeichnen_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_zeichnen(fq, prof)
    _run(fq.zeichnen.begin, "zeichnen", prof["id"], (body or BeginIn()).starter)
    return fq.zeichnen.state("zeichnen", prof["id"])


@router.post("/zeichnen/choose")
def zeichnen_choose(body: ZeichnenChooseIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.zeichnen.choose, prof["id"], body.idx)
    return fq.zeichnen.state("zeichnen", prof["id"])


@router.post("/zeichnen/draw")
def zeichnen_draw(body: ZeichnenDrawIn, request: Request, prof: dict = Playing) -> dict:
    """A batch of strokes of the drawer (sent every ~120 ms while drawing) – a short answer, not the whole view."""
    return _run(app_of(request).zeichnen.draw, prof["id"], body.ops, body.turn)


@router.post("/zeichnen/guess")
def zeichnen_guess(body: ZeichnenGuessIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    res = _run(fq.zeichnen.guess, prof["id"], body.text)
    return {**(fq.zeichnen.state("zeichnen", prof["id"]) or {}), "result": res}


@router.post("/zeichnen/skip")
def zeichnen_skip(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads skips the turn (e.g. the drawer left)."""
    fq = app_of(request)
    _lead_zeichnen(fq, prof)
    _run(fq.zeichnen.skip, prof["id"])
    return fq.zeichnen.state("zeichnen", prof["id"])


@router.post("/zeichnen/end")
def zeichnen_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_zeichnen(fq, prof)
    fq.zeichnen.end("zeichnen", prof["id"])
    return fq.zeichnen.state("zeichnen", prof["id"])


# ---------------------------------------------------------------- «Verbotene Wörter» (familyquest/verboten.py)
class VerbotenStartIn(BaseModel):
    level: str | None = None             # easy | normal | mixed
    time: int | None = None              # seconds per turn: 30 | 45 | 60 | 90 | 120
    rounds: int | None = None            # 1 – 4: how often everybody explains
    teams: bool | None = None            # two teams with 4 or more players
    skip_penalty: int | None = None      # 0 | 1 point for «Skip»


class VerbotenMarkIn(BaseModel):
    n: int                               # the number of the card the tap means (a late tap counts nothing)
    result: str                          # got | taboo | pass (the explainer) | buzz (the other team)
    guesser: str | None = None           # alone: who guessed it


def _lead_verboten(fq, prof: dict) -> None:
    if not fq.verboten.may_lead("verboten", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/verboten")
def verboten_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).verboten.state("verboten", prof["id"])


@router.get("/verboten/rules")
def verboten_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).verboten.rules_info()


@router.post("/verboten/start")
def verboten_start(body: VerbotenStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.verboten.start, "verboten", prof["id"], body.model_dump())
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/join")
def verboten_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.verboten.join, "verboten", prof["id"])
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/mix")
def verboten_mix(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads mixes the seats (and so the teams) in the lobby."""
    fq = app_of(request)
    _lead_verboten(fq, prof)
    _run(fq.verboten.mix, prof["id"])
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/begin")
def verboten_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_verboten(fq, prof)
    _run(fq.verboten.begin, "verboten", prof["id"], (body or BeginIn()).starter)
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/go")
def verboten_go(request: Request, prof: dict = Playing) -> dict | None:
    """The explainer is ready: the clock starts, the first card comes."""
    fq = app_of(request)
    _run(fq.verboten.go, prof["id"])
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/mark")
def verboten_mark(body: VerbotenMarkIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.verboten.mark, prof["id"], body.n, body.result, body.guesser)
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/skip")
def verboten_skip(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads skips the turn (e.g. the explainer left)."""
    fq = app_of(request)
    _lead_verboten(fq, prof)
    _run(fq.verboten.skip, prof["id"])
    return fq.verboten.state("verboten", prof["id"])


@router.post("/verboten/end")
def verboten_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_verboten(fq, prof)
    fq.verboten.end("verboten", prof["id"])
    return fq.verboten.state("verboten", prof["id"])


# ---------------------------------------------------------------- «Escape Room» (familyquest/escape.py)
class EscapeStartIn(BaseModel):
    rooms: int | None = None             # 1 – 5
    level: str | None = None             # easy | medium | hard | mixed
    types: list[str] | None = Field(default=None, max_length=20)   # kinds of riddles (escape_riddles.TYPES)
    mode: str | None = None              # together | teams
    time: int | None = None              # minutes: 0 (none) | 15 | 30 | 45


class EscapeKeyIn(BaseModel):
    key: str = Field(max_length=12)      # the riddle: "<room>.<number>"


class EscapeAnswerIn(BaseModel):
    key: str | None = Field(default=None, max_length=12)     # the riddle (none: the door)
    answer: list[int] | int | str | None = None              # text / number, a choice, or a list (order, moves …)


def _lead_escape(fq, prof: dict) -> None:
    if not fq.escape.may_lead("escape", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/escape")
def escape_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).escape.state("escape", prof["id"])


@router.get("/escape/rules")
def escape_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).escape.rules_info()


@router.post("/escape/start")
def escape_start(body: EscapeStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.escape.start, "escape", prof["id"], body.model_dump())
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/join")
def escape_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.escape.join, "escape", prof["id"])
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/mix")
def escape_mix(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads mixes the seats (and so the teams) in the lobby."""
    fq = app_of(request)
    _lead_escape(fq, prof)
    _run(fq.escape.mix, prof["id"])
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/begin")
def escape_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_escape(fq, prof)
    _run(fq.escape.begin, "escape", prof["id"])
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/answer")
def escape_answer(body: EscapeAnswerIn, request: Request, prof: dict = Playing) -> dict:
    """An answer for a riddle of the own team's room – or (without key) the code of the door. {"ok": …, "state": …}"""
    fq = app_of(request)
    a = body.answer
    if (isinstance(a, str) and len(a) > 60) or (isinstance(a, list) and len(a) > 400):
        raise HTTPException(400, "This answer is too long")
    ok = _run(fq.escape.door, prof["id"], a) if body.key is None else _run(fq.escape.answer, prof["id"], body.key, a)
    return {"ok": bool(ok), "state": fq.escape.state("escape", prof["id"])}


@router.post("/escape/hint")
def escape_hint(body: EscapeKeyIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.escape.hint, prof["id"], body.key)
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/peek")
def escape_peek(body: EscapeKeyIn, request: Request, prof: dict = Playing) -> dict | None:
    """A memory riddle: its picture for a few seconds."""
    fq = app_of(request)
    _run(fq.escape.peek, prof["id"], body.key)
    return fq.escape.state("escape", prof["id"])


@router.post("/escape/end")
def escape_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_escape(fq, prof)
    fq.escape.end("escape", prof["id"])
    return fq.escape.state("escape", prof["id"])


# ---------------------------------------------------------------- «Jass» – Schieber (familyquest/jass.py)
class JassStartIn(BaseModel):
    solo: bool = False                   # alone with 3 bots (private)
    deck: str | None = None              # swiss | french
    level: str | None = None             # easy | normal | hard
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    weis: bool | None = None             # Weis declared with the first card
    stoeck: bool | None = None           # König + Ober of trump: 20
    mult: bool | None = None             # multipliers ×1 / ×2 / ×3
    goal: str | None = None              # points | rounds
    target: int | None = None            # points to win (goal «points»)
    rounds: int | None = None            # rounds to play (goal «rounds»)
    partners: bool | None = None         # two people with two bots play as partners
    back: str | None = None              # card back
    bot_ids: list[int | str] = []


class JassTrumpIn(BaseModel):
    mode: str = Field(max_length=12)     # a suit, obe, une – or push


class JassPlayIn(BaseModel):
    card: str = Field(max_length=16)


def _lead_jass(fq, prof: dict) -> None:
    if not fq.jass.may_lead("jass", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/jass")
def jass_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).jass.state("jass", prof["id"])


@router.get("/jass/rules")
def jass_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).jass.rules_info()


@router.post("/jass/start")
def jass_start(body: JassStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _no_bots(fq, prof, "jass", body.solo or body.bot_ids)
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 3, body.level or "normal", BOTS)
    _run(fq.jass.start, "jass", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/join")
def jass_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.jass.join, "jass", prof["id"])
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/mix")
def jass_mix(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_jass(fq, prof)
    _run(fq.jass.mix, prof["id"])
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/begin")
def jass_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_jass(fq, prof)
    _run(fq.jass.begin, "jass", prof["id"])
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/trump")
def jass_trump(body: JassTrumpIn, request: Request, prof: dict = Playing) -> dict | None:
    """Announce the trump (a suit, Obenabe «obe», Undeufe «une») – or push it to the partner («push»)."""
    fq = app_of(request)
    _run(fq.jass.choose, prof["id"], body.mode)
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/play")
def jass_play(body: JassPlayIn, request: Request, prof: dict = Playing) -> dict | None:
    """Play one of the own cards (only legal cards – the server checks)."""
    fq = app_of(request)
    _run(fq.jass.play_card, prof["id"], body.card)
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/next")
def jass_next(request: Request, prof: dict = Playing) -> dict | None:
    """Everybody at the table may deal the next round without waiting for the round result to go."""
    fq = app_of(request)
    _run(fq.jass.next_round, prof["id"])
    return fq.jass.state("jass", prof["id"])


@router.post("/jass/end")
def jass_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_jass(fq, prof)
    fq.jass.end("jass", prof["id"])
    return fq.jass.state("jass", prof["id"])


# ---------------------------------------------------------------- «Werwölfe» (familyquest/werwolf.py)
class WerwolfRulesIn(BaseModel):
    auto: bool | None = None             # the role set by the number of players
    wolves: int | None = None            # 1 – 3 (custom)
    seer: bool | None = None
    witch: bool | None = None
    hunter: bool | None = None
    amor: bool | None = None
    talk: int | None = None              # seconds to talk during the day: 60 | 120 | 180 | 300 | 600
    fill: int | None = None              # bots fill the table up to this number of players: 5 – 12


class WerwolfActIn(BaseModel):
    action: str                          # lovers | bite | look | sleep | potion | shoot | vote
    target: str | None = None
    target2: str | None = None           # amor: the second lover
    heal: bool = False                   # witch
    poison: str | None = None            # witch


def _lead_werwolf(fq, prof: dict) -> None:
    if not fq.werwolf.may_lead("werwolf", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/werwolf")
def werwolf_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).werwolf.state("werwolf", prof["id"])


@router.get("/werwolf/rules")
def werwolf_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).werwolf.rules_info()


@router.post("/werwolf/rules")
def werwolf_set_rules(body: WerwolfRulesIn, request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads changes the roles in the lobby (when everybody is there)."""
    fq = app_of(request)
    _lead_werwolf(fq, prof)
    _run(fq.werwolf.set_rules, prof["id"], body.model_dump())
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/start")
def werwolf_start(body: WerwolfRulesIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.werwolf.start, "werwolf", prof["id"], body.model_dump())
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/join")
def werwolf_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werwolf.join, "werwolf", prof["id"])
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/begin")
def werwolf_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_werwolf(fq, prof)
    _run(fq.werwolf.begin, "werwolf", prof["id"])
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/act")
def werwolf_act(body: WerwolfActIn, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.werwolf.act, prof["id"], body.action, body.target, body.target2, body.heal, body.poison)
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/next")
def werwolf_next(request: Request, prof: dict = Gamer) -> dict | None:
    """Who leads moves on (night falls, somebody is idle, the vote starts / closes)."""
    fq = app_of(request)
    _lead_werwolf(fq, prof)
    _run(fq.werwolf.advance, prof["id"])
    return fq.werwolf.state("werwolf", prof["id"])


@router.post("/werwolf/end")
def werwolf_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_werwolf(fq, prof)
    fq.werwolf.end("werwolf", prof["id"])
    return fq.werwolf.state("werwolf", prof["id"])


# ---------------------------------------------------------------- «Schach» (familyquest/schach.py) – several games at a time, by id
class SchachStartIn(BaseModel):
    mode: str = "bot"                    # bot | duel | local
    level: str | None = None             # bot: easy | normal | hard
    color: str | None = None             # white | black | random
    clock: int | None = None             # minutes per side: 0 | 5 | 10 | 15
    opponent: int | None = None          # duel: the invited person (None: open for anybody of the family, guests via QR)


class SchachMoveIn(BaseModel):
    frm: str = Field(max_length=2)
    to: str = Field(max_length=2)
    promo: str | None = Field(default=None, max_length=1)


class SchachDrawIn(BaseModel):
    action: str                          # offer | accept | decline


def _schach_family(fq, prof: dict) -> list[dict]:
    """Who of the family can be invited to a duel (chess switched on for them)."""
    out = []
    for p in fq.db.q("SELECT * FROM profile WHERE archived=0 AND role IN ('kid','parent') ORDER BY role DESC, name"):
        if p["id"] != prof["id"] and fq.games_allowed(p, "schach"):
            out.append({"id": p["id"], "name": p["name"], "avatar": fq.profile_public(p)["avatar"]})
    return out


@router.get("/schach")
def schach_overview(request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    out = fq.schach.overview(prof["id"], prof["role"] == "parent")
    out["family"] = _schach_family(fq, prof) if prof["role"] != "guest" else []
    return out


@router.post("/schach/start")
def schach_start(body: SchachStartIn, request: Request, prof: dict = Gamer) -> dict:
    fq = app_of(request)
    if prof["role"] == "guest":
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    _no_bots(fq, prof, "schach", body.mode == "bot")
    gid = _run(fq.schach.start, prof["id"], body.model_dump(exclude={"opponent"}), body.opponent)
    return _run(fq.schach.state, gid, prof["id"])


@router.get("/schach/{gid}")
def schach_state(gid: int, request: Request, prof: dict = Playing) -> dict:
    return _run(app_of(request).schach.state, gid, prof["id"], prof["role"] == "parent")


@router.post("/schach/{gid}/join")
def schach_join(gid: int, request: Request, prof: dict = Gamer) -> dict:
    fq = app_of(request)
    if prof["role"] == "guest":
        raise HTTPException(403, "Guests join with the invitation")
    _run(fq.schach.join, "schach", prof["id"], gid)
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/move")
def schach_move(gid: int, body: SchachMoveIn, request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    _run(fq.schach.move, gid, prof["id"], body.frm, body.to, body.promo)
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/pause")
def schach_pause(gid: int, request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    _run(fq.schach.pause, gid, prof["id"])
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/resume")
def schach_resume(gid: int, request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    _run(fq.schach.resume, gid, prof["id"])
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/resign")
def schach_resign(gid: int, request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    _run(fq.schach.resign, gid, prof["id"])
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/draw")
def schach_draw(gid: int, body: SchachDrawIn, request: Request, prof: dict = Playing) -> dict:
    fq = app_of(request)
    _run(fq.schach.draw, gid, prof["id"], body.action)
    return _run(fq.schach.state, gid, prof["id"])


@router.post("/schach/{gid}/delete")
def schach_delete(gid: int, request: Request, prof: dict = Gamer) -> dict:
    """Who started the game or a parent deletes a paused game or an open invitation; the invited person declines."""
    fq = app_of(request)
    _run(fq.schach.delete, gid, prof)
    out = fq.schach.overview(prof["id"], prof["role"] == "parent")
    out["family"] = _schach_family(fq, prof)
    return out


# ---------------------------------------------------------------- «Dorfmarkt» (familyquest/dorfmarkt.py)
class DorfmarktStartIn(BaseModel):
    solo: bool = False                   # alone against bots (private)
    bots: int | None = None              # 0–5 bots at the table (alone: at least 1)
    level: str | None = None             # easy | normal | hard
    bot_ms: int | None = None            # reaction time of the bots in ms (0 = at once)
    mode: str | None = None              # rounds | time | classic
    rounds: int | None = None            # mode rounds: number of rounds (default 30)
    minutes: int | None = None           # mode time: minutes
    auction: bool | None = None          # a field nobody buys is auctioned (everybody bids once)
    mortgage: bool | None = None         # fields may be mortgaged
    money: int | None = None             # Taler at the start
    bot_ids: list[int | str] = []


class DorfmarktActIn(BaseModel):
    action: str = Field(max_length=20)   # roll | buy | skip | bid | end_turn | build | sell | mortgage | unmortgage | bail | use_card | liquidate | give_up | offer | answer | cancel
    field: int | None = Field(default=None, ge=0, le=35)
    amount: int | None = Field(default=None, ge=0, le=1_000_000)
    step: int | None = Field(default=None, ge=0, le=1000)     # bid: +10 / +25 / +50 over the current price
    to: str | None = Field(default=None, max_length=20)
    give: list[int] = Field(default=[], max_length=36)
    give_money: int = Field(default=0, ge=0, le=1_000_000)
    want: list[int] = Field(default=[], max_length=36)
    want_money: int = Field(default=0, ge=0, le=1_000_000)
    trade: str | None = Field(default=None, max_length=20)
    accept: bool = False


def _lead_dorfmarkt(fq, prof: dict) -> None:
    if not fq.dorfmarkt.may_lead("dorfmarkt", prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/dorfmarkt")
def dorfmarkt_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).dorfmarkt.state("dorfmarkt", prof["id"])


@router.get("/dorfmarkt/board")
def dorfmarkt_board(request: Request, prof: dict = Playing) -> list:
    from ..dorfmarkt import board
    return board()


@router.get("/dorfmarkt/rules")
def dorfmarkt_rules(request: Request, prof: dict = Gamer) -> dict:
    return app_of(request).dorfmarkt.rules_info()


@router.post("/dorfmarkt/start")
def dorfmarkt_start(body: DorfmarktStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    forced = _no_bots(fq, prof, "dorfmarkt", body.solo or body.bot_ids or (body.bots or 0) > 0)
    if forced:
        body.bots = 0
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        bots = fq.bots.pick(prof["id"], body.bot_ids, 5, body.level or "normal", BOTS)
    with _bots_not_remembered(fq, "dorfmarkt", forced):
        _run(fq.dorfmarkt.start, "dorfmarkt", prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


@router.post("/dorfmarkt/join")
def dorfmarkt_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.dorfmarkt.join, "dorfmarkt", prof["id"])
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


@router.post("/dorfmarkt/begin")
def dorfmarkt_begin(request: Request, body: BeginIn | None = None, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_dorfmarkt(fq, prof)
    _run(fq.dorfmarkt.begin, "dorfmarkt", prof["id"], (body or BeginIn()).starter)
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


@router.post("/dorfmarkt/act")
def dorfmarkt_act(body: DorfmarktActIn, request: Request, prof: dict = Playing) -> dict | None:
    """One move of the own player (the server rolls the dice and checks every rule)."""
    fq = app_of(request)
    _run(fq.dorfmarkt.act, prof["id"], body.action, body.model_dump(exclude={"action"}))
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


@router.post("/dorfmarkt/pause")
def dorfmarkt_pause(body: PauseIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_dorfmarkt(fq, prof)
    _run(fq.dorfmarkt.pause, prof["id"], body.on)
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


@router.post("/dorfmarkt/end")
def dorfmarkt_end(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _lead_dorfmarkt(fq, prof)
    fq.dorfmarkt.end("dorfmarkt", prof["id"])
    return fq.dorfmarkt.state("dorfmarkt", prof["id"])


# ---------------------------------------------------------------- guests
class InviteIn(BaseModel):
    game: str                       # quiz | bingo
    on: bool = True
    gid: int | None = None          # chess: which game (an open seat)


class GuestJoinIn(BaseModel):
    code: str
    name: str


@router.post("/guests")
async def guests_invite(body: InviteIn, request: Request, prof: dict = Gamer) -> dict:
    """Everybody of the family who plays (not the guests) opens the invitation of a running family game – the QR code
    points to the guest page. Closing it stays with who leads the game."""
    from ..netinfo import home_access
    fq = app_of(request)
    if body.game == "schach":                         # several games: the open seat of this person's game (or a given one)
        g = fq.schach._game("schach", gid=body.gid) if body.gid else fq.schach._game("schach", host=prof["id"])
        if not g or not fq.schach.may_lead("schach", prof, g["id"]):
            raise HTTPException(400, "No game is running")
        try:
            inv = fq.guests.invite("schach", body.on, g["id"])
        except GuestError as e:
            raise HTTPException(400, str(e)) from None
        return {"invite": inv, "access": await home_access(fq.settings)}
    if body.game in ("tschau", "karussell", "domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "klatsch", "verboten", "jass", "werwolf", "dorfmarkt", "escape"):
        games = {"domino": fq.domino, "paarjagd": fq.paarjagd, "werbinich": fq.werbinich, "kartenlauf": fq.kartenlauf,
                 "stadtland": fq.stadtland, "zeichnen": fq.zeichnen, "wuerfel": fq.wuerfel, "heimwaerts": fq.heimwaerts, "jump": fq.jump, "verkehr": fq.verkehr, "sternlauf": fq.sternlauf, "snack": fq.snack, "klatsch": fq.klatsch, "verboten": fq.verboten,
                 "jass": fq.jass, "werwolf": fq.werwolf, "dorfmarkt": fq.dorfmarkt, "escape": fq.escape}.get(body.game, fq.cards)
        running, lead = games._game(body.game), games.may_lead(body.game, prof)
    else:
        game = {"quiz": fq.community, "bingo": fq.bingo, "poker": fq.poker, "song": fq.songs}.get(body.game)
        running, lead = (game._game() if game else None), bool(game) and game.may_lead(prof)
    if not running:
        raise HTTPException(400, "No game is running")
    if not body.on and not lead:
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    try:
        inv = fq.guests.invite(body.game, body.on)
    except GuestError as e:
        raise HTTPException(400, str(e)) from None
    return {"invite": inv, "access": await home_access(fq.settings)}


@router.get("/guest/info")
def guest_info(code: str, request: Request) -> dict:
    try:
        return app_of(request).guests.info(code)
    except GuestError as e:
        raise HTTPException(404, str(e)) from None


@router.post("/guest/join")
def guest_join(body: GuestJoinIn, request: Request) -> dict:
    fq = app_of(request)
    from .. import loginlog
    key = "guest:" + loginlog.client_ip(request)
    fq.throttle.check(key)
    try:
        out = fq.guests.join(body.code, body.name)
        fq.throttle.ok(key)
        return out
    except GuestError as e:
        fq.throttle.fail(key)
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------- family council
class TopicIn(BaseModel):
    title: str
    description: str = ""
    ideas: list[str] = []
    majority: str = "relative"
    both_sides: bool = False
    vote_now: bool = False


class TextIn(BaseModel):
    text: str


class VoteIn(BaseModel):
    proposal_id: int


@router.get("/council")
def council(request: Request, prof: dict = Learner) -> list[dict]:
    return app_of(request).community.topics(prof["id"])


@router.post("/council")
def council_open(body: TopicIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).community.open_topic, prof, body.title, body.description, body.ideas,
                       body.majority, body.both_sides, body.vote_now)}


@router.post("/council/{topic_id}/proposals")
def council_propose(topic_id: int, body: TextIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).community.propose, prof, topic_id, body.text)}


@router.delete("/council/proposals/{proposal_id}")
def council_unpropose(proposal_id: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.remove_proposal, prof, proposal_id)
    return {"ok": True}


class StartVoteIn(BaseModel):
    majority: str = "relative"           # relative | absolute | unanimous
    both_sides: bool = False             # the winner needs a parent's and a child's vote


class RevoteIn(BaseModel):
    runoff: bool = False                 # only the two strongest proposals


@router.post("/council/{topic_id}/start-vote")
def council_start_vote(topic_id: int, request: Request, body: StartVoteIn | None = None, prof: dict = Learner) -> dict:
    b = body or StartVoteIn()
    _run(app_of(request).community.start_vote, prof, topic_id, b.majority, b.both_sides)
    return {"ok": True}


@router.post("/council/{topic_id}/revote")
def council_revote(topic_id: int, body: RevoteIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.revote, prof, topic_id, body.runoff)
    return {"ok": True}


@router.post("/council/{topic_id}/vote")
def council_vote(topic_id: int, body: VoteIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.vote, prof, topic_id, body.proposal_id)
    return {"ok": True}


@router.post("/council/{topic_id}/close")
def council_close(topic_id: int, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).community.close, prof, topic_id)


@router.delete("/council/{topic_id}")
def council_delete(topic_id: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.delete_topic, prof, topic_id)
    return {"ok": True}


# ---------------------------------------------------------------- polls
class PollIn(BaseModel):
    question: str
    options: list[str]
    multi: bool = False
    anonymous: bool = False
    closes_at: str | None = None


class PollVoteIn(BaseModel):
    options: list[int]


@router.get("/polls")
def polls(request: Request, prof: dict = Learner) -> list[dict]:
    return app_of(request).community.polls(prof["id"])


@router.post("/polls")
def poll_open(body: PollIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).community.open_poll, prof, body.question, body.options, body.multi, body.anonymous, body.closes_at)}


@router.post("/polls/{poll_id}/vote")
def poll_vote(poll_id: int, body: PollVoteIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.poll_vote, prof, poll_id, body.options)
    return {"ok": True}


@router.post("/polls/{poll_id}/close")
def poll_close(poll_id: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.close_poll, prof, poll_id)
    return {"ok": True}


@router.delete("/polls/{poll_id}")
def poll_delete(poll_id: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).community.delete_poll, prof, poll_id)
    return {"ok": True}


# ---------------------------------------------------------------- FamilyTime: game wishes, the vote, a game bought with coins
class FtWishIn(BaseModel):
    game: str | None = None              # a family game of the app (key) …
    title: str | None = Field(default=None, max_length=200)    # … or a board game typed in (max. 60 letters kept)


class FtVoteIn(BaseModel):
    choice: str = Field(max_length=200)


class FtSetIn(BaseModel):
    game: str | None = None
    title: str | None = Field(default=None, max_length=200)
    choice: str | None = Field(default=None, max_length=200)   # one of the wishes
    random: bool = False                 # 🎲 among the leaders of a tie (or all wishes)


@router.get("/familytime")
def familytime(request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).familytime.state, prof)


@router.post("/familytime/{eid}/wish")
def familytime_wish(eid: int, body: FtWishIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.wish, prof, eid, body.game, body.title)
    return {"ok": True}


@router.delete("/familytime/{eid}/wish")
def familytime_unwish(eid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.unwish, prof, eid)
    return {"ok": True}


@router.post("/familytime/{eid}/vote")
def familytime_vote(eid: int, body: FtVoteIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).familytime.vote, prof, eid, body.choice)


@router.post("/familytime/{eid}/buy")
def familytime_buy(eid: int, body: FtWishIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).familytime.buy, prof, eid, body.game, body.title)


@router.post("/familytime/{eid}/start")
def familytime_start(eid: int, request: Request, prof: dict = Learner) -> dict:
    return {"status": _run(app_of(request).familytime.start_vote, prof, eid)}


@router.post("/familytime/{eid}/end")
def familytime_end(eid: int, request: Request, prof: dict = Learner) -> dict:
    return {"status": _run(app_of(request).familytime.end_vote, prof, eid)}


@router.post("/familytime/{eid}/set")
def familytime_set(eid: int, body: FtSetIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.set_game, prof, eid, body.game, body.title, body.choice, body.random)
    return {"ok": True}


@router.post("/familytime/{eid}/skip")
def familytime_skip(eid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.skip, prof, eid)
    return {"ok": True}


@router.post("/familytime/{eid}/remove")
def familytime_remove(eid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.remove_game, prof, eid)
    return {"ok": True}


@router.post("/familytime/{eid}/clear")
def familytime_clear(eid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).familytime.clear, prof, eid)
    return {"ok": True}


# ---------------------------------------------------------------- personal history
@router.get("/history")
def history(request: Request, profile_id: int | None = None, prof: dict = Learner) -> list[dict]:
    """Own history; parents may look at every profile's."""
    pid = prof["id"]
    if profile_id and profile_id != pid:
        if prof["role"] != "parent":
            raise HTTPException(403, "Only your own history")
        pid = profile_id
    return app_of(request).community.history(pid)


# ---------------------------------------------------------------- pairs game (game corner): photo sets and family crest
@router.get("/memory")
def memory_sets(request: Request, me: dict = Gamer) -> dict:
    from .. import memorygame
    return memorygame.public(app_of(request))


# ---------------------------------------------------------------- duels on two devices (game corner: Tic-Tac-Toe)
class DuelIn(BaseModel):
    opponent: int
    kind: str = "ttt"


def _duel(fn):
    from ..duel import DuelError
    try:
        return fn()
    except DuelError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/duel/opponents")
def duel_opponents(request: Request, kind: str = "ttt", me: dict = Gamer) -> list[dict]:
    fq = app_of(request)
    game = "pingpong" if kind == "pong" else "ttt"
    rows = fq.db.q("SELECT * FROM profile WHERE archived=0 AND id<>? ORDER BY role DESC, name", me["id"])
    return [{"id": r["id"], "name": r["name"], "avatar": fq.profile_public(r)["avatar"],
             "busy": fq.duels.state(r["id"]) is not None or fq.pong4.busy(r["id"])}
            for r in rows if fq.games_allowed(r, game)]


@router.get("/duel")
def duel_state(request: Request, me: dict = Gamer) -> dict | None:
    return app_of(request).duels.state(me["id"])


@router.post("/duel")
def duel_invite(body: DuelIn, request: Request, me: dict = Gamer) -> dict:
    fq = app_of(request)
    game = "pingpong" if body.kind == "pong" else "ttt"
    if not fq.games_allowed(me, game):
        raise HTTPException(403, "This game is switched off")
    opp = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", body.opponent)
    if not opp or not fq.games_allowed(opp, game):
        raise HTTPException(404, "Unknown profile")
    from ..duel import DuelError
    if fq.pong4.busy(opp["id"]):
        from ..pong4 import busy_text
        raise HTTPException(400, busy_text(opp["name"]))
    try:
        return fq.duels.invite(me["id"], opp["id"], body.kind)
    except DuelError as e:
        raise HTTPException(400, str(e).replace("{0}", opp["name"])) from None


class PongIn(BaseModel):
    pad: float
    ball: dict | None = None
    points: dict | None = None
    over: str | None = None


@router.post("/duel/pong")
def duel_pong(body: PongIn, request: Request, me: dict = Gamer) -> dict | None:
    """Ping-Pong on two devices: my paddle in, the whole table out (about 20 times a second)."""
    return _duel(lambda: app_of(request).duels.pong(me["id"], body.pad, body.ball, body.points, body.over))


@router.post("/duel/accept")
def duel_accept(request: Request, me: dict = Gamer) -> dict | None:
    return _duel(lambda: app_of(request).duels.answer(me["id"], True))


@router.post("/duel/decline")
def duel_decline(request: Request, me: dict = Gamer) -> None:
    _duel(lambda: app_of(request).duels.answer(me["id"], False))


@router.post("/duel/move")
def duel_move(request: Request, body: dict = Body(...), me: dict = Gamer) -> dict:
    return _duel(lambda: app_of(request).duels.move(me["id"], int(body.get("cell", -1))))


@router.post("/duel/again")
def duel_again(request: Request, me: dict = Gamer) -> dict:
    return _duel(lambda: app_of(request).duels.again(me["id"]))


@router.post("/duel/leave")
def duel_leave(request: Request, me: dict = Gamer) -> None:
    app_of(request).duels.leave(me["id"])


# ---------------------------------------------------------------- Ping-Pong doubles on four devices (familyquest/pong4.py)
def _p4(fn):
    from ..pong4 import DoublesError
    try:
        return fn()
    except DoublesError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/pong4/players")
def pong4_players(request: Request, me: dict = Gamer) -> list[dict]:
    """Who can sit at the table: family members with Ping-Pong switched on (busy: in a duel or another match)."""
    fq = app_of(request)
    rows = fq.db.q("SELECT * FROM profile WHERE archived=0 AND id<>? ORDER BY role DESC, name", me["id"])
    return [{"id": r["id"], "name": r["name"], "avatar": fq.profile_public(r)["avatar"],
             "busy": fq.duels.state(r["id"]) is not None or fq.pong4.busy(r["id"])}
            for r in rows if fq.games_allowed(r, "pingpong")]


@router.get("/pong4")
def pong4_state(request: Request, me: dict = Gamer) -> dict | None:
    return app_of(request).pong4.state(me["id"])


class Pong4In(BaseModel):
    seats: dict
    to: int = 7


def _p4_check(fq, seats: dict) -> None:
    from ..duel import DuelError
    for spec in (seats or {}).values():
        pid = (spec or {}).get("pid") if isinstance(spec, dict) else None
        if pid is None:
            continue
        r = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", pid)
        if not r or not fq.games_allowed(r, "pingpong"):
            raise HTTPException(404, "Unknown profile")
        if fq.duels.state(r["id"]) is not None:
            raise HTTPException(400, str(DuelError("{0} is playing a duel right now")).replace("{0}", r["name"]))


@router.post("/pong4")
def pong4_create(body: Pong4In, request: Request, me: dict = Gamer) -> dict:
    """Set up a table: I sit on A1 (back, team A); A2, B1, B2 each get {"pid": id} or {"bot": "easy|normal|hard"}."""
    fq = app_of(request)
    if not isinstance(body.seats, dict):
        raise HTTPException(400, "Fill all three seats")
    _p4_check(fq, body.seats)
    _no_bots(fq, me, "pingpong", any(isinstance(x, dict) and x.get("bot") is not None for x in body.seats.values()))
    return _p4(lambda: fq.pong4.create(me["id"], body.seats, body.to))


@router.post("/pong4/seat")
def pong4_seat(request: Request, body: dict = Body(...), me: dict = Gamer) -> dict:
    fq = app_of(request)
    spec = {k: body[k] for k in ("pid", "bot") if body.get(k) is not None}
    _p4_check(fq, {"x": spec})
    _no_bots(fq, me, "pingpong", spec.get("bot") is not None)
    return _p4(lambda: fq.pong4.seat(me["id"], str(body.get("seat", "")), spec))


@router.post("/pong4/accept")
def pong4_accept(request: Request, me: dict = Gamer) -> dict | None:
    return _p4(lambda: app_of(request).pong4.answer(me["id"], True))


@router.post("/pong4/decline")
def pong4_decline(request: Request, me: dict = Gamer) -> None:
    _p4(lambda: app_of(request).pong4.answer(me["id"], False))


@router.post("/pong4/start")
def pong4_start(request: Request, me: dict = Gamer) -> dict:
    return _p4(lambda: app_of(request).pong4.start(me["id"]))


class Pong4Sync(BaseModel):
    pad: float
    bots: dict | None = None
    ball: dict | None = None
    points: dict | None = None
    over: str | None = None


@router.post("/pong4/sync")
def pong4_sync(body: Pong4Sync, request: Request, me: dict = Gamer) -> dict:
    """My paddle in, the whole table out (about 15 times a second); the host also sends bots, ball, points, end."""
    return _p4(lambda: app_of(request).pong4.sync(me["id"], body.pad, body.bots, body.ball, body.points, body.over))


@router.post("/pong4/again")
def pong4_again(request: Request, me: dict = Gamer) -> dict:
    return _p4(lambda: app_of(request).pong4.again(me["id"]))


@router.post("/pong4/leave")
def pong4_leave(request: Request, me: dict = Gamer) -> None:
    app_of(request).pong4.leave(me["id"])


# ---------------------------------------------------------------- the children's own bots (avatar area)
@router.get("/bots")
def bots_list(request: Request, me: dict = Gamer) -> dict:
    from ..bots import EMOJIS
    fq = app_of(request)
    pets = [{**b, "owner": me["name"], "mine": True} for b in fq.pets.bots(me["id"])]        # own living pets play along
    return {"bots": [{**b, "mine": b["owner_id"] == me["id"]} for b in fq.bots.visible(me["id"])] + pets, "emojis": EMOJIS}


@router.post("/bots")
def bots_create(request: Request, body: dict = Body(...), me: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).bots.save, me, body)}


@router.put("/bots/{bot_id}")
def bots_update(bot_id: int, request: Request, body: dict = Body(...), me: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).bots.save, me, body, bot_id)}


@router.delete("/bots/{bot_id}")
def bots_delete(bot_id: int, request: Request, me: dict = Gamer) -> dict:
    _run(app_of(request).bots.delete, me, bot_id)
    return {"ok": True}


# ---------------------------------------------------------------- «Errate den Song» (a speaker of Home Assistant plays its playlist)
class SongStartIn(BaseModel):
    player: str
    answer: str | None = None            # artist | title | both | either
    vote: str | None = None              # majority | unanimous
    target: int | None = None
    max_songs: int | None = None
    reveal_delay: int | None = None      # seconds after the buzz before the solution (default 5)
    reveal_by: str | None = None         # all (who buzzed or the leader) | leader
    speaker_sound: bool | None = None    # «ping» / «brrr» on the speaker after the verdict


def _song_lead(fq, prof: dict) -> None:
    if not fq.songs.may_lead(prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")


@router.get("/song/players")
def song_players(request: Request, prof: dict = Gamer) -> dict:
    fq = app_of(request)
    if not (fq.ha and fq.ha.connected):
        return {"ha": False, "players": [], "rules": fq.songs.default_rules()}
    return {"ha": True, "players": fq.ha.media_players(), "rules": fq.songs.default_rules()}


@router.get("/song")
def song_state(request: Request, prof: dict = Playing) -> dict | None:
    return app_of(request).songs.state(prof["id"])


@router.post("/song/start")
def song_start(body: SongStartIn, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _run(fq.songs.start, prof["id"], body.model_dump())
    return fq.songs.state(prof["id"])


@router.post("/song/join")
def song_join(request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.songs.join, prof["id"])
    return fq.songs.state(prof["id"])


@router.post("/song/{action}")
def song_lead(action: str, request: Request, body: dict = Body(default={}), prof: dict = Playing) -> dict | None:
    """Leader: begin, next, pause, end, decide · players: buzz, reveal (who buzzed), vote."""
    fq = app_of(request)
    if action == "buzz":
        _run(fq.songs.buzz, prof["id"])
    elif action == "reveal":
        _run(fq.songs.reveal, prof)
    elif action == "vote":
        _run(fq.songs.vote, prof["id"], bool(body.get("right")))
    elif action == "volume":
        _song_lead(fq, prof)
        _run(fq.songs.volume, int(body.get("step") or 1))
    elif action in ("begin", "next", "pause", "end", "decide"):
        _song_lead(fq, prof)
        fn = {"begin": fq.songs.begin, "next": fq.songs.next, "end": fq.songs.end, "decide": fq.songs.decide}.get(action)
        _run(fn) if fn else _run(fq.songs.pause, bool(body.get("on")))
    else:
        raise HTTPException(404, "Unknown action")
    return fq.songs.state(prof["id"])


@router.get("/song/cover")
def song_cover(request: Request, prof: dict = Playing) -> Response:
    c = app_of(request).songs.cover()
    if not c:
        raise HTTPException(404, "No cover")
    return Response(c[0], media_type=c[1], headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- Wichteln (secret gift giving) – for the whole family, not a game
class WichtelIn(BaseModel):
    title: str
    participants: list[int]
    no_parent_pairs: bool = False
    no_kid_pairs: bool = False
    due: str | None = None


class WichtelDoneIn(BaseModel):
    done: bool


@router.post("/wichteln/{wid}/done")
def wichteln_done(wid: int, body: WichtelDoneIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).wichteln.set_done, prof, wid, body.done)
    return {"ok": True}


@router.get("/wichteln")
def wichteln_list(request: Request, prof: dict = Learner) -> dict:
    fq = app_of(request)
    return {"items": fq.wichteln.list(prof["id"]),
            "members": [{"id": m["id"], "name": m["name"], "role": m["role"]} for m in fq.wichteln.members()]}


@router.post("/wichteln")
def wichteln_create(body: WichtelIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).wichteln.create, prof, body.title, body.participants, body.no_parent_pairs, body.no_kid_pairs, body.due)}


@router.delete("/wichteln/{wid}")
def wichteln_delete(wid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).wichteln.delete, prof, wid)
    return {"ok": True}


# ---------------------------------------------------------------- bulletin boards (boards.py) – the whole family, never guests
class BoardIn(BaseModel):
    title: str = Field(max_length=200)
    emoji: str = Field(default="📌", max_length=32)


class BoardEditIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    emoji: str | None = Field(default=None, max_length=32)
    archived: bool | None = None


class BoardSyncIn(BaseModel):
    since: int = 0
    ops: list[dict[str, Any]] = Field(default=[], max_length=200)
    presence: dict[str, Any] | None = None


@router.get("/boards")
def boards_list(request: Request, prof: dict = Learner) -> list[dict]:
    return app_of(request).boards.list(prof)


@router.post("/boards")
def boards_create(body: BoardIn, request: Request, prof: dict = Learner) -> dict:
    return {"id": _run(app_of(request).boards.create, prof, body.title, body.emoji)}


@router.put("/boards/{bid}")
def boards_edit(bid: int, body: BoardEditIn, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).boards.update, prof, bid, body.title, body.emoji, body.archived)
    return {"ok": True}


@router.delete("/boards/{bid}")
def boards_delete(bid: int, request: Request, prof: dict = Learner) -> dict:
    _run(app_of(request).boards.delete, prof, bid)
    return {"ok": True}


@router.post("/boards/{bid}/sync")
def boards_sync(bid: int, body: BoardSyncIn, request: Request, prof: dict = Learner) -> dict:
    return _run(app_of(request).boards.sync, prof, bid, body.since, body.ops, body.presence)


@router.post("/boards/{bid}/leave")
def boards_leave(bid: int, request: Request, prof: dict = Learner) -> dict:
    app_of(request).boards.leave(prof, bid)
    return {"ok": True}
