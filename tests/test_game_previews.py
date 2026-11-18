"""Default rents of the quick games and the game corner, and free tries before buying / renting
(familyquest/gamepasses.py: DEFAULT_RENT, `preview`)."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from test_api import setup_family

pytestmark = pytest.mark.game_prices          # the real defaults (conftest switches them off for the other tests)

QUICK = ["paarjagd", "wuerfel", "jump", "klatsch", "sternlauf", "snack", "verkehr"]
ARCADE = ["ttt", "sudoku", "patience", "pingpong", "cube", "slots"]


def login(client, pid, pin=""):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, "pin": pin}).json()["token"]}


def put_game(client, ph, game, **kw):
    r = client.put("/api/parent/games", json={"access": {game: {"mode": "all", **kw}}}, headers=ph)
    assert r.status_code == 200, r.text
    return r.json()["access"][game]


def used(fq, pid, game):
    return fq.db.val("SELECT previews_used FROM game_pass WHERE profile_id=? AND game=?", pid, game, default=0)


def clock(fq):
    now = [datetime(2026, 3, 2, 15, 0, 0)]
    fq.passes.now = lambda: now[0]
    return now


def test_defaults_rent_per_group_and_explicit_values_stay(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    acc = client.get("/api/parent/games", headers=ph).json()["access"]
    for g in QUICK:
        assert (acc[g]["price"], acc[g]["rent"], acc[g]["period"], acc[g]["preview"]) == (0, 100, "week", 1), g
    for g in ARCADE:
        assert (acc[g]["rent"], acc[g]["period"], acc[g]["preview"]) == (20, "day", 1), g
        assert acc[g]["price"] == (250 if g == "slots" else 0)
    for g in ("quiz", "jass", "schach", "poker"):
        assert (acc[g]["price"], acc[g]["rent"], acc[g]["preview"]) == (0, 0, 1)
    d = client.get("/api/me", headers=hm).json()
    assert {o["game"] for o in d["games_locked"]} == set(QUICK + ARCADE) and "jass" in d["games_list"]
    assert all(o["tries_left"] == 1 and o["preview"] == 1 for o in d["games_locked"])
    # an entry stored without price / rent / preview (older setting): the defaults
    client.put("/api/parent/settings", json={"games_access": {"jump": {"mode": "all", "profiles": []}}}, headers=ph)
    a = client.get("/api/parent/games", headers=ph).json()["access"]["jump"]
    assert (a["rent"], a["period"], a["preview"]) == (100, "week", 1)
    # saved by beta 13 (rent 0 shown as default, no free tries yet): the new default rent applies
    client.put("/api/parent/settings", json={"games_access": {"jump": {"mode": "all", "profiles": [], "price": 0, "rent": 0, "period": "week"}}}, headers=ph)
    a = client.get("/api/parent/games", headers=ph).json()["access"]["jump"]
    assert (a["rent"], a["period"]) == (100, "week")
    # explicit 0 stays 0 – also the free tries; the parents' page sends what it shows (the whole entry)
    assert (put_game(client, ph, "jump", rent=0)["rent"]) == 0
    put_game(client, ph, "sudoku", rent=0, price=0, preview=0)
    acc = client.get("/api/parent/games", headers=ph).json()["access"]
    assert acc["jump"]["rent"] == 0 and acc["jump"]["preview"] == 1
    assert (acc["sudoku"]["rent"], acc["sudoku"]["preview"]) == (0, 0)
    stored = client.app.state.fq.db.get_setting("games_access")
    assert stored["jump"]["rent"] == 0 and stored["sudoku"]["preview"] == 0
    a = client.put("/api/parent/games", json={"access": {"cube": {**acc["cube"], "preview": 3}}}, headers=ph).json()["access"]["cube"]
    assert (a["rent"], a["period"], a["preview"]) == (20, "day", 3)
    d = client.get("/api/me", headers=hm).json()
    assert "jump" in d["games_list"] and "sudoku" in d["games_list"]
    assert next(o for o in d["games_locked"] if o["game"] == "cube")["tries_left"] == 3
    for bad in (21, -1, "x"):
        assert client.put("/api/parent/games", json={"access": {"jump": {"mode": "all", "preview": bad}}}, headers=ph).status_code == 400


def test_family_game_try_once_per_table_no_double_count_and_locked_again(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    put_game(client, ph, "jump", rent=100, period="week", preview=2)
    d = client.get("/api/me", headers=hm).json()
    assert "jump" not in d["games_list"] and d["games_trial"]["jump"] == {"left": 2, "member": False}
    assert client.get("/api/community/jump", headers=hm).status_code == 200          # a look while tries are left
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 200
    assert used(fq, mia, "jump") == 1
    # a double tap / a second device right after: the same try
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 200
    assert used(fq, mia, "jump") == 1
    # seated: the table can be played – nothing more is counted
    now[0] += timedelta(seconds=30)
    assert client.get("/api/community/jump", headers=hm).status_code == 200
    assert client.post("/api/community/jump/sync", json={"t": 0.2}, headers=hm).status_code != 403
    assert client.get("/api/me", headers=hm).json()["games_trial"]["jump"] == {"left": 1, "member": True}
    assert used(fq, mia, "jump") == 1
    assert client.post("/api/community/jump/end", headers=hm).status_code == 200
    # a new table (also «again») is a new try
    assert client.post("/api/community/jump/start", json={}, headers=hm).status_code == 200
    assert used(fq, mia, "jump") == 2
    assert client.post("/api/community/jump/join", headers=hm).status_code != 403   # seated already: no try
    assert used(fq, mia, "jump") == 2
    assert client.post("/api/community/jump/end", headers=hm).status_code == 200
    now[0] += timedelta(seconds=30)
    r = client.post("/api/community/jump/start", json={"solo": True}, headers=hm)
    assert r.status_code == 403 and "No free tries left" in r.json()["detail"]
    assert used(fq, mia, "jump") == 2
    # locked again as before once the try is over
    now[0] += timedelta(hours=3)
    d = client.get("/api/me", headers=hm).json()
    assert "jump" not in d["games_list"] and "jump" not in d["games_trial"]
    assert next(o for o in d["games_locked"] if o["game"] == "jump")["tries_left"] == 0
    assert client.get("/api/community/jump", headers=hm).status_code == 403
    # Leo has his own tries; a start that fails gives the try back
    assert client.post("/api/community/jump/join", headers=hl).status_code == 400     # no table to join
    assert used(fq, leo, "jump") == 0
    # parents: never locked, nothing counted
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=ph).status_code == 200
    assert fq.db.q1("SELECT * FROM game_pass WHERE game='jump' AND profile_id NOT IN (?, ?)", mia, leo) is None


def test_parallel_tries_cannot_use_more_than_there_are(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    now = clock(fq)
    a = put_game(client, ph, "wuerfel", preview=2)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    assert fq.use_game_try(prof, "wuerfel") == "new"
    assert fq.use_game_try(prof, "wuerfel") == "same"                     # within TRY_SAME_S
    now[0] += timedelta(seconds=11)
    assert fq.use_game_try(prof, "wuerfel") == "new"
    now[0] += timedelta(seconds=11)
    assert fq.use_game_try(prof, "wuerfel") is None
    assert used(fq, mia, "wuerfel") == 2 and fq.passes.tries_left(mia, "wuerfel", a) == 0
    # parallel requests (threads): never more than the tries
    put_game(client, ph, "klatsch", preview=3)
    import threading
    res = []
    now[0] += timedelta(minutes=1)

    def go():
        res.append(fq.passes.use_try(mia, "klatsch", fq.games_access()["klatsch"], same=False))
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert res.count("new") == 3 and used(fq, mia, "klatsch") == 3


def test_parent_table_joined_without_a_try(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    assert client.post("/api/community/jump/start", json={}, headers=ph).status_code == 200      # a parent's family table
    assert client.post("/api/community/jump/join", headers=hm).status_code == 200
    assert used(fq, mia, "jump") == 0
    assert client.get("/api/me", headers=hm).json()["games_trial"]["jump"]["left"] == 1


def test_game_corner_try_and_duel(client):
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    assert client.post("/api/me/games/try", json={"game": "jump"}, headers=hm).status_code == 400   # family game: at a table
    r = client.post("/api/me/games/try", json={"game": "sudoku"}, headers=hm).json()
    assert r == {"ok": True, "tries_left": 0, "open": False} and used(fq, mia, "sudoku") == 1
    assert client.post("/api/me/games/try", json={"game": "sudoku"}, headers=hm).status_code == 200   # double tap
    assert used(fq, mia, "sudoku") == 1
    assert client.post("/api/me/playtime", headers=hm).json()["ok"]
    now[0] += timedelta(seconds=20)
    r = client.post("/api/me/games/try", json={"game": "sudoku"}, headers=hm)
    assert r.status_code == 403 and used(fq, mia, "sudoku") == 1
    d = client.get("/api/me", headers=hm).json()
    assert "sudoku" not in d["games_list"] and next(o for o in d["games_locked"] if o["game"] == "sudoku")["tries_left"] == 0
    # a duel of the game corner on a try (Tic-Tac-Toe) – against a parent
    papa = fq.db.val("SELECT id FROM profile WHERE role='parent'")
    assert client.post("/api/community/duel", json={"opponent": papa, "kind": "ttt"}, headers=hm).status_code == 403
    assert client.post("/api/me/games/try", json={"game": "ttt"}, headers=hm).status_code == 200
    assert client.post("/api/community/duel", json={"opponent": papa, "kind": "ttt"}, headers=hm).status_code == 200
    assert used(fq, mia, "ttt") == 1
    # a game that is free or bought: nothing used
    put_game(client, ph, "cube", rent=0)
    assert client.post("/api/me/games/try", json={"game": "cube"}, headers=hm).json()["open"] and used(fq, mia, "cube") == 0
    # switched off: no try
    client.put("/api/parent/games", json={"access": {"patience": {"mode": "off"}}}, headers=ph)
    assert client.post("/api/me/games/try", json={"game": "patience"}, headers=hm).status_code == 403


def test_slots_free_try_is_one_spin(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 10}, headers=ph)
    st = client.get("/api/me/slots", headers=hm).json()
    assert st["owned"] is False and st["tries_left"] == 1 and st["rent"] == 20 and st["period"] == "day"
    assert client.post("/api/me/games/try", json={"game": "slots"}, headers=hm).json()["tries_left"] == 1   # opening: nothing
    fq.slots.spin_reels = lambda luck: ["bell", "lemon", "star"]
    r = client.post("/api/me/slots/spin", headers=hm)
    assert r.status_code == 200 and r.json()["tries_left"] == 0 and r.json()["coins"] == 9
    assert used(fq, mia, "slots") == 1
    r = client.post("/api/me/slots/spin", headers=hm)
    assert r.status_code == 400 and used(fq, mia, "slots") == 1
    # no coins for the bet: the try is not used
    put_game(client, ph, "slots", preview=3)
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": -9}, headers=ph)
    assert client.post("/api/me/slots/spin", headers=hm).status_code == 400 and used(fq, mia, "slots") == 1


def test_migration_36_everybody_starts_with_no_try_used(tmp_path):
    from familyquest.db import MIGRATIONS, Database
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    for i, sql in enumerate(MIGRATIONS[:35], start=1):
        c.executescript("BEGIN;" + sql + f";PRAGMA user_version={i};COMMIT;")
    c.execute("INSERT INTO profile(id, name) VALUES(7, 'Anna')")
    c.execute("INSERT INTO game_pass(profile_id, game, bought) VALUES(7, 'jump', 1)")
    c.commit(); c.close()
    db = Database(p)
    r = db.q1("SELECT * FROM game_pass")
    assert r["previews_used"] == 0 and r["preview_at"] is None and r["bought"] == 1
