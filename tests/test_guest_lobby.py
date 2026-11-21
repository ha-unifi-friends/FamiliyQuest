"""Guests stay for the game night (guests.py): the guest profile and its token last 24 hours, the guest page shows a
lobby with the family tables open to join – one tap, no new invitation – and the guest token opens nothing else."""
import json
import time

import pytest
from test_api import setup_family


def _family(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    return ph, hm, hl, mia, leo


def _guest(client, hm, name="Oma"):
    """A guest who came with the invitation of a bingo game (the first entry point stays the QR code)."""
    client.post("/api/community/bingo/start", json={}, headers=hm)
    code = client.post("/api/community/guests", json={"game": "bingo"}, headers=hm).json()["invite"]["code"]
    r = client.post("/api/community/guest/join", json={"code": code, "name": name})
    assert r.status_code == 200, r.text
    return {"X-FQ-Token": r.json()["token"]}, r.json()["profile"]["id"]


def _lobby(client, g):
    r = client.get("/api/guest/lobby", headers=g)
    assert r.status_code == 200, r.text
    return r.json()


def test_guest_profile_and_token_last_24_hours(client, monkeypatch):
    from itsdangerous.timed import TimestampSigner

    from familyquest import guests
    assert guests.GUEST_HOURS == 24
    ph, hm, hl, mia, leo = _family(client)
    fq = client.app.state.fq
    g, gid = _guest(client, hm)
    real = TimestampSigner.get_timestamp
    # a token made 23 hours ago still works, one made 25 hours ago not
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: int(time.time()) - 23 * 3600)
    old23 = {"X-FQ-Token": fq.tokens.make(gid, "guest")}
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: int(time.time()) - 25 * 3600)
    old25 = {"X-FQ-Token": fq.tokens.make(gid, "guest")}
    monkeypatch.setattr(TimestampSigner, "get_timestamp", real)
    assert client.get("/api/guest/lobby", headers=old23).status_code == 200
    assert client.get("/api/community/bingo", headers=old23).status_code == 200
    assert client.get("/api/guest/lobby", headers=old25).status_code == 403
    assert client.get("/api/community/bingo", headers=old25).status_code == 401
    # the cleanup: a guest of 13 hours stays, one of 25 hours is deleted with everything
    fq.db.x("UPDATE profile SET created_at=datetime('now','-13 hours') WHERE id=?", gid)
    assert fq.guests.cleanup() == 0
    fq.db.x("UPDATE profile SET created_at=datetime('now','-25 hours') WHERE id=?", gid)
    assert fq.guests.cleanup() == 1
    assert client.get("/api/guest/lobby", headers=g).status_code == 401


def test_lobby_lists_the_open_family_tables(client):
    ph, hm, hl, mia, leo = _family(client)
    g, gid = _guest(client, hm)
    lb = _lobby(client, g)
    assert lb["on"] and lb["profile"]["name"] == "Oma" and lb["profile"]["guest"]
    assert [(t["game"], t["joined"]) for t in lb["tables"]] == [("bingo", True)]          # the table of the invitation
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    client.post("/api/community/domino/start", json={"bots": 0}, headers=hl)
    tables = {t["game"]: t for t in _lobby(client, g)["tables"]}
    assert set(tables) == {"bingo", "tschau", "domino"}
    assert tables["tschau"]["host"] == "Mia" and tables["tschau"]["join"] == "community/cards/tschau/join"
    assert not tables["tschau"]["joined"] and tables["domino"]["host"] == "Leo"
    # alone against bots: not a family table
    client.post("/api/community/wuerfel/start", json={"solo": True, "bots": 1}, headers=hl)
    assert "wuerfel" not in {t["game"] for t in _lobby(client, g)["tables"]}
    # a table that started takes nobody late
    client.post("/api/community/cards/tschau/join", headers=hl)
    client.post("/api/community/cards/tschau/begin", headers=hm)
    assert "tschau" not in {t["game"] for t in _lobby(client, g)["tables"]}


def test_lobby_hides_full_tables(client):
    ph, hm, hl, mia, leo = _family(client)
    fq = client.app.state.fq
    g, gid = _guest(client, hm)
    client.post("/api/community/jass/start", json={"bots": 0}, headers=hm)
    assert "jass" in {t["game"] for t in _lobby(client, g)["tables"]}
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='jass' AND status='lobby'")
    st = json.loads(row["state"])
    while len(st["players"]) < 4:                                   # four seats: full
        st["players"].append({**st["players"][0], "id": str(900 + len(st["players"])), "name": f"X{len(st['players'])}"})
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
    assert "jass" not in {t["game"] for t in _lobby(client, g)["tables"]}
    assert client.post("/api/community/jass/join", headers=g).status_code == 403
    # poker: while a seat is free
    assert client.post("/api/community/poker/start", json={"max_players": 2}, headers=hm).status_code == 200
    assert "poker" in {t["game"] for t in _lobby(client, g)["tables"]}
    client.post("/api/community/poker/join", headers=hl)
    assert "poker" not in {t["game"] for t in _lobby(client, g)["tables"]}


def test_lobby_respects_the_guest_switch(client):
    ph, hm, hl, mia, leo = _family(client)
    g, gid = _guest(client, hm)
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    client.put("/api/parent/settings", json={"games_guests": False}, headers=ph)
    lb = _lobby(client, g)
    assert lb["on"] is False and [t["game"] for t in lb["tables"]] == ["bingo"]          # only the own seat stays
    assert client.post("/api/community/cards/tschau/join", headers=g).status_code == 403
    client.put("/api/parent/settings", json={"games_guests": True}, headers=ph)
    assert "tschau" in {t["game"] for t in _lobby(client, g)["tables"]}


def test_lobby_leaves_out_the_facts_quiz(client):
    from test_family_facts import seed_for_api
    ph, hm, hl, mia, leo = _family(client)
    fq = client.app.state.fq
    g, gid = _guest(client, hm)
    client.post("/api/community/bingo/end", headers=hm)
    seed_for_api(fq, {"Mia": mia, "Leo": leo})
    assert client.post("/api/community/quiz/facts/start", json={"count": 5}, headers=hm).status_code == 200
    assert "quiz" not in {t["game"] for t in _lobby(client, g)["tables"]}
    assert client.post("/api/community/quiz/join", headers=g).status_code == 403
    assert gid not in fq.community._game()["players"]


def test_lobby_leaves_out_hidden_games(client, monkeypatch):
    from familyquest import channel
    ph, hm, hl, mia, leo = _family(client)
    g, gid = _guest(client, hm)
    monkeypatch.setattr(channel, "_channel", "dev")                 # a dev game opened in the dev channel …
    assert client.post("/api/community/stempeljagd/start", json={"bots": 0, "bot_ms": 0, "projects": "random"}, headers=hm).status_code == 200
    assert "stempeljagd" in {t["game"] for t in _lobby(client, g)["tables"]}
    monkeypatch.setattr(channel, "_channel", "")                    # … does not exist in the normal app
    assert "stempeljagd" not in {t["game"] for t in _lobby(client, g)["tables"]}
    assert client.post("/api/community/stempeljagd/join", headers=g).status_code in (403, 404)


def test_join_from_the_lobby_without_a_code(client):
    ph, hm, hl, mia, leo = _family(client)
    g, gid = _guest(client, hm)
    # not yet open: no seat for the guest
    assert client.post("/api/community/cards/tschau/join", headers=g).status_code == 403
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    t = next(t for t in _lobby(client, g)["tables"] if t["game"] == "tschau")
    r = client.post("/api/" + t["join"], headers=g)
    assert r.status_code == 200, r.text
    assert "Oma" in [p["name"] for p in r.json()["players"]]
    t = next(t for t in _lobby(client, g)["tables"] if t["game"] == "tschau")
    assert t["joined"]
    assert client.post("/api/" + t["join"], headers=g).status_code == 200                # the own seat again
    # the guest plays the game, but never leads it
    assert client.post("/api/community/cards/tschau/begin", headers=g).status_code in (401, 403)
    # a new table of another game appears and the guest sits down with one request
    client.post("/api/community/wuerfel/start", json={"bots": 0}, headers=hl)
    assert client.post("/api/community/wuerfel/join", headers=g).status_code == 200


def test_the_guest_token_opens_nothing_else(client):
    ph, hm, hl, mia, leo = _family(client)
    g, gid = _guest(client, hm)
    for path in ("/api/me", "/api/profiles/" + str(gid), "/api/community/tables", "/api/community/quizzes", "/api/community/history",
                 "/api/community/council", "/api/community/song/players", "/api/parent/settings", "/api/parent/games/running",
                 "/api/me/games", "/api/community/duel", "/api/community/pong4", "/api/community/boards", "/api/community/wichteln"):
        assert client.get(path, headers=g).status_code in (401, 403, 404, 405), path
    assert client.get("/api/parent/settings", headers={"X-FQ-Parent": g["X-FQ-Token"]}).status_code == 401
    for path, body in (("/api/community/cards/tschau/start", {}), ("/api/community/domino/start", {}),
                       ("/api/community/quiz/start", {}), ("/api/me/games/try", {"game": "ttt"})):
        assert client.post(path, json=body, headers=g).status_code in (401, 403, 404, 422), path
    # a guest is no family member: the guest endpoints refuse a family token
    assert client.get("/api/guest/lobby", headers=hm).status_code == 403
    assert client.get("/api/guest/lobby").status_code == 403


def test_leave_deletes_the_guest(client):
    ph, hm, hl, mia, leo = _family(client)
    fq = client.app.state.fq
    g, gid = _guest(client, hm)
    client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm)
    client.post("/api/community/cards/tschau/join", headers=g)
    assert client.delete("/api/guest/me", headers=g).status_code == 200
    assert not fq.db.q1("SELECT 1 FROM profile WHERE id=?", gid)
    st = json.loads(fq.db.val("SELECT state FROM card_game WHERE kind='tschau' AND status='lobby'"))
    assert str(gid) not in [p["id"] for p in st["players"]]                       # out of the waiting table
    assert client.get("/api/guest/lobby", headers=g).status_code == 401
    assert client.get("/api/community/bingo", headers=g).status_code == 401


@pytest.mark.parametrize("page", ["/guest"])
def test_guest_page_has_the_lobby(client, page):
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web" / "gast.js").read_text(encoding="utf-8")
    assert 'api("guest/lobby' in js and 'api("guest/me", { method: "DELETE" })' in js
    assert "localStorage" in js and "sessionStorage" not in js                    # the visit outlives the tab
    assert "const back = () => lobby();" in js                                     # after a game: back in the lobby
    assert client.get(page).status_code == 200
