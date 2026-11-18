"""Game battery of the children and the party mode of the parents (familyquest/battery.py)."""
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_api import setup_family

pytestmark = pytest.mark.battery          # the battery on as by default (conftest switches it off for the other tests)


def login(client, pid, pin=""):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, "pin": pin}).json()["token"]}


def clock(fq, start=datetime(2026, 3, 2, 15, 0, 0)):
    now = [start]
    fq.battery.now = lambda: now[0]
    return now


def tick(now, s=30):
    now[0] += timedelta(seconds=s)


def bat(client, h):
    return client.get("/api/me", headers=h).json()["battery"]


def start(client, h, game="jump"):
    return client.post(f"/api/community/{game}/start", json={"solo": True}, headers=h)


def coins(fq, pid, n):
    fq.rewards.book(pid, "coins", float(n), "test", "test", f"test:{pid}:{n}:{datetime.now().timestamp()}")


def test_defaults_start_costs_a_segment_and_empty_blocks_own_starts(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    b = bat(client, hm)
    assert (b["on"], b["charge"], b["cap"], b["cost"], b["unlimited"], b["free"]) == (True, 5, 5, 50, False, False)
    assert client.get("/api/me", headers=ph).json()["battery"] is None          # parents: no battery
    assert start(client, hm).status_code == 200
    assert bat(client, hm)["charge"] == 4
    # the same start again right after (double tap, a second device): not charged twice
    assert start(client, hm).status_code == 200
    assert bat(client, hm)["charge"] == 4
    for left in (3, 2, 1, 0):
        tick(now)
        assert start(client, hm).status_code == 200
        assert bat(client, hm)["charge"] == left
    tick(now)
    r = start(client, hm)
    assert r.status_code == 403 and "battery is empty" in r.json()["detail"]
    assert bat(client, hm)["charge"] == 0
    # joining a table somebody else opened is free – also with an empty battery
    assert client.post("/api/community/jump/start", json={}, headers=hl).status_code == 200
    assert client.post("/api/community/jump/join", headers=hm).status_code == 200
    assert bat(client, hm)["charge"] == 0 and bat(client, hl)["charge"] == 4
    # a parent's family quiz: the children join for free; parents are never charged
    assert start(client, ph).status_code == 200
    assert client.get("/api/me", headers=ph).json()["battery"] is None


def test_failed_start_gives_the_segment_back(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    clock(fq)
    r = client.post("/api/community/quiz/start", json={"quiz_id": 999999}, headers=hm)
    assert r.status_code >= 400
    assert bat(client, hm)["charge"] == 5
    assert fq.db.val("SELECT COUNT(*) FROM battery_log WHERE profile_id=?", mia, default=0) == 0


def test_recharge_books_coins_once_and_not_enough_coins(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    r = client.post("/api/me/battery/recharge", headers=hm)
    assert r.status_code == 400 and "full" in r.json()["detail"]
    for _ in range(5):
        tick(now)
        assert start(client, hm).status_code == 200
    r = client.post("/api/me/battery/recharge", headers=hm)
    assert r.status_code == 400 and r.json()["detail"] == "Not enough coins"
    coins(fq, mia, 120)
    r = client.post("/api/me/battery/recharge", headers=hm)
    assert r.status_code == 200, r.text
    assert r.json()["battery"]["charge"] == 5 and r.json()["coins"] == 70
    # a second tap: full already – nothing booked
    assert client.post("/api/me/battery/recharge", headers=hm).status_code == 400
    assert fq.rewards.balance(mia, "coins") == 70
    rows = fq.db.q("SELECT * FROM ledger WHERE profile_id=? AND event='energy_recharge'", mia)
    assert len(rows) == 1 and rows[0]["amount"] == -50
    # cost 0: recharging is free
    tick(now)
    start(client, hm)
    client.put("/api/parent/battery", json={"cost": 0}, headers=ph)
    assert client.post("/api/me/battery/recharge", headers=hm).json()["coins"] == 70
    assert client.post("/api/me/battery/recharge", headers=ph).status_code == 400   # parents have no battery


def test_parallel_starts_and_recharges_do_not_double_count(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    now = clock(fq)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda _: fq.battery.use(prof, "jump")[0], range(8)))
    assert res.count("new") == 1 and res.count("same") == 7
    assert fq.battery.state(prof)["charge"] == 4
    # different games in parallel: never below 0
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda i: fq.battery.use(prof, f"g{i}")[0], range(8)))
    assert res.count("new") == 4 and res.count(None) == 4
    assert fq.battery.state(prof)["charge"] == 0
    coins(fq, mia, 500)
    tick(now)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda _: _try(lambda: fq.battery.recharge(prof)), range(6)))
    assert res.count("ok") == 1
    assert fq.rewards.balance(mia, "coins") == 450


def _try(fn):
    try:
        fn()
        return "ok"
    except ValueError:
        return "err"


def test_unlimited_permanent_and_periods_with_expiry_and_end(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    r = client.put("/api/parent/battery", json={"unlimited": "forever"}, headers=ph)
    assert r.status_code == 200 and r.json()["family"]["unlimited"] == "forever"
    b = bat(client, hm)
    assert b["unlimited"] and b["forever"] and b["free"]
    for _ in range(7):
        tick(now)
        assert start(client, hm).status_code == 200
    assert bat(client, hm)["charge"] == 5
    client.put("/api/parent/battery", json={"unlimited": "off"}, headers=ph)
    assert not bat(client, hm)["unlimited"]
    # per child: one day – shows until when, ends by itself
    r = client.put(f"/api/parent/battery/{mia}", json={"unlimited": "day"}, headers=ph)
    assert r.status_code == 200
    b = bat(client, hm)
    assert b["unlimited"] and not b["forever"] and b["until"] == "2026-03-03 15:03:30"
    assert not bat(client, hl)["unlimited"]
    tick(now)
    start(client, hm)
    assert bat(client, hm)["charge"] == 5
    now[0] += timedelta(days=1)
    assert not bat(client, hm)["unlimited"]
    tick(now)
    start(client, hm)
    assert bat(client, hm)["charge"] == 4
    # one week / one month, then ended by the parent
    client.put(f"/api/parent/battery/{mia}", json={"unlimited": "week"}, headers=ph)
    assert bat(client, hm)["until"] == (now[0] + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    client.put(f"/api/parent/battery/{mia}", json={"unlimited": "month"}, headers=ph)
    assert bat(client, hm)["until"].startswith("2026-04-03")
    client.put(f"/api/parent/battery/{mia}", json={"unlimited": "family"}, headers=ph)
    assert not bat(client, hm)["unlimited"]
    # the family is unlimited, the child explicitly not
    client.put("/api/parent/battery", json={"unlimited": "forever"}, headers=ph)
    client.put(f"/api/parent/battery/{mia}", json={"unlimited": "off"}, headers=ph)
    assert not bat(client, hm)["unlimited"] and bat(client, hl)["unlimited"]
    assert client.put("/api/parent/battery", json={"unlimited": "year"}, headers=ph).status_code == 400


def test_per_child_values_override_the_family_default_and_off(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    r = client.put("/api/parent/battery", json={"cap": 3, "cost": 20}, headers=ph)
    assert r.status_code == 200 and (r.json()["family"]["cap"], r.json()["family"]["cost"]) == (3, 20)
    assert (bat(client, hm)["cap"], bat(client, hm)["charge"], bat(client, hm)["cost"]) == (3, 3, 20)
    client.put(f"/api/parent/battery/{mia}", json={"cap": 8, "cost": 0}, headers=ph)
    assert (bat(client, hm)["cap"], bat(client, hm)["charge"], bat(client, hm)["cost"]) == (8, 8, 0)
    assert bat(client, hl)["cap"] == 3
    # off for one child: no limit at all
    client.put(f"/api/parent/battery/{leo}", json={"on": False}, headers=ph)
    for _ in range(5):
        tick(now)
        assert start(client, hl).status_code == 200
    assert bat(client, hl)["free"] and bat(client, hl)["charge"] == 3
    # back to «as the family»
    client.put(f"/api/parent/battery/{mia}", json={"cap": None, "cost": None}, headers=ph)
    assert bat(client, hm)["cap"] == 3
    ov = client.get("/api/parent/battery", headers=ph).json()
    assert ov["kids"][1]["own"] == {"on": False}
    for bad in ({"cap": 0}, {"cap": 21}, {"cost": -1}, {"cost": 10001}, {"goal": "x"}):
        assert client.put("/api/parent/battery", json=bad, headers=ph).status_code == 400
    assert client.put(f"/api/parent/battery/{mia}", json={"cap": 50}, headers=ph).status_code == 400
    # family off: nobody has a limit
    client.put("/api/parent/battery", json={"on": False}, headers=ph)
    assert bat(client, hm)["free"]


def test_daily_goal_charges_once(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    for _ in range(4):
        tick(now)
        start(client, hm)
    assert bat(client, hm)["charge"] == 1
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", '{"daily_goal": 5}', mia)
    fq.rewards.emit(mia, "lesson_done")                     # 10 XP ≥ 5: the daily goal – default +1 segment
    assert bat(client, hm)["charge"] == 2
    fq.rewards.emit(mia, "lesson_done")
    fq.battery.on_reward("goal", mia, {})                   # the same day again: nothing more
    assert bat(client, hm)["charge"] == 2
    client.put("/api/parent/battery", json={"goal": "full"}, headers=ph)
    now[0] += timedelta(days=1)
    fq.battery.on_reward("goal", mia, {})
    assert bat(client, hm)["charge"] == 5
    client.put("/api/parent/battery", json={"goal": "plus", "goal_plus": 3}, headers=ph)
    for _ in range(4):
        tick(now)
        start(client, hm)
    now[0] += timedelta(days=1)
    fq.battery.on_reward("goal", mia, {})
    assert bat(client, hm)["charge"] == 4
    client.put("/api/parent/battery", json={"goal": "off"}, headers=ph)
    now[0] += timedelta(days=1)
    fq.battery.on_reward("goal", mia, {})
    assert bat(client, hm)["charge"] == 4


def test_chore_energy_bonus_once_and_capped(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    r = client.post("/api/parent/chores", json={"name": "Tisch decken", "points": 5, "profiles": [mia], "energy": 3, "confirm": True}, headers=ph)
    assert r.status_code == 200, r.text
    assert client.get("/api/parent/chores", headers=ph).json()["chores"][0]["energy"] == 3
    assert client.post("/api/parent/chores", json={"name": "X", "profiles": [mia], "energy": 21}, headers=ph).status_code == 400
    for _ in range(4):
        tick(now)
        start(client, hm)
    me = client.get("/api/me", headers=hm).json()
    assert me["chores"][0]["energy"] == 3
    uid = me["chores"][0]["uid"]
    client.post(f"/api/me/chores/{uid}/done", headers=hm)
    assert bat(client, hm)["charge"] == 1                    # pending: not yet
    tid = client.get("/api/parent/overview", headers=ph).json()["chores_pending"][0]["id"]
    assert client.post(f"/api/parent/chores/tasks/{tid}", json={"ok": True}, headers=ph).json()["status"] == "done"
    assert bat(client, hm)["charge"] == 4 and fq.rewards.balance(mia, "coins") == 5
    fq.battery.on_reward("chore", mia, {"task": tid})        # booked again: once only
    client.post(f"/api/parent/chores/tasks/{tid}", json={"ok": True}, headers=ph)
    assert bat(client, hm)["charge"] == 4
    # capped at the capacity
    tid2 = fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status) VALUES(?,?,?,?)", 1, mia, "2020-01-01", "pending")
    fq.chores.decide(tid2, True)
    assert bat(client, hm)["charge"] == 5


def test_game_corner_opening_costs_a_segment_and_duel_answer_is_free(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    r = client.post("/api/me/games/try", json={"game": "sudoku"}, headers=hm)
    assert r.status_code == 200 and r.json()["open"] and r.json()["battery"]["charge"] == 4
    assert client.post("/api/me/games/try", json={"game": "sudoku"}, headers=hm).json()["battery"]["charge"] == 4   # same start
    tick(now)
    assert client.post("/api/me/games/try", json={"game": "ttt"}, headers=hl).json()["battery"]["charge"] == 4
    assert client.post("/api/community/duel", json={"opponent": mia, "kind": "ttt"}, headers=hl).status_code == 200
    assert bat(client, hl)["charge"] == 4                     # the duel is part of the opened game corner game
    r = client.post("/api/me/games/try", json={"game": "ttt", "join": True}, headers=hm)
    assert r.status_code == 200 and r.json()["battery"]["charge"] == 4
    for _ in range(4):
        tick(now)
        client.post("/api/me/games/try", json={"game": "cube"}, headers=hm)
    tick(now)
    r = client.post("/api/me/games/try", json={"game": "patience"}, headers=hm)
    assert r.status_code == 403 and "battery is empty" in r.json()["detail"]
    # «join» without an invitation waiting is a normal start
    r = client.post("/api/me/games/try", json={"game": "pingpong", "join": True}, headers=hl)
    assert r.json()["battery"]["charge"] == 3


def test_parents_unaffected(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    now = clock(fq)
    client.put("/api/parent/battery", json={"cap": 1}, headers=ph)
    for _ in range(4):
        tick(now)
        assert start(client, ph).status_code == 200
        assert client.post("/api/me/games/try", json={"game": "sudoku"}, headers=ph).status_code == 200
    assert fq.db.val("SELECT COUNT(*) FROM battery", default=0) == 0


def test_parent_recharge_gift(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    for _ in range(3):
        tick(now)
        start(client, hm)
    r = client.post(f"/api/parent/battery/{mia}/recharge", headers=ph)
    assert r.status_code == 200 and r.json()["kids"][0]["state"]["charge"] == 5
    assert fq.rewards.balance(mia, "coins") == 0


# ---------------------------------------------------------------- party mode
def test_party_scope_unlock_battery_and_expiry(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    fq = client.app.state.fq
    now = clock(fq)
    client.put("/api/parent/games", json={"access": {"jump": {"mode": "off", "profiles": []},
                                                     "wuerfel": {"mode": "all", "profiles": [], "price": 300}}}, headers=ph)
    me = client.get("/api/me", headers=hm).json()
    assert "jump" not in me["games_list"] and "wuerfel" not in me["games_list"] and me["party"] is None
    for bad in ({"kids": [], "unlock": True}, {"unlock": False, "battery": False, "limits": False}, {"for": "7y"}):
        assert client.post("/api/parent/party", json=bad, headers=ph).status_code == 400
    r = client.post("/api/parent/party", json={"kids": [mia], "unlock": True, "battery": True, "limits": True, "for": "3h"}, headers=ph)
    assert r.status_code == 200 and r.json()["until"] == "2026-03-02 18:00:00"
    me = client.get("/api/me", headers=hm).json()
    assert me["party"]["until"] == "2026-03-02 18:00:00" and me["party"]["theme"]["id"] == "disco"
    assert {"jump", "wuerfel", "slots"} <= set(me["games_list"]) and not me["games_locked"]
    assert me["battery"]["party"] and me["battery"]["free"]
    assert client.get("/api/me", headers=hl).json()["party"] is None                  # Leo is not invited
    assert "jump" not in client.get("/api/me", headers=hl).json()["games_list"]
    for _ in range(7):
        tick(now)
        assert start(client, hm).status_code == 200                                    # unlocked and free
    assert bat(client, hm)["charge"] == 5
    assert fq.db.val("SELECT COUNT(*) FROM game_pass WHERE profile_id=?", mia, default=0) == 0    # nothing bought
    tick(now)
    start(client, hl, "wuerfel")                                                       # Leo: still locked
    assert bat(client, hl)["charge"] == 5
    # the party ends by itself – everything as before
    now[0] = datetime(2026, 3, 2, 18, 0, 1)
    me = client.get("/api/me", headers=hm).json()
    assert me["party"] is None and "jump" not in me["games_list"] and not me["battery"]["free"]
    assert start(client, hm).status_code == 403
    assert client.get("/api/parent/party", headers=ph).json() is None


def test_party_lifts_limits_only_with_the_option_and_can_be_ended(client):
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    fq = client.app.state.fq
    now = clock(fq)
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", '{"game_limit": {"all": 0, "days": {}}}', mia)
    r = start(client, hm)
    assert r.status_code == 403 and "Game time" in r.json()["detail"]
    assert client.get("/api/me", headers=hm).json()["time_left"]["games"] == 0
    # party only for the battery: the limit stays
    client.post("/api/parent/party", json={"kids": "all", "unlock": False, "battery": True, "limits": False}, headers=ph)
    assert start(client, hm).status_code == 403
    # «also lift limits»
    r = client.post("/api/parent/party", json={"kids": "all", "unlock": False, "battery": True, "limits": True, "for": "midnight"}, headers=ph)
    assert r.json()["until"] == "2026-03-03 00:00:00"
    tick(now)
    assert start(client, hm).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert me["time_left"]["games"] is None and me["party"]["limits"]
    assert client.post("/api/me/playtime", headers=hm).json()["ok"]
    assert fq.db.val("SELECT COUNT(*) FROM play_minute WHERE profile_id=?", mia, default=0) == 0   # no game time counted
    # ended by the parent
    assert client.delete("/api/parent/party", headers=ph).status_code == 200
    tick(now)
    assert start(client, hm).status_code == 403
    assert client.get("/api/me", headers=hm).json()["party"] is None


def test_party_forever_and_one_day(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    now = clock(fq)
    client.post("/api/parent/party", json={"unlock": True, "battery": False, "limits": False, "for": "forever"}, headers=ph)
    now[0] += timedelta(days=30)
    p = client.get("/api/parent/party", headers=ph).json()
    assert p["until"] is None and p["kids"] == "all"
    client.post("/api/parent/party", json={"unlock": True, "for": "day"}, headers=ph)
    assert client.get("/api/parent/party", headers=ph).json()["until"] == (now[0] + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    client.post("/api/parent/party", json={"unlock": True, "for": "1h"}, headers=ph)
    now[0] += timedelta(hours=1, seconds=1)
    assert client.get("/api/parent/party", headers=ph).json() is None


def test_migration_existing_children_start_full(fq, kid):
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    st = fq.battery.state(prof)
    assert st["charge"] == st["cap"] == 5 and st["on"]
    assert fq.db.val("SELECT energy FROM chore LIMIT 1", default=0) == 0
