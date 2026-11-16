import json
import random

from familyquest import verboten as vw
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=4, seed=3, clock=None, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    r = {"level": "mixed", "time": 60, "rounds": 1, "teams": True, "skip_penalty": 0, **rules}
    st = {"kind": "verboten", "rules": r, "players": players, "phase": "lobby"}
    t = vw.Table(st, random.Random(seed), now=clock or Clock())
    t.begin()
    return t


def fails(fn, *a):
    try:
        fn(*a)
    except CommunityError as e:
        return str(e)
    raise AssertionError("no error")


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- the cards
def test_the_deck():
    c = vw.cards()
    assert set(c) == {"easy", "normal"} and len(c["easy"]) >= 100 and len(c["normal"]) >= 100
    words = [x["word"].lower() for lv in c.values() for x in lv]
    assert len(words) >= 250 and len(set(words)) == len(words)
    for lv in c.values():
        for x in lv:
            assert len(x["taboo"]) == 5 and len({w.lower() for w in x["taboo"]}) == 5, x
            assert x["word"].lower() not in {w.lower() for w in x["taboo"]}
    assert vw.card("e0") == c["easy"][0] and vw.card("n3") == c["normal"][3]
    assert vw.card("x1") is None and vw.card("e99999") is None and vw.card("eab") is None
    assert len(vw.deck_keys("easy")) == len(c["easy"]) and len(vw.deck_keys("mixed")) == len(words)
    assert all(k.startswith("n") for k in vw.deck_keys("normal"))


# ---------------------------------------------------------------- the rules of a turn
def test_teams_schedule_and_alone():
    t = table(4)
    assert t.teams() and t.st["team_of"] == {"1": "0", "2": "1", "3": "0", "4": "1"}
    assert t.st["schedule"] == ["1", "2", "3", "4"] and t.st["phase"] == "ready" and t.st["explainer"] == "1"
    t5 = table(5, rounds=2)                                   # 3 against 2: both teams get the same number of turns
    assert t5.st["schedule"] == ["1", "2", "3", "4", "5", "2", "1", "4", "3", "2", "5", "4"]
    t3 = table(3, rounds=2)                                   # 2 or 3 players: everybody for themselves
    assert not t3.teams() and t3.st["schedule"] == ["1", "2", "3", "1", "2", "3"] and t3.st["scores"] == {"1": 0, "2": 0, "3": 0}
    t4 = table(4, teams=False)
    assert not t4.teams() and len(t4.st["schedule"]) == 4


def test_only_the_explainer_starts_and_marks_the_other_team_buzzes():
    c = Clock()
    t = table(4, clock=c)
    assert fails(t.go, "2") == "It is not your turn to explain"
    assert fails(t.mark, "1", 0, "got") == "The time is up"
    t.go("1")
    assert t.st["phase"] == "explain" and t.st["deadline"] == 1060 and t.st["n"] == 1 and vw.card(t.st["card"])
    assert fails(t.go, "1") == "The turn is already running"
    # who sees the card: the explainer and the other team – never the teammate
    assert [t.sees_card(p) for p in ("1", "2", "3", "4")] == [True, True, False, True]
    assert fails(t.mark, "3", 1, "got") == "Only who explains can do that"
    assert fails(t.mark, "3", 1, "buzz") == "Only the other team can buzz"
    assert fails(t.mark, "1", 1, "buzz") == "Only the other team can buzz"
    assert fails(t.mark, "1", 1, "win") == "Unknown action"
    first = t.st["card"]
    t.mark("1", 1, "got")
    assert t.st["scores"] == {"0": 1, "1": 0} and t.st["n"] == 2 and t.st["card"] != first
    assert fails(t.mark, "2", 1, "buzz") == "Too late – this card is gone"      # the old card: counts once
    t.mark("2", 2, "buzz")
    assert t.st["scores"] == {"0": 0, "1": 0} and t.st["cards"][-1] == {"key": t.st["cards"][-1]["key"], "res": "buzz", "pts": -1, "by": "2"}
    t.mark("1", 3, "taboo")
    t.mark("1", 4, "pass")                                     # no penalty by default
    t.mark("1", 5, "got")
    assert t.st["scores"] == {"0": 0, "1": 0} and [x["res"] for x in t.st["cards"]] == ["got", "buzz", "taboo", "pass", "got"]
    assert t.st["stats"]["1"] == {"explained": 2, "guessed": 0, "taboo": 2}


def test_skip_penalty_and_timer_expiry():
    c = Clock()
    t = table(4, clock=c, skip_penalty=1, time=30)
    t.go("1")
    t.mark("1", 1, "pass")
    assert t.st["scores"]["0"] == -1
    t.mark("1", 2, "got")
    c.t += 29.9
    assert not t.tick()
    c.t += 0.2
    open_card = t.st["card"]
    assert t.tick() and t.st["phase"] == "ready" and t.st["explainer"] == "2" and t.st["card"] is None
    e = t.st["log"][-1]
    assert e["explainer"] == "1" and e["side"] == "0" and e["points"] == 0 and e["open"] == open_card and len(e["cards"]) == 2
    assert fails(t.mark, "1", 3, "got") == "The time is up"


def test_alone_the_explainer_picks_who_guessed():
    t = table(3)
    t.go("1")
    assert fails(t.mark, "1", 1, "got") == "Who guessed it?"
    assert fails(t.mark, "1", 1, "got", "1") == "Who guessed it?"
    assert fails(t.mark, "2", 1, "buzz") == "Only the other team can buzz"     # alone nobody else sees the card
    assert [t.sees_card(p) for p in "123"] == [True, False, False]
    t.mark("1", 1, "got", "3")
    assert t.st["scores"] == {"1": 1, "2": 0, "3": 1} and t.st["stats"]["3"]["guessed"] == 1
    t.mark("1", 2, "taboo")
    assert t.st["scores"] == {"1": 0, "2": 0, "3": 1}
    t2 = table(2)
    t2.go("1")
    t2.mark("1", 1, "got")                                     # two players: the other one guessed it
    assert t2.st["scores"] == {"1": 1, "2": 1}


def test_rounds_end_skip_and_places():
    c = Clock()
    t = table(4, clock=c)
    for ex in ("1", "2", "3"):
        assert t.st["explainer"] == ex
        t.go(ex)
        if ex in ("1", "3"):
            t.mark(ex, t.st["n"], "got")
        c.t += 61
        t.tick()
    assert t.st["explainer"] == "4" and t.round() == 1
    t.skip()                                                   # who leads skips the last explainer before «Go!»
    assert t.st["phase"] == "done" and t.st["scores"] == {"0": 2, "1": 0}
    assert t.st["places"] == {"1": 1, "3": 1, "2": 3, "4": 3} and t.st["ranking"] == ["1", "3", "2", "4"]
    t2 = table(4, clock=Clock())
    t2.go("1")
    t2.mark("1", 1, "got")
    t2.end()                                                   # a turn in progress counts
    assert t2.st["phase"] == "done" and t2.st["log"][0]["points"] == 1 and t2.st["places"]["1"] == 1
    t3 = table(4)
    t3.end()
    assert t3.st["phase"] == "done" and t3.st["places"] == {}


# ---------------------------------------------------------------- the family table over the API
def family4(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    ben = client.post("/api/parent/profiles", json={"name": "Ben"}, headers=phd).json()["id"]
    lea = client.post("/api/parent/profiles", json={"name": "Lea"}, headers=phd).json()["id"]
    return phd, mia, leo, ben, lea


def test_family_flow_no_leak_coins_once_history_champion(client):
    phd, mia, leo, ben, lea = family4(client)
    fq = client.app.state.fq
    clock = Clock(5000)
    fq.verboten.now = clock
    fq.verboten.rng = random.Random(1)
    assert client.put("/api/parent/game-rewards", json={"verboten": [8, 4, 1]}, headers=phd).json()["verboten"] == [8, 4, 1]
    hm, hl, hb, ha = login(client, mia, "1111"), login(client, leo), login(client, ben), login(client, lea)
    r = client.get("/api/community/verboten/rules", headers=hm).json()
    assert r["rewards"] == [8, 4, 1] and r["level"] == "mixed" and r["times"] == [30, 45, 60, 90, 120] and r["counts"]["easy"] >= 100
    st = client.post("/api/community/verboten/start", json={"level": "easy", "time": 45, "rounds": 1, "teams": True, "skip_penalty": 1}, headers=hm).json()
    assert st["phase"] == "lobby" and st["rules"] == {"level": "easy", "time": 45, "rounds": 1, "teams": True, "skip_penalty": 1}
    assert client.post("/api/community/verboten/start", json={}, headers=hl).status_code == 400     # already running
    assert client.post("/api/community/verboten/begin", headers=hm).status_code == 400              # alone
    for h in (hl, hb, ha):
        client.post("/api/community/verboten/join", headers=h)
    v = client.get("/api/community/verboten", headers=hl).json()
    assert v["teams"] and [p["team"] for p in v["players"]] == ["0", "1", "0", "1"]
    assert client.post("/api/community/verboten/mix", headers=hl).status_code == 403                # Leo does not lead
    assert client.post("/api/community/verboten/begin", headers=hl).status_code == 403
    assert client.post("/api/community/verboten/mix", headers=hm).status_code == 200
    st = client.post("/api/community/verboten/begin", headers=hm).json()
    assert st["phase"] == "ready" and st["coins_on"] and st["card"] is None
    assert client.get("/api/me", headers=hl).json()["community"]["verboten"]["joined"]
    heads = {str(mia): hm, str(leo): hl, str(ben): hb, str(lea): ha}
    ex = st["explainer"]
    team = {p["id"]: p["team"] for p in st["players"]}
    mate = next(p for p in heads if p != ex and team[p] == team[ex])
    opp = [p for p in heads if team[p] != team[ex]]
    assert client.post("/api/community/verboten/go", headers=heads[mate]).status_code == 400
    v = client.post("/api/community/verboten/go", headers=heads[ex]).json()
    assert v["phase"] == "explain" and v["me_explainer"] and v["left_ms"] == 45000 and v["time_ms"] == 45000
    word = v["card"]["word"]
    assert len(v["card"]["taboo"]) == 5 and not v["can_buzz"]
    # the teammate never gets the card – the other team does (and may buzz)
    vm = client.get("/api/community/verboten", headers=heads[mate]).json()
    assert vm["card"] is None and vm["turn_cards"] is None and not vm["can_buzz"] and vm["count"] == {"got": 0, "taboo": 0, "pass": 0, "buzz": 0}
    assert word not in json.dumps(vm, ensure_ascii=False)
    vo = client.get("/api/community/verboten", headers=heads[opp[0]]).json()
    assert vo["card"]["word"] == word and vo["can_buzz"]
    # only the explainer marks; a late or double tap counts once
    assert client.post("/api/community/verboten/mark", json={"n": v["n"], "result": "got"}, headers=heads[mate]).status_code == 400
    n = v["n"]
    v = client.post("/api/community/verboten/mark", json={"n": n, "result": "got"}, headers=heads[ex]).json()
    assert v["scores"][team[ex]] == 1 and v["card"]["word"] != word and v["turn_cards"][0] == {"word": word, "res": "got", "pts": 1, "by": None}
    r = client.post("/api/community/verboten/mark", json={"n": n, "result": "got"}, headers=heads[ex])
    assert r.status_code == 400 and r.json()["detail"] == "Too late – this card is gone"
    vm = client.get("/api/community/verboten", headers=heads[mate]).json()
    assert vm["count"]["got"] == 1 and vm["card"] is None and word not in json.dumps(vm, ensure_ascii=False)
    v = client.post("/api/community/verboten/mark", json={"n": n + 1, "result": "buzz"}, headers=heads[opp[1]]).json()
    assert v["scores"][team[ex]] == 0
    v = client.post("/api/community/verboten/mark", json={"n": n + 2, "result": "got"}, headers=heads[ex]).json()
    v = client.post("/api/community/verboten/mark", json={"n": n + 3, "result": "got"}, headers=heads[ex]).json()
    v = client.post("/api/community/verboten/mark", json={"n": n + 4, "result": "pass"}, headers=heads[ex]).json()
    assert v["scores"][team[ex]] == 1                          # +1 −1 +1 +1 −1 (skip costs 1 here)
    # the time is up: the turn's cards for everybody, the next explainer gets ready
    clock.t += 45.1
    v = client.get("/api/community/verboten", headers=heads[mate]).json()
    assert v["phase"] == "ready" and v["explainer"] != ex and team[v["explainer"]] != team[ex] and v["last"]["cards"][0]["word"] == word
    assert v["last"]["points"] == 1 and v["last"]["open"]
    # the leader cannot be skipped by others; then the leader ends: coins once, history, the hat
    assert client.post("/api/community/verboten/skip", headers=hl).status_code == 403
    before = {p: fq.rewards.balance(int(p), "coins") for p in heads}
    assert client.post("/api/community/verboten/end", headers=hb).status_code == 403
    v = client.post("/api/community/verboten/end", headers=hm).json()
    assert v["phase"] == "done" and v["log"][0]["cards"][0]["word"] == word
    win = [p for p in heads if team[p] == team[ex]]
    assert {p["id"]: (p["place"], p["coins"], p["total"]) for p in v["players"]} == {p: ((1, 8, 1) if p in win else (3, 1, 0)) for p in heads}
    for p in heads:
        assert fq.rewards.balance(int(p), "coins") == before[p] + (8 if p in win else 1)
    gid = v["game"]
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.verboten._save(row, json.loads(row["state"]))                       # saving again pays nothing more
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"verboten:{gid}:%") == 4
    assert all(fq.rewards.balance(int(p), "coins") == before[p] + (8 if p in win else 1) for p in heads)
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"verboten:{gid}:{win[0]}")["reason"] == "Verbotene Wörter – Platz 1"
    e = next(x for x in client.get("/api/community/history", headers=heads[ex]).json() if x["kind"] == "verboten")
    assert e["data"]["place"] == 1 and e["data"]["points"] == 1 and e["data"]["teams"] and e["data"]["explained"] == 3 and e["data"]["coins"] == 8
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='verboten'") == 4
    champs = {str(r["id"]) for r in fq.db.q("SELECT id, settings FROM profile") if json.loads(r["settings"] or "{}").get("champion")}
    assert champs == set(win)


def test_end_without_a_turn_pays_nothing_and_alone_mode_api(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/verboten/start", json={"teams": True}, headers=hm)
    client.post("/api/community/verboten/join", headers=hl)
    v = client.post("/api/community/verboten/begin", headers=hm).json()
    assert not v["teams"] and v["explainer"] == str(mia)                    # two players: alone, even with teams on
    client.post("/api/community/verboten/go", headers=hm)
    vl = client.get("/api/community/verboten", headers=hl).json()
    assert vl["card"] is None and not vl["can_buzz"]
    assert client.post("/api/community/verboten/mark", json={"n": vl["n"], "result": "buzz"}, headers=hl).status_code == 400
    client.post("/api/community/verboten/end", headers=phd)                      # a parent leads too
    v = client.get("/api/community/verboten", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'verboten:%'")


def test_guests_play_but_not_lead_and_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    client.post("/api/community/verboten/start", json={}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "verboten"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Verbotene Wörter"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "skip", "mix"):
        assert client.post("/api/community/verboten/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/verboten/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/verboten/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    client.post("/api/community/verboten/go", headers=hm)
    v = client.get("/api/community/verboten", headers=hm).json()
    v = client.post("/api/community/verboten/mark", json={"n": v["n"], "result": "got"}, headers=hm).json()
    assert v["scores"] == {str(mia): 1, str(g["profile"]["id"]): 1}
    client.post("/api/community/verboten/skip", headers=hm)
    v = client.get("/api/community/verboten", headers=hg).json()
    assert v["me_explainer"] and v["phase"] == "ready"                      # the guest explains too
    assert client.post("/api/community/verboten/go", headers=hg).json()["card"]
    v = client.post("/api/community/verboten/end", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='verboten'") == 1         # Mia only, not the guest
    assert client.put("/api/parent/games", json={"access": {"verboten": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/verboten", headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "verboten" not in me["games_list"] and me["community"]["verboten"] is None
    for p in ("", "/join", "/go", "/mark"):
        assert netfilter.is_guest_path("/api/community/verboten" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/skip", "/mix"):
        assert not netfilter.is_guest_path("/api/community/verboten" + p), p


def test_parents_end_it_in_the_running_list(client):
    phd, mia, leo, ben, lea = family4(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/verboten/start", json={}, headers=hm)
    client.post("/api/community/verboten/join", headers=hl)
    v = client.post("/api/community/verboten/begin", headers=hm).json()
    client.post("/api/community/verboten/go", headers=hm)
    v = client.post("/api/community/verboten/mark", json={"n": 1, "result": "got", "guesser": str(leo)}, headers=hm).json()
    games = client.get("/api/parent/games/running", headers=phd).json()
    g = next(x for x in games if x["game"] == "verboten")
    assert g["icon"] == "🚫" and g["title"] == "Verbotene Wörter" and g["players"] == 2 and g["host"] == "Mia"
    client.post("/api/parent/games/end", json={"key": g["key"]}, headers=phd)
    v = client.get("/api/community/verboten", headers=hm).json()
    assert v["phase"] == "done" and v["ranking"] == [str(mia), str(leo)] and {p["coins"] for p in v["players"]} == {10}
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'verboten:%'") == 2
