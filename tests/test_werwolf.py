import json
import random

import pytest

from familyquest import werwolf as ww
from familyquest.community import CommunityError


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def table(roles, clock=None, **rules):
    """A table with fixed roles: roles = ["wolf", "seer", …] for players "1", "2", …"""
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, len(roles) + 1)]
    r = {**ww.DEFAULTS, **rules}
    st = {"kind": "werwolf", "rules": r, "players": players, "phase": "lobby"}
    t = ww.Table(st, random.Random(1), now=clock or Clock())
    t.begin()
    st["roles"] = {str(i): x for i, x in enumerate(roles, 1)}
    return t


def fails(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except CommunityError as e:
        return str(e)
    raise AssertionError("no error")


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


# ---------------------------------------------------------------- dealing the roles
def test_presets_and_dealing_per_count():
    assert ww.preset(5) == {"wolves": 1, "seer": True, "witch": False, "hunter": False, "amor": False}
    assert ww.preset(6)["witch"] and not ww.preset(6)["hunter"] and ww.preset(6)["wolves"] == 1
    assert ww.preset(7)["wolves"] == 2 and ww.preset(8)["hunter"] and not ww.preset(8)["amor"]
    assert ww.preset(9)["amor"] and ww.preset(10)["wolves"] == 2 and ww.preset(11)["wolves"] == 3 and ww.preset(12)["wolves"] == 3
    for n in range(5, 13):
        players = [{"id": str(i), "name": f"P{i}"} for i in range(n)]
        st = {"kind": "werwolf", "rules": dict(ww.DEFAULTS), "players": players, "phase": "lobby"}
        ww.Table(st, random.Random(n)).begin()
        roles = list(st["roles"].values())
        d = ww.preset(n)
        assert len(roles) == n and roles.count("wolf") == d["wolves"] and st["phase"] == "roles"
        for s in ww.SPECIALS:
            assert roles.count(s) == (1 if d[s] else 0)
        assert roles.count("villager") == n - d["wolves"] - sum(d[s] for s in ww.SPECIALS)
        assert roles.count("wolf") * 2 < n
    # custom sets: checked against the number of players
    custom = {**ww.DEFAULTS, "auto": False, "wolves": 3, "seer": True, "witch": True, "hunter": True, "amor": True}
    assert fails(ww.deck_for, custom, 6) == "Too many wolves for this number of players"
    assert ww.deck_for(custom, 7) == {"wolves": 3, "seer": True, "witch": True, "hunter": True, "amor": True}
    assert fails(ww.deck_for, {**custom, "wolves": 2}, 5) == "Too many roles for this number of players"
    players = [{"id": str(i), "name": "x"} for i in range(4)]
    assert fails(ww.Table({"rules": dict(ww.DEFAULTS), "players": players, "phase": "lobby"}).begin) == "At least 5 players are needed"


# ---------------------------------------------------------------- the night
def test_night_order_amor_wolves_seer_witch():
    t = table(["wolf", "wolf", "seer", "witch", "amor", "hunter", "villager", "villager"])
    assert t.st["phase"] == "roles" and t.actors() == []
    t.advance()                                                  # the leader: night falls
    assert (t.st["phase"], t.st["step"], t.st["night"]) == ("night", "amor", 1) and t.actors() == ["5"]
    assert fails(t.act, "1", "bite", "3") == "It is not your turn"
    assert fails(t.act, "5", "lovers", "7", "7") == "Choose two different players"
    t.act("5", "lovers", "7", "8")
    assert t.st["lovers"] == ["7", "8"] and t.st["step"] == "wolves" and t.actors() == ["1", "2"]
    t.act("1", "bite", "3")
    assert t.st["step"] == "wolves" and t.st["wolf_votes"] == {"1": "3"}
    assert fails(t.act, "2", "bite", "1") == "Choose a player who is not a wolf"
    t.act("2", "bite", "4")                                      # disagree: no victim yet
    assert t.st["step"] == "wolves" and t.st["victim"] is None
    t.act("2", "bite", "3")                                      # agree: the victim is chosen
    assert t.st["victim"] == "3" and t.st["step"] == "seer" and t.actors() == ["3"]
    assert fails(t.act, "3", "look", "3") == "Not yourself"
    t.act("3", "look", "1")
    assert t.st["seen"] == [{"night": 1, "id": "1", "role": "wolf"}] and t.st["step"] == "seer"
    assert fails(t.act, "3", "look", "2") == "You already looked tonight"
    t.act("3", "sleep")
    assert t.st["step"] == "witch" and t.actors() == ["4"]
    t.act("4", "potion", heal=False, poison=None)
    # dawn: the seer is dead, the day starts with the talk timer
    assert t.st["phase"] == "day" and t.st["dead"] == ["3"] and t.st["deaths"] == [{"id": "3", "role": "seer", "cause": "wolves"}]
    assert t.st["deadline"] == 1000 + 180
    # the second night: no amor, no seer (dead)
    t.advance()
    for p in ("1", "2", "4", "5", "6", "7"):
        t.act(p, "vote", "")                                     # everybody abstains
    t.act("8", "vote", "")
    assert t.st["phase"] == "verdict" and t.st["lynch"] is None
    t.advance()
    assert t.st["night"] == 2 and t.st["step"] == "wolves" and t.steps() == ["wolves", "witch"]


def test_wolves_leader_advance_majority_and_tie():
    t = table(["wolf", "wolf", "wolf", "villager", "villager", "villager", "villager", "seer"])
    t.advance()
    assert t.st["step"] == "wolves"
    t.act("1", "bite", "4")
    t.act("2", "bite", "4")
    t.act("3", "bite", "5")
    assert t.st["victim"] is None
    t.advance()                                                  # the leader: the most votes
    assert t.st["victim"] == "4" and t.st["step"] == "seer"
    t.advance()
    assert t.st["phase"] == "day" and t.st["dead"] == ["4"]
    t2 = table(["wolf", "wolf", "villager", "villager", "villager", "villager", "villager"])
    t2.advance()
    t2.act("1", "bite", "3")
    t2.act("2", "bite", "4")
    t2.advance()                                                 # a tie: nobody dies
    assert t2.st["phase"] == "day" and t2.st["dead"] == [] and t2.st["deaths"] == []


def test_witch_potions_once():
    t = table(["wolf", "witch", "villager", "villager", "villager", "villager"])
    t.advance()
    t.act("1", "bite", "3")
    assert t.st["step"] == "witch"
    assert fails(t.act, "2", "potion", poison="2") == "Not yourself"
    t.act("2", "potion", heal=True, poison="4")                   # heal the victim, poison 4 – both in one night
    assert t.st["dead"] == ["4"] and t.st["potions"] == {"heal": False, "poison": False}
    t.advance()                                                  # day → vote
    t.advance()                                                  # close the vote without votes
    t.advance()                                                  # night 2
    t.act("1", "bite", "5")
    assert fails(t.act, "2", "potion", heal=True) == "The healing potion is used up"
    assert fails(t.act, "2", "potion", poison="3") == "The poison potion is used up"
    t.act("2", "potion")
    assert "5" in t.st["dead"]
    # no victim: nothing to heal
    t3 = table(["wolf", "witch", "villager", "villager", "villager", "villager"])
    t3.advance()
    t3.advance()                                                 # the wolves did not choose
    assert fails(t3.act, "2", "potion", heal=True) == "Nobody to heal tonight"


def test_hunter_shoots_at_night_and_after_the_vote():
    t = table(["wolf", "hunter", "villager", "villager", "villager", "villager", "wolf", "villager"])
    t.advance()
    t.act("1", "bite", "2")
    t.act("7", "bite", "2")
    assert t.st["phase"] == "hunter" and t.st["hunter"] == "2" and t.actors() == ["2"]
    assert fails(t.act, "3", "shoot", "1") == "It is not your turn"
    assert fails(t.act, "2", "shoot", "2") == "Choose a living player"
    t.act("2", "shoot", "1")                                     # the dead hunter acts once
    assert t.st["phase"] == "day" and [d["id"] for d in t.st["deaths"]] == ["2", "1"] and t.st["deaths"][1]["cause"] == "shot"
    # the hunter lynched: he shoots before the verdict
    t2 = table(["wolf", "hunter", "villager", "villager", "villager", "wolf", "villager"])
    t2.advance()
    t2.advance()                                                 # no victim
    t2.advance()                                                 # day → vote
    for p in ("1", "3", "4", "5", "6", "7"):
        t2.act(p, "vote", "2")
    t2.act("2", "vote", "1")
    assert t2.st["phase"] == "hunter" and t2.st["lynch"] == "2"
    t2.advance()                                                 # the leader: nobody shot
    assert t2.st["phase"] == "verdict" and t2.st["dead"] == ["2"]


def test_lovers_die_together_and_win_together():
    t = table(["wolf", "amor", "villager", "villager", "villager", "villager"])
    t.advance()
    t.act("2", "lovers", "1", "3")                               # a wolf and a villager
    t.act("1", "bite", "4")
    assert t.st["phase"] == "day"
    t.advance()                                                  # vote
    for p in ("1", "2", "3", "5"):
        t.act(p, "vote", "6")
    t.act("6", "vote", "5")
    assert t.st["phase"] == "verdict" and t.st["lynch"] == "6"
    t.advance()
    t.act("1", "bite", "5")
    t.advance()
    for p in ("1", "3"):
        t.act(p, "vote", "2")
    t.act("2", "vote", "")
    # only the two lovers left (a wolf and a villager): they win together
    assert t.st["phase"] == "done" and t.st["winner"] == "lovers" and t.st["winners"] == ["1", "3"]
    # one lover dies, the other dies of grief
    t2 = table(["wolf", "amor", "villager", "villager", "villager", "villager", "villager"])
    t2.advance()
    t2.act("2", "lovers", "3", "4")
    t2.act("1", "bite", "3")
    assert t2.st["phase"] == "day" and t2.st["deaths"] == [{"id": "3", "role": "villager", "cause": "wolves"}, {"id": "4", "role": "villager", "cause": "love"}]


def test_day_vote_majority_and_tie():
    t = table(["wolf", "villager", "villager", "villager", "villager", "villager"], clock=(c := Clock()))
    t.advance()
    t.advance()                                                  # no victim
    assert t.st["phase"] == "day"
    c.t += 179
    assert not t.tick()
    c.t += 2
    assert t.tick() and t.st["phase"] == "vote"                  # the talk time is over: the vote
    assert fails(t.act, "2", "vote", "2") == "Not yourself"
    t.act("1", "vote", "2")
    t.act("2", "vote", "1")
    t.act("3", "vote", "1")
    t.act("3", "vote", "2")                                      # changed the mind
    t.act("4", "vote", "1")
    t.act("5", "vote", "")
    assert t.tally() == {"2": 2, "1": 2} and t.st["phase"] == "vote"
    t.act("6", "vote", "")
    assert t.st["phase"] == "verdict" and t.st["lynch"] is None and t.st["dead"] == []     # a tie: nobody
    t.advance()
    t.advance()
    t.advance()
    for p, v in (("1", "2"), ("2", "1"), ("3", "1"), ("4", "1"), ("5", "2"), ("6", "")):
        t.act(p, "vote", v)
    assert t.st["phase"] == "done" and t.st["winner"] == "village" and t.st["lynch"] == "1"


def test_win_conditions():
    t = table(["wolf", "wolf", "villager", "villager", "villager", "villager", "villager"])
    t.st["dead"] = ["3", "4", "5"]
    assert t.winner() == "wolves"                                # 2 wolves against 2
    t.st["dead"] = ["3", "4"]
    assert t.winner() is None
    t.st["dead"] = ["1", "2"]
    assert t.winner() == "village"
    t.st["dead"] = ["1", "2", "3", "4", "5", "6", "7"]
    assert t.winner() == "village"                               # all wolves dead
    t.st.update(dead=["2", "4", "5", "6", "7"], lovers=["1", "3"])
    assert t.winner() == "lovers"
    t.st.update(lovers=["3", "4"], dead=["2", "5", "6", "7"])
    assert t.winner() is None
    # the wolves eat the last villagers: the game ends at dawn
    t2 = table(["wolf", "villager", "villager", "villager", "villager"])
    t2.st["dead"] = ["3", "4"]
    t2.advance()
    t2.act("1", "bite", "2")
    assert t2.st["phase"] == "done" and t2.st["winner"] == "wolves" and t2.st["winners"] == ["1"]


def test_dead_cannot_act_and_end():
    t = table(["wolf", "seer", "villager", "villager", "villager", "villager"])
    t.advance()
    t.act("1", "bite", "2")
    assert t.st["step"] == "seer"
    t.advance()                                                  # the seer is idle: the leader moves on
    assert t.st["phase"] == "day" and "2" in t.st["dead"]
    t.advance()
    assert fails(t.act, "2", "vote", "1") == "It is not your turn"
    assert fails(t.act, "3", "vote", "2") == "Choose a living player"
    t.advance()
    t.advance()
    assert t.steps() == ["wolves"]                               # the dead seer is not called
    assert fails(t.act, "2", "look", "1") == "It is not your turn"
    assert fails(t.act, "9", "vote", "1") == "You are not at this table"
    assert fails(t.act, "1", "dance") == "Unknown action"
    t.end()
    assert t.st["phase"] == "done" and t.st["winner"] is None and t.st["ended"]
    assert fails(t.advance) == "The game is not running"


# ---------------------------------------------------------------- the family table over the API
def family(client, n=6):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    ids = [mia, leo]
    for i in range(n - 2):
        ids.append(client.post("/api/parent/profiles", json={"name": f"Kind{i}"}, headers=phd).json()["id"])
    heads = {str(mia): login(client, mia, "1111")}
    for pid in ids[1:]:
        heads[str(pid)] = login(client, pid)
    return phd, ids, heads


def start_game(client, heads, ids, roles, **rules):
    fq = client.app.state.fq
    hm = heads[str(ids[0])]
    st = client.post("/api/community/werwolf/start", json={"talk": 120, **rules}, headers=hm).json()
    assert st["phase"] == "lobby"
    for pid in ids[1:]:
        client.post("/api/community/werwolf/join", headers=heads[str(pid)])
    st = client.post("/api/community/werwolf/begin", headers=hm).json()
    assert st["phase"] == "roles"
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werwolf' AND status!='done'")
    s = json.loads(row["state"])
    s["roles"] = {str(p): r for p, r in zip(ids, roles)}
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    return row["id"]


def get(client, h):
    r = client.get("/api/community/werwolf", headers=h)
    assert r.status_code == 200
    return r.json()


def act(client, h, **body):
    r = client.post("/api/community/werwolf/act", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_secrecy_on_the_raw_json(client):
    phd, ids, heads = family(client, 8)
    fq = client.app.state.fq
    roles = ["villager", "wolf", "wolf", "seer", "witch", "amor", "hunter", "villager"]
    start_game(client, heads, ids, roles)
    who = {r: str(p) for p, r in zip(ids, roles) if r != "villager"}
    who["wolf"] = str(ids[1])
    vill = str(ids[0])
    v = get(client, heads[vill])
    assert v["my_role"] == "villager" and [p["role"] for p in v["players"]] == ["villager"] + [None] * 7
    raw = json.dumps(v)
    for word in ("wolf", "seer", "witch", "amor", "hunter"):
        assert f'"role": "{word}"' not in raw
    assert v["deck"] == {"wolves": 2, "seer": True, "witch": True, "hunter": True, "amor": False}     # public: the roles in play
    w = get(client, heads[who["wolf"]])
    assert {p["id"]: p["role"] for p in w["players"] if p["role"]} == {who["wolf"]: "wolf", str(ids[2]): "wolf"}
    client.post("/api/community/werwolf/next", headers=heads[vill])            # the host (Mia) leads: night 1
    v = get(client, heads[vill])
    assert v["phase"] == "night" and v["step"] == "amor" and not v["my_turn"]
    assert get(client, heads[who["amor"]])["my_turn"]
    act(client, heads[who["amor"]], action="lovers", target=vill, target2=who["hunter"])
    v = get(client, heads[vill])
    assert v["my_lover"] == who["hunter"] and [p["id"] for p in v["players"] if p["lover"]] == [vill, who["hunter"]]
    assert next(p for p in v["players"] if p["id"] == who["hunter"])["role"] is None        # the lover's role stays secret
    assert get(client, heads[who["amor"]])["lovers"] == [vill, who["hunter"]]
    o = get(client, heads[who["seer"]])
    assert o["lovers"] is None and o["my_lover"] is None and not any(p["lover"] for p in o["players"])
    # the wolves see each other's votes – nobody else
    act(client, heads[who["wolf"]], action="bite", target=who["seer"])
    w2 = get(client, heads[str(ids[2])])
    assert w2["step"] == "wolves" and w2["my_turn"] and w2["wolf_votes"] == {who["wolf"]: who["seer"]}
    for r in ("seer", "witch", "amor", "hunter"):
        x = get(client, heads[who[r]])
        assert x["wolf_votes"] is None and x["victim"] is None and who["seer"] not in json.dumps({k: x[k] for k in ("wolf_votes", "victim")})
    act(client, heads[str(ids[2])], action="bite", target=who["seer"])
    # the seer's result only for the seer
    act(client, heads[who["seer"]], action="look", target=who["wolf"])
    s = get(client, heads[who["seer"]])
    assert s["seen"] == [{"night": 1, "id": who["wolf"], "role": "wolf"}] and s["looked"]
    assert next(p for p in s["players"] if p["id"] == who["wolf"])["role"] == "wolf"
    for r in ("witch", "amor", "hunter"):
        x = get(client, heads[who[r]])
        assert x["seen"] is None and next(p for p in x["players"] if p["id"] == who["wolf"])["role"] is None
    act(client, heads[who["seer"]], action="sleep")
    # the witch sees the victim and her potions – the others do not
    x = get(client, heads[who["witch"]])
    assert x["step"] == "witch" and x["victim"] == who["seer"] and x["potions"] == {"heal": True, "poison": True}
    for p in (vill, who["wolf"], who["amor"]):
        y = get(client, heads[p])
        assert y["victim"] is None and y["potions"] is None
    act(client, heads[who["witch"]], action="potion", heal=False, poison=str(ids[7]))
    # the day: the dead are revealed (not how they died); the dead see everything
    v = get(client, heads[vill])
    assert v["phase"] == "day" and v["deaths"] == [{"id": who["seer"], "role": "seer", "cause": "night"}, {"id": str(ids[7]), "role": "villager", "cause": "night"}]
    assert 115000 < v["left_ms"] <= 120000 and v["time_ms"] == 120000
    assert sorted(p["id"] for p in v["players"] if p["role"]) == sorted([vill, who["seer"], str(ids[7])])
    d = get(client, heads[who["seer"]])
    assert d["spectator"] and not d["alive"] and all(p["role"] for p in d["players"]) and d["lovers"] == [vill, who["hunter"]]
    assert d["potions"] == {"heal": True, "poison": False} and d["deaths"][1]["cause"] == "poison"
    r = client.post("/api/community/werwolf/act", json={"action": "vote", "target": vill}, headers=heads[who["seer"]])
    assert r.status_code == 400                                               # the dead cannot act
    # the vote: who voted is public, the targets only after the vote
    client.post("/api/community/werwolf/next", headers=heads[vill])
    act(client, heads[vill], action="vote", target=who["wolf"])
    y = get(client, heads[who["amor"]])
    assert y["voted"] == [vill] and y["votes"] is None and y["my_vote"] is None
    assert get(client, heads[vill])["my_vote"] == who["wolf"]
    assert get(client, heads[who["seer"]])["votes"] == {vill: who["wolf"]}       # the dead watch


def test_family_flow_coins_once_history_hat_and_guests(client):
    phd, ids, heads = family(client, 5)
    fq = client.app.state.fq
    assert client.put("/api/parent/game-rewards", json={"werwolf": [7, 3, 1]}, headers=phd).json()["werwolf"] == [7, 3, 1]
    hm = heads[str(ids[0])]
    r = client.get("/api/community/werwolf/rules", headers=hm).json()
    assert r["rewards"] == [7, 3, 1] and r["talks"] == [60, 120, 180, 300, 600] and r["presets"]["5"]["wolves"] == 1
    client.post("/api/community/werwolf/start", json={}, headers=hm)
    assert client.post("/api/community/werwolf/start", json={}, headers=heads[str(ids[1])]).status_code == 400
    r = client.post("/api/community/werwolf/begin", headers=hm)
    assert r.status_code == 400 and r.json()["detail"] == "At least 2 players are needed"      # alone: not even with bots
    # a guest via the invitation
    inv = client.post("/api/community/guests", json={"game": "werwolf"}, headers=heads[str(ids[1])]).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Werewolves"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    gid = str(g["profile"]["id"])
    for path in ("start", "begin", "end", "next", "rules"):
        assert client.post("/api/community/werwolf/" + path, json={}, headers=hg).status_code in (401, 403), path
    for pid in ids[1:]:
        client.post("/api/community/werwolf/join", headers=heads[str(pid)])
    # the leader changes the roles in the lobby
    assert client.post("/api/community/werwolf/rules", json={"auto": False, "wolves": 3}, headers=heads[str(ids[1])]).status_code == 403
    v = client.post("/api/community/werwolf/rules", json={"auto": False, "wolves": 3}, headers=hm).json()
    assert v["deck"] is None and v["deck_error"] == "Too many wolves for this number of players"
    assert client.post("/api/community/werwolf/begin", headers=hm).status_code == 400
    v = client.post("/api/community/werwolf/rules", json={"auto": True}, headers=hm).json()
    assert v["deck"] == ww.preset(6) and len(v["players"]) == 6
    client.post("/api/community/werwolf/begin", headers=hm)
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werwolf' AND status!='done'")
    s = json.loads(row["state"])
    order = [p["id"] for p in s["players"]]
    fam = [p for p in order if p != gid]
    wolf, seer, witch = fam[1], fam[2], fam[3]
    s["roles"] = {p: {wolf: "wolf", seer: "seer", witch: "witch"}.get(p, "villager") for p in order}      # the guest is a villager
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    H = {**heads, gid: hg}
    before = {p: fq.rewards.balance(int(p), "coins") for p in heads}
    client.post("/api/community/werwolf/next", headers=hm)                # night
    assert client.post("/api/community/werwolf/next", headers=H[wolf]).status_code == 403
    act(client, H[wolf], action="bite", target=fam[0])
    act(client, H[seer], action="look", target=wolf)
    act(client, H[seer], action="sleep")
    act(client, H[witch], action="potion", heal=True)
    v = get(client, hm)
    assert v["phase"] == "day" and v["deaths"] == [] and v["alive"]
    client.post("/api/community/werwolf/next", headers=hm)                # vote
    for p in order:
        if p != wolf:
            act(client, H[p], action="vote", target=wolf)
    v = get(client, hg)
    assert v["phase"] == "vote" and v["voted"] == [p for p in order if p != wolf]
    v = act(client, H[wolf], action="vote", target=seer)
    assert v["phase"] == "done" and v["winner"] == "village" and v["lynch"] == wolf
    assert all(p["role"] for p in v["players"])
    coins = {p["id"]: p["coins"] for p in v["players"]}
    assert coins == {**{p: 7 for p in order if p not in (wolf, gid)}, wolf: 0, gid: 0}
    for p in heads:
        assert fq.rewards.balance(int(p), "coins") == before[p] + (0 if p == wolf else 7)
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
    fq.werwolf._save(row, json.loads(row["state"]))                       # saving again pays nothing more
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"werwolf:{row['id']}:%") == 4
    e = next(x for x in client.get("/api/community/history", headers=H[seer]).json() if x["kind"] == "werwolf")
    assert e["data"]["won"] and e["data"]["role"] == "seer" and e["data"]["side"] == "village" and e["data"]["coins"] == 7
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='werwolf'") == 5                   # not the guest
    champs = {str(r["id"]) for r in fq.db.q("SELECT id, settings FROM profile") if json.loads(r["settings"] or "{}").get("champion")}
    assert champs == {p for p in heads if p != wolf}
    with pytest.raises(CommunityError):
        fq.werwolf.act(int(seer), "vote", wolf)


def test_end_by_leader_pays_nothing_and_paths(client):
    from familyquest import netfilter
    phd, ids, heads = family(client, 5)
    fq = client.app.state.fq
    start_game(client, heads, ids, ["villager", "wolf", "seer", "villager", "villager"])
    client.post("/api/community/werwolf/next", headers=phd)                # a parent leads too
    assert get(client, heads[str(ids[0])])["phase"] == "night"
    assert client.post("/api/community/werwolf/end", headers=heads[str(ids[1])]).status_code == 403
    v = client.post("/api/community/werwolf/end", headers=phd).json()
    v = get(client, heads[str(ids[0])])
    assert v["phase"] == "done" and v["ended"] and v["winner"] is None and all(p["coins"] == 0 for p in v["players"])
    assert all(p["role"] for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'werwolf:%'")
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='werwolf'") == 0
    for p in ("", "/join", "/act"):
        assert netfilter.is_guest_path("/api/community/werwolf" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/next"):
        assert not netfilter.is_guest_path("/api/community/werwolf" + p), p
    assert client.put("/api/parent/games", json={"access": {"werwolf": {"mode": "off"}}}, headers=phd).status_code == 200
    hm = heads[str(ids[0])]
    assert client.get("/api/community/werwolf", headers=hm).status_code == 403
    me = client.get("/api/me", headers=hm).json()
    assert "werwolf" not in me["games_list"] and me["community"]["werwolf"] is None


def test_twelve_players_no_more_and_running_list_end(client):
    phd, ids, heads = family(client, 12)
    fq = client.app.state.fq
    hm = heads[str(ids[0])]
    client.post("/api/community/werwolf/start", json={}, headers=hm)
    for pid in ids[1:]:
        assert client.post("/api/community/werwolf/join", headers=heads[str(pid)]).status_code == 200
    extra = client.post("/api/parent/profiles", json={"name": "Dreizehn"}, headers=phd).json()["id"]
    r = client.post("/api/community/werwolf/join", headers=login(client, extra))
    assert r.status_code == 400 and r.json()["detail"] == "The table is full"
    v = client.post("/api/community/werwolf/begin", headers=hm).json()
    assert v["phase"] == "roles" and v["deck"]["wolves"] == 3 and len(v["players"]) == 12
    games = client.get("/api/parent/games/running", headers=phd).json()
    g = next(x for x in games if x["game"] == "werwolf")
    assert g["icon"] == "🐺" and g["title"] == "Werewolves" and g["players"] == 12 and g["host"] == "Mia"
    client.post("/api/parent/games/end", json={"key": g["key"]}, headers=phd)
    v = get(client, hm)
    assert v["phase"] == "done" and v["winner"] is None
    assert fq.db.val("SELECT status FROM card_game WHERE kind='werwolf'") == "done"
    assert client.get("/api/me", headers=hm).json()["community"]["werwolf"] is None


# ---------------------------------------------------------------- bots fill the table (from 2 people)
def bot_table(roles, bots, clock=None, seed=1, **rules):
    """Fixed roles for players "1", "2", …; the players in `bots` (ids) are bots."""
    players = [{"id": str(i), "name": f"P{i}", **({"bot": True, "emoji": "🦊"} if str(i) in bots else {})}
               for i in range(1, len(roles) + 1)]
    st = {"kind": "werwolf", "rules": {**ww.DEFAULTS, **rules}, "players": players, "phase": "lobby"}
    t = ww.Table(st, random.Random(seed), now=clock or Clock())
    t.begin()
    st["roles"] = {str(i): x for i, x in enumerate(roles, 1)}
    return t


def test_bots_act_in_every_night_step_after_thinking():
    c = Clock()
    # people: 1 (villager), 8 (wolf) – the rest are bots
    t = bot_table(["villager", "hunter", "amor", "wolf", "seer", "witch", "villager", "wolf"], {"2", "3", "4", "5", "6", "7"}, c)
    assert not t.tick()                                          # roles: the leader lets the night fall
    t.advance()
    assert t.st["step"] == "amor"
    wait = t.bot_wait()
    assert ww.BOT_NIGHT <= wait < ww.BOT_NIGHT + ww.BOT_NIGHT_SPREAD
    c.t += wait - 0.5
    assert not t.tick() and t.st["lovers"] is None              # still thinking
    c.t += 0.5
    assert t.tick()
    lv = t.st["lovers"]
    assert len(lv) == 2 and lv[0] != lv[1] and t.st["step"] == "wolves"
    # the bot wolf first chooses at random – then follows the human wolf
    c.t += t.bot_wait()
    t.tick()
    first = t.st["wolf_votes"]["4"]
    assert t.role(first) != "wolf" and t.st["step"] == "wolves"
    other = next(p for p in t.living() if t.role(p) != "wolf" and p != first)
    t.act("8", "bite", other)
    assert t.st["step"] == "wolves"
    assert t.tick() and t.st["victim"] == other and t.st["step"] == "seer"
    # the seer looks and closes her eyes, the witch decides
    c.t += t.bot_wait()
    assert t.tick() and t.st["looked"] and len(t.st["seen"]) == 1 and t.st["seen"][0]["id"] != "5"
    assert t.st["step"] == "witch"
    c.t += t.bot_wait()
    assert t.tick() and t.st["phase"] in ("day", "hunter", "done")


def test_bot_wolves_agree_and_bot_hunter_shoots_and_bots_vote():
    c = Clock()
    t = bot_table(["villager", "villager", "wolf", "wolf", "hunter", "villager"], {"3", "4", "5", "6"}, c, auto=False,
                  wolves=2, seer=False, witch=False, hunter=True, amor=False)
    t.advance()
    assert t.st["step"] == "wolves"
    c.t += t.bot_wait()
    assert t.tick()
    assert t.st["phase"] in ("day", "hunter") and t.st["night"] == 1 and len(t.st["dead"]) >= 1
    v = t.st["deaths"][0]["id"]
    assert t.role(v) != "wolf"
    # the day: the talk timer opens the vote, the bots vote one after the other
    if t.st["phase"] == "hunter":                                # the hunter (a bot) was bitten: he shoots
        c.t += t.bot_wait()
        assert t.tick() and t.st["phase"] in ("day", "done")
    if t.st["phase"] == "done":
        return
    c.t += 180
    assert t.tick() and t.st["phase"] == "vote"
    assert t.st["votes"] == {}
    c.t += ww.BOT_VOTE
    t.tick()
    assert len(t.st["votes"]) == 1
    c.t += ww.BOT_STAGGER * 4
    t.tick()
    bots = [p for p in t.living() if t.is_bot(p)]
    assert all(p in t.st["votes"] for p in bots)
    for b in bots:
        target = t.st["votes"][b]
        assert target != b and t.alive(target)
        if t.role(b) == "wolf":
            assert t.role(target) != "wolf"
    for p in t.living():
        if not t.is_bot(p):
            t.act(p, "vote", "")
    assert t.st["phase"] in ("verdict", "hunter", "done")


def test_bot_seer_witch_hunter_and_the_seer_votes_for_the_wolf():
    c = Clock()
    t = bot_table(["wolf", "villager", "seer", "witch", "hunter", "villager"], {"3", "4", "5", "6"}, c, seed=3)
    t.advance()
    assert t.st["step"] == "wolves" and t.actors() == ["1"]
    c.t += 60
    assert not t.tick()                                          # a person's step: the bots do not move it on
    t.act("1", "bite", "5")                                      # the hunter (a bot)
    assert t.st["step"] == "seer"
    c.t += t.bot_wait()
    assert t.tick() and t.st["step"] == "witch" and t.st["seen"][0]["id"] in ("1", "2", "4", "5", "6")
    t.st["potions"]["heal"] = False                              # no healing left: the hunter dies
    c.t += t.bot_wait()
    assert t.tick() and t.st["phase"] == "hunter" and t.st["hunter"] == "5"
    assert t.st["deaths"][0] == {"id": "5", "role": "hunter", "cause": "wolves"}
    c.t += t.bot_wait()
    assert t.tick() and [d["cause"] for d in t.st["deaths"]].count("shot") == 1
    assert t.st["phase"] in ("day", "done")
    # a bot seer that saw a wolf votes for it (mostly)
    hits = 0
    for seed in range(40):
        t2 = bot_table(["villager", "villager", "wolf", "seer", "villager"], {"3", "4", "5"}, Clock(), seed=seed)
        t2.st["seen"] = [{"night": 1, "id": "3", "role": "wolf"}]
        hits += t2._bot_vote("4") == "3"
    assert hits > 25


def play_out(t, c, rng):
    """The leader moves on whenever nobody else can – people act at random, the bots by themselves."""
    for _ in range(400):
        ph = t.st["phase"]
        if ph == "done":
            return
        c.t += 30
        t.tick()
        ph = t.st["phase"]
        if ph == "done":
            return
        people = [p for p in t.actors() if not t.is_bot(p)]
        if ph in ("roles", "day", "verdict"):
            t.advance()
        elif ph == "vote":
            for p in people:
                if p not in t.st["votes"] and t.st["phase"] == "vote":
                    t.act(p, "vote", rng.choice([x for x in t.living() if x != p]))
        elif people:
            t.advance()                                          # a person is idle at night: the leader moves on
    raise AssertionError("the game did not end")


def test_full_games_with_bots_reach_the_end():
    ends = set()
    for seed in range(30):
        c = Clock()
        players = [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}] + [
            {"id": f"bot{i}", "name": f"B{i}", "bot": True} for i in range(1, 4 + seed % 6)]
        st = {"kind": "werwolf", "rules": dict(ww.DEFAULTS), "players": players, "phase": "lobby"}
        t = ww.Table(st, random.Random(seed), now=c)
        t.begin()
        play_out(t, c, random.Random(seed))
        assert st["phase"] == "done" and st["winner"] in ("village", "wolves", "lovers") and st["winners"]
        ends.add(st["winner"])
    assert {"village", "wolves"} <= ends


def test_two_people_begin_with_three_bots_over_the_api(client):
    phd, ids, heads = family(client, 2)
    fq = client.app.state.fq
    c = Clock(5000.0)
    fq.werwolf.now = c
    fq.werwolf.rng = random.Random(7)
    assert client.put("/api/parent/game-rewards", json={"werwolf": [7, 3, 1]}, headers=phd).status_code == 200
    hm, hl = heads[str(ids[0])], heads[str(ids[1])]
    assert client.get("/api/community/werwolf/rules", headers=hm).json()["min_humans"] == 2
    v = client.post("/api/community/werwolf/start", json={"talk": 60}, headers=hm).json()
    assert v["bots"] == 4 and v["min_humans"] == 2 and v["rules"]["fill"] == 5
    v = client.post("/api/community/werwolf/join", headers=hl).json()
    assert v["bots"] == 3 and v["deck"] == ww.preset(5) and len(v["players"]) == 2
    v = client.post("/api/community/werwolf/rules", json={"fill": 99}, headers=hm).json()
    assert v["rules"]["fill"] == 12 and v["bots"] == 10 and v["deck"] == ww.preset(12)
    v = client.post("/api/community/werwolf/rules", json={"fill": 5}, headers=hm).json()
    v = client.post("/api/community/werwolf/begin", headers=hm).json()
    assert v["phase"] == "roles" and len(v["players"]) == 5 and v["bots"] is None
    bots = [p for p in v["players"] if p["bot"]]
    assert len(bots) == 3 and all(p["emoji"] and p["id"].startswith("bot") for p in bots)
    assert len({p["name"] for p in bots}) == 3
    # secrecy: a bot's role is only shown like a person's
    for h in (hm, hl):
        x = get(client, h)
        mine = x["my_role"]
        for p in x["players"]:
            if p["id"] != x["me"]:
                assert p["role"] is None or (mine == "wolf" and p["role"] == "wolf")
    # play it out over the API: every state request moves the bots
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werwolf' AND status!='done'")
    rng = random.Random(3)
    for _ in range(300):
        c.t += 30
        v = get(client, hm)
        if v["phase"] == "done":
            break
        ph = v["phase"]
        mine = {str(ids[0]): v, str(ids[1]): get(client, hl)}
        acted = False
        for pid, x in mine.items():
            if x["my_turn"] and ph == "vote":
                live = [p["id"] for p in x["players"] if p["alive"] and p["id"] != pid]
                act(client, heads[pid], action="vote", target=rng.choice(live))
                acted = True
        if ph in ("roles", "day", "verdict") or (ph in ("night", "hunter") and any(x["my_turn"] for x in mine.values())):
            client.post("/api/community/werwolf/next", headers=hm)
        elif ph == "vote" and not acted and v["voted"] is not None and len(v["voted"]) == len([p for p in v["players"] if p["alive"]]):
            raise AssertionError("the vote should have closed")
    v = get(client, hm)
    assert v["phase"] == "done" and v["winner"]
    s = json.loads(fq.db.q1("SELECT state FROM card_game WHERE id=?", row["id"])["state"])
    assert all(not p.startswith("bot") for p in s["coins"])                         # bots never get coins
    assert fq.db.val("SELECT COUNT(*) FROM history WHERE kind='werwolf'") == 2      # only the two people
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'werwolf:%bot%'") == 0
