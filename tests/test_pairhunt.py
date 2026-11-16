import json
import random
from collections import Counter

import pytest

from familyquest import pairhunt as ph
from familyquest.community import CommunityError


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(n=2, bots=0, pairs=6, seed=3, level="normal"):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": level} for i in range(1, bots + 1)]
    st = {"kind": "paarjagd", "rules": {**ph.DEFAULTS, "pairs": pairs}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = ph.Table(st, random.Random(seed), now=clock)
    t.deal()
    return t, clock


def pair_of(t, k):
    return [i for i, x in enumerate(t.st["cards"]) if x == k]


def no_pair(t):
    a = 0
    b = next(i for i, x in enumerate(t.st["cards"]) if x != t.st["cards"][a])
    return a, b


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def test_deal_every_pair_twice():
    for pairs in ph.PAIRS:
        t, _ = table(pairs=pairs)
        c = Counter(t.st["cards"])
        assert len(t.st["cards"]) == 2 * pairs and set(c.values()) == {2} and len(c) == pairs
        assert t.st["turn"] == "1" and t.st["phase"] == "play"


def test_flip_rules_pair_and_mismatch():
    t, clock = table(2)
    with pytest.raises(CommunityError):
        t.flip("2", 0)                                               # not your turn
    a, b = pair_of(t, 0)
    t.flip("1", a)
    with pytest.raises(CommunityError):
        t.flip("1", a)                                               # already open
    t.flip("1", b)                                                   # a pair: a point, the same player again
    assert t.st["scores"]["1"] == 1 and t.st["turn"] == "1" and t.st["open"] == [] and t.st["found"][str(a)] == "1"
    with pytest.raises(CommunityError):
        t.flip("1", a)                                               # found already
    x, y = next((i, j) for i in range(12) for j in range(12) if i < j and str(i) not in t.st["found"]
                and str(j) not in t.st["found"] and t.st["cards"][i] != t.st["cards"][j])
    t.flip("1", x)
    t.flip("1", y)                                                   # no pair: both stay open for a moment
    assert t.st["open"] == [x, y] and t.st["turn"] == "1"
    z = next(i for i in range(12) if str(i) not in t.st["found"] and i not in (x, y))
    with pytest.raises(CommunityError):
        t.flip("1", z)                                               # a third card
    assert not t.tick()                                              # not yet
    clock.t += ph.HIDE + 0.1
    assert t.tick()
    assert t.st["open"] == [] and t.st["turn"] == "2"


def test_finish_ranking_and_shared_places():
    t, _ = table(3, pairs=6)
    t.st["turn"] = "1"
    for k in range(3):
        a, b = pair_of(t, k)
        t.flip("1", a)
        t.flip("1", b)
    t.st["turn"] = "2"
    for k in range(3, 6):
        a, b = pair_of(t, k)
        t.flip("2", a)
        t.flip("2", b)
    assert t.st["phase"] == "done"
    assert t.st["places"] == {"1": 1, "2": 1, "3": 3} and t.st["ranking"][:2] == ["1", "2"]


@pytest.mark.parametrize("level", ["easy", "normal", "hard"])
def test_bots_play_to_the_end(level):
    for seed in range(3):
        t, clock = table(0, bots=3, pairs=12, seed=seed, level=level)
        for _ in range(5000):
            if t.st["phase"] == "done":
                break
            clock.t += 2
            t.tick()
        assert t.st["phase"] == "done", (level, seed)
        assert sum(t.st["scores"].values()) == 12 and len(t.st["found"]) == 24


def test_view_hides_face_down_cards(fq, kid):
    gid = fq.paarjagd.start("paarjagd", kid, {"pairs": 8, "bots": 1}, solo=True)
    v = fq.paarjagd.state("paarjagd", kid)
    assert v["game"] == gid and v["count"] == 16 and v["faces"] == {} and "cards" not in v and v["my_turn"]
    assert len(v["items"]) == 8 and all("e" in x for x in v["items"])
    fq.paarjagd.flip("paarjagd", kid, 5)
    v = fq.paarjagd.state("paarjagd", kid)
    assert list(v["faces"]) == ["5"] and v["open"] == [5]
    assert "cards" not in json.dumps(v).replace('"count"', "")


def _finish_family(client, fq, first, hf, second, hs):
    """Mia (first) and Leo (second) play a table where first finds 4 pairs and second 2."""
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='paarjagd' AND solo=0 AND status!='done'")
    s = json.loads(row["state"])
    s["turn"] = str(first)
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    cards = s["cards"]
    pos = {}
    for i, k in enumerate(cards):
        pos.setdefault(k, []).append(i)
    pairs = list(pos.values())
    for a, b in pairs[:4]:
        assert client.post("/api/community/paarjagd/flip", json={"idx": a}, headers=hf).status_code == 200
        assert client.post("/api/community/paarjagd/flip", json={"idx": b}, headers=hf).status_code == 200
    s = json.loads(fq.db.q1("SELECT state FROM card_game WHERE id=?", row["id"])["state"])
    s["turn"] = str(second)
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    for a, b in pairs[4:]:
        client.post("/api/community/paarjagd/flip", json={"idx": a}, headers=hs)
        r = client.post("/api/community/paarjagd/flip", json={"idx": b}, headers=hs)
    return r.json(), row["id"]


def test_family_table_coins_once(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json() == {"paarjagd": [10, 5, 2], "werbinich": [10, 5, 2], "kartenlauf": [10, 5, 2], "stadtland": [10, 5, 2], "zeichnen": [10, 5, 2], "wuerfel": [10, 5, 2], "heimwaerts": [10, 5, 2], "jump": [10, 5, 2], "klatsch": [10, 5, 2], "verboten": [10, 5, 2], "jass": [10, 5, 2], "werwolf": [10, 5, 2], "schach": [10, 5, 2]}
    assert client.put("/api/parent/game-rewards", json={"paarjagd": [7, 3, 1]}, headers=phd).status_code == 200
    hm, hl = login(client, mia, "1111"), login(client, leo)
    assert client.get("/api/community/paarjagd/rules", headers=hm).json()["rewards"] == [7, 3, 1]
    st = client.post("/api/community/paarjagd/start", json={"pairs": 6, "bots": 0}, headers=hm).json()
    assert st["phase"] == "lobby" and st["coins_on"] is False
    assert client.post("/api/community/paarjagd/flip", json={"idx": 0}, headers=hm).status_code == 400   # not started
    client.post("/api/community/paarjagd/join", headers=hl)
    assert client.post("/api/community/paarjagd/begin", headers=hl).status_code == 403                   # Leo does not lead
    st = client.post("/api/community/paarjagd/begin", headers=hm).json()
    assert st["phase"] == "play" and st["coins_on"] and len(st["players"]) == 2
    assert client.get("/api/me", headers=hl).json()["community"]["paarjagd"]["joined"]
    assert client.post("/api/community/paarjagd/flip", json={"idx": 0}, headers=hl).status_code == 400  # not Leo's turn
    before = fq.rewards.balance(mia, "coins"), fq.rewards.balance(leo, "coins")
    v, gid = _finish_family(client, fq, mia, hm, leo, hl)
    assert v["phase"] == "done"
    assert {p["id"]: (p["place"], p["coins"]) for p in v["players"]} == {str(mia): (1, 7), str(leo): (2, 3)}
    assert fq.rewards.balance(mia, "coins") == before[0] + 7 and fq.rewards.balance(leo, "coins") == before[1] + 3
    # saving the finished table again pays nothing more
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.paarjagd._save(row, json.loads(row["state"]))
    client.get("/api/community/paarjagd", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before[0] + 7
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"paarjagd:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"paarjagd:{gid}:{mia}")["reason"] == "Paarjagd – Platz 1"


def test_no_coins_alone_against_bots(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/paarjagd/start", json={"solo": True, "pairs": 6, "bots": 1}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and not st["coins_on"]
    assert client.get("/api/community/paarjagd", headers=login(client, leo)).json() is None     # private
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='paarjagd' AND solo=1")
    s = json.loads(row["state"])
    pos = {}
    for i, k in enumerate(s["cards"]):
        pos.setdefault(k, []).append(i)
    for a, b in pos.values():                                       # Mia finds every pair herself
        client.post("/api/community/paarjagd/flip", json={"idx": a}, headers=hm)
        v = client.post("/api/community/paarjagd/flip", json={"idx": b}, headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'paarjagd:%'")


def test_guest_gets_no_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    client.post("/api/community/paarjagd/start", json={"pairs": 6, "bots": 0}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "paarjagd"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Paarjagd"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    gid = g["profile"]["id"]
    st = client.post("/api/community/paarjagd/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]      # only one person of the family
    v, _ = _finish_family(client, fq, mia, hm, gid, {"X-FQ-Token": g["token"]})
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'paarjagd:%'")
    # with two of the family and a guest: the guest gets none, even on place 1
    st = {"solo": False, "phase": "done", "players": [{"id": "1"}, {"id": "2"}, {"id": "3", "guest": True}, {"id": "bot1", "bot": True}],
          "places": {"3": 1, "bot1": 2, "1": 3, "2": 4}}
    assert fq.paarjagd.coins_for(st) == {"1": 2}


def test_game_rewards_validated(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    for bad in ({"paarjagd": [1, 2]}, {"paarjagd": [1, 2, 3, 4]}, {"paarjagd": [1, -1, 0]}, {"paarjagd": [1001, 0, 0]},
                {"paarjagd": [1.5, 0, 0]}, {"paarjagd": ["5", 0, 0]}, {"domino": [1, 2, 3]}, {"werbinich": [1, 2]}):
        assert client.put("/api/parent/game-rewards", json=bad, headers=phd).status_code == 400, bad
    assert client.put("/api/parent/game-rewards", json={"paarjagd": [0, 0, 1000]}, headers=phd).json() == {"paarjagd": [0, 0, 1000], "werbinich": [10, 5, 2], "kartenlauf": [10, 5, 2], "stadtland": [10, 5, 2], "zeichnen": [10, 5, 2], "wuerfel": [10, 5, 2], "heimwaerts": [10, 5, 2], "jump": [10, 5, 2], "klatsch": [10, 5, 2], "verboten": [10, 5, 2], "jass": [10, 5, 2], "werwolf": [10, 5, 2], "schach": [10, 5, 2]}
    assert client.put("/api/parent/game-rewards", json={"paarjagd": [1, 2, 3]}, headers=login(client, mia, "1111")).status_code in (401, 403)


def test_switched_off_and_guest_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.put("/api/parent/games", json={"access": {"paarjagd": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/paarjagd", headers=hm).status_code == 403
    assert client.post("/api/community/paarjagd/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/community/paarjagd", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "paarjagd" not in me["games_list"] and me["community"]["paarjagd"] is None
    assert netfilter.is_guest_path("/api/community/paarjagd") and netfilter.is_guest_path("/api/community/paarjagd/flip")
    assert not netfilter.is_guest_path("/api/community/paarjagd/start") and not netfilter.is_guest_path("/api/community/paarjagd/rules")


def test_photo_set_and_crest(fq, kid):
    fq.db.set_setting("memory", {"sets": [{"id": "abc123", "name": "Ferien", "photos": ["a.jpg", "b.jpg", "c.jpg", "d.jpg"]}],
                                 "crest": {"icon": "🏠", "colors": ["#000000", "#ffffff"], "pattern": "split"}})
    fq.paarjagd.start("paarjagd", kid, {"set": "photo:abc123", "pairs": 6, "back": "crest", "bots": 1}, solo=True)
    v = fq.paarjagd.state("paarjagd", kid)
    assert v["rules"]["set"] == "photo:abc123" and v["count"] == 8 and v["crest"]["icon"] == "🏠"   # only 4 photos: 4 pairs
    assert sorted(x["img"] for x in v["items"]) == [f"media/_memory/{p}" for p in ("a.jpg", "b.jpg", "c.jpg", "d.jpg")]
    assert fq.paarjagd.clean_rules("paarjagd", {"set": "photo:nope", "pairs": 7, "level": "x", "back": "y"}) == {**ph.DEFAULTS, "back": "classic"}
