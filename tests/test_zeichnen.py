import json
import random

from familyquest import zeichnen as zr
from familyquest.community import CommunityError
from familyquest.zeichnen_data import CATEGORIES


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(n=3, seed=3, clock=None, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    r = {"category": "tiere", "rounds": 2, "time": 80, "hints": True, **rules}
    st = {"kind": "zeichnen", "rules": r, "players": players, "phase": "lobby"}
    t = zr.Table(st, random.Random(seed), now=clock or Clock())
    t.begin()
    return t


def pick(t, word=None):
    """The drawer chooses – or the test sets the word it wants."""
    if word:
        t.st["choices"][0] = word
    t.choose(t.st["drawer"], 0)


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- words
def test_word_lists():
    assert set(CATEGORIES) == {"tiere", "berufe", "essen", "gegenstaende", "sport", "gemischt"}
    for c in CATEGORIES.values():
        names = [w["name"] for w in c["words"]]
        assert len(names) >= 40 and len(set(names)) == len(names)
        assert not {"pictionary", "montagsmaler", "skribbl"} & {n.lower() for n in names}


def test_word_choice_and_timeout_pick():
    c = Clock()
    t = table(3, clock=c)
    assert t.st["phase"] == "choose" and t.st["drawer"] == "1" and len(t.st["choices"]) == 3 and len(set(t.st["choices"])) == 3
    names = {w["name"] for w in CATEGORIES["tiere"]["words"]}
    assert set(t.st["choices"]) <= names
    try:
        t.choose("2", 0)
        raise AssertionError
    except CommunityError:
        pass
    try:
        t.choose("1", 7)
        raise AssertionError
    except CommunityError:
        pass
    ch = list(t.st["choices"])
    c.t += zr.CHOOSE - 1
    assert not t.tick() and t.st["phase"] == "choose"
    c.t += 1.1
    assert t.tick() and t.st["phase"] == "draw" and t.st["word"] in ch and t.st["deadline"] == 1000 + zr.CHOOSE + 80
    assert t.st["used"] == [t.st["word"]]
    # a word chosen is not offered again
    while t.st["phase"] != "done":
        t.skip()
        t.skip()
        if t.st["phase"] == "choose":
            assert not set(t.st["choices"]) & set(t.st["used"])
            pick(t)
    assert len(t.st["used"]) == 6 and len(set(t.st["used"])) == 6


def test_mask_and_hints():
    c = Clock()
    t = table(2, clock=c)
    pick(t, "Turtle")                                          # the key; every viewer gets the mask of their language
    assert t.mask("de-DE") == ["_"] * 11 and t.revealed("de-DE") == [] and t.mask() == ["_"] * 6
    assert t.mask("fr-FR") == ["_"] * 6 and t.mask("sv-SE") == ["_"] * 10          # Tortue, Sköldpadda
    c.t += 40                                                  # 50 %
    r1 = t.revealed("de-DE")
    assert len(r1) == 2                                        # 11 // 3 = 3 → 2 at 50 %, 3 at 75 %
    m = t.mask("de-DE")
    assert sum(1 for x in m if x != "_") == 2 and all(m[i] == "Schildkröte"[i] for i in r1)
    mf = t.mask("fr-FR")
    assert sum(1 for x in mf if x != "_") == 1 and all(x == "_" or x == "Tortue"[i] for i, x in enumerate(mf))
    c.t += 20
    r2 = t.revealed("de-DE")
    assert len(r2) == 3 and set(r1) <= set(r2)
    t2 = table(2, clock=Clock(), hints=False)
    pick(t2, "Turtle")
    t2.now.t += 79
    assert t2.revealed("de-DE") == [] and t2.mask("de-DE") == ["_"] * 11
    t3 = table(2, clock=Clock())
    pick(t3, "Polar bear")
    assert t3.mask()[5] == " " and t3.mask().count("_") == 9
    assert t3.mask("fr-FR")[4] == " " and t3.mask("fr-FR").count("_") == 11      # Ours polaire
    t3.now.t += 70
    assert len(t3.revealed()) == 3 and all("Polar bear"[i].isalpha() for i in t3.revealed())
    t4 = table(2, clock=Clock())
    pick(t4, "Egg")
    t4.now.t += 79
    assert t4.revealed("de-DE") == []                          # never more than a third (Ei)


def test_guess_normalisation_typos_close():
    w = {"name": "Eisbär", "aliases": []}
    for g in ("Eisbär", "eisbaer", "EISBAR", "der Eisbär", "ein eisbär", "Eis-bär", "eis bär", " Eisbär! "):
        assert zr.check(g, w) == "right", g
    assert zr.check("Eisbr", w) == "right"                    # one typo, 6 letters
    assert zr.check("Eisbxx", w) == "close"
    assert zr.check("Pinguin", w) == "wrong"
    assert zr.check("grosser Eisbär", w) == "hidden"          # contains the word – never broadcast
    assert zr.check("Kuh", {"name": "Kuh", "aliases": []}) == "right"
    assert zr.check("Kuhh", {"name": "Kuh", "aliases": []}) == "close"     # short words: no typo tolerance
    assert zr.check("Hund", {"name": "Hand", "aliases": []}) == "close"
    assert zr.check("Fußball", {"name": "Fussball", "aliases": ["Fußball"]}) == "right"
    assert zr.check("Kaninchen", {"name": "Hase", "aliases": ["Kaninchen"]}) == "right"
    assert zr.check("Écureuil", {"name": "Ecureuil", "aliases": []}) == "right"
    assert zr.check("die Löwe", {"name": "Löwe", "aliases": []}) == "right"
    assert zr.check("Loewe", {"name": "Löwe", "aliases": []}) == "right" and zr.check("Lowe", {"name": "Löwe", "aliases": []}) == "right"
    assert zr.check("", w) == "wrong"


def test_scoring_by_order_drawer_points_and_turn_end_when_all_found():
    c = Clock()
    t = table(4, clock=c)
    pick(t, "Elefant")
    c.t += 20                                                  # 60 of 80 s left
    assert t.guess("2", "elefant") == "right"
    assert t.st["turn_pts"]["2"] == round((50 + 50 * 0.75) * 1.0) == 88
    c.t += 20                                                  # half left
    assert t.guess("4", "Elefnt") == "right"                  # a typo
    assert t.st["turn_pts"]["4"] == round(75 * 0.9) == 68
    try:
        t.guess("4", "Elefant")
        raise AssertionError
    except CommunityError:
        pass
    try:
        t.guess("1", "Elefant")                                # the drawer
        raise AssertionError
    except CommunityError:
        pass
    assert t.st["phase"] == "draw" and t.st["turn_pts"]["1"] == 20
    assert t.guess("3", "Elefant") == "right"
    assert t.st["phase"] == "reveal"                            # all found: the turn ends
    assert t.st["turn_pts"] == {"2": 88, "4": 68, "3": 60, "1": 30}
    assert t.st["totals"] == {"1": 30, "2": 88, "3": 60, "4": 68}
    assert t.st["log"][-1]["found"] == ["2", "4", "3"] and t.st["log"][-1]["word"] == "Elefant"
    # late guesser with no time left still gets the minimum
    t2 = table(3, clock=Clock())
    pick(t2, "Hund")
    t2.now.t += 79.9
    t2.guess("2", "Hund")
    t2.guess("3", "Hund")
    assert t2.st["turn_pts"]["2"] == 50 and t2.st["turn_pts"]["3"] == 45


def test_time_over_reveal_and_rotation_over_rounds():
    c = Clock()
    t = table(3, clock=c, rounds=2)
    drawers = []
    for n in range(6):
        assert t.st["phase"] == "choose" and t.st["turn"] == n
        drawers.append(t.st["drawer"])
        pick(t)
        c.t += 81
        assert t.tick() and t.st["phase"] == "reveal" and t.st["log"][-1]["found"] == []
        c.t += zr.REVEAL + 0.1
        assert t.tick()
    assert drawers == ["1", "2", "3", "1", "2", "3"]
    assert t.st["phase"] == "done" and t.st["places"] == {"1": 1, "2": 1, "3": 1}
    # one call to tick catches up a long pause (choose timeout → draw → reveal → next)
    c2 = Clock()
    t2 = table(2, clock=c2, rounds=1)
    c2.t += zr.CHOOSE + 81 + zr.REVEAL + 1
    t2.tick()
    assert t2.st["turn"] == 1 and t2.st["phase"] in ("choose", "draw")


def test_skip_and_end():
    c = Clock()
    t = table(3, clock=c)
    t.skip()                                                   # while choosing: the next drawer
    assert t.st["drawer"] == "2" and t.st["phase"] == "choose" and t.st["log"] == []
    pick(t, "Katze")
    t.guess("1", "Katze")
    t.skip()
    assert t.st["phase"] == "reveal" and t.st["log"][-1]["skipped"] and t.st["totals"]["1"] > 0
    t.skip()
    assert t.st["drawer"] == "3"
    pick(t, "Maus")
    t.guess("2", "Maus")
    t.end()
    assert t.st["phase"] == "done" and len(t.st["log"]) == 2 and t.st["ranking"] == ["2", "1", "3"]
    assert t.st["totals"] == {"1": 100, "2": 110, "3": 10} and t.st["places"] == {"2": 1, "1": 2, "3": 3}


def test_strokes_batches_cursor_undo_clear_cap():
    c = Clock()
    t = table(2, clock=c)
    try:
        t.draw("1", [{"c": "#000000", "w": 2, "p": [0.1, 0.1]}])      # choosing: no drawing yet
        raise AssertionError
    except CommunityError:
        pass
    pick(t, "Hund")
    try:
        t.draw("2", [{"c": "#000000", "w": 2, "p": [0.1, 0.1]}])      # not the drawer
        raise AssertionError
    except CommunityError:
        pass
    try:
        t.draw("1", [{"p": [0.1, 0.1]}], turn=5)                       # a late batch of another turn
        raise AssertionError
    except CommunityError:
        pass
    r = t.draw("1", [{"c": "#e03131", "w": 3, "p": [0.12345, 0.5, 2, -1, 0.3]}], turn=0)
    assert r == {"n": 1, "npts": 2, "full": False}
    assert t.st["strokes"] == [{"c": "#e03131", "w": 3, "p": [0.123, 0.5, 1.0, 0.0]}]
    full = t.strokes_since(0)
    assert full["from"] == 0 and not full["cont"] and full["ev"] == t.st["strokes"] and full["n"] == 1
    t.draw("1", [{"p": [0.4, 0.4, 0.5, 0.5]}])                          # continues the stroke
    s = t.strokes_since(1, 4, 0)
    assert s["cont"] and s["from"] == 0 and s["ev"] == [{"p": [0.4, 0.4, 0.5, 0.5]}]
    assert t.strokes_since(1, 8, 0)["ev"] == [{"p": []}]               # nothing new
    t.draw("1", [{"c": "nope", "w": 9, "p": [0.1, 0.2]}, {"u": 1}, {"x": 1}, {"c": "#000000", "w": 1, "e": True, "p": [0.9, 0.9]}, "junk"])
    ev = t.st["strokes"]
    assert ev[1] == {"c": "#000000", "w": 2, "p": [0.1, 0.2]} and ev[2] == {"u": 1} and ev[3] == {"x": 1} and ev[4]["e"] == 1
    s = t.strokes_since(1, 8, 0)
    assert s["cont"] and [list(e) for e in s["ev"][1:]] == [["c", "w", "p"], ["u"], ["x"], ["c", "w", "p", "e"]]
    s = t.strokes_since(3, 0, 0)                                        # the last known event is an undo
    assert s["from"] == 3 and not s["cont"] and len(s["ev"]) == 2
    assert t.strokes_since(9, 0, 0)["from"] == 0                         # a cursor that does not fit: everything
    assert t.strokes_since(2, 0, 7)["from"] == 0 and len(t.strokes_since(2, 0, 7)["ev"]) == 5      # another turn
    # the cap per turn
    t.st["npts"] = zr.MAX_POINTS - 3
    r = t.draw("1", [{"p": [0.5] * 20}])
    assert r["full"] and t.st["npts"] == zr.MAX_POINTS
    n = len(t.st["strokes"][-1]["p"])
    r = t.draw("1", [{"c": "#000000", "w": 1, "p": [0.5, 0.5]}])
    assert r["full"] and len(t.st["strokes"][-1]["p"]) == n
    # the next turn starts with an empty picture
    t.skip()
    t.skip()
    assert t.st["strokes"] == [] and t.st["npts"] == 0


def test_chat_never_shows_right_or_close_guesses():
    c = Clock()
    t = table(3, clock=c)
    pick(t, "Giraffe")
    t.guess("2", "Pferd")
    t.guess("3", "Girafe")                                      # right (a typo)
    t.guess("2", "Girxffx")                                  # close / hidden
    t.guess("2", "eine grosse Giraffe")
    chat = t.st["chat"]
    assert chat[0] == {"id": 1, "t": c.t, "k": "guess", "p": "2", "text": "Pferd"}
    assert chat[1]["k"] == "found" and "text" not in chat[1]
    assert all(e.get("to") == "2" for e in chat[2:])


def test_family_flow_no_leak_coins_once_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = Clock(5000)
    fq.zeichnen.now = clock
    assert client.put("/api/parent/game-rewards", json={"zeichnen": [8, 4, 1]}, headers=phd).json()["zeichnen"] == [8, 4, 1]
    hm, hl = login(client, mia, "1111"), login(client, leo)
    r = client.get("/api/community/zeichnen/rules", headers=hm).json()
    assert r["rewards"] == [8, 4, 1] and len(r["categories"]) == 6 and r["category"] == "gemischt" and r["times"] == [60, 80, 120]
    st = client.post("/api/community/zeichnen/start", json={"category": "tiere", "rounds": 1, "time": 60, "hints": True}, headers=hm).json()
    assert st["phase"] == "lobby" and st["rules"] == {"category": "tiere", "rounds": 1, "time": 60, "hints": True}
    assert client.post("/api/community/zeichnen/start", json={}, headers=hl).status_code == 400     # already running
    assert client.post("/api/community/zeichnen/begin", headers=hm).status_code == 400              # alone
    client.post("/api/community/zeichnen/join", headers=hl)
    assert client.post("/api/community/zeichnen/begin", headers=hl).status_code == 403              # Leo does not lead
    st = client.post("/api/community/zeichnen/begin", headers=hm).json()
    assert st["phase"] == "choose" and st["me_drawer"] and len(st["choices"]) == 3 and st["coins_on"]
    assert client.get("/api/me", headers=hl).json()["community"]["zeichnen"]["joined"]
    vl = client.get("/api/community/zeichnen", headers=hl).json()
    assert vl["choices"] is None and vl["word"] is None and vl["drawer"] == str(mia)
    for w in st["choices"]:
        assert w not in json.dumps(vl, ensure_ascii=False)
    assert client.post("/api/community/zeichnen/choose", json={"idx": 0}, headers=hl).status_code == 400
    st = client.post("/api/community/zeichnen/choose", json={"idx": 1}, headers=hm).json()
    word = st["word"]
    assert st["phase"] == "draw" and st["mask"] is not None
    assert st["word"] and st["left_ms"] == 60000
    r = client.post("/api/community/zeichnen/draw", json={"turn": 0, "ops": [{"c": "#000000", "w": 2, "p": [0.1, 0.1, 0.2, 0.2]}]}, headers=hm).json()
    assert r["n"] == 1
    assert client.post("/api/community/zeichnen/draw", json={"ops": [{"p": [0.3, 0.3]}]}, headers=hl).status_code == 400
    client.post("/api/community/zeichnen/draw", json={"turn": 0, "ops": [{"p": [0.3, 0.3]}]}, headers=hm)
    vl = client.get("/api/community/zeichnen", params={"n": 0, "t": 0}, headers=hl).json()
    assert vl["strokes"]["ev"] == [{"c": "#000000", "w": 2, "p": [0.1, 0.1, 0.2, 0.2, 0.3, 0.3]}]
    assert all(x == "_" or not word[i].isalnum() for i, x in enumerate(vl["mask"]))
    vl = client.get("/api/community/zeichnen", params={"n": 1, "pl": 6, "t": 0}, headers=hl).json()
    assert vl["strokes"]["ev"] == [{"p": []}] and vl["strokes"]["cont"]
    assert "strokes" not in client.get("/api/community/zeichnen", headers=hl).json()
    # a wrong guess goes to the chat, a guess with the word in it does not
    v = client.post("/api/community/zeichnen/guess", json={"text": "Bratpfanne"}, headers=hl).json()
    assert v["result"] == "wrong" and v["chat"][-1]["text"] == "Bratpfanne"
    v = client.post("/api/community/zeichnen/guess", json={"text": "riesen " + word}, headers=hl).json()
    assert v["result"] in ("hidden", "close")
    vm = client.get("/api/community/zeichnen", headers=hm).json()
    assert [c["text"] for c in vm["chat"]] == ["Bratpfanne"]
    clock.t += 30
    vl = client.get("/api/community/zeichnen", headers=hl).json()
    dump = json.dumps({k: v for k, v in vl.items() if k != "chat"}, ensure_ascii=False)
    assert word not in dump and vl["word"] is None and vl["choices"] is None
    k = len(zr.letters_of(word)) // 3                          # half the time: the first hint letters
    assert sum(1 for i, x in enumerate(vl["mask"]) if x != "_" and word[i].isalnum()) == (k + 1) // 2
    v = client.post("/api/community/zeichnen/guess", json={"text": word.upper()}, headers=hl).json()
    assert v["result"] == "right" and v["phase"] == "reveal" and v["word"] == word
    assert v["chat"][-1] == {"id": v["chat"][-1]["id"], "k": "found", "p": str(leo), "pts": 75}
    assert all(word.upper() != (c.get("text") or "") for c in client.get("/api/community/zeichnen", headers=hm).json()["chat"])
    clock.t += zr.REVEAL + 0.1
    v = client.get("/api/community/zeichnen", headers=hl).json()
    assert v["phase"] == "choose" and v["me_drawer"] and v["drawer"] == str(leo) and len(v["choices"]) == 3 and v["chat"] == []
    before = fq.rewards.balance(mia, "coins"), fq.rewards.balance(leo, "coins")
    assert client.post("/api/community/zeichnen/skip", headers=hl).status_code == 403
    assert client.post("/api/community/zeichnen/end", headers=hl).status_code == 403
    v = client.post("/api/community/zeichnen/end", headers=hm).json()
    assert v["phase"] == "done" and v["ranking"] == [str(leo), str(mia)] and v["log"][0]["word"] == word
    assert {p["id"]: (p["place"], p["coins"], p["total"]) for p in v["players"]} == {str(mia): (2, 4, 10), str(leo): (1, 8, 75)}
    assert fq.rewards.balance(mia, "coins") == before[0] + 4 and fq.rewards.balance(leo, "coins") == before[1] + 8
    gid = v["game"]
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.zeichnen._save(row, json.loads(row["state"]))                      # saving again pays nothing more
    assert fq.rewards.balance(leo, "coins") == before[1] + 8
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"zeichnen:{gid}:%") == 2
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"zeichnen:{gid}:{leo}")["reason"] == "Draw & Guess – place 1"
    e = next(x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "zeichnen")
    assert e["data"]["place"] == 2 and e["data"]["points"] == 10 and e["data"]["drawn"] == [word] and e["data"]["coins"] == 4
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='zeichnen'") == 2


def test_end_without_a_turn_pays_nothing(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/zeichnen/start", json={}, headers=hm)
    client.post("/api/community/zeichnen/join", headers=hl)
    client.post("/api/community/zeichnen/begin", headers=hm)
    client.post("/api/community/zeichnen/end", headers=phd)                      # a parent leads too
    v = client.get("/api/community/zeichnen", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 and p["place"] is None for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'zeichnen:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='zeichnen'") == 0


def test_guests_play_but_not_lead_no_coins_with_one_family_person(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    clock = Clock(9000)
    fq.zeichnen.now = clock
    hm = login(client, mia, "1111")
    client.post("/api/community/zeichnen/start", json={"category": "essen"}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "zeichnen"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Draw & Guess"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "skip"):
        assert client.post("/api/community/zeichnen/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/zeichnen/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/zeichnen/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    w = st["choices"][0]
    client.post("/api/community/zeichnen/choose", json={"idx": 0}, headers=hm)
    v = client.post("/api/community/zeichnen/guess", json={"text": w}, headers=hg).json()
    assert v["result"] == "right"
    clock.t += zr.REVEAL + 0.1
    v = client.get("/api/community/zeichnen", headers=hg).json()
    assert v["me_drawer"] and v["choices"]                                       # the guest draws too
    client.post("/api/community/zeichnen/choose", json={"idx": 2}, headers=hg)
    assert client.post("/api/community/zeichnen/draw", json={"turn": 1, "ops": [{"c": "#000000", "w": 1, "p": [0.5, 0.5]}]}, headers=hg).json()["n"] == 1
    v = client.post("/api/community/zeichnen/end", headers=hm).json()
    assert v["phase"] == "done" and all(p["coins"] == 0 for p in v["players"])
    assert next(p for p in v["players"] if p["guest"])["place"] == 1
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'zeichnen:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='zeichnen'") == 1         # Mia only, not the guest
    st = {"solo": False, "phase": "done", "log": [{}], "players": [{"id": "1"}, {"id": "2"}, {"id": "3", "guest": True}],
          "places": {"3": 1, "2": 2, "1": 3}, "totals": {"3": 50, "2": 20, "1": 10}}
    assert fq.zeichnen.coins_for(st) == {"2": 5, "1": 2}
    assert fq.zeichnen.coins_for({**st, "totals": {"1": 0, "2": 0, "3": 0}}) == {}            # nobody scored
    assert fq.zeichnen.coins_for({**st, "log": []}) == {}
    assert fq.zeichnen.coins_for({**st, "players": [{"id": "1"}, {"id": "3", "guest": True}]}) == {}


def test_switched_off_and_guest_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert client.put("/api/parent/games", json={"access": {"zeichnen": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/zeichnen", headers=hm).status_code == 403
    assert client.post("/api/community/zeichnen/start", json={}, headers=hm).status_code == 403
    assert client.get("/api/community/zeichnen", headers=phd).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert "zeichnen" not in me["games_list"] and me["community"]["zeichnen"] is None
    for p in ("", "/join", "/choose", "/draw", "/guess"):
        assert netfilter.is_guest_path("/api/community/zeichnen" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/next", "/skip"):
        assert not netfilter.is_guest_path("/api/community/zeichnen" + p), p
