"""«Schach» – the rules (move generation, the end of a game), the bots, and the games in the app: duels, pausing,
clocks, draws, coins paid once, guests, deleting and ending by a parent."""
import json
import random
import time

import pytest

from familyquest import schach_engine as se
from familyquest.community import CommunityError
from familyquest.schach_engine import Position


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def perft(p, d):
    if d == 0:
        return 1
    return sum(perft(p.make(m), d - 1) for m in p.legal())


# ---------------------------------------------------------------- the rules
@pytest.mark.parametrize("fen,counts", [
    (se.START_FEN, [20, 400, 8902]),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039]),       # castling, ep, pins
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812]),                              # en passant pins
    ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467]),        # promotions
    ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486]),
])
def test_move_generation_perft(fen, counts):
    p = Position.from_fen(fen)
    for d, n in enumerate(counts, 1):
        assert perft(p, d) == n


def play(p, *sans):
    for s in sans:
        m = next(m for m in p.legal() if p.san(m) == s)
        p = p.make(m)
    return p


def test_castling_en_passant_promotion_and_san():
    p = Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    sans = {p.san(m) for m in p.legal()}
    assert {"O-O", "O-O-O"} <= sans
    q = play(p, "O-O")
    assert q.b[se.parse_sq("f1")] == "R" and q.b[se.parse_sq("g1")] == "K" and q.castle == "kq"
    # no castling through an attacked square
    p = Position.from_fen("r3k2r/8/8/8/8/8/5r2/R3K2R w KQkq - 0 1")
    assert "O-O" not in {p.san(m) for m in p.legal()} and not p.in_check()
    # no castling out of check
    p = Position.from_fen("r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1")
    assert not {"O-O", "O-O-O"} & {p.san(m) for m in p.legal()}
    # en passant
    p = play(Position.from_fen(se.START_FEN), "e4", "a6", "e5", "d5")
    assert p.fen().split()[3] == "d6"
    q = play(p, "exd6")
    assert q.b[se.parse_sq("d5")] == "." and q.b[se.parse_sq("d6")] == "P"
    # promotion: four choices, check marks
    p = Position.from_fen("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    assert {p.san(m) for m in p.legal() if m[0] == se.parse_sq("a7")} == {"a8=Q+", "a8=R+", "a8=B", "a8=N"}
    # disambiguation
    p = Position.from_fen("k7/8/8/8/8/8/8/KN3N2 w - - 0 1")
    assert "Nbd2" in {p.san(m) for m in p.legal()} and "Nfd2" in {p.san(m) for m in p.legal()}


def test_mate_stalemate_material():
    p = play(Position.from_fen(se.START_FEN), "f3", "e5", "g4")
    m = next(m for m in p.legal() if p.san(m) == "Qh4#")
    q = p.make(m)
    assert q.in_check() and not q.legal()
    st = Position.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert not st.in_check() and not st.legal()
    assert Position.from_fen("8/8/8/4k3/8/8/8/4K3 w - - 0 1").insufficient()
    assert Position.from_fen("8/8/8/4k3/8/8/8/4KN2 w - - 0 1").insufficient()
    assert Position.from_fen("8/8/8/4k3/2b5/8/8/4KB2 w - - 0 1").insufficient()        # both bishops on light squares
    assert not Position.from_fen("8/8/8/2b1k3/8/8/8/4KB2 w - - 0 1").insufficient()     # different colours
    assert not Position.from_fen("8/8/8/4k3/8/8/8/3NKN2 w - - 0 1").insufficient()
    assert not Position.from_fen("8/8/8/4k3/8/8/4P3/4K3 w - - 0 1").insufficient()


def test_incremental_score_matches():
    rng = random.Random(3)
    p = Position.from_fen(se.START_FEN)
    for _ in range(150):
        ms = p.legal()
        if not ms:
            break
        p = p.make(rng.choice(ms))
        assert p.score == Position.from_fen(p.fen()).score


# ---------------------------------------------------------------- the bots
def test_bots_find_mate_and_answer_in_time():
    p = Position.from_fen("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 2 3")
    for lvl in ("normal", "hard"):
        assert p.san(se.bot_move(p, lvl, random.Random(1))) == "Qxf7#"
    p = Position.from_fen("r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/2N1PN2/PP3PPP/R2QKB1R w KQ - 0 8")
    for lvl in ("easy", "normal", "hard"):
        t = time.monotonic()
        m = se.bot_move(p, lvl, random.Random(1))
        assert m in p.legal() and time.monotonic() - t < 2.5
    # the hard bot takes a hanging queen
    p = Position.from_fen("4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1")
    assert p.san(se.bot_move(p, "hard", random.Random(1))) == "Rxd5"
    # easy prefers captures (mostly)
    caps = sum(p.is_capture(se.bot_easy(p, random.Random(i))) for i in range(40))
    assert caps >= 20


# ---------------------------------------------------------------- the games
def make(fq, clock=None):
    s = fq.schach
    if clock:
        s.now = clock
    s.bot_delay = 0
    s.bot_limit = 0.3
    return s


def two(fq):
    a = fq.db.x("INSERT INTO profile(name, role) VALUES('Mia', 'kid')")
    b = fq.db.x("INSERT INTO profile(name, role) VALUES('Leo', 'kid')")
    return a, b


def moves(s, gid, *pairs):
    for pid, frm, to in pairs:
        s.move(gid, pid, frm, to)


def test_duel_only_own_moves_and_checkmate_coins_once(fq):
    s = make(fq)
    a, b = two(fq)
    gid = s.start(a, {"mode": "duel", "color": "white", "clock": 0}, b)
    with pytest.raises(CommunityError):
        s.move(gid, a, "e2", "e4")                                  # not started yet
    c = fq.db.x("INSERT INTO profile(name, role) VALUES('Ida', 'kid')")
    with pytest.raises(CommunityError, match="somebody else"):
        s.join("schach", c, gid)
    s.join("schach", b, gid)
    with pytest.raises(CommunityError, match="not your turn"):
        s.move(gid, b, "e7", "e5")
    with pytest.raises(CommunityError, match="not allowed"):
        s.move(gid, a, "e2", "e5")
    with pytest.raises(CommunityError, match="do not play"):
        s.move(gid, c, "e2", "e4")
    # a long game first (the winner needs 10 moves for coins), then a quick mate
    for f in "abch":
        moves(s, gid, (a, f + "2", f + "3"), (b, f + "7", f + "6"))
    for f in "abc":
        moves(s, gid, (a, f + "3", f + "4"), (b, f + "6", f + "5"))
    moves(s, gid, (a, "e2", "e4"), (b, "f7", "f6"), (a, "d2", "d4"), (b, "g7", "g5"), (a, "d1", "h5"))
    v = s.state(gid, a)
    assert v["status"] == "done" and v["result"] == {"winner": "w", "reason": "checkmate"}
    assert v["moves"][-1] == "Qh5#" and v["coins"] == {str(a): 10}
    assert fq.rewards.balance(a, "coins") == 10
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    st = json.loads(row["state"])
    st["paid"] = False
    s._save(row, st)                                               # paid once (ledger ref)
    assert fq.rewards.balance(a, "coins") == 10
    hist = fq.community.history(a)
    assert hist[0]["kind"] == "schach" and hist[0]["data"]["result"] == "win" and hist[0]["data"]["coins"] == 10
    assert fq.community.history(b)[0]["data"]["result"] == "loss"
    assert json.loads(fq.db.q1("SELECT settings FROM profile WHERE id=?", a)["settings"] or "{}").get("champion")


def test_quick_win_no_coins_and_repetition_draw(fq):
    s = make(fq)
    a, b = two(fq)
    gid = s.start(a, {"mode": "duel", "color": "black"})           # open seat: anybody
    assert s._game("schach")["id"] == gid
    s.join("schach", b)                                            # b plays white
    moves(s, gid, (b, "f2", "f3"), (a, "e7", "e5"), (b, "g2", "g4"), (a, "d8", "h4"))
    v = s.state(gid, b)
    assert v["result"]["winner"] == "b" and v["coins"] == {}       # fool's mate: too short for coins
    gid = s.start(a, {"mode": "duel", "color": "white"}, b)
    s.join("schach", b, gid)
    for _ in range(2):
        moves(s, gid, (a, "g1", "f3"), (b, "g8", "f6"), (a, "f3", "g1"), (b, "f6", "g8"))
    v = s.state(gid, a)
    assert v["result"] == {"winner": None, "reason": "repetition"} and not v["coins"]
    assert fq.community.history(a)[0]["data"]["result"] == "draw"


def test_promotion_needs_a_choice_fifty_moves(fq):
    s = make(fq)
    a, b = two(fq)
    gid = s.start(a, {"mode": "duel", "color": "white"}, b)
    s.join("schach", b, gid)
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    st = json.loads(row["state"])
    st["fen"] = "7k/P7/8/8/8/8/8/K7 w - - 0 1"
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), gid)
    with pytest.raises(CommunityError, match="promotion"):
        s.move(gid, a, "a7", "a8")
    s.move(gid, a, "a7", "a8", "r")
    v = s.state(gid, b)
    assert v["board"][0] == "R" and v["moves"] == ["a8=R+"] and v["check"] == "h8"
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE id=?", gid)["state"])
    st["fen"] = "7k/8/8/8/8/8/R7/K7 b - - 99 80"
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), gid)
    s.move(gid, b, "h8", "g8")
    assert s.state(gid, a)["result"] == {"winner": None, "reason": "fifty"}


def test_pause_resume_clock_and_timeout(fq):
    clock = Clock()
    s = make(fq, clock)
    a, b = two(fq)
    gid = s.start(a, {"mode": "duel", "color": "white", "clock": 5}, b)
    s.join("schach", b, gid)
    clock.t += 10
    s.move(gid, a, "e2", "e4")
    v = s.state(gid, a)
    assert v["clock"] == {"w": 290000, "b": 300000} and v["ticking"] == "b"
    clock.t += 20
    s.pause(gid, b)                                                # either player pauses: the clock stops
    v = s.state(gid, a)
    assert v["status"] == "paused" and v["clock"]["b"] == 280000 and v["ticking"] is None and v["paused_by"] == "Leo"
    with pytest.raises(CommunityError, match="paused"):
        s.move(gid, b, "e7", "e5")
    clock.t += 5000                                                # a long pause costs no time
    assert s.state(gid, a)["clock"]["b"] == 280000
    o = s.overview(a)
    assert o["games"][0]["status"] == "paused"
    s.resume(gid, a)
    clock.t += 281
    v = s.state(gid, a)                                            # b's flag fell: white wins (it has mating material)
    assert v["result"] == {"winner": "w", "reason": "timeout"} and v["clock"]["b"] == 0


def test_resign_and_draw_offer(fq):
    s = make(fq)
    a, b = two(fq)
    gid = s.start(a, {"mode": "duel", "color": "white"}, b)
    s.join("schach", b, gid)
    s.draw(gid, a, "offer")
    with pytest.raises(CommunityError):
        s.draw(gid, a, "accept")                                   # not your own offer
    s.draw(gid, b, "decline")
    assert s.state(gid, a)["draw_offer"] is None
    s.draw(gid, b, "offer")
    s.draw(gid, a, "accept")
    assert s.state(gid, a)["result"] == {"winner": None, "reason": "agreement"}
    gid = s.start(a, {"mode": "duel", "color": "white"}, b)
    s.join("schach", b, gid)
    s.resign(gid, b)
    v = s.state(gid, a)
    assert v["result"] == {"winner": "w", "reason": "resign"} and v["coins"] == {}   # no moves: no coins


def test_bot_game_moves_and_coins_by_level(fq):
    s = make(fq)
    a, _ = two(fq)
    gid = s.start(a, {"mode": "bot", "level": "hard", "color": "white"})
    s.move(gid, a, "e2", "e4")
    v = s.state(gid, a)                                            # the bot answers on the next look
    assert len(v["moves"]) == 2 and v["my_turn"] and v["players"]["b"]["bot"]
    with pytest.raises(CommunityError, match="not allowed"):
        s.move(gid, a, "e7", "e6")                                 # not a piece of the own colour
    with pytest.raises(CommunityError, match="do not play"):
        s.move(gid, a + 100, "d2", "d4")
    st = {"mode": "bot", "result": {"winner": "w", "reason": "checkmate"}, "players": {"w": {"id": "1"}, "b": {"id": "bot", "bot": True, "level": "hard"}},
          "moves": [{"by": "w"}] * 10}
    assert s.coins_for(st) == {"1": 5}
    st["players"]["b"]["level"] = "normal"
    assert s.coins_for(st) == {"1": 2}
    st["players"]["b"]["level"] = "easy"
    assert s.coins_for(st) == {}
    assert s.coins_for({**st, "mode": "local"}) == {}
    st2 = {**st, "mode": "duel", "players": {"w": {"id": "1"}, "b": {"id": "9", "guest": True}}}
    assert s.coins_for(st2) == {}
    # the bot accepts a draw only when it stands clearly worse
    with pytest.raises(CommunityError, match="play on"):
        s.draw(gid, a, "offer")


def test_local_game_both_sides_and_several_games(fq):
    s = make(fq)
    a, b = two(fq)
    gid = s.start(a, {"mode": "local"})
    moves(s, gid, (a, "e2", "e4"), (a, "e7", "e5"))
    with pytest.raises(CommunityError):
        s.move(gid, b, "g1", "f3")
    v = s.state(gid, a)
    assert v["my_side"] == "w" and v["my_turn"] and v["coins_on"] == 0
    g2 = s.start(a, {"mode": "bot", "level": "easy"})
    s.pause(gid, a)
    o = s.overview(a)
    assert {g["id"] for g in o["games"]} == {gid, g2}
    for _ in range(s._open_count(a), 12):
        s.start(a, {"mode": "bot"})
    with pytest.raises(CommunityError, match="too many"):
        s.start(a, {"mode": "bot"})


# ---------------------------------------------------------------- the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def test_api_duel_delete_and_parent_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    fq.schach.bot_delay, fq.schach.bot_limit = 0, 0.3
    hm, hl = login(client, mia, "1111"), login(client, leo)
    o = client.get("/api/community/schach", headers=hm).json()
    assert {p["name"] for p in o["family"]} == {"Leo", "Papa"} and o["games"] == []
    v = client.post("/api/community/schach/start", json={"mode": "duel", "color": "white", "opponent": leo}, headers=hm).json()
    gid = v["game"]
    assert v["status"] == "lobby" and v["invite"]["name"] == "Leo"
    me = client.get("/api/me", headers=hl).json()
    assert me["community"]["schach"]["invites"] == 1 and me["community"]["schach"]["from"] == "Mia"
    assert client.post(f"/api/community/schach/{gid}/join", headers=hl).json()["status"] == "running"
    assert client.post(f"/api/community/schach/{gid}/move", json={"frm": "e7", "to": "e5"}, headers=hl).status_code == 400
    v = client.post(f"/api/community/schach/{gid}/move", json={"frm": "e2", "to": "e4"}, headers=hm).json()
    assert v["last"] == ["e2", "e4"] and not v["my_turn"]
    assert client.get("/api/me", headers=hl).json()["community"]["schach"]["my_turn"] == 1
    # deleting: only paused games, only the host or a parent
    assert client.post(f"/api/community/schach/{gid}/delete", headers=hm).status_code == 400
    client.post(f"/api/community/schach/{gid}/pause", headers=hl)
    assert client.post(f"/api/community/schach/{gid}/delete", headers=hl).status_code == 400
    # the parent area lists the paused game and ends it
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "schach")
    assert g["status"] == "paused" and g["icon"] == "♟️" and g["players"] == 2 and not g["solo"]
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "schach" for x in r["running"])
    v = client.get(f"/api/community/schach/{gid}", headers=hm).json()
    assert v["status"] == "done" and v["result"]["reason"] == "ended"
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'schach:%'")
    # a paused bot game: the host deletes it
    v = client.post("/api/community/schach/start", json={"mode": "bot", "level": "easy"}, headers=hm).json()
    client.post(f"/api/community/schach/{v['game']}/pause", headers=hm)
    o = client.post(f"/api/community/schach/{v['game']}/delete", headers=hm).json()
    assert o["games"] == []
    # others cannot look into a private game
    v = client.post("/api/community/schach/start", json={"mode": "bot", "level": "easy"}, headers=hm).json()
    assert client.get(f"/api/community/schach/{v['game']}", headers=hl).status_code == 400
    assert client.get(f"/api/community/schach/{v['game']}", headers=ph).status_code == 200


def test_guests_join_open_seat(client):
    from test_api import setup_family
    from familyquest import netfilter
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    gid = client.post("/api/community/schach/start", json={"mode": "duel", "color": "white"}, headers=hm).json()["game"]
    inv = client.post("/api/community/guests", json={"game": "schach"}, headers=hm).json()["invite"]
    assert inv["game_id"] == gid
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Chess"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    assert client.post("/api/community/schach/start", json={"mode": "bot"}, headers=hg).status_code in (401, 403)
    o = client.get("/api/community/schach", headers=hg).json()
    assert [x["id"] for x in o["games"]] == [gid]
    v = client.get(f"/api/community/schach/{gid}", headers=hg).json()
    assert v["status"] == "running" and v["my_side"] == "b" and v["players"]["b"]["guest"] and v["coins_on"] == 0
    client.post(f"/api/community/schach/{gid}/move", json={"frm": "e2", "to": "e4"}, headers=hm)
    assert client.post(f"/api/community/schach/{gid}/move", json={"frm": "e7", "to": "e5"}, headers=hg).status_code == 200
    for p in ("", "/3", "/3/move", "/3/pause"):
        assert netfilter.is_guest_path("/api/community/schach" + p), p
    for p in ("/start", "/3/delete"):
        assert not netfilter.is_guest_path("/api/community/schach" + p), p


def test_switched_off(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "schach" in client.get("/api/me", headers=hm).json()["games_list"]
    client.put("/api/parent/games", json={"access": {"schach": {"mode": "off"}}}, headers=ph)
    assert client.get("/api/community/schach", headers=hm).status_code == 403
    assert client.post("/api/community/schach/start", json={"mode": "bot"}, headers=hm).status_code == 403
