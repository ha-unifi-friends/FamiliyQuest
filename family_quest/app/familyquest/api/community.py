"""Etappe H – community API: family quiz, family council, personal history (see familyquest/community.py).

Everybody (children and parents) makes quizzes, plays and votes with the learning-app token (or the parent token).
A game is led by whoever started it; a parent may always lead.
"""
from __future__ import annotations

import random

from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from ..community import CommunityError
from ..guests import GUEST, GUEST_HOURS, GuestError
from .auth import Learner, app_of, learner

router = APIRouter(prefix="/api/community")


def game_of(path: str) -> str | None:
    """Which game an address of the community API belongs to (None: council, polls, history – always open)."""
    part = path.split("/api/community/", 1)[-1].split("/")
    head = part[0]
    if head in ("quiz", "quizzes", "templates"):
        return "quiz"
    if head in ("bingo", "poker", "song", "domino"):
        return head
    if head == "cards" and len(part) > 1:
        return part[1]
    return {"duel": "ttt", "memory": "pairs"}.get(head)


def Player(request: Request, prof: dict = Learner) -> dict:      # noqa: N802 – used like Learner
    """A learner who may play this game (parent area › Settings › Games, per game and person)."""
    fq = app_of(request)
    game = game_of(request.url.path)
    if not fq.games_allowed(prof, game):
        if game:
            raise HTTPException(403, "This game is switched off for you")
        raise HTTPException(403, "Games are switched off for you")
    return prof


Gamer = Depends(Player)


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


class StartIn(BaseModel):
    quiz_id: int
    count: int | None = None        # play only this many questions
    shuffle: bool = True


class TemplateIn(BaseModel):
    template: str


@router.get("/quizzes")
def quizzes(request: Request, prof: dict = Gamer) -> list[dict]:
    return app_of(request).community.quizzes()


@router.get("/templates")
def templates(request: Request, prof: dict = Gamer) -> list[dict]:
    from ..quiz_templates import TEMPLATES
    return [{"id": k, "title": t["title"], "icon": t["icon"], "questions": len(t["questions"]), "region": t["region"],
             "example": t["questions"][0]["q"] if isinstance(t["questions"][0], dict) else t["questions"][0][0]}
            for k, t in TEMPLATES.items()]


@router.post("/quizzes")
def quiz_create(body: QuizIn, request: Request, prof: dict = Gamer) -> dict:
    return {"id": _run(app_of(request).community.save_quiz, body.model_dump(), prof)}


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
    bot_ids: list[int] = []


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
def poker_begin(request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    _poker_lead(fq, prof)
    _run(fq.poker.begin, prof["id"])
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
    bot_ids: list[int] = []              # own / shared bots of the children (bots.py) – the rest are animal bots


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
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        n = body.bots if body.bots is not None else fq.cards.default_rules(_kind(kind)).get("bots", 2)
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1 if body.solo else 0, min(5, n)), body.level or "normal", BOTS)
    _run(fq.cards.start, _kind(kind), prof["id"], body.model_dump(exclude={"solo", "bot_ids"}), body.solo, bots)
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/join")
def cards_join(kind: str, request: Request, prof: dict = Playing) -> dict | None:
    fq = app_of(request)
    _run(fq.cards.join, _kind(kind), prof["id"])
    return fq.cards.state(kind, prof["id"])


@router.post("/cards/{kind}/begin")
def cards_begin(kind: str, request: Request, prof: dict = Gamer) -> dict | None:
    fq = app_of(request)
    if not fq.cards.may_lead(_kind(kind), prof):
        raise HTTPException(403, "Only who started the game (or a parent) leads it")
    _run(fq.cards.begin, kind, prof["id"])
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
    bot_ids: list[int] = []


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
    bots = None
    if body.bot_ids:
        from ..cardgames import BOTS
        n = body.bots if body.bots is not None else fq.domino.default_rules().get("bots", 3)
        bots = fq.bots.pick(prof["id"], body.bot_ids, max(1 if body.solo else 0, min(5, n)), body.level or "normal", BOTS)
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


# ---------------------------------------------------------------- guests
class InviteIn(BaseModel):
    game: str                       # quiz | bingo
    on: bool = True


class GuestJoinIn(BaseModel):
    code: str
    name: str


@router.post("/guests")
async def guests_invite(body: InviteIn, request: Request, prof: dict = Gamer) -> dict:
    """Everybody of the family who plays (not the guests) opens the invitation of a running family game – the QR code
    points to the guest page. Closing it stays with who leads the game."""
    from ..netinfo import home_access
    fq = app_of(request)
    if body.game in ("tschau", "karussell", "domino"):
        games = fq.domino if body.game == "domino" else fq.cards
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
def duel_opponents(request: Request, me: dict = Gamer) -> list[dict]:
    fq = app_of(request)
    rows = fq.db.q("SELECT * FROM profile WHERE archived=0 AND id<>? ORDER BY role DESC, name", me["id"])
    return [{"id": r["id"], "name": r["name"], "avatar": fq.profile_public(r)["avatar"], "busy": fq.duels.state(r["id"]) is not None}
            for r in rows if fq.games_allowed(r, "ttt")]


@router.get("/duel")
def duel_state(request: Request, me: dict = Gamer) -> dict | None:
    return app_of(request).duels.state(me["id"])


@router.post("/duel")
def duel_invite(body: DuelIn, request: Request, me: dict = Gamer) -> dict:
    fq = app_of(request)
    opp = fq.db.q1("SELECT * FROM profile WHERE id=? AND archived=0", body.opponent)
    if not opp or not fq.games_allowed(opp, "ttt"):
        raise HTTPException(404, "Unknown profile")
    from ..duel import DuelError
    try:
        return fq.duels.invite(me["id"], opp["id"], body.kind)
    except DuelError as e:
        raise HTTPException(400, str(e).replace("{0}", opp["name"])) from None


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


# ---------------------------------------------------------------- the children's own bots (avatar area)
@router.get("/bots")
def bots_list(request: Request, me: dict = Gamer) -> dict:
    from ..bots import EMOJIS
    fq = app_of(request)
    return {"bots": [{**b, "mine": b["owner_id"] == me["id"]} for b in fq.bots.visible(me["id"])], "emojis": EMOJIS}


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
