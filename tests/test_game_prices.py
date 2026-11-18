"""Games with a price for children (familyquest/gamepasses.py): buy once, rent per day / week / month, the kid shop,
tables a parent opened for a locked game, the one-armed bandit in the standard model and its luck slider."""
import random
import sqlite3
from datetime import datetime

from familyquest import slots
from familyquest.gamepasses import add_period
from test_api import setup_family


def login(client, pid, pin=""):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, "pin": pin}).json()["token"]}


def put_game(client, ph, game, **kw):
    a = {"mode": "all", **kw}
    r = client.put("/api/parent/games", json={"access": {game: a}}, headers=ph)
    assert r.status_code == 200, r.text
    return r.json()["access"][game]


def coins(client, ph, pid, n):
    client.post("/api/parent/book", json={"profile_id": pid, "account": "coins", "amount": n}, headers=ph)


def me(client, h):
    d = client.get("/api/me", headers=h).json()
    d["games_locked"] = [g for g in d["games_locked"] if g["game"] != "slots"]      # priced by default (250)
    return d


def shop(client, h):
    return [g for g in client.get("/api/me/games/shop", headers=h).json()["games"] if g["game"] != "slots"]


def test_price_zero_is_free_and_buying_once(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    a = client.get("/api/parent/games", headers=ph).json()["access"]["jump"]
    assert a["price"] == 0 and a["rent"] == 0 and a["period"] == "week"
    assert "jump" in me(client, hm)["games_list"]                                    # free by default
    assert put_game(client, ph, "jump", price=300)["price"] == 300
    d = me(client, hm)
    assert "jump" not in d["games_list"] and [g["game"] for g in d["games_locked"]] == ["jump"]
    assert client.get("/api/community/jump", headers=hm).status_code == 403
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/community/jump", headers=ph).status_code == 200          # parents always, for free
    assert shop(client, hm) == [{"game": "jump", "price": 300, "rent": 0, "period": "week", "bought": False, "rent_until": None, "left_s": 0, "open": False}]
    r = client.post("/api/me/games/buy", json={"game": "jump", "kind": "buy"}, headers=hm)
    assert r.status_code == 400 and r.json()["detail"] == "Not enough coins"
    assert client.post("/api/me/games/buy", json={"game": "jump", "kind": "rent"}, headers=hm).status_code == 400   # no rent price
    coins(client, ph, mia, 400)
    r = client.post("/api/me/games/buy", json={"game": "jump", "kind": "buy"}, headers=hm).json()
    assert r["coins"] == 100 and r["games"][0]["game"] == "jump" and r["games"][0]["bought"] and r["games"][0]["open"]
    assert client.post("/api/me/games/buy", json={"game": "jump", "kind": "buy"}, headers=hm).status_code == 400    # no double booking
    rows = fq.db.q("SELECT amount, event, ref FROM ledger WHERE profile_id=? AND event='game_buy'", mia)
    assert rows == [{"amount": -300.0, "event": "game_buy", "ref": f"game:buy:jump:{mia}"}]
    d = me(client, hm)
    assert "jump" in d["games_list"] and d["games_locked"] == []
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 200
    assert "jump" not in me(client, hl)["games_list"]                                 # Leo did not buy it
    # back to 0: free again for everybody – and Mia keeps hers when a price comes back
    put_game(client, ph, "jump", price=0)
    assert "jump" in me(client, hl)["games_list"] and shop(client, hl) == []
    put_game(client, ph, "jump", price=50)
    assert "jump" in me(client, hm)["games_list"] and "jump" not in me(client, hl)["games_list"]
    # a game switched off is not for sale; parents do not buy
    put_game(client, ph, "domino", price=10)
    client.put("/api/parent/games", json={"access": {"domino": {"mode": "off"}}}, headers=ph)
    assert client.post("/api/me/games/buy", json={"game": "domino", "kind": "buy"}, headers=hm).status_code == 403
    assert client.post("/api/me/games/buy", json={"game": "jump", "kind": "buy"}, headers=ph).status_code == 400
    assert client.put("/api/parent/games", json={"access": {"jump": {"mode": "all", "price": -1}}}, headers=ph).status_code == 400
    assert client.put("/api/parent/games", json={"access": {"jump": {"mode": "all", "period": "year"}}}, headers=ph).status_code == 400


def test_rent_day_week_month_expiry_extension_and_buy_replaces_rent(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = [datetime(2026, 1, 31, 10, 0, 0)]
    fq.passes.now = lambda: now[0]
    coins(client, ph, mia, 1000)
    put_game(client, ph, "tschau", rent=20, period="day")
    assert "tschau" not in me(client, hm)["games_list"]                              # rent only: locked too
    assert client.post("/api/me/games/buy", json={"game": "tschau", "kind": "buy"}, headers=hm).status_code == 400   # no buy price
    g = client.post("/api/me/games/buy", json={"game": "tschau", "kind": "rent", "until": ""}, headers=hm).json()["games"][0]
    assert g["rent_until"] == "2026-02-01 10:00:00" and g["left_s"] == 86400 and not g["bought"]
    assert "tschau" in me(client, hm)["games_list"]
    # a second tap with the old end: nothing booked
    r = client.post("/api/me/games/buy", json={"game": "tschau", "kind": "rent", "until": ""}, headers=hm)
    assert r.status_code == 400
    assert fq.rewards.balance(mia, "coins") == 980
    # extended: the day comes after the current end
    g = client.post("/api/me/games/buy", json={"game": "tschau", "kind": "rent", "until": "2026-02-01 10:00:00"}, headers=hm).json()["games"][0]
    assert g["rent_until"] == "2026-02-02 10:00:00"
    refs = [r["ref"] for r in fq.db.q("SELECT ref FROM ledger WHERE event='game_rent' ORDER BY id")]
    assert len(refs) == 2 and len(set(refs)) == 2
    now[0] = datetime(2026, 2, 2, 10, 0, 1)                                          # over
    assert "tschau" not in me(client, hm)["games_list"]
    assert client.get("/api/community/cards/tschau", headers=hm).status_code == 403
    # a week, a month (from 31 January: to the end of February)
    put_game(client, ph, "domino", rent=30, period="week")
    g = client.post("/api/me/games/buy", json={"game": "domino", "kind": "rent"}, headers=hm).json()["games"]
    assert next(x for x in g if x["game"] == "domino")["rent_until"] == "2026-02-09 10:00:01"
    now[0] = datetime(2026, 1, 31, 12, 0, 0)
    put_game(client, ph, "poker", rent=50, period="month")
    g = client.post("/api/me/games/buy", json={"game": "poker", "kind": "rent"}, headers=hm).json()["games"]
    assert next(x for x in g if x["game"] == "poker")["rent_until"] == "2026-02-28 12:00:00"
    assert add_period(datetime(2026, 12, 15, 8, 0), "month") == datetime(2027, 1, 15, 8, 0)
    # buying replaces renting
    put_game(client, ph, "poker", rent=50, period="month", price=200)
    g = client.post("/api/me/games/buy", json={"game": "poker", "kind": "buy"}, headers=hm).json()["games"]
    p = next(x for x in g if x["game"] == "poker")
    assert p["bought"] and p["rent_until"] is None
    assert client.post("/api/me/games/buy", json={"game": "poker", "kind": "rent"}, headers=hm).status_code == 400
    now[0] = datetime(2027, 6, 1)
    assert "poker" in me(client, hm)["games_list"]


def test_parent_table_of_a_locked_game_can_be_joined_but_no_own_start(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.put("/api/parent/games", json={"access": {"jump": {"mode": "off"}, "wuerfel": {"mode": "all", "price": 100}}}, headers=ph)
    assert client.get("/api/community/jump", headers=hm).status_code == 403
    # a child's table does not open the game
    assert client.post("/api/community/wuerfel/start", json={}, headers=hm).status_code == 403
    assert client.post("/api/community/jump/start", json={}, headers=ph).status_code == 200          # a parent's family table
    d = me(client, hm)
    assert d["games_tables"] == ["jump"] and d["community"]["jump"] and "jump" not in d["games_list"]
    assert [t["game"] for t in client.get("/api/community/tables", headers=hm).json()] == ["jump"]
    assert client.get("/api/community/jump", headers=hm).status_code == 200
    assert client.post("/api/community/jump/join", headers=hm).status_code == 200
    assert client.post("/api/community/jump/start", json={"solo": True}, headers=hm).status_code == 403   # no own table
    assert client.post("/api/community/jump/start", json={}, headers=hl).status_code == 403
    assert client.post("/api/community/jump/join", headers=hl).status_code == 200
    assert client.post("/api/community/jump/begin", headers=ph).status_code == 200
    assert client.post("/api/community/jump/sync", json={"t": 0.5, "jumps": [], "hits": []}, headers=hm).status_code == 200   # playing
    assert client.get("/api/community/tables", headers=hm).json() == []                # running and joined: no note
    client.post("/api/community/jump/end", headers=ph)
    assert me(client, hm)["games_tables"] == [] and client.get("/api/community/jump", headers=hm).status_code == 403
    # a price-locked game: the same – and alone at a parent's solo table: nothing
    assert client.post("/api/community/wuerfel/start", json={"solo": True}, headers=ph).status_code == 200
    assert me(client, hm)["games_tables"] == [] and client.get("/api/community/wuerfel", headers=hm).status_code == 403
    client.post("/api/community/wuerfel/end", headers=ph)
    assert client.post("/api/community/wuerfel/start", json={}, headers=ph).status_code == 200
    assert me(client, hm)["games_tables"] == ["wuerfel"]
    assert client.post("/api/community/wuerfel/join", headers=hm).status_code == 200


def test_slots_default_price_250_luck_and_old_owners_keep_it(client, tmp_path):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    a = client.get("/api/parent/games", headers=ph).json()
    assert a["access"]["slots"]["price"] == 250 and a["access"]["slots"]["luck"] == 5 and a["slots_returns"]["5"] == 92
    st = client.get("/api/me/slots", headers=hm).json()
    assert st["owned"] is False and st["price"] == 250 and "slots" not in me(client, hm)["games_list"]
    assert [g["game"] for g in client.get("/api/me", headers=hm).json()["games_locked"]] == ["slots"]
    coins(client, ph, mia, 251)
    assert client.post("/api/me/games/buy", json={"game": "slots", "kind": "buy"}, headers=hm).json()["coins"] == 1
    assert client.get("/api/me/slots", headers=hm).json()["owned"] and "slots" in me(client, hm)["games_list"]
    assert put_game(client, ph, "slots", luck=9)["luck"] == 9
    assert client.put("/api/parent/games", json={"access": {"slots": {"mode": "all", "luck": 11}}}, headers=ph).status_code == 400
    seen = []
    client.app.state.fq.slots.spin_reels = lambda luck: seen.append(luck) or ["bell", "lemon", "star"]
    assert client.post("/api/me/slots/spin", headers=hm).json()["win"] == 0 and seen == [9]
    # the update: whoever had the unlock «slot_machine» (bought for 150 before) has the game bought
    from familyquest.db import MIGRATIONS, Database
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    for i, sql in enumerate(MIGRATIONS[:34], start=1):
        c.executescript("BEGIN;" + sql + f";PRAGMA user_version={i};COMMIT;")
    c.execute("INSERT INTO profile(id, name) VALUES(7, 'Anna')")
    c.execute("INSERT INTO profile(id, name) VALUES(8, 'Ben')")
    c.execute("INSERT INTO unlock(profile_id, item) VALUES(7, 'slot_machine')")
    c.commit(); c.close()
    db = Database(p)
    assert [(r["profile_id"], r["game"], r["bought"]) for r in db.q("SELECT * FROM game_pass")] == [(7, "slots", 1)]


def test_slots_return_per_luck_level_by_simulation():
    assert 0.98 < slots.expected_return() < 0.99                                     # the plain reels
    assert slots.target_return(1) == 0.6 and slots.target_return(5) == 0.92 and abs(slots.target_return(10) - 1.2) < 1e-9
    rng = random.Random(42)
    last = 0
    for luck in range(1, 11):
        table = slots.outcomes(luck)
        assert abs(sum(table.values()) - 1) < 1e-9 and min(table.values()) > 0
        n = 60000
        back = sum(slots.payout(slots.spin_reels(luck, rng)) for _ in range(n)) / n
        assert abs(back - slots.target_return(luck)) < 0.035, (luck, back)
        assert back > last - 0.02
        last = back
    # the reels show the outcome that was drawn
    for kind in ("three:seven", "cherry:2", "cherry:1", "none"):
        for _ in range(50):
            r = slots.reels_for(kind, rng)
            assert slots._outcome(r) == kind
