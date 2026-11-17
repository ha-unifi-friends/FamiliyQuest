"""Bulletin boards: boards, items, versions («since»), limits, presence – family only, never guests."""
import pytest

from familyquest import boards as B
from familyquest.community import CommunityError
from test_api import setup_family


def _logins(client):
    ph, mia, leo = setup_family(client)
    papa = next(p["id"] for p in client.get("/api/profiles").json() if p["name"] == "Papa")
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    return ph, hm, hl, mia, leo, papa


def _sync(client, h, bid, since=0, ops=None, presence=None):
    r = client.post(f"/api/community/boards/{bid}/sync", json={"since": since, "ops": ops or [], "presence": presence}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


NOTE = {"x": 10, "y": 20, "c": 2, "t": "Ferien planen"}


def test_boards_create_list_manage(client):
    ph, hm, hl, mia, leo, papa = _logins(client)
    assert client.get("/api/community/boards", headers=hm).json() == []
    assert client.post("/api/community/boards", json={"title": "  "}, headers=hm).status_code == 400
    bid = client.post("/api/community/boards", json={"title": "Ferien", "emoji": "🏖️"}, headers=hm).json()["id"]
    lst = client.get("/api/community/boards", headers=hl).json()
    assert [(b["title"], b["emoji"], b["author"], b["manage"]) for b in lst] == [("Ferien", "🏖️", "Mia", False)]
    # Leo neither made it nor is a parent: no renaming, archiving or removing
    assert client.put(f"/api/community/boards/{bid}", json={"title": "X"}, headers=hl).status_code == 400
    assert client.delete(f"/api/community/boards/{bid}", headers=hl).status_code == 400
    # … but he may work on it
    assert _sync(client, hl, bid, ops=[{"op": "add", "tmp": "a", "kind": "note", "data": NOTE}])["ids"]["a"]
    assert client.put(f"/api/community/boards/{bid}", json={"title": "Sommerferien", "emoji": "☀️"}, headers=hm).status_code == 200
    # the parent area (parent token) manages every board
    assert client.put(f"/api/community/boards/{bid}", json={"archived": True}, headers=ph).status_code == 200
    b = client.get("/api/community/boards", headers=hm).json()[0]
    assert b["title"] == "Sommerferien" and b["archived"] and b["items"] == 1
    # archived: look only
    d = _sync(client, hl, bid, ops=[{"op": "add", "tmp": "b", "kind": "note", "data": NOTE}])
    assert d["errors"] and d["ids"] == {"b": None} and d["board"]["archived"] and len(d["items"]) == 1
    assert client.delete(f"/api/community/boards/{bid}", headers=ph).status_code == 200
    assert client.get("/api/community/boards", headers=hm).json() == []
    assert client.post(f"/api/community/boards/{bid}/sync", json={}, headers=hm).status_code == 400


def test_guests_and_strangers_refused(client):
    ph, hm, hl, mia, leo, papa = _logins(client)
    bid = client.post("/api/community/boards", json={"title": "Ferien"}, headers=hm).json()["id"]
    assert client.get("/api/community/boards").status_code == 401
    assert client.post(f"/api/community/boards/{bid}/sync", json={}).status_code == 401
    # a guest of a game (QR invitation) is no family member
    client.post("/api/community/bingo/start", json={}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "bingo"}, headers=hm).json()["invite"]
    g = {"X-FQ-Token": client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()["token"]}
    assert client.get("/api/community/boards", headers=g).status_code == 401
    assert client.post(f"/api/community/boards/{bid}/sync", json={"ops": [{"op": "add", "kind": "note", "data": NOTE}]}, headers=g).status_code == 401
    assert client.post("/api/community/boards", json={"title": "X"}, headers=g).status_code == 401


def test_items_add_move_edit_delete_and_since(client):
    ph, hm, hl, mia, leo, papa = _logins(client)
    bid = client.post("/api/community/boards", json={"title": "Ferien"}, headers=hm).json()["id"]
    d0 = _sync(client, hl, bid)
    assert d0["full"] and d0["items"] == [] and {p["name"] for p in d0["people"]} == {"Mia", "Leo", "Papa"}
    v0 = d0["version"]
    # one request: a note, a text, a line and a shape; a change inside the same batch may use the temporary id
    d = _sync(client, hm, bid, ops=[
        {"op": "add", "tmp": "n", "kind": "note", "data": NOTE},
        {"op": "add", "tmp": "t", "kind": "text", "data": {"x": 0, "y": 0, "t": "Hallo", "s": 48}},
        {"op": "add", "tmp": "s", "kind": "stroke", "data": {"x": 5, "y": 5, "c": 1, "w": 6, "p": [0, 0, 10, 10, 20, 5]}},
        {"op": "add", "tmp": "a", "kind": "shape", "data": {"x": 0, "y": 0, "f": "arrow", "w": -100, "h": 50}},
        {"op": "set", "id": "n", "data": {"x": 300}},
    ])
    assert d["errors"] == [] and all(d["ids"].values())
    n, s = d["ids"]["n"], d["ids"]["s"]
    # Leo gets only what changed since his version – with the author
    d1 = _sync(client, hl, bid, since=v0)
    assert not d1["full"] and len(d1["items"]) == 4
    note = next(i for i in d1["items"] if i["id"] == n)
    assert note["d"]["x"] == 300 and note["d"]["y"] == 20 and note["d"]["t"] == "Ferien planen" and note["by"] == mia
    assert next(i for i in d1["items"] if i["k"] == "shape")["d"]["w"] == -100
    v1 = d1["version"]
    assert _sync(client, hl, bid, since=v1)["items"] == []
    # moving, editing, bring to front, removing – last write wins
    _sync(client, hl, bid, ops=[{"op": "set", "id": n, "data": {"x": 1, "y": 2}}])
    _sync(client, hm, bid, ops=[{"op": "set", "id": n, "data": {"x": 50, "t": "Neu"}}, {"op": "front", "id": s}])
    d2 = _sync(client, hl, bid, since=v1)
    got = {i["id"]: i for i in d2["items"]}
    assert got[n]["d"] == {**got[n]["d"], "x": 50, "y": 2, "t": "Neu"} and got[n]["ub"] == mia
    assert got[s]["z"] == max(i["z"] for i in _sync(client, hl, bid)["items"])
    v2 = d2["version"]
    _sync(client, hl, bid, ops=[{"op": "del", "id": s}])
    d3 = _sync(client, hm, bid, since=v2)
    assert [(i["id"], i["del"]) for i in d3["items"]] == [(s, True)]
    assert len(_sync(client, hm, bid)["items"]) == 3                  # a full load leaves removed items out
    # undo: bring it back
    _sync(client, hl, bid, ops=[{"op": "restore", "id": s}])
    assert len(_sync(client, hm, bid)["items"]) == 4
    # unknown items and kinds are named, the rest of the batch counts
    d = _sync(client, hm, bid, ops=[{"op": "set", "id": 99999, "data": {}}, {"op": "add", "tmp": "x", "kind": "bomb", "data": {}},
                                    {"op": "add", "tmp": "y", "kind": "note", "data": NOTE}])
    assert len(d["errors"]) == 2 and d["ids"]["x"] is None and d["ids"]["y"]
    # an item of another board cannot be touched
    other = client.post("/api/community/boards", json={"title": "Anderes"}, headers=hm).json()["id"]
    assert _sync(client, hm, other, ops=[{"op": "del", "id": n}])["errors"]


def test_new_badge(client):
    ph, hm, hl, mia, leo, papa = _logins(client)
    bid = client.post("/api/community/boards", json={"title": "Ferien"}, headers=hm).json()["id"]
    _sync(client, hm, bid, ops=[{"op": "add", "kind": "note", "data": NOTE}])
    assert client.get("/api/me/community", headers=hm).json()["boards_new"] == 0       # own items are not new
    assert client.get("/api/me/community", headers=hl).json()["boards_new"] == 1
    assert client.get("/api/community/boards", headers=hl).json()[0]["new"] == 1
    _sync(client, hl, bid)
    assert client.get("/api/me/community", headers=hl).json()["boards_new"] == 0


def test_clean_limits():
    d = B.clean("note", {"x": 1e12, "y": "a", "c": 99, "w": 1, "t": "x" * 5000})
    assert d["x"] == B.COORD and d["y"] == 0 and d["c"] == B.COLORS - 1 and d["w"] == 40 and len(d["t"]) == B.NOTE_TEXT
    s = B.clean("stroke", {"p": list(range(5001))})
    assert len(s["p"]) == 2 * B.MAX_POINTS and s["p"][-2:] == [4998, 4999]
    with pytest.raises(CommunityError):
        B.clean("stroke", {"p": [1]})
    assert B.clean("shape", {"f": "star"})["f"] == "rect"
    assert B.clean("text", {"s": float("nan")})["s"] == 32 and B.clean("text", {"s": 1})["s"] == 10


def test_item_and_size_limits(fq, monkeypatch):
    pid = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    bid = fq.boards.create(prof, "Voll")
    monkeypatch.setattr(B, "MAX_ITEMS", 3)
    d = fq.boards.sync(prof, bid, 0, [{"op": "add", "tmp": i, "kind": "note", "data": NOTE} for i in range(5)])
    assert sum(1 for v in d["ids"].values() if v) == 3 and len(d["errors"]) == 2
    first = d["ids"]["0"]
    fq.boards.sync(prof, bid, 0, [{"op": "del", "id": first}])
    assert len(fq.boards.sync(prof, bid, 0, [{"op": "add", "kind": "note", "data": NOTE}])["items"]) == 3
    assert fq.boards.sync(prof, bid, 0, [{"op": "restore", "id": first}])["errors"]        # full again
    monkeypatch.setattr(B, "MAX_ITEMS", 2000)
    monkeypatch.setattr(B, "MAX_BYTES", 300)
    assert fq.boards.sync(prof, bid, 0, [{"op": "add", "kind": "note", "data": {"t": "x" * 200}}])["errors"]


def test_purge_old_removed_items(fq, monkeypatch):
    pid = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    bid = fq.boards.create(prof, "Viel")
    monkeypatch.setattr(B, "PURGE_AT", 4)
    monkeypatch.setattr(B, "KEEP_DELETED", 2)
    d = fq.boards.sync(prof, bid, 0, [{"op": "add", "tmp": i, "kind": "note", "data": NOTE} for i in range(6)])
    old = d["version"]
    d = fq.boards.sync(prof, bid, 0, [{"op": "del", "id": i} for i in d["ids"].values()])
    assert fq.db.val("SELECT COUNT(*) FROM board_item WHERE board_id=?", bid) == 2
    # a client older than the purge loads the whole board again
    d = fq.boards.sync(prof, bid, old)
    assert d["full"] and d["items"] == []


def test_presence_and_expiry(client):
    ph, hm, hl, mia, leo, papa = _logins(client)
    fq = client.app.state.fq
    clock = [1000.0]
    fq.boards.now = lambda: clock[0]
    bid = client.post("/api/community/boards", json={"title": "Ferien"}, headers=hm).json()["id"]
    _sync(client, hm, bid, presence={"x": 12.5, "y": -3, "view": [0, 0, 390, 700], "edit": None})
    d = _sync(client, hl, bid, presence={"x": "bad"})
    assert [(p["id"], p["x"], p["view"]) for p in d["presence"]] == [(mia, 12.5, [0, 0, 390, 700])]
    assert {p["name"] for p in client.get("/api/community/boards", headers=ph).json()[0]["here"]} == {"Mia", "Leo"}
    clock[0] += B.PRESENCE_TTL + 1
    assert _sync(client, hl, bid)["presence"] == []                     # Mia has been gone too long
    _sync(client, hm, bid)
    assert client.post(f"/api/community/boards/{bid}/leave", headers=hm).status_code == 200
    assert _sync(client, hl, bid)["presence"] == []
