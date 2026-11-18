import json
import random

import pytest

from familyquest import escape as es
from familyquest import escape_riddles as er
from familyquest.community import CommunityError
from familyquest.escape_words import CONCEPTS, LANGS, plain


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def right(rd):
    """The right answer of a riddle (from the server's solution)."""
    return rd["sol"][0] if rd["check"] == "word" else rd["sol"]


WRONG = {"digits": "999999999", "int": "-77", "time": "9999", "word": "zzzzqq", "choice": 99, "seq": [99], "set": [99]}


def table(n=2, mode="together", seed=3, clock=None, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    r = {**es.DEFAULTS, "mode": mode, **rules}
    st = {"kind": "escape", "rules": r, "players": players, "phase": "lobby"}
    t = es.Table(st, random.Random(seed), now=clock or Clock())
    used = t.begin({})
    return t, used


def fails(fn, *a):
    try:
        fn(*a)
    except CommunityError as e:
        return str(e)
    raise AssertionError("no error")


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- the riddles
def test_about_fifty_templates_in_all_types_and_levels():
    assert len(er.TEMPLATES) >= 50
    assert {x[0] for x in er.TEMPLATES.values()} == set(er.TYPES)
    for lv in er.LEVELS:
        assert sum(1 for x in er.TEMPLATES.values() if lv in x[1]) >= 20, lv
    for t, x in er.TEMPLATES.items():
        assert x[1] and all(lv in er.LEVELS for lv in x[1]) and x[2], t
    names = [x[2] for x in er.TEMPLATES.values()]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("tid", sorted(er.TEMPLATES))
def test_every_template_right_wrong_and_no_leak(tid):
    typ, levels, name, _ = er.TEMPLATES[tid]
    answers = set()
    for lv in levels:
        for seed in range(12):
            r = er.make(tid, random.Random(seed * 7 + 1), lv)
            assert r["tpl"] == tid and r["type"] == typ and r["level"] == lv and r["name"] == name
            assert r["lines"] and 1 <= len(r["hints"]) <= 3 and r["input"]["k"]
            assert er.check(r, right(r)), (tid, lv, seed)
            if r["check"] in WRONG:
                assert not er.check(r, WRONG[r["check"]])
            else:                                     # a mechanical puzzle is not solved as it starts
                assert not er.check(r, [])
            assert not er.check(r, None) and not er.check(r, {"x": 1})
            pub = er.public(r, True)
            assert "sol" not in pub and "check" not in pub and "hints" not in pub
            dump = json.dumps(pub, ensure_ascii=False).lower()
            if r["check"] == "word":                  # the word itself never shows (only mixed, coded or with gaps)
                for w in r["sol"]:
                    if len(w) >= 4:
                        assert '"' + w + '"' not in dump and " " + w + " " not in dump, (tid, w)
            if r.get("peek"):                         # memory: the picture only while it is shown
                assert er.public(r, False)["show"] == [] and pub["show"]
            answers.add(json.dumps(r["sol"]))
    assert len(answers) > 1, tid                       # the answers differ from game to game


def test_word_riddles_in_every_language_and_any_language_counts():
    assert len(CONCEPTS) >= 40
    for c in CONCEPTS:
        assert set(c["words"]) == set(LANGS) and all(c["words"].values())
    r = er.make("anagram", random.Random(5), "medium")
    view = r["show"][0]["v"]["L"]
    assert set(view) == set(LANGS)
    concept = next(c for c in CONCEPTS if plain(c["words"]["en"]) in r["sol"])
    for lg in LANGS:                                   # the mixed letters are the letters of the word in that language
        assert sorted(view[lg].replace(" ", "")) == sorted(concept["words"][lg].upper().replace("ß", "SS"))
        assert er.check(r, concept["words"][lg]) and er.check(r, concept["words"][lg].upper() + " ")
    c = er.make("caesar", random.Random(2), "medium")
    assert c["show"][0]["v"]["L"]["de"] != c["show"][0]["v"]["L"]["en"] or c["sol"]
    assert er.check({"check": "word", "sol": ["zaba"]}, "Żaba") and er.check({"check": "word", "sol": ["apfel"]}, "Äpfel!")
    assert not er.check({"check": "word", "sol": ["apfel"]}, "apfels")


def test_mechanical_checks_replay_the_moves():
    r = er.make("lights_out", random.Random(1), "medium")
    assert er.check(r, r["sol"]) and er.check(r, r["sol"][::-1]) and not er.check(r, r["sol"][:-1])
    assert er.check(r, r["sol"] + [0, 0]) and not er.check(r, r["sol"] + [99])
    s = er.make("sliding", random.Random(1), "medium")
    assert er.check(s, s["sol"]) and not er.check(s, s["sol"][:-1]) and not er.check(s, [s["sol"][0], 99])
    tl = s["input"]["v"]
    far = next(v for i, v in enumerate(tl) if v and abs(i // 3 - tl.index(0) // 3) + abs(i % 3 - tl.index(0) % 3) > 1)
    assert not er.check(s, [far] + s["sol"])          # a tile that does not touch the gap cannot move
    g = er.make("rings", random.Random(4), "hard")
    assert er.check(g, g["sol"]) and er.check(g, g["sol"] + [0] * 6) and not er.check(g, g["sol"] + [0])
    p = er.make("pipes", random.Random(3), "hard")
    assert er.check(p, p["sol"]) and not er.check(p, [t[1] for t in p["input"]["v"]]) and not er.check(p, p["sol"][:-1])
    lv = er.make("levers", random.Random(2), "medium")
    assert er.check(lv, lv["sol"]) and not er.check(lv, lv["sol"] + lv["sol"][:1])
    c = er.make("clock_read", random.Random(3), "easy")
    hh, mm = int(c["sol"][:2]), c["sol"][2:]
    assert er.check(c, f"{hh + 12}{mm}") and er.check(c, f"{hh}:{mm}") and not er.check(c, f"{hh % 12 + 1}{mm}")


# ---------------------------------------------------------------- rooms, the combined door
def test_rooms_riddles_and_the_combined_door():
    t, used = table(1, rooms=3, level="hard")
    st = t.st
    assert len(st["rooms"]) == 3 and all(len(r["riddles"]) == 3 for r in st["rooms"]) and len(used) == 9
    assert len(set(used)) == 9 and all("hard" in er.TEMPLATES[u][1] for u in used)
    assert len({r["theme"] for r in st["rooms"]}) == 3
    for room in st["rooms"]:
        assert room["door"]["kind"] in ("order", "sum", "colours") and len(room["door"]["frags"]) == 3
    # a room: the riddles one by one; the door needs all parts together
    p = st["prog"]["0"]
    room = st["rooms"][0]
    assert fails(t.answer, "1", "1.0", "x") == "This riddle is in another room"
    assert t.answer("1", "0.0", WRONG.get(room["riddles"][0]["check"], [])) is False and p["pen"] == es.WRONG_S
    for i, rd in enumerate(room["riddles"]):
        assert t.answer("1", f"0.{i}", right(rd)) is True
    assert p["solved"]["0.0"]["by"] == "1"
    d = room["door"]
    if d["kind"] == "order":                           # the digits in the order of the symbols
        code = "".join(str(next(f["d"] for f in d["frags"] if f["sym"] == s)) for s in d["order"])
        assert code == d["sol"]
    elif d["kind"] == "sum":
        code = str(sum(f["n"] for f in d["frags"]))
    else:
        code = [f["c"] for f in sorted(d["frags"], key=lambda f: f["pos"])]
    assert t.door("1", "nonsense" if d["kind"] != "colours" else [9]) is False
    assert t.door("1", code) is True and p["room"] == 1 and st["phase"] == "play"
    assert fails(t.answer, "1", "0.0", "x") == "This riddle is in another room"
    for r in (1, 2):
        for i, rd in enumerate(st["rooms"][r]["riddles"]):
            t.answer("1", f"{r}.{i}", right(rd))
        t.door("1", st["rooms"][r]["door"]["sol"])
    assert st["phase"] == "done" and st["winners"] == ["0"] and st["result"]["0"]["out"] and st["places"] == {"1": 1}
    assert st["result"]["0"]["riddles"] == 9 and st["result"]["0"]["rooms"] == 3 and st["result"]["0"]["score"] > 2500


def test_mixed_rooms_get_harder_and_easy_has_two_riddles():
    assert es.room_levels("mixed", 3) == ["easy", "medium", "hard"] and es.room_levels("mixed", 1) == ["medium"]
    assert es.room_levels("mixed", 5) == ["easy", "easy", "medium", "hard", "hard"]
    t, used = table(1, rooms=2, level="easy")
    assert [len(r["riddles"]) for r in t.st["rooms"]] == [2, 2]
    assert all(rd["level"] == "easy" for r in t.st["rooms"] for rd in r["riddles"])
    assert all(r["door"]["kind"] in ("order", "sum") for r in t.st["rooms"])
    t, used = table(1, rooms=5, level="medium", types=["memory"])
    assert all(er.TEMPLATES[u][0] == "memory" for u in used) and len(used) == 15      # few templates: they come again


def test_hints_peek_and_time_penalty():
    clock = Clock(100)
    t, _ = table(2, clock=clock, rooms=1, level="medium", types=["memory"])
    p = t.st["prog"]["0"]
    rd = t.st["rooms"][0]["riddles"][0]
    t.hint("2", "0.0")
    assert p["hints"] == {"0.0": 1} and p["pen"] == es.HINT_S and p["log"][-1]["what"] == "hint"
    t.hint("1", "0.0")
    t.hint("1", "0.0")
    assert fails(t.hint, "1", "0.0") == "There are no more hints"
    assert fails(t.hint, "9", "0.0") == "You are not at this table"
    t.peek("1", "0.0")
    assert p["peek"]["0.0"] == 100 + rd["peek"]
    t.answer("1", "0.0", right(rd))
    assert fails(t.hint, "1", "0.0") == "This riddle is solved already"
    clock.t += 30
    assert t.elapsed() == 30 and t.eff("0") == 30 + 3 * es.HINT_S


# ---------------------------------------------------------------- what was played: fresh templates first, then a new round
def test_pick_templates_fresh_first_then_round_two():
    rng = random.Random(1)
    counts = {t: 0 for t in er.TEMPLATES}
    seen = set()
    levels = ["easy", "medium", "hard"]
    for _ in range(40):
        lv = [rng.choice(levels) for _ in range(3)]
        got = es.pick_templates(lv, list(er.TYPES), counts, rng)
        assert all(lvl in er.TEMPLATES[g][1] for g, lvl in zip(got, lv))
        for g in got:
            assert counts[g] == min(counts[x] for x in er.TEMPLATES if lv[got.index(g)] in er.TEMPLATES[x][1]) or g in seen
            seen.add(g)
        for g in set(got):
            counts[g] += 1
    assert len(seen) == len(er.TEMPLATES)
    only = es.pick_templates(["easy"] * 4, ["knowledge"], {t: 0 for t in er.TEMPLATES}, rng)
    assert len(set(only)) == 4 and all(er.TEMPLATES[g][0] == "knowledge" for g in only)
    hard_kn = es.pick_templates(["hard"], ["knowledge"], {}, rng)          # no hard knowledge riddle: the nearest level
    assert er.TEMPLATES[hard_kn[0]][0] == "knowledge"


def test_played_counter_and_round(fq):
    eng = fq.escape
    info = eng.played_info()
    assert info["total"] == len(er.TEMPLATES) and info["new"] == info["total"] and info["round"] == 1
    assert sum(x["total"] for x in info["types"].values()) == info["total"]
    eng._mark_played(["anagram", "pipes", "anagram"])
    info = eng.played_info()
    assert info["new"] == info["total"] - 2 and info["types"]["words"]["new"] == info["types"]["words"]["total"] - 1
    eng._mark_played([t for t in er.TEMPLATES if t not in ("anagram", "pipes")])
    info = eng.played_info()
    assert info["round"] == 2 and info["new"] == info["total"]          # everything played: a new round, all fresh again


def test_rules_are_cleaned():
    eng = es.Escape.__new__(es.Escape)
    assert eng.clean_rules("escape", {}) == es.DEFAULTS
    r = eng.clean_rules("escape", {"rooms": 9, "level": "x", "types": ["maths", "bogus", "logic"], "mode": "solo", "time": 20})
    assert r == {"rooms": 3, "level": "mixed", "types": ["logic", "maths"], "mode": "together", "time": 0}
    assert eng.clean_rules("escape", {"types": []})["types"] == list(er.TYPES)
    assert eng.clean_rules("escape", {"rooms": "5", "time": 45, "mode": "teams", "level": "hard"})["rooms"] == 5


# ---------------------------------------------------------------- two teams
def test_two_teams_same_rooms_own_state_and_the_faster_wins():
    clock = Clock(0)
    t, _ = table(4, mode="teams", clock=clock, rooms=1, level="easy")
    st = t.st
    assert st["teams"] and st["team_of"] == {"1": "0", "2": "1", "3": "0", "4": "1"} and set(st["prog"]) == {"0", "1"}
    room = st["rooms"][0]
    for i, rd in enumerate(room["riddles"]):
        t.answer("1", f"0.{i}", right(rd))
    assert len(st["prog"]["0"]["solved"]) == len(room["riddles"]) and st["prog"]["1"]["solved"] == {}
    st["prog"]["0"]["pen"] += 2 * es.HINT_S                      # team A used two hints: +120 s
    clock.t = 100
    assert t.door("3", room["door"]["sol"]) and st["prog"]["0"]["done_t"] == 100 and t.eff("0") == 220
    assert st["phase"] == "play"                                  # team B could still be faster
    assert fails(t.answer, "1", "0.0", "1") == "Your team is already out"
    clock.t = 150
    t.tick()
    assert st["phase"] == "play" and st["prog"]["1"]["solved"] == {}
    for i, rd in enumerate(room["riddles"]):                     # the same riddles for team B
        assert t.answer("2", f"0.{i}", right(rd))
    assert t.door("4", room["door"]["sol"])                       # out at 150 (no penalty): faster than 220
    assert st["phase"] == "done" and st["winners"] == ["1"] and st["places"] == {"1": 2, "2": 1, "3": 2, "4": 1}
    assert st["result"]["0"]["time"] == 220 and st["result"]["1"]["time"] == 150


def test_two_teams_ends_when_the_other_cannot_be_faster():
    clock = Clock(0)
    t, _ = table(2, mode="teams", clock=clock, rooms=1, level="easy")
    st = t.st
    room = st["rooms"][0]
    for i, rd in enumerate(room["riddles"]):
        t.answer("1", f"0.{i}", right(rd))
    t.hint("2", "0.0")                                            # team B: +60 s
    st["prog"]["0"]["pen"] = 50
    clock.t = 30
    assert t.door("1", room["door"]["sol"]) and t.eff("0") == 80          # B: 30 + 60 = 90 ≥ 80 – it cannot win any more
    assert st["phase"] == "done" and st["winners"] == ["0"] and st["result"]["1"]["hints"] == 1
    t2, _ = table(2, mode="teams", clock=clock, rooms=1, level="easy")
    clock.t = 0
    s2 = t2.st
    for i, rd in enumerate(s2["rooms"][0]["riddles"]):
        t2.answer("1", f"0.{i}", right(rd))
    s2["prog"]["0"]["pen"] = 50
    clock.t = 30
    t2.door("1", s2["rooms"][0]["door"]["sol"])                   # A: 30 + 50 = 80; B: 30
    assert s2["phase"] == "play"
    clock.t = 79
    t2.tick()
    assert s2["phase"] == "play"
    clock.t = 80                                                  # B cannot be faster than 80 any more
    t2.tick()
    assert s2["phase"] == "done" and s2["winners"] == ["0"] and s2["result"]["1"]["out"] is False


def test_time_limit_ends_without_winner():
    clock = Clock(0)
    t, _ = table(2, clock=clock, rooms=2, time=15)
    assert t.st["deadline"] == 900
    clock.t = 899
    assert not t.tick()
    clock.t = 901
    assert t.tick() and t.st["phase"] == "done" and t.st["winners"] == [] and t.elapsed() == 900
    assert fails(t.answer, "1", "0.0", "1") == "The game is not running"


# ---------------------------------------------------------------- the family table over the API
def family4(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    ben = client.post("/api/parent/profiles", json={"name": "Ben"}, headers=phd).json()["id"]
    return phd, mia, leo, ben


def solve_room(client, fq, heads, gid, team_player):
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE id=?", gid)["state"])
    tm = st["team_of"][team_player]
    ri = st["prog"][tm]["room"]
    room = st["rooms"][ri]
    for i, rd in enumerate(room["riddles"]):
        r = client.post("/api/community/escape/answer", json={"key": f"{ri}.{i}", "answer": right(rd)}, headers=heads[team_player]).json()
        assert r["ok"], rd["tpl"]
    return client.post("/api/community/escape/answer", json={"answer": room["door"]["sol"]}, headers=heads[team_player]).json()


def test_family_flow_no_leak_coins_once_history_champion(client):
    phd, mia, leo, ben = family4(client)
    fq = client.app.state.fq
    fq.escape.rng = random.Random(7)
    assert client.put("/api/parent/game-rewards", json={"escape": [12, 0, 0]}, headers=phd).json()["escape"] == [12, 0, 0]
    hm, hl, hb = login(client, mia, "1111"), login(client, leo), login(client, ben)
    heads = {str(mia): hm, str(leo): hl, str(ben): hb}
    info = client.get("/api/community/escape/rules", headers=hm).json()
    assert info["rooms"] == 3 and info["played"]["new"] == len(er.TEMPLATES) and len(info["riddles"]) == len(er.TEMPLATES)
    st = client.post("/api/community/escape/start", json={"rooms": 2, "level": "medium", "types": ["maths", "logic", "observe"], "mode": "together"}, headers=hm).json()
    assert st["phase"] == "lobby" and st["rules"]["types"] == ["logic", "observe", "maths"]
    assert client.post("/api/community/escape/start", json={}, headers=hl).status_code == 400
    for h in (hl, hb):
        client.post("/api/community/escape/join", headers=h)
    assert client.post("/api/community/escape/begin", headers=hl).status_code == 403
    st = client.post("/api/community/escape/begin", headers=hm).json()
    assert st["phase"] == "play" and st["coins_on"] and st["room"]["index"] == 0 and len(st["room"]["riddles"]) == 3
    assert client.get("/api/community/escape/rules", headers=hm).json()["played"]["new"] == len(er.TEMPLATES) - 6
    gid = st["game"]
    dump = json.dumps(st)
    assert '"sol"' not in dump and '"check"' not in dump and '"frags"' not in dump and st["room"]["riddles"][0]["hints"] == []
    assert all(r["frag"] is None for r in st["room"]["riddles"])
    # a wrong answer, a hint for everybody, a right answer reveals a part of the code
    k0 = st["room"]["riddles"][0]["key"]
    r = client.post("/api/community/escape/answer", json={"key": k0, "answer": "000000"}, headers=hl).json()
    assert r["ok"] is False and r["state"]["progress"]["0"]["pen"] == es.WRONG_S
    v = client.post("/api/community/escape/hint", json={"key": k0}, headers=hl).json()
    assert len(v["room"]["riddles"][0]["hints"]) == 1
    assert len(client.get("/api/community/escape", headers=hb).json()["room"]["riddles"][0]["hints"]) == 1
    assert client.post("/api/community/escape/answer", json={"key": "5.0", "answer": "1"}, headers=hl).status_code == 400
    assert client.post("/api/community/escape/answer", json={"key": k0, "answer": "x" * 99}, headers=hl).status_code == 400
    row = json.loads(fq.db.q1("SELECT state FROM card_game WHERE id=?", gid)["state"])
    rd0 = row["rooms"][0]["riddles"][0]
    r = client.post("/api/community/escape/answer", json={"key": k0, "answer": right(rd0)}, headers=hb).json()
    assert r["ok"] and r["state"]["room"]["riddles"][0]["solved"]["by"] == str(ben) and r["state"]["room"]["riddles"][0]["frag"]
    assert r["state"]["room"]["log"][-1]["what"] == "solved"
    # somebody not at the table cannot play
    from test_api import setup_family  # noqa: F401
    papa = fq.db.val("SELECT id FROM profile WHERE role='parent'")
    hp = login(client, papa, "1234")
    assert client.post("/api/community/escape/answer", json={"key": k0, "answer": "1"}, headers=hp).status_code == 400
    # the rest of both rooms: out!
    before = {p: fq.rewards.balance(int(p), "coins") for p in heads}
    solve_room(client, fq, heads, gid, str(mia))
    out = solve_room(client, fq, heads, gid, str(leo))
    v = out["state"]
    assert v["phase"] == "done" and v["winners"] == ["0"] and v["result"]["0"]["out"] and v["result"]["0"]["hints"] == 1
    assert {p["id"]: p["coins"] for p in v["players"]} == {p: 12 for p in heads}
    for p in heads:
        assert fq.rewards.balance(int(p), "coins") == before[p] + 12
    rowx = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.escape._save(rowx, json.loads(rowx["state"]))                     # saving again pays nothing more
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"escape:{gid}:%") == 3
    assert fq.db.q1("SELECT reason FROM ledger WHERE ref=?", f"escape:{gid}:{mia}")["reason"] == "Escape Room – place 1"
    e = next(x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "escape")
    assert e["data"]["out"] and e["data"]["won"] and e["data"]["rooms"] == 2 and e["data"]["of"] == 2 and e["data"]["coins"] == 12
    champs = {str(r["id"]) for r in fq.db.q("SELECT id, settings FROM profile") if json.loads(r["settings"] or "{}").get("champion")}
    assert champs == set(heads)
    assert client.post("/api/community/escape/answer", json={"answer": "1"}, headers=hm).status_code == 400


def test_teams_over_the_api_see_only_the_other_progress(client):
    phd, mia, leo, ben = family4(client)
    fq = client.app.state.fq
    fq.escape.rng = random.Random(2)
    hm, hl, hb = login(client, mia, "1111"), login(client, leo), login(client, ben)
    heads = {str(mia): hm, str(leo): hl, str(ben): hb}
    client.post("/api/community/escape/start", json={"rooms": 1, "level": "easy", "mode": "teams"}, headers=hm)
    for h in (hl, hb):
        client.post("/api/community/escape/join", headers=h)
    v = client.get("/api/community/escape", headers=hm).json()
    assert v["teams"] and [p["team"] for p in v["players"]] == ["0", "1", "0"]
    assert client.post("/api/community/escape/mix", headers=hl).status_code == 403
    v = client.post("/api/community/escape/begin", headers=hm).json()
    team = {p["id"]: p["team"] for p in v["players"]}
    other = next(p for p in heads if team[p] != team[str(mia)])
    vo = client.get("/api/community/escape", headers=heads[other]).json()
    assert set(vo["progress"]) == {"0", "1"} and vo["my_team"] == team[other]
    assert [r["tpl"] for r in vo["room"]["riddles"]] == [r["tpl"] for r in v["room"]["riddles"]]   # the same riddles
    out = solve_room(client, fq, heads, v["game"], other)["state"]
    assert out["phase"] == "done" and out["winners"] == [team[other]]
    assert {p["id"]: p["coins"] for p in out["players"]} == {p: (10 if team[p] == team[other] else 0) for p in heads}
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'escape:%'") == 1


def test_guests_play_but_not_lead_alone_no_coins_and_paths(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    client.post("/api/community/escape/start", json={"rooms": 1}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "escape"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Escape Room"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "mix"):
        assert client.post("/api/community/escape/" + path, json={}, headers=hg).status_code in (401, 403), path
    assert client.get("/api/community/escape/rules", headers=hg).status_code in (401, 403)
    st = client.post("/api/community/escape/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    gid = st["game"]
    out = solve_room(client, fq, {str(mia): hm, str(g["profile"]["id"]): hg}, gid, str(g["profile"]["id"]))["state"]
    assert out["phase"] == "done" and out["winners"] == ["0"] and all(p["coins"] == 0 for p in out["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'escape:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='escape'") == 1           # Mia only, not the guest
    for p in ("", "/join", "/answer", "/hint", "/peek"):
        assert netfilter.is_guest_path("/api/community/escape" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/mix"):
        assert not netfilter.is_guest_path("/api/community/escape" + p), p
    assert client.put("/api/parent/games", json={"access": {"escape": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.get("/api/community/escape", headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "escape" not in me["games_list"] and me["community"]["escape"] is None
    assert "escape" not in client.get("/api/parent/games", headers=phd).json()["bot_games"]


def test_parents_end_it_in_the_running_list(client):
    phd, mia, leo, ben = family4(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/escape/start", json={"rooms": 1}, headers=hm)
    client.post("/api/community/escape/join", headers=hl)
    assert client.post("/api/community/escape/end", headers=hl).status_code == 403
    client.post("/api/community/escape/begin", headers=hm)
    games = client.get("/api/parent/games/running", headers=phd).json()
    g = next(x for x in games if x["game"] == "escape")
    assert g["icon"] == "🗝️" and g["title"] == "Escape Room" and g["players"] == 2 and g["host"] == "Mia"
    client.post("/api/parent/games/end", json={"key": g["key"]}, headers=phd)
    v = client.get("/api/community/escape", headers=hm).json()
    assert v["phase"] == "done" and v["winners"] == [] and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'escape:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='escape'") == 2
