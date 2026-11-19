"""🗝️ Adventure games on the bookshelf (adventuregame.py, stories.py): cleaning and limits, the checker with the
solvability search, the play engine on the server (items, switches, dialogues, use and combine rules, endings, saved
games), privacy, approval and rewards for the game type, ▶ try-out of the working copy, the templates in every
language, the file format (export, import, AI answers, malicious input)."""
import copy
import json

import pytest

from familyquest import adventuregame as A
from familyquest import stories as S
from test_stories import _logins, coins


def C(*atoms):
    return A._c(*atoms)


def D(*acts):
    return A._a(*acts)


def spot(sid, kind, name, **kw):
    return A._spot(sid, kind, name, (10, 10, 20, 20), None, f"look {name}", **kw)


def game():
    """Hall: a chest with a key, a door to the garden that needs the key, a lever (switches the ghost on), the ghost
    (gives a coin in a talk). Garden: rope + stick = fishing rod, the rod on the hole opens the gate (win), the pond
    (lose)."""
    return {
        "start": 1,
        "items": [{"id": 1, "name": "Key", "icon": {"k": "asset", "v": "key"}}, {"id": 2, "name": "Rope", "icon": None},
                  {"id": 3, "name": "Stick", "icon": None}, {"id": 4, "name": "Fishing rod", "icon": {"k": "emoji", "v": "🎣"}},
                  {"id": 5, "name": "Coin", "icon": None}],
        "flags": [{"id": 1, "name": "Lever down"}, {"id": 2, "name": "Gate open"}],
        "endings": [{"id": 1, "kind": "win", "text": "Free!"}, {"id": 2, "kind": "lose", "text": "Splash."}],
        "rooms": [
            {"id": 1, "name": "Hall", "text": "A hall.", "bg": {"k": "lib", "v": "hall"},
             "variants": [{"if": C(("f", 1)), "text": "A hall with a ghost.", "bg": None}], "spots": [
                spot(11, "object", "Chest", take=True, item=1),
                spot(12, "door", "Garden door", to=2, lock=C(("i", 1)), locked="Locked!"),
                spot(13, "object", "Lever"),
                spot(14, "person", "Ghost", talk=1, **{"if": C(("f", 1))})]},
            {"id": 2, "name": "Garden", "text": "A garden.", "bg": {"k": "lib", "v": "village"}, "variants": [], "spots": [
                spot(21, "door", "Back", to=1),
                spot(22, "door", "Gate", end=1, lock=C(("f", 2))),
                spot(23, "object", "Rope", take=True, item=2),
                spot(24, "object", "Stick", take=True, item=3),
                spot(25, "object", "Hole"),
                spot(26, "door", "Pond", end=2)]}],
        "lines": [
            {"id": 1, "text": "Boo!", "answers": [A._ans("Hi", 2), A._ans("Bye")]},
            {"id": 2, "text": "Take a coin.", "answers": [A._ans("Thanks", None, do=[("give", 5)], cond=[("!i", 5)]), A._ans("No")]}],
        "rules": [
            {"id": 1, "kind": "use", "item": None, "spot": 13, "if": C(("!f", 1)), "do": D(("set", 1), ("say", "Clack."))},
            {"id": 2, "kind": "combine", "item": 2, "item2": 3, "if": [], "do": D(("take", 2), ("take", 3), ("give", 4))},
            {"id": 3, "kind": "use", "item": 4, "spot": 25, "if": [], "do": D(("set", 2), ("say", "The gate opens."))}],
    }


def codes(issues, level=None):
    return sorted(i["code"] for i in issues if level is None or i["level"] == level)


def _game(client, h, data=None, title="Garden escape", visibility="family"):
    sid = client.post("/api/stories", json={"title": title, "lang": "en", "visibility": visibility, "type": "game"}, headers=h).json()["id"]
    r = client.put(f"/api/stories/{sid}", json={"data": data or game()}, headers=h)
    assert r.status_code == 200, r.text
    return sid, r.json()


def act(client, h, sid, **mv):
    return client.post(f"/api/stories/{sid}/read/act", json=mv, headers=h)


# ---------------------------------------------------------------- cleaning and limits
def test_clean_keeps_a_valid_game():
    d = A.clean(game())
    assert d == A.clean(d) and A.check(d, "T") == []
    s = d["rooms"][0]["spots"][3]
    assert s["kind"] == "person" and s["if"] == [{"k": "flag", "id": 1, "not": False}] and s["talk"] == 1


def test_clean_limits_and_bad_values():
    g = game()
    room = g["rooms"][0]
    room["spots"] += [{"id": 11, "kind": "door", "name": "duplicate"}, {"id": "x"}, "nope",
                      {"id": 90, "kind": "weird", "name": "n" * 200, "x": -50, "y": 500, "w": 900, "h": "NaN", "art": {"k": "asset", "v": "../../x"},
                       "if": [{"k": "flag", "id": 1}] * 9 + ["x"], "look": "l" * 5000, "to": 77, "talk": 99}]
    room["bg"] = {"k": "svg", "v": "<svg viewBox='0 0 4 3' onload='alert(1)'><script>x</script><rect width='4' height='3'/></svg>"}
    room["variants"] *= 5
    g["lines"][0]["answers"] *= 5
    g["rules"].append({"id": 9, "kind": "use", "spot": 13, "do": [{"k": "say", "v": "x" * 999}, {"k": "explode"}, {"k": "give", "id": "a"}] * 10})
    d = A.clean(g)
    r = d["rooms"][0]
    assert [s["id"] for s in r["spots"]] == [11, 12, 13, 14, 90] and len(r["variants"]) == A.MAX_VARIANTS
    s = r["spots"][-1]
    assert s["kind"] == "object" and len(s["name"]) == A.NAME and s["x"] == 0 and s["y"] == 98 and s["w"] == 100 and s["h"] == 2
    assert s["art"] is None and len(s["if"]) == A.MAX_COND and len(s["look"]) == A.LOOK and s["to"] is None and s["talk"] is None
    assert "script" not in r["bg"]["v"] and "onload" not in r["bg"]["v"]
    assert len(d["lines"][0]["answers"]) == A.MAX_ANSWERS
    rule = d["rules"][-1]
    assert len(rule["do"]) == A.MAX_ACTIONS and all(a["k"] == "say" and len(a["v"]) == A.SAY for a in rule["do"])
    for key, n, one in (("rooms", A.MAX_ROOMS, {"id": 1}), ("items", A.MAX_ITEMS, {"id": 1}), ("flags", A.MAX_FLAGS, {"id": 1}),
                        ("lines", A.MAX_LINES, {"id": 1}), ("rules", A.MAX_RULES, {"id": 1}), ("endings", A.MAX_ENDINGS, {"id": 1})):
        with pytest.raises(Exception):
            A.clean({key: [dict(one, id=i + 1) for i in range(n + 1)]})
    with pytest.raises(Exception):
        A.clean({"rooms": [{"id": 1, "spots": [{"id": i + 1} for i in range(A.MAX_SPOTS + 1)]}]})
    big = "<svg viewBox='0 0 4 3'>" + "".join(f"<rect x='{i}' width='1' height='1' fill='#123456'/>" for i in range(200)) + "</svg>"
    many = {"rooms": [{"id": i + 1, "bg": {"k": "svg", "v": big}, "variants": [{"bg": {"k": "svg", "v": big}}] * 3, "spots": [
        {"id": (i + 1) * 100 + j, "art": {"k": "svg", "v": big}} for j in range(30)]} for i in range(40)]}
    with pytest.raises(Exception):
        A.clean(many)                                           # too many bytes
    assert A.clean(None)["rooms"] == [] and A.clean("x")["start"] is None


# ---------------------------------------------------------------- the checker
def test_checker_static_problems():
    assert codes(A.check(A.clean({}), "")) == ["no_rooms", "title"]
    g = game()
    g["rooms"][0]["name"] = ""
    g["rooms"][0]["spots"][0]["item"] = None                    # takeable, but no item
    g["rooms"][0]["spots"].append(spot(15, "door", "Nowhere"))
    g["rooms"][0]["spots"].append(spot(16, "person", "Mute"))
    g["rooms"][0]["spots"].append(spot(17, "object", "", **{"if": C(("f", 42))}))   # unknown flag
    g["lines"].append({"id": 3, "text": "", "answers": [A._ans("", cond=[("f", 1)])]})   # dead end, never said, no text
    g["rules"].append({"id": 4, "kind": "combine", "item": 2, "item2": 2, "if": [], "do": D(("say", "x"))})
    g["rules"].append({"id": 5, "kind": "use", "item": 1, "spot": 999, "if": [], "do": D(("go", 77))})
    g["items"].append({"id": 6, "name": "Never", "icon": None})
    g["rooms"][1]["spots"][0]["lock"] = C(("i", 6))              # the way back needs an item nobody gives
    g["flags"].append({"id": 3, "name": ""})
    g["endings"].append({"id": 3, "kind": "lose", "text": ""})
    c = codes(A.check(A.clean(g), "T"))
    for code in ("room_name", "take_item", "door_target", "person_talk", "spot_name", "unknown", "line_dead", "line_lost", "line_text",
                 "answer_text", "rule_incomplete", "item_never", "door_key", "flag_name", "ending_text"):
        assert code in c, code
    i = next(x for x in A.check(A.clean(g), "T") if x["code"] == "door_target")
    assert i["room"] == 1 and i["spot"] == 15 and i["args"] == ["1", "Nowhere"] and i["level"] == "error"
    assert next(x for x in A.check(A.clean(g), "T") if x["code"] == "line_lost")["level"] == "warn"


def test_checker_flags_and_win():
    g = game()
    g["rules"] = [r for r in g["rules"] if r["id"] != 3]        # nothing opens the gate: the switch is never set
    c = codes(A.check(A.clean(g), "T"))
    assert "flag_never" in c and "door_key" in c and "unsolvable" in c
    g = game()
    g["rooms"][1]["spots"][1]["end"] = 2                         # the gate is a lose ending now: no win at all
    assert "no_win" in codes(A.check(A.clean(g), "T"))
    g = game()
    g["rooms"].append({"id": 3, "name": "Attic", "text": "x", "spots": []})
    assert "unreachable" in codes(A.check(A.clean(g), "T"))


def test_solvability_search():
    d = A.clean(game())
    r = A.search(d)
    assert r["complete"] and r["win"] and r["rooms"] == {1, 2} and r["items"] == {1, 2, 3, 4, 5} and r["endings"] == {1, 2}
    assert r["lines"] == {1, 2} and r["stuck"] is None
    # unsolvable: the stick is hidden behind a switch nobody can set any more → no rod, no gate
    g = game()
    g["rooms"][1]["spots"][3]["if"] = C(("f", 2))
    res = A.search(A.clean(g))
    assert res["complete"] and not res["win"] and "unsolvable" in codes(A.check(A.clean(g), "T"), "error")
    # stuck: the key can be thrown into the hole before the door is open → the garden is out of reach for good
    g = game()
    g["rooms"][0]["spots"].append(spot(18, "object", "Well"))
    g["rules"].append({"id": 7, "kind": "use", "item": 1, "spot": 18, "if": [], "do": D(("take", 1), ("say", "Plop."))})
    res = A.search(A.clean(g))
    assert res["win"] and res["stuck"] == 1
    issues = A.check(A.clean(g), "T")
    assert codes(issues) == ["stuck"] and issues[0]["level"] == "warn" and S.blocking_as("game", A.clean(g), "T") == []
    # a room behind a door that never opens: reachable on the map, never in play
    g = game()
    g["rooms"].append({"id": 3, "name": "Vault", "text": "x", "bg": None, "spots": []})
    g["rooms"][0]["spots"].append(spot(19, "door", "Vault door", to=3, lock=C(("f", 1), ("!f", 1))))
    assert "never_reached" in codes(A.check(A.clean(g), "T"), "warn")


def test_search_is_bounded(monkeypatch):
    monkeypatch.setattr(A, "SEARCH_STATES", 5)
    issues = A.check(A.clean(game()), "T")
    assert codes(issues) == ["too_big"] and issues[0]["level"] == "warn"


# ---------------------------------------------------------------- the engine
def test_engine_moves_items_flags_dialogue_combine():
    d = A.clean(game())
    ix = A.Index(d)
    st = A.new_state(d)
    v = A.view(ix, st)
    assert v["room"]["name"] == "Hall" and [s["id"] for s in v["spots"]] == [11, 12, 13]          # the ghost is hidden
    assert {s["id"]: s["verbs"] for s in v["spots"]} == {11: ["look", "take"], 12: ["look", "go"], 13: ["look", "use"]}
    assert set(v) == {"room", "spots", "inv", "talk", "end"} and "rules" not in json.dumps(v)
    assert A.act(ix, st, {"verb": "look", "spot": 11}) == [{"t": "look Chest"}]
    assert A.act(ix, st, {"verb": "go", "spot": 12}) == [{"t": "Locked!"}] and st["room"] == 1
    assert A.act(ix, st, {"verb": "take", "spot": 11}) == [{"c": "got", "a": ["Key"]}] and st["inv"] == [1]
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "take", "spot": 11})                                                 # gone
    assert A.act(ix, st, {"verb": "use", "spot": 13}) == [{"t": "Clack."}] and st["flags"] == [1]
    assert A.act(ix, st, {"verb": "use", "spot": 13}) == [{"c": "no_use", "a": []}]                 # once only (condition)
    assert A.view(ix, st)["room"]["text"] == "A hall with a ghost."                                 # variant
    assert A.act(ix, st, {"verb": "talk", "spot": 14}) == [] and st["talk"] == {"spot": 14, "line": 1}
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "go", "spot": 12})                                                   # finish the talk first
    A.act(ix, st, {"verb": "answer", "answer": 0})
    v = A.view(ix, st)
    assert v["talk"]["line"]["text"] == "Take a coin." and [a["i"] for a in v["talk"]["answers"]] == [0, 1]
    assert A.act(ix, st, {"verb": "answer", "answer": 0}) == [{"c": "got", "a": ["Coin"]}] and st["talk"] is None
    A.act(ix, st, {"verb": "talk", "spot": 14})
    A.act(ix, st, {"verb": "answer", "answer": 0})
    assert [a["i"] for a in A.view(ix, st)["talk"]["answers"]] == [1]                                # the coin only once
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "answer", "answer": 0})
    A.act(ix, st, {"verb": "leave"})
    assert A.act(ix, st, {"verb": "use", "spot": 12, "item": 1}) == [] and st["room"] == 2           # a key on a door: go through
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "look", "spot": 11})                                                 # not in this room
    A.act(ix, st, {"verb": "take", "spot": 23})
    A.act(ix, st, {"verb": "take", "spot": 24})
    assert A.act(ix, st, {"verb": "combine", "item": 2, "item2": 1}) == [{"c": "no_combine", "a": []}]
    A.act(ix, st, {"verb": "combine", "item": 3, "item2": 2})
    assert sorted(st["inv"]) == [1, 4, 5]
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "use", "spot": 25, "item": 2})                                       # not in the backpack
    assert A.act(ix, st, {"verb": "use", "spot": 25, "item": 1}) == [{"c": "no_use", "a": []}]
    A.act(ix, st, {"verb": "use", "spot": 25, "item": 4})
    A.act(ix, st, {"verb": "go", "spot": 22})
    assert st["end"] == 1 and A.view(ix, st)["end"] == {"id": 1, "kind": "win", "text": "Free!"}
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "look", "spot": 21})                                                 # the game is over
    for bad in (None, "x", {"verb": "look"}, {"verb": "fly", "spot": 11}, {"verb": "answer", "answer": True}):
        with pytest.raises(A.PlayError):
            A.act(ix, A.new_state(d), bad)


def test_clean_state_of_a_tampered_save():
    d = A.clean(game())
    st = A.clean_state(d, {"room": 2, "inv": [1, 1, 99, "x"], "flags": [2, 7], "taken": [11, 999], "talk": {"spot": 14, "line": 1}, "end": 5})
    assert st == {"room": 2, "inv": [1], "flags": [2], "taken": [11], "talk": None, "end": None}       # the ghost is not in the garden
    assert A.clean_state(d, {"room": 77}) == A.new_state(d) and A.clean_state(d, "x") == A.new_state(d)


# ---------------------------------------------------------------- on the shelf: create, publish, play, privacy
def test_game_crud_publish_play_rate_and_rewards(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid = client.post("/api/stories", json={"title": "Garden", "type": "game", "lang": "fr-FR", "visibility": "family"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    assert ed["type"] == "game" and ed["emoji"] == "🗝️" and len(ed["data"]["rooms"]) == 1 and ed["data"]["endings"][0]["kind"] == "win"
    assert "room_text" in codes(ed["issues"]) and client.post(f"/api/stories/{sid}/publish", headers=hm).status_code == 400
    r = client.put(f"/api/stories/{sid}", json={"data": game()}, headers=hm).json()
    assert r["issues"] == []
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    fq = client.app.state.fq
    assert coins(fq, mia) == 20                                                     # the writing reward
    sh = client.get("/api/stories", headers=hl).json()
    b = next(x for x in sh["books"] if x["id"] == sid)
    assert b["type"] == "game" and b["pages"] == 2 and b["endings"] == 2 and b["found"] == 0 and b["cover_bg"] == "hall" and not b["reading"]
    assert "game" in sh["creatable"]
    # Leo plays
    v = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert v["type"] == "game" and v["room"]["name"] == "Hall" and v["fresh"] and v["inv"] == [] and "rules" not in v and "lines" not in v
    v = act(client, hl, sid, verb="take", spot=11).json()
    assert v["msgs"] == [{"c": "got", "a": ["Key"]}] and v["inv"][0]["name"] == "Key" and not v["fresh"]
    assert act(client, hl, sid, verb="take", spot=11).status_code == 400
    act(client, hl, sid, verb="go", spot=12)
    assert next(x for x in client.get("/api/stories", headers=hl).json()["books"] if x["id"] == sid)["reading"]
    # resume: the saved game is where Leo stopped – Mia's own game starts fresh
    v = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert v["room"]["name"] == "Garden" and [i["id"] for i in v["inv"]] == [1]
    assert client.get(f"/api/stories/{sid}/read", headers=hm).json()["room"]["name"] == "Hall"
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hl).status_code == 400   # not finished yet
    v = act(client, hl, sid, verb="go", spot=26).json()                                                 # the pond
    assert v["end"]["kind"] == "lose" and v["new_ending"] and v["found"] == 1 and v["may_rate"]
    assert act(client, hl, sid, verb="look", spot=21).status_code == 400
    v = client.post(f"/api/stories/{sid}/read/restart", headers=hl).json()
    assert v["fresh"] and v["room"]["name"] == "Hall" and v["found"] == 1
    for mv in ({"verb": "take", "spot": 11}, {"verb": "go", "spot": 12}, {"verb": "take", "spot": 23}, {"verb": "take", "spot": 24},
               {"verb": "combine", "item": 2, "item2": 3}, {"verb": "use", "spot": 25, "item": 4}):
        assert act(client, hl, sid, **mv).status_code == 200, mv
    v = act(client, hl, sid, verb="go", spot=22).json()
    assert v["end"] == {"id": 1, "kind": "win", "text": "Free!"} and v["found"] == 2 and v["new_ending"]
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 4}, headers=hl).status_code == 200
    assert coins(fq, mia) == 20                                                     # the reading reward is 0 by default
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 4}, headers=hm).status_code == 400   # own game
    b = next(x for x in client.get("/api/stories", headers=hl).json()["books"] if x["id"] == sid)
    assert b["found"] == 2 and b["rating"] == 4 and not b["reading"]
    # a picture book move or a page choice is not a game move – and a game move not a book's
    assert client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/read/page", json={"page": 1}, headers=hl).status_code == 400


def test_game_privacy_and_try(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, ed = _game(client, hm, visibility="me")
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    # nobody but Mia: no reading, no moves, no try-out, no export – the parent area only knows that it exists
    for h in (hl, ph):
        assert client.get(f"/api/stories/{sid}/read", headers=h).status_code == 400
        assert act(client, h, sid, verb="look", spot=11).status_code == 400
        assert client.post(f"/api/stories/{sid}/try", json={}, headers=h).status_code == 400
        assert client.get(f"/api/stories/{sid}/export", headers=h).status_code == 400
        assert client.get(f"/api/stories/{sid}", headers=h).status_code == 400
    pv = client.get("/api/stories", headers=ph).json()["private"]
    assert len(pv) == 1 and pv[0]["type"] == "game" and pv[0]["pages"] == 2 and "title" not in pv[0]
    assert "Garden escape" not in json.dumps(client.get("/api/stories", headers=ph).json())
    # ▶ try-out of the working copy: from any room, nothing is saved, the state comes back checked
    t = client.post(f"/api/stories/{sid}/try", json={"room": 2}, headers=hm).json()
    assert t["room"]["name"] == "Garden" and t["state"]["room"] == 2
    t = client.post(f"/api/stories/{sid}/try", json={"state": t["state"], "move": {"verb": "take", "spot": 23}}, headers=hm).json()
    assert [i["name"] for i in t["inv"]] == ["Rope"]
    forged = dict(t["state"], inv=[1, 2, 3, 4, 77], flags=[2])
    t = client.post(f"/api/stories/{sid}/try", json={"state": forged, "move": {"verb": "go", "spot": 22}}, headers=hm).json()
    assert t["end"]["kind"] == "win" and t["new_ending"]
    assert client.app.state.fq.db.val("SELECT COUNT(*) FROM story_read WHERE story_id=?", sid) == 0
    assert client.post(f"/api/stories/{sid}/try", json={"move": {"verb": "take", "spot": 23}}, headers=hm).status_code == 400   # not in the hall
    # a state with wrong types: refused (400), never a server error
    for bad in ({"room": [2]}, {"room": 2, "inv": [[1]]}, {"room": 2, "flags": [{"a": 1}]}, {"room": 2, "taken": "x"},
                {"room": 2, "talk": {"spot": [1], "line": 1}}, {"room": 2, "end": {"x": 1}}, {"room": "2"}):
        r = client.post(f"/api/stories/{sid}/try", json={"state": bad, "move": {"verb": "look", "spot": 23}}, headers=hm)
        assert r.status_code == 400, bad
    from familyquest import adventuregame as A
    data = json.loads(client.app.state.fq.db.val("SELECT data FROM story WHERE id=?", sid))
    assert A.clean_state(data, {"room": [2], "inv": [[1]]}) == A.new_state(data)        # a saved state: cleaned, no error
    # guests: nothing
    assert client.post("/api/stories", json={"title": "X", "type": "game"}).status_code == 401
    assert client.post(f"/api/stories/{sid}/read/act", json={"verb": "look", "spot": 11}).status_code == 401


def test_game_kids_visibility_approval(client):
    ph, hm, hl, mia, leo = _logins(client)
    client.put("/api/stories/settings", json={"approval": True}, headers=ph)
    sid, _ = _game(client, hm, visibility="kids")
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "pending"
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    # 👀 the parent plays the waiting version
    t = client.post(f"/api/stories/{sid}/try", json={"pending": True}, headers=ph).json()
    assert t["room"]["name"] == "Hall"
    assert client.post(f"/api/stories/{sid}/try", json={"pending": True}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["room"]["name"] == "Hall"
    papa_app = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}
    assert all(b["id"] != sid for b in client.get("/api/stories", headers=papa_app).json()["books"])      # «other children» only
    assert client.get(f"/api/stories/{sid}/read", headers=papa_app).status_code == 400


def test_publish_with_warnings_only(client, monkeypatch):
    ph, hm, hl, mia, leo = _logins(client)
    g = game()
    g["lines"].append({"id": 9, "text": "Never said", "answers": [A._ans("Bye")]})
    sid, ed = _game(client, hm, g)
    assert codes(ed["issues"]) == ["line_lost"] and ed["issues"][0]["level"] == "warn"
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"


def test_limits_via_api(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _game(client, hm)
    too_many = {"rooms": [{"id": i + 1, "name": "r"} for i in range(A.MAX_ROOMS + 1)]}
    r = client.put(f"/api/stories/{sid}", json={"data": too_many}, headers=hm)
    assert r.status_code == 400 and "40" in r.json()["detail"]
    r = client.put(f"/api/stories/{sid}", json={"data": {"rooms": [{"id": 1, "spots": [{"id": i + 1} for i in range(31)]}]}}, headers=hm)
    assert r.status_code == 400
    assert act(client, hm, sid, verb="x" * 40).status_code == 422


# ---------------------------------------------------------------- templates
def test_templates_valid_and_solvable_in_all_languages():
    texts = A.template_texts()
    assert set(texts) == set(S.LANGS)
    for lang in S.LANGS:
        assert set(texts[lang]) == set(A.TEMPLATES)
        for key in A.TEMPLATES:
            assert set(texts[lang][key]) == set(texts["en"][key]), (lang, key)
            t = A.template(key, lang)
            d = t["data"]
            assert t["lang"] == lang and t["title"] and "@" not in json.dumps(d), (lang, key)
            assert A.check(d, t["title"]) == [], (lang, key, A.check(d, t["title"]))
            res = A.search(d)
            assert res["complete"] and res["win"] and res["stuck"] is None, (lang, key)
            assert 4 <= len(d["rooms"]) <= 6 and d["lines"] and any(r["kind"] == "combine" for r in d["rules"]), (lang, key)
            assert any(e["kind"] == "lose" for e in d["endings"]) and res["endings"] == {e["id"] for e in d["endings"]}
            assert all(v for k, v in texts[lang][key].items()), (lang, key)
            for r in d["rooms"]:                                                   # the pictures exist
                assert r["bg"]["v"] in A.ROOMS or r["bg"]["v"] in S.BACKGROUNDS
    assert A.template("tower", "de-CH")["title"] != A.template("tower", "de-DE")["title"]
    assert A.template("tower", "fr")["lang"] == "fr-FR" and A.template("tower", "xx")["lang"] == "en"
    assert "ß" in json.dumps(texts["de-DE"], ensure_ascii=False) and "ß" not in json.dumps(texts["de-CH"], ensure_ascii=False)


def test_create_from_template_and_play_through(client):
    ph, hm, hl, mia, leo = _logins(client)
    tl = client.get("/api/stories/templates?type=game&lang=de-CH", headers=hm).json()
    assert [t["key"] for t in tl] == ["tower", "attic", "spaceship"] and tl[0]["title"] == "Flucht us em Zauberturm"
    sid = client.post("/api/stories", json={"template": "spaceship", "lang": "it-IT", "type": "game", "visibility": "family"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    assert ed["title"] == "Perso nell'astronave" and ed["issues"] == [] and ed["lang"] == "it-IT"
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    moves = [("take", 12), ("take", 14), ("go", 15), ("use", 25, 1), ("talk", 25), ("answer", 0), ("answer", 0), ("go", 22), ("take", 31),
             ("combine", 2, 3), ("go", 33), ("go", 23), ("use", 41, 4), ("go", 43), ("go", 24), ("use", 51)]
    v = None
    for m in moves:
        body = {"verb": m[0]}
        if m[0] == "combine":
            body.update(item=m[1], item2=m[2])
        elif m[0] == "answer":
            body["answer"] = m[1]
        else:
            body["spot"] = m[1]
            if len(m) > 2:
                body["item"] = m[2]
        r = act(client, hl, sid, **body)
        assert r.status_code == 200, (m, r.text)
        v = r.json()
    assert v["end"]["kind"] == "win" and v["msgs"][0]["t"].startswith("Premi")


# ---------------------------------------------------------------- file format
def test_ai_template_document(client):
    r = client.get("/api/stories/ai-template?type=game")
    assert r.status_code == 200 and "adventuregame" in r.headers["content-disposition"]
    doc = r.json()
    assert doc["_format"] == A.FORMAT and doc["_ai_instructions"] and set(doc["_assets"]) == set(A.ASSETS)
    assert set(A.ROOMS) <= set(doc["_backgrounds"]) and doc["games"][0]["type"] == "adventure_game"
    [g] = S.import_books(r.text)
    assert g["type"] == "game" and A.check(g["data"], g["title"]) == [] and A.search(g["data"])["win"]


def test_export_import_round_trip(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid = client.post("/api/stories", json={"template": "attic", "lang": "sv-SE", "type": "game"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    # an own photo as room picture stays out of the file
    data = copy.deepcopy(ed["data"])
    data["rooms"][0]["bg"] = {"k": "img", "v": "s-0123456789abcdef.png", "src": "photo"}
    r = client.get(f"/api/stories/{sid}/export", headers=hm)
    doc = r.json()
    assert r.status_code == 200 and doc["_format"] == A.FORMAT and doc["games"][0]["language"] == "sv-SE"
    assert client.get(f"/api/stories/{sid}/export", headers=hl).status_code == 400
    ids = client.post("/api/stories/import", json={"text": r.text}, headers=hl).json()["ids"]
    new = client.get(f"/api/stories/{ids[0]}", headers=hl).json()
    assert new["type"] == "game" and new["visibility"] == "me" and new["mine"] and new["issues"] == [] and new["title"] == ed["title"]
    a, b = ed["data"], new["data"]
    assert [r["name"] for r in a["rooms"]] == [r["name"] for r in b["rooms"]] and [r["bg"] for r in a["rooms"]] == [r["bg"] for r in b["rooms"]]
    assert [len(r["spots"]) for r in a["rooms"]] == [len(r["spots"]) for r in b["rooms"]]
    strip = lambda d: [[{k: v for k, v in s.items() if k not in ("id", "to", "end", "talk", "item")} for s in r["spots"]] for r in d["rooms"]]  # noqa: E731
    assert strip(a) == strip(b)
    assert [x["text"] for x in a["lines"]] == [x["text"] for x in b["lines"]] and len(a["rules"]) == len(b["rules"])
    assert A.search(b)["win"]
    assert A.export_game("T", "🗝️", "en", A.clean({**data}))["rooms"][0].get("background") is None


def test_object_that_stays_in_the_room():
    g = game()
    g["rooms"][0]["spots"][0]["keep"] = True                    # the chest stays, only the key goes into the backpack
    d = A.clean(g)
    ix = A.Index(d)
    st = A.new_state(d)
    A.act(ix, st, {"verb": "take", "spot": 11})
    v = A.view(ix, st)
    assert st["inv"] == [1] and next(s for s in v["spots"] if s["id"] == 11)["verbs"] == ["look"]
    with pytest.raises(A.PlayError):
        A.act(ix, st, {"verb": "take", "spot": 11})
    exp = A.export_game("T", "🗝️", "en", d)
    assert exp["rooms"][0]["hotspots"][0]["stays"] is True and A.import_game(exp)["data"]["rooms"][0]["spots"][0]["keep"]


AI_GAME = {
    "type": "adventure_game", "title": "Das Spukschloss", "emoji": "👻", "language": "de-CH", "id": 9, "author_id": 1, "start": "gate",
    "rooms": [
        {"id": "gate", "name": "Tor", "text": "<b>Ein altes Tor.</b>", "background": "castle", "hotspots": [
            {"id": "door", "kind": "door", "name": "Tor", "box": [60, 30, 20, 50], "picture": "asset:door", "goes_to": "hall", "needs": ["item:key"],
             "locked_text": "Zu!"},
            {"id": "stone", "kind": "object", "name": "Stein", "box": {"x": 1}, "x": 10, "y": 70, "w": 15, "h": 15, "picture": "🪨",
             "look": "Ein Schlüssel liegt darunter.", "takeable": True, "item": "key"}]},
        {"id": "hall", "name": "Halle", "text": "Dunkel.", "background": {"svg": "<svg viewBox='0 0 400 300'><script>alert(1)</script><rect width='400' height='300' fill='#123'/></svg>"},
         "hotspots": [
             {"id": "ghost", "kind": "character", "name": "Gespenst", "box": [40, 20, 20, 40], "picture": "asset:ghost", "dialogue": "hi"},
             {"id": "exit", "kind": "door", "name": "Ausgang", "box": [80, 20, 18, 60], "goes_to": "win", "needs": "flag:friends"},
             {"id": "evil", "kind": "object", "name": "<img src=x onerror=alert(1)>", "box": [0, 0, 5, 5], "picture": "javascript:alert(1)" * 3}]}],
    "dialogue": [{"id": "hi", "text": "Buh!", "answers": [
        {"text": "Freunde?", "do": [{"type": "set", "flag": "friends"}, "say: Juhu!"], "next": None}, {"text": "Tschüss"}]}],
    "endings": [{"id": "win", "type": "win", "text": "Geschafft!"}],
}


def test_import_ai_answer_and_bad_input(client):
    ph, hm, hl, mia, leo = _logins(client)
    answer = "Klar! Hier ist dein Spiel:\n\n```json\n" + json.dumps({"_format": A.FORMAT, "games": [AI_GAME]}, ensure_ascii=False) + "\n```\nViel Spass!"
    ids = client.post("/api/stories/import", json={"text": answer}, headers=hm).json()["ids"]
    ed = client.get(f"/api/stories/{ids[0]}", headers=hm).json()
    assert ed["type"] == "game" and ed["author_id"] == mia and ed["visibility"] == "me" and ed["lang"] == "de-CH" and ed["title"] == "Das Spukschloss"
    d = ed["data"]
    r1, r2 = d["rooms"]
    assert r1["bg"] == {"k": "lib", "v": "castle"} and r1["text"] == "<b>Ein altes Tor.</b>"            # plain text, shown as text
    assert r2["bg"]["k"] == "svg" and "script" not in r2["bg"]["v"]
    door, stone = r1["spots"]
    assert door["to"] == r2["id"] and door["lock"] == [{"k": "item", "id": stone["item"], "not": False}] and door["art"] == {"k": "asset", "v": "door"}
    assert stone["take"] and stone["x"] == 10 and stone["art"] == {"k": "emoji", "v": "🪨"}
    assert {i["name"] for i in d["items"]} == {"key"} and {f["name"] for f in d["flags"]} == {"friends"}
    assert r2["spots"][1]["end"] == d["endings"][0]["id"] and r2["spots"][2]["art"] is None
    assert d["lines"][0]["answers"][0]["do"] == [{"k": "set", "id": d["flags"][0]["id"]}, {"k": "say", "v": "Juhu!"}]
    assert ed["issues"] == [] and A.search(d)["win"]
    # a single game without the wrapper, with comments and trailing commas
    lax = '{"type": "adventure_game", "title": "X", // a game\n "rooms": [{"id": "a", "name": "A", "text": "t", "hotspots": [],},],}'
    r = client.post("/api/stories/import", json={"text": lax}, headers=hm)
    assert r.status_code == 200
    assert "no_win" in codes(client.get(f"/api/stories/{r.json()['ids'][0]}", headers=hm).json()["issues"])
    for bad in ('{"games": [{"rooms": "x"}]}', json.dumps({"games": [{"type": "game", "rooms": [{"id": i} for i in range(A.MAX_ROOMS + 5)]}]}),
                json.dumps({"games": [{"type": "game", "rooms": [{"id": 1, "hotspots": [{"id": i} for i in range(99)]}]}]}),
                json.dumps({"games": [{"type": "game", "rooms": [{"id": 1}], "rules": [{}] * 999}]}), "[[[[[[[[[[]]]]]]]]]]"):
        assert client.post("/api/stories/import", json={"text": bad}, headers=hm).status_code == 400, bad
    assert client.post("/api/stories/import", json={"text": answer}).status_code == 401
