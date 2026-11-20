import json
import random

import pytest

from familyquest import whoami as wb
from familyquest.community import CommunityError
from familyquest.whoami_data import CATEGORIES


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def table(n=3, cat="tiere", seed=3):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    st = {"kind": "werbinich", "rules": {"category": cat}, "players": players, "phase": "lobby"}
    t = wb.Table(st, random.Random(seed), now=Clock())
    t.deal()
    return t


def name_of(t, pid):
    return t.char_of(pid)["name"]


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- the characters
def test_categories_distinct_and_sized():
    assert set(CATEGORIES) == {"tiere", "berufe", "essen", "laender", "schweiz", "maerchen", "gegenstaende", "sport", "personen"}
    for key, c in CATEGORIES.items():
        assert c["title"] and c["emoji"]
        names = [wb.norm(x["name"]) for x in c["chars"]]
        assert 25 <= len(names) <= 40, key
        assert len(set(names)) == len(names), key
        for x in c["chars"]:
            assert wb.matches(x["name"], x) and all(wb.matches(a, x) for a in x["aliases"]), x


def test_deal_distinct_characters():
    for seed in range(20):
        t = table(8, cat="maerchen", seed=seed)
        idx = list(t.st["chars"].values())
        assert len(set(idx)) == 8 and t.st["turn"] == "1" and t.st["phase"] == "play"
    t = table(2)
    with pytest.raises(CommunityError):
        t.st["players"] = [{"id": str(i)} for i in range(50)]
        t.deal()


def test_guess_normalisation_and_typos():
    m = lambda g, n, *a: wb.matches(g, {"name": n, "aliases": list(a)})    # noqa: E731
    assert m("Ich bin der Gestiefelte Kater!", "Der gestiefelte Kater")
    assert m("eisbaer", "Eisbär") and m("EISBÄR", "Eisbär") and m("Eis-Bär", "Eisbär")
    assert m("ein Elefannt", "Elefant")                       # 1 typo, ≥ 5 letters
    assert not m("Elfannt", "Elefant")                        # 2 typos are too many for 7 letters
    assert m("Schneewitchen", "Schneewittchen") and m("Schneewitchn", "Schneewittchen")    # ≥ 9 letters: 2
    assert not m("Hund", "Huhn") and m("Huhn", "Huhn")        # short names: exact
    assert m("Einstein", "Albert Einstein", "Einstein") and m("le Mozart", "Wolfgang Amadeus Mozart", "Mozart")
    assert not m("", "Hund") and not m("der die das", "Hund")
    assert m("Geißlein", "Die sieben Geisslein", "Geisslein")


# ---------------------------------------------------------------- the view never shows your own character
def test_hidden_own_character(fq):
    a = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    b = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    fq.werbinich.start("werbinich", a, {"category": "personen"})
    fq.werbinich.join("werbinich", b)
    lobby = fq.werbinich.state("werbinich", a)
    assert lobby["phase"] == "lobby" and all(p["char"] is None and not p["hidden"] for p in lobby["players"])
    fq.werbinich.begin("werbinich", a)
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werbinich'")
    st = json.loads(row["state"])
    t = wb.Table(st)
    mine, his = t.char_of(str(a)), t.char_of(str(b))
    v = fq.werbinich.state("werbinich", a)
    me = next(p for p in v["players"] if p["id"] == str(a))
    other = next(p for p in v["players"] if p["id"] == str(b))
    assert me["char"] is None and me["hidden"] and other["char"] == his["name"]
    dump = json.dumps(v, ensure_ascii=False)
    for s in [mine["name"], *mine["aliases"]]:
        assert s not in dump or s in his["name"]
    assert "chars" not in v and set(next(p for p in v["players"] if p["id"] == str(a))) == set(other)
    assert v["my_turn"] and v["category"]["key"] == "personen"
    # a wrong guess does not show it either
    fq.werbinich.guess(a, "Niemand Bekanntes")
    dump = json.dumps(fq.werbinich.state("werbinich", a), ensure_ascii=False)
    assert mine["name"] not in dump
    # after giving up it is shown
    fq.werbinich.give_up(a)
    v = fq.werbinich.state("werbinich", a)
    assert next(p for p in v["players"] if p["id"] == str(a))["char"] == mine["name"]


# ---------------------------------------------------------------- questions
def test_question_yes_keeps_turn_no_passes():
    t = table(3)
    with pytest.raises(CommunityError):
        t.ask("2", "Bin ich ein Tier?")                       # not your turn
    with pytest.raises(CommunityError):
        t.answer("2", "yes")                                  # no question open
    t.ask("1", "  Bin   ich gross? ")
    assert t.st["question"]["text"] == "Bin ich gross?"
    with pytest.raises(CommunityError):
        t.ask("1", "again")                                   # one at a time
    with pytest.raises(CommunityError):
        t.answer("1", "yes")                                  # not your own
    with pytest.raises(CommunityError):
        t.answer("2", "maybe")
    with pytest.raises(CommunityError):
        t.guess("1", "Hund")                                  # close the question first
    t.answer("2", "no")
    t.answer("2", "yes")                                      # may change the answer
    assert t.st["question"] and t.voters() == ["2", "3"]
    t.answer("3", "yes")                                      # everybody answered: closed, a majority of yes
    assert t.st["question"] is None and t.st["turn"] == "1"
    assert t.st["log"][-1] == {**t.st["log"][-1], "asker": "1", "yes": 2, "no": 0, "unknown": 0, "result": "yes"}
    t.ask("1", "")
    t.answer("2", "yes")
    t.answer("3", "no")                                       # a tie: the turn passes
    assert t.st["log"][-1]["result"] == "unknown" and t.st["turn"] == "2"
    t.ask("2", "Kann ich fliegen?")
    t.answer("1", "no")
    t.answer("3", "unknown")
    assert t.st["turn"] == "3"


def test_close_early():
    t = table(3)
    t.ask("1", "Habe ich Fell?")
    with pytest.raises(CommunityError):
        t.close("1")                                          # no answer yet
    t.answer("2", "yes")
    with pytest.raises(CommunityError):
        t.close("2")                                          # only the asker …
    t.close("1")
    assert t.st["question"] is None and t.st["turn"] == "1" and t.st["log"][-1]["yes"] == 1
    t.ask("1", "")
    t.answer("3", "no")
    t.close("9", lead=True)                                   # … or who leads (also without playing)
    assert t.st["turn"] == "2"


# ---------------------------------------------------------------- guessing, giving up, the end
def test_guess_wrong_passes_right_finishes_and_places():
    t = table(3)
    assert not t.guess("1", "Ganz falsch")
    assert t.st["turn"] == "2" and t.st["last"]["ok"] is False and "char" not in t.st["last"]
    with pytest.raises(CommunityError):
        t.guess("2", "  ")
    assert t.guess("2", name_of(t, "2").upper())
    assert t.st["done"]["2"]["place"] == 1 and t.st["turn"] == "3" and t.st["last"]["char"] == name_of(t, "2")
    t.guess("3", "falsch")
    assert t.st["turn"] == "1"                                # 2 is finished: skipped
    t.ask("1", "")
    t.answer("2", "no")                                       # finished players still answer
    t.answer("3", "no")
    assert t.st["turn"] == "3"
    assert t.guess("3", name_of(t, "3"))
    assert t.st["turn"] == "1" and t.st["phase"] == "play"
    assert t.guess("1", name_of(t, "1"))
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 3, "2": 1, "3": 2} and t.st["ranking"] == ["2", "3", "1"]


def test_give_up_and_end():
    t = table(3)
    t.ask("1", "")
    t.give_up("1")                                            # the asker gives up: the question is dropped, the turn passes
    assert t.st["question"] is None and t.st["turn"] == "2" and t.st["last"]["char"] == name_of(t, "1")
    with pytest.raises(CommunityError):
        t.give_up("1")
    with pytest.raises(CommunityError):
        t.ask("1", "")
    t.give_up("3")                                            # not their turn: possible any time
    assert t.st["turn"] == "2" and t.st["phase"] == "play"
    assert t.guess("2", name_of(t, "2"))
    assert t.st["phase"] == "done" and t.st["places"] == {"2": 1} and t.st["ranking"] == ["2", "1", "3"]
    # who leads ends early: only who found it has a place
    t = table(3)
    t.guess("1", name_of(t, "1"))
    t.end()
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1} and t.st["ranking"][0] == "1"
    with pytest.raises(CommunityError):
        t.ask("2", "")


def test_skip_by_the_leader():
    t = table(2)
    t.ask("1", "")
    t.skip()
    assert t.st["question"] is None and t.st["turn"] == "2"


# ---------------------------------------------------------------- the family table over the API
def _start(client, hm, hl, cat="tiere"):
    st = client.post("/api/community/werbinich/start", json={"category": cat}, headers=hm).json()
    assert st["phase"] == "lobby" and st["category"]["key"] == cat
    client.post("/api/community/werbinich/join", headers=hl)


def _raw_char(fq, pid):
    """The character key as stored (some carry a note, e.g. «Boxing (sport)»)."""
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werbinich' ORDER BY id DESC LIMIT 1")
    return wb.Table(json.loads(row["state"])).char_of(str(pid))["name"], row["id"]


def _char(fq, pid):
    """The name a player types: the character without its note («Boxing (sport)» → «Boxing») – what the game accepts."""
    from familyquest.gamewords import english
    name, gid = _raw_char(fq, pid)
    return english(name), gid


def test_every_character_is_found_with_its_own_name():
    """Every character of every category is accepted with its plain name (the note in brackets is not typed)."""
    from familyquest.gamewords import english
    for key, cat in CATEGORIES.items():
        for i, c in enumerate(cat["chars"]):
            t = wb.Table({"rules": {"category": key}, "chars": {"1": i}, "players": [{"id": "1"}]})
            assert wb.matches(english(c["name"]), t.accepted("1")), (key, c["name"])
            assert wb.matches(english(c["name"]), t.accepted("1", "en")), (key, c["name"])


def test_family_table_flow_coins_once_and_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.put("/api/parent/game-rewards", json={"werbinich": [8, 4, 1]}, headers=phd).json()["werbinich"] == [8, 4, 1]
    hm, hl = login(client, mia, "1111"), login(client, leo)
    r = client.get("/api/community/werbinich/rules", headers=hm).json()
    assert r["rewards"] == [8, 4, 1] and len(r["categories"]) == 9
    _start(client, hm, hl)
    assert client.post("/api/community/werbinich/start", json={}, headers=hl).status_code == 400   # already running
    assert client.post("/api/community/werbinich/ask", json={"text": "x"}, headers=hm).status_code == 400   # not started
    assert client.post("/api/community/werbinich/begin", headers=hl).status_code == 403            # Leo does not lead
    st = client.post("/api/community/werbinich/begin", headers=hm).json()
    assert st["phase"] == "play" and st["coins_on"] and st["my_turn"] and len(st["players"]) == 2
    assert client.get("/api/me", headers=hl).json()["community"]["werbinich"]["joined"]
    assert client.post("/api/community/werbinich/ask", json={"text": "x"}, headers=hl).status_code == 400   # not Leo's turn
    st = client.post("/api/community/werbinich/ask", json={"text": "Bin ich ein Tier?"}, headers=hm).json()
    assert st["question"]["text"] == "Bin ich ein Tier?" and st["question"]["need"] == 1 and not st["my_turn"]
    vl = client.get("/api/community/werbinich", headers=hl).json()
    assert vl["question"]["asker"] == str(mia) and vl["question"]["mine"] is None
    vl = client.post("/api/community/werbinich/answer", json={"vote": "yes"}, headers=hl).json()
    assert vl["question"] is None and vl["last_q"]["result"] == "yes" and vl["turn"] == str(mia)
    st = client.get("/api/community/werbinich", headers=hm).json()
    assert st["my_log"][0]["text"] == "Bin ich ein Tier?" and st["my_log"][0]["result"] == "yes"
    assert client.get("/api/community/werbinich", headers=hl).json()["my_log"] == []
    name, gid = _char(fq, mia)
    before = fq.rewards.balance(mia, "coins"), fq.rewards.balance(leo, "coins")
    st = client.post("/api/community/werbinich/guess", json={"text": name}, headers=hm).json()
    assert next(p for p in st["players"] if p["id"] == str(mia))["place"] == 1 and st["turn"] == str(leo)
    name, _ = _char(fq, leo)
    v = client.post("/api/community/werbinich/guess", json={"text": "ich bin " + name.lower()}, headers=hl).json()
    assert v["phase"] == "done"
    assert {p["id"]: (p["place"], p["coins"]) for p in v["players"]} == {str(mia): (1, 8), str(leo): (2, 4)}
    assert all(p["char"] for p in v["players"])
    assert fq.rewards.balance(mia, "coins") == before[0] + 8 and fq.rewards.balance(leo, "coins") == before[1] + 4
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.werbinich._save(row, json.loads(row["state"]))                  # saving again pays nothing more
    client.get("/api/community/werbinich", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before[0] + 8
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"werbinich:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"werbinich:{gid}:{mia}")["reason"] == "Who am I? – place 1"
    h = client.get("/api/community/history", headers=hm).json()
    e = next(x for x in h if x["kind"] == "werbinich")
    assert e["data"]["place"] == 1 and e["data"]["players"] == 2 and e["data"]["found"] and e["data"]["questions"] == 1
    assert e["data"]["char"] == _raw_char(fq, mia)[0] and e["data"]["found_count"] == 2
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='werbinich'") == 2


def test_leader_ends_and_closes(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    _start(client, hm, hl)
    client.post("/api/community/werbinich/begin", headers=hm)
    client.post("/api/community/werbinich/guess", json={"text": "falsch"}, headers=hm)
    client.post("/api/community/werbinich/ask", json={"text": ""}, headers=hl)
    client.post("/api/community/werbinich/answer", json={"vote": "no"}, headers=hm)        # all answered: closed
    st = client.post("/api/community/werbinich/guess", json={"text": "falsch"}, headers=hm).json()
    assert st["turn"] == str(leo)
    assert client.post("/api/community/werbinich/end", headers=hl).status_code == 403
    assert client.post("/api/community/werbinich/skip", headers=hl).status_code == 403
    assert client.post("/api/community/werbinich/skip", headers=phd).json()["turn"] == str(mia)   # a parent leads
    v = client.post("/api/community/werbinich/end", headers=hm).json()
    assert v["phase"] == "done" and all(p["char"] and p["place"] is None for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'werbinich:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='werbinich'") == 2


def test_no_coins_with_one_family_person_and_guest(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/werbinich/start", json={"category": "sport"}, headers=hm).json()
    assert client.post("/api/community/werbinich/begin", headers=hm).status_code == 400              # alone: wait
    inv = client.post("/api/community/guests", json={"game": "werbinich"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Who am I?"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    # guests may play but not start, begin or end
    assert client.post("/api/community/werbinich/start", json={}, headers=hg).status_code in (401, 403)
    assert client.post("/api/community/werbinich/begin", headers=hg).status_code in (401, 403)
    assert client.post("/api/community/werbinich/end", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/werbinich/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    assert client.get("/api/community/werbinich", headers=hg).json()["joined"]
    r = client.post("/api/community/werbinich/guess", json={"text": "falsch"}, headers=hm)
    assert r.status_code == 200, r.text
    r = client.post("/api/community/werbinich/ask", json={"text": "Mit Ball?"}, headers=hg)
    assert r.status_code == 200, r.text
    assert r.json()["question"]["asker"] == str(g["profile"]["id"])
    r = client.post("/api/community/werbinich/answer", json={"vote": "yes"}, headers=hm)
    assert r.status_code == 200, r.text
    name, _ = _char(fq, g["profile"]["id"])
    r = client.post("/api/community/werbinich/guess", json={"text": name}, headers=hg)
    assert r.status_code == 200 and r.json()["last"]["ok"], (name, r.text)
    name, _ = _char(fq, mia)
    r = client.post("/api/community/werbinich/guess", json={"text": name}, headers=hm)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"]), (name, v.get("last"))
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'werbinich:%'")
    st = {"solo": False, "phase": "done", "players": [{"id": "1"}, {"id": "2"}, {"id": "3", "guest": True}],
          "places": {"3": 1, "2": 2, "1": 3}}
    assert fq.werbinich.coins_for(st) == {"2": 5, "1": 2}


def test_switched_off_and_guest_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.put("/api/parent/games", json={"access": {"werbinich": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/werbinich", headers=hm).status_code == 403
    assert client.post("/api/community/werbinich/start", json={}, headers=hm).status_code == 403
    assert client.get("/api/community/werbinich", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "werbinich" not in me["games_list"] and me["community"]["werbinich"] is None
    for p in ("", "/join", "/ask", "/answer", "/close", "/guess", "/giveup"):
        assert netfilter.is_guest_path("/api/community/werbinich" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/skip"):
        assert not netfilter.is_guest_path("/api/community/werbinich" + p), p
