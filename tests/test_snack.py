"""«Snack Rush» – the customer stream (the same for everybody), the server's checks of the serves, angry customers, the
till, the end and ranking, bots, the table in the app (coins once, guests, without bots, the running list)."""
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from familyquest import snack as sn
from familyquest.community import CommunityError

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
NO_BOTS = "Playing with bots is switched off for this game"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=2, bots=0, level="normal", solo=False, seed=7, rng_seed=1, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "snack", "rules": {**sn.DEFAULTS, "level": level, **rules}, "players": players, "phase": "lobby", "solo": solo}
    clock = Clock()
    t = sn.Table(st, random.Random(rng_seed), now=clock)
    t.setup(seed)
    return t, clock


def at(t, clock, gt, alive=()):
    """Move the clock to this game time (these players' apps stay alive)."""
    clock.t = t.st["t0"] + gt
    for p in alive:
        t.st["run"][p]["seen"] = clock.t


def first_with(t, foods, upto=200):
    """The first customer whose order has only these foods."""
    return next(i for i, (a, p, o) in enumerate(t.custs(upto)) if set(o) <= set(foods))


# ---------------------------------------------------------------- the stream
def test_customer_stream_is_the_same_for_a_seed_and_gets_harder():
    c = sn.customers(42, "normal", list(sn.FOOD_KEYS), 600)
    assert c == sn.customers(42, "normal", list(sn.FOOD_KEYS), 600) and c != sn.customers(43, "normal", list(sn.FOOD_KEYS), 600)
    assert sn.customers(42, "normal", list(sn.FOOD_KEYS), 200) == c[:len(sn.customers(42, "normal", list(sn.FOOD_KEYS), 200))]
    assert c[0][0] == sn.FIRST and all(1 <= len(o) <= 3 for _, _, o in c)
    assert all(b[0] > a[0] for a, b in zip(c, c[1:]))
    assert {f for _, _, o in c for f in o} == set(sn.FOOD_KEYS)
    early = [x for x in c if x[0] < 60]
    late = [x for x in c if 240 <= x[0] < 300]
    assert len(late) > len(early)                                                    # more customers …
    assert sum(len(o) for *_, o in late) / len(late) > sum(len(o) for *_, o in early) / len(early)   # … bigger orders
    lp = lambda xs: sum(p - 4 * len(o) - max(sn.chain(f) for f in o) for _, p, o in xs) / len(xs)
    assert lp(late) < lp(early)                                                      # … less patience
    # only the chosen foods; easier levels: fewer customers, more patience
    assert {f for *_, o in sn.customers(1, "normal", ["drink", "pizza"], 300) for f in o} == {"drink", "pizza"}
    easy, hard = sn.customers(5, "easy", list(sn.FOOD_KEYS), 300), sn.customers(5, "hard", list(sn.FOOD_KEYS), 300)
    assert len(easy) < len(sn.customers(5, "normal", list(sn.FOOD_KEYS), 300)) < len(hard)
    assert min(p for _, p, _ in easy[:5]) > max(p for _, p, _ in hard[:5]) - 10


def test_setup_one_seed_from_the_server_and_the_rules():
    t, clock = table(3)
    assert t.st["phase"] == "play" and t.st["seed"] == 7 and t.st["t0"] == clock.t + sn.COUNTDOWN
    assert all(r["served"] == {} and r["angry"] == {} and r["out"] is None for r in t.st["run"].values())
    st = {"kind": "snack", "rules": dict(sn.DEFAULTS), "players": [{"id": "1", "name": "A"}], "phase": "lobby"}
    sn.Table(st).setup()
    assert 1 <= st["seed"] < 2 ** 31


# ---------------------------------------------------------------- the server checks the serves
def test_a_serve_is_checked_and_pays_with_stars_and_tip():
    t, clock = table(1, solo=True, foods="drink")
    a, p, o = t.custs(10)[0]
    assert o == ["drink"]
    at(t, clock, a + 0.5, ["1"])
    assert t.report("1", a + 0.5, [[0, a + 0.5]]) == [0]                         # a drink needs 3 s from the start: too fast
    at(t, clock, a + 3.2, ["1"])
    assert t.report("1", a + 3.2, [[0, a + 3.2], [0, a + 3.2]]) == [0]           # once only
    assert t.st["run"]["1"]["served"]["0"] == [round(a + 3.2, 3), 3, sn.PRICE["drink"] + sn.TIP[3], 1]
    assert t.till("1") == sn.PRICE["drink"] + sn.TIP[3] - sn.cost("drink", "normal")
    assert sn.stars(0, 30, 5) == 3 and sn.stars(0, 30, 15) == 2 and sn.stars(0, 30, 25) == 1


def test_serves_before_the_customer_came_after_patience_in_the_future_or_unknown_are_refused():
    t, clock = table(1, solo=True, foods="drink")
    cs = t.custs(100)
    a1, p1, _ = cs[1]
    at(t, clock, a1 - 2, ["1"])
    assert t.report("1", a1 - 2, [[1, a1 - 2]]) == [1]                           # not there yet
    at(t, clock, a1 + 5, ["1"])
    assert t.report("1", a1 + 5, [[1, a1 + 6.5]]) == [1]                          # in the future
    assert t.report("1", a1 + 5, [[999, a1 + 4], ["x", 1], [1]]) == [999]          # unknown customer; junk is ignored
    a, p, _ = cs[0]
    at(t, clock, a + p + 2, ["1"])
    assert t.report("1", a + p + 2, [[0, a + p + 1.5]]) == [0]                    # patience ran out
    at(t, clock, a1 + 20, ["1"])
    assert t.report("1", a1 + 20, [[1, a1 + 5]]) == [1]                           # reported far too late (LATE)


def test_the_stand_cannot_serve_more_than_its_stations_can_make():
    """Two grill places, 4 s + 2 s assembling: 10 burgers in 10 seconds cannot be – the bookings catch it."""
    free = {}
    ok = [sn.book(free, ["burger"], 7.0 + k * 0.2) for k in range(4)]
    assert ok == [True, True, False, False]                                      # the 3rd burger is ready at 10 s at the earliest
    assert sn.book(free, ["burger"], 10.0) and sn.book(free, ["burger"], 10.0)
    assert not sn.book(free, ["burger", "burger"], 11.0)
    # food made ahead is fine – but only HOLD seconds ahead
    free = {}
    assert all(sn.book(free, ["pizza"], 60.0) for _ in range(6))                 # 2 ovens × 6 s: plenty of pizzas by 60 s
    free = {}
    assert sum(sn.book(free, ["pizza"], 200.0) for _ in range(40)) == 2 * int(sn.HOLD // 6)
    # the prep counter is shared by burger, hot dog and fries
    free = {}
    assert sn.book(free, ["burger", "burger", "fries"], 6.3) and sn.book({}, ["hotdog"], 6.3)
    assert not sn.book(free, ["hotdog"], 6.3)                                    # the prep counter is full until 6 s


def test_angry_customers_are_decided_by_the_server_and_cost_no_payment():
    t, clock = table(2)
    cs = t.custs(100)
    a, p, _ = cs[0]
    at(t, clock, a + p + 1, ["1", "2"])
    t.tick()
    assert t.angry("1") == 0                                                     # a serve may still be on its way
    t.report("2", a + p + 1, [], [0])                                            # P2's app says so itself: angry now
    assert t.angry("2") == 1 and t.st["run"]["2"]["angry"]["0"] == round(a + p, 3)
    at(t, clock, a + p + sn.FINAL + 0.5, ["1", "2"])
    t.tick()
    assert t.angry("1") == 1 and t.till("1") == 0
    assert t.report("1", a + p + sn.FINAL, [[0, a + p - 1]]) == [0]              # too late: angry stays
    t.report("1", 0, [], [1])                                                    # the next one is not angry yet
    assert "1" not in t.st["run"]["1"]["angry"]


def test_the_spent_money_counts_at_least_the_ingredients_of_the_served_food():
    t, clock = table(1, solo=True, foods="burger")
    a, p, _ = t.custs(10)[0]
    at(t, clock, a + 7, ["1"])
    t.report("1", a + 7, [[0, a + 7]], [], 0)                                    # an app that says it spent nothing
    paid = t.st["run"]["1"]["served"]["0"][2]
    assert t.money("1") == (paid, 3) and t.till("1") == paid - 3
    t.report("1", a + 7, [], [], 12)                                             # burnt food: it spent more
    assert t.money("1") == (paid, 12)
    t.report("1", a + 7, [], [], 5)                                              # never less again
    assert t.money("1")[1] == 12
    t.report("1", a + 7, [], [], float("nan"))
    t.report("1", a + 7, [], [], -3)
    assert t.money("1")[1] == 12
    assert sn.cost("burger", "easy") == 1 and sn.cost("fries", "easy") == 0 and sn.cost("pizza", "hard") == 3


def test_only_own_player_and_only_while_running():
    t, clock = table(1, bots=1)
    with pytest.raises(CommunityError):
        t.report("bot1", 0)
    with pytest.raises(CommunityError):
        t.report("9", 0)
    t.end()
    with pytest.raises(CommunityError):
        t.report("1", 0)


# ---------------------------------------------------------------- the end and the ranking
def test_time_up_most_money_wins_ties_share_the_place():
    t, clock = table(3, mode="t3", foods="drink")
    cs = t.custs(200)
    good = [i for i, (a, p, o) in enumerate(cs) if a < 150][:6]
    for k, i in enumerate(good):
        a, p, _ = cs[i]
        at(t, clock, a + 3.5, ["1", "2", "3"])
        t.report("1", a + 3.5, [[i, a + 3.5]])
        if k < 3:
            t.report("2", a + 3.5, [[i, a + 3.5]])
            t.report("3", a + 3.5, [[i, a + 3.5]])
    at(t, clock, 179.0, ["1", "2", "3"])
    t.tick()
    assert t.st["phase"] == "play"
    at(t, clock, 180.2, ["1", "2", "3"])
    t.tick()
    assert t.st["phase"] == "done" and t.st["complete"] and t.st["end_t"] == 180.0
    assert t.st["places"] == {"1": 1, "2": 2, "3": 2} and t.st["ranking"][0] == "1"
    assert t.st["scores"]["1"] == t.till("1") > t.st["scores"]["2"] and t.st["served"]["1"] == 6


def test_optional_limit_angry_customers_send_you_out_and_the_game_ends_without_people():
    t, clock = table(2, limit=3, foods="drink")
    cs = t.custs(300)
    for i in range(3):                                                           # P2 serves the first three, P1 nobody
        a, p, _ = cs[i]
        at(t, clock, a + 3.5, ["1", "2"])
        assert t.report("2", a + 3.5, [[i, a + 3.5]]) == []
    a, p, _ = cs[2]
    at(t, clock, a + p + sn.FINAL + 1, ["1", "2"])
    t.tick()
    assert t.angry("1") >= 3 and t.st["run"]["1"]["out"] == round(a + p, 3) and t.st["run"]["2"]["out"] is None
    assert t.report("1", a + p + 3, [[3, a + p + 3]]) == []                       # out: nothing counts any more
    assert "3" not in t.st["run"]["1"]["served"]
    assert t.st["phase"] == "play"                                               # P2 plays on (the time limit counts)
    a, p, _ = cs[5]
    at(t, clock, a + p + sn.FINAL + 1, ["1", "2"])
    t.tick()                                                                     # P2 out too: nobody left
    assert t.st["run"]["2"]["out"] is not None
    at(t, clock, a + p + sn.FINAL + 2, ["1", "2"])
    t.tick()
    assert t.st["phase"] == "done" and t.st["complete"] and t.st["places"] == {"2": 1, "1": 2}
    t2, clock2 = table(1, limit=0)                                               # off: nobody is out
    a, p, _ = t2.custs(300)[12]
    at(t2, clock2, a + p + sn.FINAL + 1, ["1"])
    t2.tick()
    assert t2.angry("1") >= 10 and t2.st["run"]["1"]["out"] is None and t2.st["phase"] == "play"


def test_leader_ends_early_ranked_as_it_stands():
    t, clock = table(2, foods="drink")
    a, p, _ = t.custs(10)[0]
    at(t, clock, a + 4, ["1", "2"])
    t.report("2", a + 4, [[0, a + 4]])
    t.end()
    assert t.st["phase"] == "done" and not t.st["complete"] and t.st["places"] == {"2": 1, "1": 2}


# ---------------------------------------------------------------- bots
def test_bots_serve_get_angry_and_hard_beats_easy():
    tills = {}
    for lvl in ("easy", "hard"):
        t, clock = table(1, bots=1, level=lvl, mode="t8", rng_seed=3)
        for k in range(0, 486, 5):
            at(t, clock, k, ["1"])
            t.tick()
        assert t.st["phase"] == "done"
        tills[lvl] = t.st["scores"]["bot1"]
        assert t.st["served"]["bot1"] > 10
        if lvl == "easy":
            assert t.angry("bot1") > 0                                           # busy at the end: some walk away
    assert tills["hard"] > tills["easy"]


def test_bot_plans_after_the_end_do_not_count():
    t, clock = table(1, bots=2, mode="t3")
    at(t, clock, 179.9, ["1"])
    t.tick()
    at(t, clock, 180.1, ["1"])
    t.tick()
    assert t.st["phase"] == "done"
    assert all(v[0] <= 180 for v in t.st["run"]["bot1"]["served"].values())


# ---------------------------------------------------------------- the app has the same kitchen
def test_the_app_uses_the_same_kitchen_numbers():
    src = (WEB / "snack.js").read_text(encoding="utf-8")
    for f, steps in sn.FOODS.items():
        m = re.search(r"\b%s: \{ steps: (\[.*?\]\]), price: (\d+), cost: (\[[\d, ]*\])" % f, src)
        assert m, f
        assert [tuple(x) for x in json.loads(m.group(1))] == [tuple(x) for x in steps], f
        assert int(m.group(2)) == sn.PRICE[f] and tuple(json.loads(m.group(3))) == sn.COST[f]
    for s, n in sn.STATIONS.items():
        m = re.search(r"\b%s: \{ n: (\d+)(?:, spoil: ([\d.]+))?" % s, src)
        assert m and int(m.group(1)) == n and (float(m.group(2)) if m.group(2) else None) == sn.SPOIL.get(s), s
    assert f"SHELF: {sn.SHELF}, SHELF_COLD: {int(sn.SHELF_COLD)}, COUNTER: {sn.COUNTER}" in src
    assert "TIP: { 3: %d, 2: %d, 1: %d }" % (sn.TIP[3], sn.TIP[2], sn.TIP[1]) in src


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_app_pays_and_counts_stars_like_the_server():
    src = (WEB / "snack.js").read_text(encoding="utf-8").split("function snackRulesView")[0]
    code = "const T = s => s;\n" + src + ("\nconsole.log(JSON.stringify([snStars(0, 30, 5), snStars(0, 30, 15), snStars(0, 30, 25),"
                                          " snPay(['burger', 'fries'], 3), snFoodCost('burger', 'easy'), snFoodCost('burger', 'normal')]));")
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out == [3, 2, 1, sn.pay(["burger", "fries"], 3), sn.cost("burger", "easy"), sn.cost("burger", "normal")]


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _clock(fq):
    c = Clock(2_000_000_000.0)
    fq.snack.now = c
    return c


def test_family_table_same_customers_coins_once_history_and_hat(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    assert client.get("/api/parent/game-rewards", headers=phd).json()["snack"] == [10, 5, 2]
    assert client.put("/api/parent/game-rewards", json={"snack": [8, 4, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/snack/rules", headers=hm).json()["rewards"] == [8, 4, 1]
    st = client.post("/api/community/snack/start", json={"bots": 0, "mode": "t3", "foods": "drink,icecream"}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"] and st["rules"]["foods"] == "drink,icecream"
    assert client.post("/api/community/snack/sync", json={"t": 0}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/snack/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/snack/begin", headers=hl).status_code == 403                # Leo does not lead
    st = client.post("/api/community/snack/begin", headers=hm).json()
    assert st["phase"] == "play" and st["t0"] == clock.t + sn.COUNTDOWN and st["duration"] == 180
    lv = client.get("/api/community/snack", headers=hl).json()
    assert lv["customers"] == st["customers"] and lv["customers"][0][0] == 0                       # the same customers
    assert "seed" not in lv and client.get("/api/me", headers=hl).json()["community"]["snack"]["joined"]
    # Mia serves the first customer – only her stand changes; Leo sees it
    i, a, p, o = st["customers"][0]
    clock.t = st["t0"] + a + max(sn.chain(f) for f in o) + 0.5
    v = client.post("/api/community/snack/sync", json={"t": a + 5, "serves": [[i, a + max(sn.chain(f) for f in o) + 0.4]], "spent": 2}, headers=hm).json()
    assert v["refused"] == [] and str(i) in v["mine"]["served"]
    me = next(p_ for p_ in v["players"] if p_["id"] == str(mia))
    assert me["served"] == 1 and me["till"] > 0 and me["stars"] == 3
    other = next(p_ for p_ in client.get("/api/community/snack", headers=hl).json()["players"] if p_["id"] == str(mia))
    assert other["till"] == me["till"]
    assert client.post("/api/community/snack/sync", json={"t": 1, "serves": [[0, 1]] * 31}, headers=hm).status_code == 422
    # time is up: Mia wins
    clock.t = st["t0"] + 181
    v = client.post("/api/community/snack/sync", json={"t": 181}, headers=hl).json()
    assert v["phase"] == "done" and v["complete"]
    res = {p_["id"]: (p_["place"], p_["coins"]) for p_ in v["players"]}
    assert res == {str(mia): (1, 8), str(leo): (2, 4)}
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", st["game"])
    fq.snack._save(row, json.loads(row["state"]))                                                  # paid once
    client.get("/api/community/snack", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"snack:{st['game']}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"snack:{st['game']}:{mia}")["reason"] == "Snack Rush – Platz 1"
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "snack" and hist[0]["data"]["place"] == 1 and hist[0]["data"]["coins"] == 8
    assert hist[0]["data"]["served"] == 1 and hist[0]["data"]["record"] and hist[0]["data"]["score"] == me["till"]
    av = lambda pid: fq.avatar_public(fq.db.q1("SELECT * FROM profile WHERE id=?", pid), {"items": {}})["items"].get("hat")
    assert av(mia) == "champion" and av(leo) is None
    assert client.post("/api/community/snack/sync", json={"t": 1}, headers=hl).json()["phase"] == "done"


def test_solo_high_score_and_personal_best(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = _clock(fq)
    hm = login(client, mia, "1111")
    st = client.post("/api/community/snack/start", json={"solo": True, "bots": 0, "mode": "t3", "foods": "drink"}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 1 and not st["coins_on"] and st["best"] == 0
    i, a, p, o = st["customers"][0]
    clock.t = st["t0"] + a + 4
    client.post("/api/community/snack/sync", json={"t": a + 4, "serves": [[i, a + 3.5]]}, headers=hm)
    clock.t = st["t0"] + 181
    v = client.get("/api/community/snack", headers=hm).json()
    assert v["phase"] == "done" and v["players"][0]["record"] and v["best"] == v["players"][0]["till"] > 0
    assert v["players"][0]["coins"] == 0 and not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'snack:%'")
    assert client.get("/api/community/snack", headers=login(client, leo)).json() is None


def test_ended_by_the_leader_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    _clock(fq)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/snack/start", json={"bots": 1, "level": "easy"}, headers=hm)
    client.post("/api/community/snack/join", headers=hl)
    st = client.post("/api/community/snack/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"] and st["players"][2]["level"] == "easy"
    assert client.post("/api/community/snack/end", headers=hl).status_code == 403
    v = client.post("/api/community/snack/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'snack:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='snack'") == 2


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.snack.clean_rules("snack", {"bots": 9, "level": "x", "mode": "t9", "limit": 4, "foods": "pizza,cake,drink"}) == \
        {"bots": 5, "level": "normal", "mode": "t5", "limit": 0, "foods": "drink,pizza"}
    assert fq.snack.clean_rules("snack", {"foods": ""})["foods"] == ",".join(sn.FOOD_KEYS)
    fq.snack.start("snack", kid, {"bots": 2, "level": "hard", "mode": "t8", "limit": 5, "foods": ["burger"]}, solo=True)
    assert fq.snack.default_rules() == {"bots": 2, "level": "hard", "mode": "t8", "limit": 5, "foods": "burger"}
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='snack'")["state"])
    assert len(st["players"]) == 3 and st["players"][1]["level"] == "hard"


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/snack/start", json={"bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "snack"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Snack Rush"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end"):
        assert client.post("/api/community/snack/" + path, json={}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/snack/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.post("/api/community/snack/sync", json={"t": 0}, headers=hg).status_code == 200
    client.post("/api/community/snack/end", headers=hm)
    for p in ("", "/join", "/sync"):
        assert netfilter.is_guest_path("/api/community/snack" + p), p
    for p in ("/start", "/begin", "/end", "/rules"):
        assert not netfilter.is_guest_path("/api/community/snack" + p), p


def test_switched_off_blocks_it(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "snack" in client.get("/api/me", headers=hm).json()["games_list"]
    assert client.put("/api/parent/games", json={"access": {"snack": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/snack", headers=hm).status_code == 403
    assert client.post("/api/community/snack/start", json={"solo": True}, headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "snack" not in me["games_list"] and me["community"]["snack"] is None


def test_without_bots_alone_still_works_but_no_bots_take_a_seat(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    d = client.get("/api/parent/games", headers=ph).json()
    assert "snack" in d["bot_games"]
    assert client.put("/api/parent/games", json={"access": {"snack": {"mode": "all", "bots": False}}}, headers=ph).status_code == 200
    assert client.get("/api/me", headers=hm).json()["games_nobots"] == ["snack"]
    r = client.post("/api/community/snack/start", json={"solo": True, "bots": 2}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == NO_BOTS
    client.app.state.fq.db.set_setting("game_rules.snack", {"bots": 3})
    st = client.post("/api/community/snack/start", json={"solo": True}, headers=hm).json()      # alone: still fine
    assert len(st["players"]) == 1
    assert client.app.state.fq.db.get_setting("game_rules.snack")["bots"] == 3               # not remembered as 0
    st = client.post("/api/community/snack/start", json={"solo": True}, headers=ph).json()      # parents are not bound
    assert len(st["players"]) == 4


def test_running_list_and_end(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.post("/api/community/snack/start", json={"solo": True, "bots": 2}, headers=hm).status_code == 200
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "snack")
    assert g["title"] == "Snack Rush" and g["icon"] == "🍔" and g["solo"] and g["players"] == 1
    r = client.post("/api/parent/games/end", json={"key": g["key"]}, headers=ph).json()
    assert not any(x["game"] == "snack" for x in r["running"])
    v = client.get("/api/community/snack", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"]
