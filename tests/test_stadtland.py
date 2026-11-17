import json
import random

import pytest

from familyquest import stadtland as sl
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=3, seed=3, clock=None, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    r = {"cats": ["stadt", "land", "fluss"], "own": [], "rounds": 3, "time": 60, "stopp": True, "hard": False, **rules}
    st = {"kind": "stadtland", "rules": r, "players": players, "phase": "lobby"}
    t = sl.Table(st, random.Random(seed), now=clock or Clock())
    t.begin()
    return t


def write(t, answers: dict) -> None:
    """answers: {pid: [stadt, land, fluss]}"""
    for p, xs in answers.items():
        t.save(p, dict(zip(t.cat_keys(), xs)))


def to_review(t):
    t.lead_next()
    t.now.t += sl.LATE + 1
    assert t.tick() and t.st["phase"] == "review"


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- letters
def test_letters_no_repeats_no_hard_no_umlauts():
    for seed in range(30):
        t = table(2, seed=seed, rounds=10)
        for _ in range(9):
            t.st["phase"] = "scores"
            t.lead_next()
        ls = t.st["letters"]
        assert len(ls) == 10 and len(set(ls)) == 10
        assert not set(ls) & set("QXYC") and all(c in sl.EASY for c in ls)
    hard = set()
    for seed in range(40):
        t = table(2, seed=seed, hard=True)
        hard.add(t.st["letter"])
        assert t.st["letter"] in sl.HARD
    assert hard & set("QXYC")
    assert not set(sl.HARD) & set("ÄÖÜ") and len(sl.EASY) == 22


def test_normalisation_and_letter_check():
    assert sl.fits("Écosse", "E") and sl.fits("ägypten", "A") and sl.fits("Österreich", "O") and sl.fits("Übersee", "U")
    assert sl.fits("die Aare", "A") and sl.fits("Der Rhein", "R") and sl.fits("le Havre", "H") and sl.fits("il Po", "P")
    assert sl.fits("the Thames", "T") and sl.fits("l'Isère", "I") and sl.fits("  bern ", "B")
    assert not sl.fits("", "B") and not sl.fits("Zürich", "B") and not sl.fits("die", "B")
    assert sl.fits("Die", "D")                                # only an article: it is the word
    assert sl.norm("Die  Aare!") == sl.norm("aare") == "aare" and sl.norm("St. Gallen") == "stgallen"
    assert sl.norm("Straße") == "strasse"


# ---------------------------------------------------------------- writing
def test_autosave_and_lock_after_time():
    c = Clock()
    t = table(2, clock=c)
    assert t.st["deadline"] == c.t + sl.SPIN + 60
    t.save("1", {"stadt": "  Bern ", "land": "Belgien", "nope": "x"})
    t.save("1", {"fluss": "Birs"})
    assert t.st["answers"]["1"] == {"stadt": "Bern", "land": "Belgien", "fluss": "Birs"}
    assert t.filled("1") == 3 and t.filled("2") == 0
    t.save("1", {"land": "x" * 100})
    assert len(t.st["answers"]["1"]["land"]) == sl.MAX_ANSWER
    with pytest.raises(CommunityError):
        t.save("9", {"stadt": "Basel"})
    c.t += sl.SPIN + 60 + 1                                     # time is up, the last saves still arrive (LATE)
    t.save("2", {"stadt": "Basel"})
    assert not t.tick() and t.st["phase"] == "write"
    c.t += sl.LATE
    with pytest.raises(CommunityError):
        t.save("2", {"land": "Brasilien"})
    assert t.tick() and t.st["phase"] == "review" and t.st["answers"]["2"] == {"stadt": "Basel"}


def test_stopp_and_grace():
    c = Clock()
    t = table(3, clock=c, time=180)
    t.st["letter"] = "B"
    t.save("1", {"stadt": "Bern", "land": "Belgien"})
    with pytest.raises(CommunityError):
        t.stopp("1")                                            # not every field filled
    t.save("1", {"fluss": "Zihl"})
    with pytest.raises(CommunityError):
        t.stopp("1")                                            # Zihl does not start with B
    t.save("1", {"fluss": "die Birs"})
    c.t += 30
    t.stopp("1")
    assert t.st["stopp"]["by"] == "1" and t.st["deadline"] == c.t + sl.GRACE
    with pytest.raises(CommunityError):
        t.stopp("1")                                            # once only
    c.t += sl.GRACE
    t.save("2", {"stadt": "Basel"})                             # still in the grace time
    c.t += sl.LATE + 0.5
    assert t.tick() and t.st["phase"] == "review"
    # «until Stopp»: no deadline at all until somebody calls it; stopp off is not possible then
    c2 = Clock()
    t = table(2, clock=c2, time=0, stopp=False)
    assert t.st["deadline"] is None
    c2.t += 10000
    assert not t.tick()
    write(t, {"2": ["Aarau", "Albanien", "Aare"]})
    t.st["letter"] = "A"
    t.r["stopp"] = True
    t.stopp("2")
    assert t.st["deadline"] == c2.t + sl.GRACE
    # stopp switched off with a time limit
    t = table(2, time=60, stopp=False)
    with pytest.raises(CommunityError):
        t.stopp("1")


def test_stopp_off_with_time_zero_is_forced_on(fq):
    r = fq.stadtland.clean_rules("stadtland", {"time": 0, "stopp": False, "rounds": 7, "cats": ["stadt", "x", "stadt"], "own": [" Superheld ", "superheld", "Auto", "Drei"]})
    assert r == {"cats": ["stadt"], "own": ["Superheld", "Auto"], "rounds": 5, "time": 0, "stopp": True, "hard": False}


# ---------------------------------------------------------------- review and scoring
def test_scoring_20_10_5_0():
    t = table(3)
    t.st["letter"] = "B"
    write(t, {"1": ["Bern", "Belgien", "Birs"],
              "2": ["bern", "Brasilien", "Zihl"],
              "3": ["Basel", "", "die Birs"]})
    to_review(t)
    j = t.judge()
    assert [j["stadt"][p]["pts"] for p in "123"] == [5, 5, 10]      # Bern twice (no case), Basel alone
    assert [j["land"][p]["pts"] for p in "123"] == [10, 10, 0]      # empty: 0
    assert [j["fluss"][p]["pts"] for p in "123"] == [5, 0, 5]       # wrong letter 0, «die Birs» = «Birs»
    assert not j["fluss"]["2"]["auto"]
    t.st["answers"]["2"]["land"] = ""
    assert t.judge()["land"]["1"]["pts"] == 20                      # the only valid answer
    assert t.round_points() == {"1": 5 + 20 + 5, "2": 5 + 0 + 0, "3": 10 + 0 + 5}


def test_votes_majority_and_leader_override():
    t = table(3)
    t.st["letter"] = "B"
    write(t, {"1": ["Bern", "Bla", "Birs"], "2": ["Basel", "Belgien", "Broye"], "3": ["Bulle", "Bolivien", "Brenno"]})
    with pytest.raises(CommunityError):
        t.vote("2", "1", "land")                                    # not in the review yet
    to_review(t)
    with pytest.raises(CommunityError):
        t.vote("1", "1", "land")                                    # not on your own answer
    with pytest.raises(CommunityError):
        t.vote("2", "1", "nope")
    t.vote("2", "1", "land")
    t.vote("2", "1", "land")                                        # twice counts once
    assert t.judge()["land"]["1"]["valid"]                          # 1 of 2 others: no strict majority
    t.vote("3", "1", "land")
    j = t.judge()
    assert not j["land"]["1"]["valid"] and j["land"]["1"]["pts"] == 0 and j["land"]["1"]["rejects"] == ["2", "3"]
    t.vote("3", "1", "land", reject=False)                          # taken back
    assert t.judge()["land"]["1"]["valid"]
    t.vote("3", "1", "land")
    t.override("1", "land", True)                                   # who leads wins over the votes
    assert t.judge()["land"]["1"]["valid"]
    t.override("1", "land", None)
    assert not t.judge()["land"]["1"]["valid"]
    t.override("2", "stadt", False)
    assert not t.judge()["stadt"]["2"]["valid"]
    # two players: one «no» of the other is a majority
    t2 = table(2)
    t2.st["letter"] = "B"
    write(t2, {"1": ["Bern", "Belgien", "Birs"], "2": ["Basel", "Bolivien", "Broye"]})
    to_review(t2)
    t2.vote("2", "1", "stadt")
    assert not t2.judge()["stadt"]["1"]["valid"] and t2.judge()["stadt"]["2"]["pts"] == 20
    # a wrong letter can be made valid by who leads
    t2.st["answers"]["1"]["fluss"] = "Aare"
    assert not t2.judge()["fluss"]["1"]["valid"]
    t2.override("1", "fluss", True)
    assert t2.judge()["fluss"]["1"]["valid"]


def test_ready_closes_review_then_scores_next_round_and_ties():
    t = table(2, rounds=2)
    t.st["letter"] = "B"
    write(t, {"1": ["Bern", "Belgien", "Birs"], "2": ["Basel", "Brasilien", "Broye"]})
    to_review(t)
    t.ready("1")
    assert t.st["phase"] == "review"
    t.ready("1", False)
    t.ready("1")
    t.ready("2")
    assert t.st["phase"] == "scores" and t.st["totals"] == {"1": 30, "2": 30} and t.st["log"][0]["points"] == {"1": 30, "2": 30}
    assert t.st["log"][0]["answers"]["stadt"]["1"] == {"text": "Bern", "valid": True, "pts": 10}
    t.lead_next()
    assert t.st["phase"] == "write" and t.st["round"] == 2 and t.st["answers"] == {"1": {}, "2": {}}
    assert t.st["letter"] != t.st["letters"][0]
    to_review(t)                                                    # nobody wrote anything
    t.lead_next()
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "2": 1} and t.st["ranking"] == ["1", "2"]


def test_end_early():
    t = table(3, rounds=5)
    t.end()                                                         # a round still being written is dropped
    assert t.st["phase"] == "done" and t.st["log"] == [] and t.st["places"] == {}
    t = table(3, rounds=5)
    t.st["letter"] = "B"
    write(t, {"1": ["Bern", "", ""], "2": ["", "", ""], "3": ["Basel", "Belgien", ""]})
    to_review(t)
    t.end()                                                         # a round in the review counts as it stands
    assert t.st["phase"] == "done" and len(t.st["log"]) == 1
    assert t.st["places"] == {"3": 1, "1": 2, "2": 3} and t.st["totals"] == {"1": 10, "2": 0, "3": 30}


# ---------------------------------------------------------------- the family table over the API
def _start(client, hm, hl, **body):
    st = client.post("/api/community/stadtland/start", json={"cats": ["stadt", "land", "fluss"], "rounds": 3, "time": 60, **body}, headers=hm).json()
    assert st["phase"] == "lobby", st
    client.post("/api/community/stadtland/join", headers=hl)
    return st


def test_family_flow_view_does_not_leak_coins_once_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = Clock(5000)
    fq.stadtland.now = clock
    assert client.put("/api/parent/game-rewards", json={"stadtland": [8, 4, 1]}, headers=phd).json()["stadtland"] == [8, 4, 1]
    hm, hl = login(client, mia, "1111"), login(client, leo)
    r = client.get("/api/community/stadtland/rules", headers=hm).json()
    assert r["rewards"] == [8, 4, 1] and len(r["categories"]) == 16 and r["cats"] == ["stadt", "land", "fluss", "tier", "name", "beruf"]
    assert client.post("/api/community/stadtland/start", json={"cats": ["stadt", "land"]}, headers=hm).status_code == 400   # < 3
    assert client.post("/api/community/stadtland/start", json={"cats": list(sl.CATS)}, headers=hm).status_code == 400       # > 8
    _start(client, hm, hl, own=["Superheld"])
    assert client.post("/api/community/stadtland/start", json={}, headers=hl).status_code == 400          # already running
    assert client.post("/api/community/stadtland/begin", headers=hl).status_code == 403                    # Leo does not lead
    st = client.post("/api/community/stadtland/begin", headers=hm).json()
    assert st["phase"] == "write" and st["coins_on"] and [c["key"] for c in st["cats"]] == ["stadt", "land", "fluss", "own1"]
    assert st["cats"][3] == {"key": "own1", "title": "Superheld", "own": True} and st["left_ms"] == int((sl.SPIN + 60) * 1000)
    assert client.get("/api/me", headers=hl).json()["community"]["stadtland"]["joined"]
    L = st["letter"]
    mine = {"stadt": L + "mia-stadt", "land": L + "mia-land", "fluss": L + "mia-fluss", "own1": L + "mia-held"}
    v = client.post("/api/community/stadtland/answers", json={"answers": mine}, headers=hm).json()
    assert v["mine"] == mine and next(p for p in v["players"] if p["id"] == str(mia))["complete"]
    vl = client.post("/api/community/stadtland/answers", json={"answers": {"stadt": L + "leo-stadt", "land": L + "mia-land"}}, headers=hl).json()
    # while writing: nobody sees the answers of the others
    dump = json.dumps(vl, ensure_ascii=False)
    assert "mia-" not in dump.replace(L + "mia-land", "") and vl["review"] is None and vl["finished"] == 1
    assert next(p for p in vl["players"] if p["id"] == str(mia))["filled"] == 4
    assert "leo-stadt" not in json.dumps(client.get("/api/community/stadtland", headers=hm).json())
    assert client.post("/api/community/stadtland/stopp", headers=hl).status_code == 400                    # Leo is not finished
    v = client.post("/api/community/stadtland/stopp", headers=hm).json()
    assert v["stopp"]["by"] == str(mia) and v["left_ms"] == sl.GRACE * 1000
    clock.t += sl.GRACE + sl.LATE + 1
    assert client.post("/api/community/stadtland/answers", json={"answers": {"fluss": "x"}}, headers=hl).status_code == 400
    v = client.get("/api/community/stadtland", headers=hl).json()
    assert v["phase"] == "review" and v["review"]["stadt"][str(mia)]["text"] == L + "mia-stadt"
    assert v["review"]["land"][str(mia)]["pts"] == 5 and v["review"]["own1"][str(mia)]["pts"] == 20
    v = client.post("/api/community/stadtland/vote", json={"target": str(mia), "cat": "own1"}, headers=hl).json()
    assert v["review"]["own1"][str(mia)]["mine_reject"] and not v["review"]["own1"][str(mia)]["valid"]
    assert client.post("/api/community/stadtland/override", json={"target": str(mia), "cat": "own1", "valid": True}, headers=hl).status_code == 403
    v = client.post("/api/community/stadtland/override", json={"target": str(mia), "cat": "own1", "valid": True}, headers=hm).json()
    assert v["review"]["own1"][str(mia)]["valid"]
    client.post("/api/community/stadtland/ready", json={}, headers=hl)
    v = client.post("/api/community/stadtland/ready", json={"ready": True}, headers=hm).json()
    assert v["phase"] == "scores" and v["last"]["points"] == {str(mia): 10 + 5 + 20 + 20, str(leo): 10 + 5}
    before = fq.rewards.balance(mia, "coins"), fq.rewards.balance(leo, "coins")
    assert client.post("/api/community/stadtland/next", headers=hl).status_code == 403
    v = client.post("/api/community/stadtland/next", headers=hm).json()
    assert v["phase"] == "write" and v["round"] == 2 and v["letter"] != L and v["mine"] == {}
    v = client.post("/api/community/stadtland/end", headers=hm).json()
    assert v["phase"] == "done" and v["ranking"] == [str(mia), str(leo)]
    assert {p["id"]: (p["place"], p["coins"]) for p in v["players"]} == {str(mia): (1, 8), str(leo): (2, 4)}
    assert fq.rewards.balance(mia, "coins") == before[0] + 8 and fq.rewards.balance(leo, "coins") == before[1] + 4
    gid = v["game"]
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.stadtland._save(row, json.loads(row["state"]))                      # saving again pays nothing more
    assert fq.rewards.balance(mia, "coins") == before[0] + 8
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"stadtland:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"stadtland:{gid}:{mia}")["reason"] == "Stadt-Land-Fluss – Platz 1"
    e = next(x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "stadtland")
    assert e["data"]["place"] == 1 and e["data"]["points"] == 55 and e["data"]["rounds"] == 1 and e["data"]["coins"] == 8
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='stadtland'") == 2


def test_end_without_a_round_pays_nothing(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    _start(client, hm, hl)
    client.post("/api/community/stadtland/begin", headers=hm)
    v = client.post("/api/community/stadtland/end", headers=phd).json()            # a parent leads too
    assert v is None or v["phase"] == "done"
    v = client.get("/api/community/stadtland", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 and p["place"] is None for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'stadtland:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='stadtland'") == 0


def test_guests_play_but_not_lead_no_coins_with_one_family_person(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = Clock(9000)
    fq.stadtland.now = clock
    hm = login(client, mia, "1111")
    client.post("/api/community/stadtland/start", json={"cats": ["stadt", "land", "fluss"], "rounds": 3}, headers=hm)
    assert client.post("/api/community/stadtland/begin", headers=hm).status_code == 400              # alone: wait
    inv = client.post("/api/community/guests", json={"game": "stadtland"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Stadt-Land-Fluss"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "next", "override"):
        assert client.post("/api/community/stadtland/" + path, json={"target": "1", "cat": "stadt"}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/stadtland/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/stadtland/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    L = st["letter"]
    v = client.post("/api/community/stadtland/answers", json={"answers": {"stadt": L + "oma"}}, headers=hg).json()
    assert v["mine"] == {"stadt": L + "oma"}
    client.post("/api/community/stadtland/next", headers=hm)
    clock.t += sl.LATE + 1
    v = client.post("/api/community/stadtland/vote", json={"target": str(mia), "cat": "stadt"}, headers=hg).json()
    assert v["phase"] == "review"
    v = client.post("/api/community/stadtland/end", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert next(p for p in v["players"] if p["guest"])["place"] == 1
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'stadtland:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='stadtland'") == 1         # Mia only, not the guest
    st = {"solo": False, "phase": "done", "log": [{}], "players": [{"id": "1"}, {"id": "2"}, {"id": "3", "guest": True}],
          "places": {"3": 1, "2": 2, "1": 3}}
    assert fq.stadtland.coins_for(st) == {"2": 5, "1": 2}
    assert fq.stadtland.coins_for({**st, "log": []}) == {}
    assert fq.stadtland.coins_for({**st, "players": [{"id": "1"}, {"id": "3", "guest": True}]}) == {}


def test_switched_off_and_guest_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.put("/api/parent/games", json={"access": {"stadtland": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/stadtland", headers=hm).status_code == 403
    assert client.post("/api/community/stadtland/start", json={}, headers=hm).status_code == 403
    assert client.get("/api/community/stadtland", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "stadtland" not in me["games_list"] and me["community"]["stadtland"] is None
    for p in ("", "/join", "/answers", "/stopp", "/vote", "/ready"):
        assert netfilter.is_guest_path("/api/community/stadtland" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/next", "/override"):
        assert not netfilter.is_guest_path("/api/community/stadtland" + p), p
