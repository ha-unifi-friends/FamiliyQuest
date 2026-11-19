"""«Beat the Bureaucracy» (stempeljagd.py) – setup and modes, turn order, the entry scenes (appointment → booked out →
argue → call → audience; the queue → wait or cheat), referrals and ping-pong, stamps and documents, trick cards with
the inspector's risk, objections, the counters' opening hours and the commission, events, mini-games, the
administration, the win at N stamps, bots, the table in the app (coins once, history, records, guests, battery,
rules, running games)."""
import json
import random

import pytest

from familyquest import stempeljagd as sj
from familyquest.community import CommunityError

pytestmark = pytest.mark.dev_channel        # a dev game (channel.py DEV_GAMES): only in «Family Quest Dev»


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Rng(random.Random):
    """random() returns the given numbers first (then seeded random)."""

    def __init__(self, seq=(), seed=1):
        super().__init__(seed)
        self.seq = list(seq)

    def random(self):
        return self.seq.pop(0) if self.seq else super().random()

    def _randbelow(self, n):                    # choice / sample / randint do not use the given numbers
        return self._randbelow_with_getrandbits(n)


@pytest.fixture(autouse=True)
def _no_random_events(monkeypatch):
    monkeypatch.setattr(sj, "EVENT_CHANCE", 0.0)       # events only where a test asks for them


def table(n=2, bots=0, seq=(), mode="teams", admin=None, **rules):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, n + 1)]
    players += [{"id": f"bot{i}", "name": f"B{i}", "bot": True, "level": "normal"} for i in range(1, bots + 1)]
    st = {"kind": "stempeljagd", "rules": {**sj.DEFAULTS, "bot_ms": 0, "projects": "random", "mode": mode, **rules},
          "players": players, "phase": "lobby"}
    if admin:
        st["admin_id"] = admin
    clock = Clock()
    t = sj.Table(st, Rng(), now=clock)
    t.setup()
    t.rng.seq = list(seq)                         # the given numbers count from the first move on
    return t, clock


def at_desk(t, pid, counter, scene="free", mood="cheerful"):
    """pid goes to a desk with the given scene (visited before unless the scene is the first contact)."""
    tm = t.team(pid)
    if scene != "first" and counter not in tm["visited"]:
        tm["visited"].append(counter)
    t.st["scenes"][counter] = {"kind": "free" if scene == "first" else scene, "mood": mood, "queue": 12, "shown": 3}
    t.go(pid, counter)


def force_card(t, monkeypatch, card):
    monkeypatch.setattr(t, "_deck", lambda c: [card])


# ---------------------------------------------------------------- setup, modes, turn order
def test_setup_projects_tricks_and_order():
    t, _ = table(3)
    assert t.st["phase"] == "play" and t.st["turn"] == "1" and t.st["stage"] == "go" and t.target == 7
    assert len({t.team(p)["project"] for p in "123"}) == 3
    for p in "123":
        tm = t.team(p)
        assert len(tm["tricks"]) == 2 and tm["mayor"] and tm["stamps"] == [] and set(tm["tricks"]) <= set(sj.TRICKS)
    assert {sj.Table(dict(t.st, rules={**t.r, "length": k}), now=lambda: 0).target for k in sj.LENGTHS} == {5, 7, 9}


def test_pick_projects_unique_then_play():
    players = [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}, {"id": "bot1", "name": "C", "bot": True}]
    st = {"kind": "stempeljagd", "rules": {**sj.DEFAULTS, "bot_ms": 0}, "players": players, "phase": "lobby"}
    t = sj.Table(st, Rng(), now=Clock())
    t.setup()
    assert st["phase"] == "projects" and st["teams"]["bot1"]["project"]          # the bot chose at once
    taken = st["teams"]["bot1"]["project"]
    with pytest.raises(CommunityError):
        t.pick_project("1", taken)
    with pytest.raises(CommunityError):
        t.pick_project("1", "castle")
    free = [k for k in sj.PROJECTS if k != taken]
    t.pick_project("1", free[0])
    assert st["phase"] == "projects"
    t.pick_project("2", free[1])
    assert st["phase"] == "play" and st["turn"] == "1"


def test_turn_order_rounds_and_only_own_turn():
    t, _ = table(3)
    with pytest.raises(CommunityError):
        t.go("2", "coffee")
    for p in "123":
        assert t.st["turn"] == p
        t.go(p, "coffee")
        with pytest.raises(CommunityError):
            t.go(p, "coffee")                                 # one visit per turn
        t.end_turn(p)
    assert t.st["turn"] == "1" and t.st["round"] == 2


# ---------------------------------------------------------------- the entry scenes
def test_first_contact_appointment_booked_argue_call_audience(monkeypatch):
    t, _ = table(2, seq=[0.0])                       # the argument works
    force_card(t, monkeypatch, "i_yes")
    at_desk(t, "1", "info", scene="first", mood="cheerful")
    assert t.st["stage"] == "appt" and t.st["cur"]["scene"] == "appt"
    t.team("1")["tricks"] = []
    with pytest.raises(CommunityError):
        t.appt("1", True)                            # «Yes» only with an appointment card
    t.appt("1", False)
    assert t.st["stage"] == "argue" and t.team("1")["stats"]["booked"] == 1
    assert t.argue_chance("1", "polite") == pytest.approx(0.8)          # a cheerful clerk likes politeness
    with pytest.raises(CommunityError):
        t.argue("1", "croissant")                    # no croissants in the hand
    t.argue("1", "polite")
    kinds = [e["kind"] for e in t.st["log"]]
    assert "call" in kinds and "booked" in kinds
    assert t.st["stage"] == "done" and t.st["cur"]["result"] == "stamp" and len(t.team("1")["stamps"]) == 1
    assert t.st["display"]["c"] == "info" and t.st["display"]["n"] == t.st["ticket"]


def test_appointment_card_and_failed_argument():
    t, _ = table(2, seq=[0.99])
    t.team("1")["tricks"] = ["appointment"]
    at_desk(t, "1", "green", scene="first")
    t.appt("1", True)
    assert t.st["stage"] in ("done", "mini", "card") and "appointment" not in t.team("1")["tricks"]
    t2, _ = table(2, seq=[0.99])
    at_desk(t2, "1", "green", scene="appt", mood="grumpy")
    t2.appt("1", False)
    t2.argue("1", "urgent")
    assert t2.st["stage"] == "done" and t2.st["cur"]["result"] == "no_audience" and not t2.team("1")["stamps"]


def test_croissants_open_the_door_and_draw_the_better_card(monkeypatch):
    t, _ = table(2, seq=[0.0])
    t.team("1")["tricks"] = ["croissant"]
    cards = iter(["b_lunch", "b_received"])
    monkeypatch.setattr(t.rng, "choice", lambda seq: next(cards) if seq and seq[0].startswith("b_") else seq[0])
    t.st["round"] = 2                                # Tuesday: the building office is open
    at_desk(t, "1", "building", scene="appt")
    t.appt("1", False)
    t.argue("1", "croissant")
    assert t.st["cur"]["card"] == "b_received" and t.team("1")["stats"]["croissants"] == 1


def test_queue_wait_served_or_place_kept():
    t, _ = table(2, seq=[0.1])
    at_desk(t, "1", "info", scene="queue")
    assert t.st["stage"] == "queue" and len(t.st["cur"]["cheats"]) == 3
    t.queue("1", "wait")
    assert t.st["stage"] in ("done", "card", "mini")
    t2, _ = table(2, seq=[0.9])
    at_desk(t2, "1", "info", scene="queue")
    t2.queue("1", "wait")
    tm = t2.team("1")
    assert t2.st["cur"]["result"] == "held" and tm["held"] == "info" and tm["sent_to"] == "info"
    t2.end_turn("1")
    t2.go("2", "coffee")
    t2.end_turn("2")
    assert t2.allowed("1") == ["info"]
    t2.go("1", "info")                                 # the place was kept: no scene, straight to the audience
    assert t2.st["cur"]["scene"] == "free" and t2.st["stage"] != "queue"


@pytest.mark.parametrize("how,conseq", [("toilet", "end"), ("signature", "complain"), ("delivery", "close")])
def test_queue_cheats_caught(how, conseq):
    t, _ = table(2, seq=[0.999])
    t.team("1")["relations"] = 2
    at_desk(t, "1", "green", scene="queue")
    t.st["cur"]["cheats"] = [how, "folder", "stroller"]
    t.queue("1", how)
    assert t.st["cur"]["result"] == "caught" and t.st["cur"]["conseq"] == conseq
    if conseq == "complain":
        assert t.team("1")["relations"] == 1
    if conseq == "close":
        assert t.closed("green") == "lunch"
    t.end_turn("1")
    if conseq == "close":
        with pytest.raises(CommunityError):
            t.go("2", "green")


def test_queue_cheat_works():
    t, _ = table(2, seq=[0.0])
    at_desk(t, "1", "info", scene="queue")
    t.st["cur"]["cheats"] = ["toilet", "folder", "stroller"]
    with pytest.raises(CommunityError):
        t.queue("1", "delivery")                       # not offered this time
    with pytest.raises(CommunityError):
        t.queue("1", "folder")                         # the folder is empty
    t.queue("1", "toilet")
    assert t.st["stage"] != "queue" and t.st["display"]["c"] == "info"


# ---------------------------------------------------------------- authority cards
def test_referral_ping_pong_and_connections(monkeypatch):
    t, _ = table(2)
    force_card(t, monkeypatch, "i_refer4")
    t.team("1")["tricks"] = []
    at_desk(t, "1", "info")
    tm = t.team("1")
    assert t.st["cur"]["result"] == "refer" and tm["sent_to"] == "slow" and tm["stats"]["referrals"] == 1
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    assert t.allowed("1") == ["slow"]
    with pytest.raises(CommunityError):
        t.go("1", "info")
    t.st["round"] = 3                                   # the commission meets: cards
    force_card(t, monkeypatch, "s_refer1")
    at_desk(t, "1", "slow")
    assert tm["sent_to"] == "info" and tm["stats"]["pingpong"] == 1 and tm["stats"]["ref_to"] == {"slow": 1, "info": 1}
    # 🤝 connections cancels a referral: another card of the same counter
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    tm["tricks"] = ["connections"]
    monkeypatch.setattr(t, "_deck", lambda c: ["i_refer2", "i_yes"])
    monkeypatch.setattr(t.rng, "choice", lambda seq: seq[0])
    at_desk(t, "1", "info")
    assert t.st["stage"] == "card"
    t.react("1", True)
    assert t.st["cur"]["card"] == "i_yes" and len(tm["stamps"]) == 1 and "connections" not in tm["tricks"]


def test_documents_missing_archive_hand_in(monkeypatch):
    t, _ = table(2, seq=[0.9, 0.9])
    t.st["round"] = 2
    force_card(t, monkeypatch, "b_b12")
    t.team("1")["tricks"] = []
    at_desk(t, "1", "building")
    tm = t.team("1")
    assert t.st["cur"]["result"] == "missing" and tm["todo"] == "b12"
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    t.go("1", "archive")                               # 0.9: no form for the form
    assert tm["folder"] == ["b12"]
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    at_desk(t, "1", "green")
    assert t.st["cur"]["result"] == "handed" and tm["todo"] is None and len(tm["stamps"]) == 1 and tm["folder"] == []


def test_complete_folder_and_friendly(monkeypatch):
    t, _ = table(2)
    t.st["round"] = 2
    tm = t.team("1")
    tm["tricks"] = ["folder", "friendly"]
    force_card(t, monkeypatch, "b_copy")
    at_desk(t, "1", "building")
    assert t.st["cur"]["result"] == "folder" and len(tm["stamps"]) == 1 and tm["todo"] is None
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    force_card(t, monkeypatch, "g_lunch")
    at_desk(t, "1", "green")
    assert t.st["cur"]["result"] == "friendly" and len(tm["stamps"]) == 2 and tm["skip"] == 0 and tm["tricks"] == []


def test_lunch_skips_the_next_turn(monkeypatch):
    t, _ = table(2)
    t.team("1")["tricks"] = []
    force_card(t, monkeypatch, "g_lunch")
    at_desk(t, "1", "green")
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    assert t.st["turn"] == "2" and t.st["round"] == 2 and t.team("1")["skip"] == 0     # player 1 had lunch


def test_building_office_hours_and_commission():
    t, _ = table(2)
    assert t.weekday() == 0
    t.st["moon0"] = 3
    assert t.closed("building") == "hours" and not t.building_open()
    with pytest.raises(CommunityError):
        t.go("1", "building")
    t.st["round"] = 2
    assert t.building_open()                            # Tuesday
    t.st["round"] = 6                                    # a Monday … at new moon
    assert t.weekday() == 0 and t.moon() == 0 and t.building_open()
    # the commission: between the meetings the application goes on the pile; the meeting decides
    t.st["round"] = 1
    at_desk(t, "1", "slow")
    assert t.st["cur"]["result"] == "pile" and t.team("1")["pending"] == 1
    t.st["round"] = 3
    t.rng.seq = [0.1]
    t._new_round()
    assert t.team("1")["pending"] == 0 and len(t.team("1")["stamps"]) == 1


def test_coffee_kitchen_trick_rumour_relations():
    t, _ = table(2)
    t.team("1")["tricks"] = []
    t.go("1", "coffee")
    tm = t.team("1")
    assert tm["relations"] == 1 and len(tm["tricks"]) == 1 and t.st["cur"]["rumour"] in sj.RUMOURS


# ---------------------------------------------------------------- trick cards
def test_gift_and_the_inspector():
    t, _ = table(2, seq=[0.9])                       # not caught
    t.team("1")["tricks"] = ["gift"]
    t.play("1", "gift")
    assert len(t.team("1")["stamps"]) == 2 and t.st["stage"] == "done"
    t2, _ = table(2, seq=[0.1])                      # caught by the order inspector
    tm = t2.team("1")
    tm["tricks"] = ["gift"]
    tm["stamps"] = [{"o": "info", "r": 1}, {"o": "info", "r": 1}]
    t2.play("1", "gift")
    assert len(tm["stamps"]) == 1 and tm["fines"] == 1 and tm["sent_to"] == "info" and tm["stats"]["caught"] == 1
    assert t2.st["last"]["kind"] == "inspector"
    with pytest.raises(CommunityError):
        t2.play("1", "gift")                          # no gift left (and the turn is used)


def test_mayor_once_per_game():
    t, _ = table(2)
    tm = t.team("1")
    tm.update(sent_to="slow", todo="map")
    t.play("1", "mayor")
    assert len(tm["stamps"]) == 1 and tm["sent_to"] is None and tm["todo"] is None and not tm["mayor"]
    assert t.st["stage"] == "go"                        # the turn goes on
    with pytest.raises(CommunityError):
        t.play("1", "mayor")


def test_objection_defences(monkeypatch):
    t, _ = table(3, seq=[0.99])
    t.team("1")["tricks"] = ["objection"]
    with pytest.raises(CommunityError):
        t.play("1", "objection", "2")                 # Team 2 has no stamp yet
    t.team("2")["stamps"] = [{"o": "info", "r": 1}]
    with pytest.raises(CommunityError):
        t.play("1", "objection", "1")
    t.play("1", "objection", "2")
    assert t.st["stage"] == "objection" and t.actor() == "2"
    with pytest.raises(CommunityError):
        t.defend("1", "compromise")                   # only the team objected to answers
    with pytest.raises(CommunityError):
        t.defend("2", "report")                       # no document for an expert report
    t.defend("2", "signatures")                       # 0.99: the neighbours do not sign
    assert t.team("2")["stamps"] == [] and t.team("1")["stats"]["objections_won"] == 1
    assert t.st["stage"] == "done" and t.actor() == "1"
    # an expert report always works; a compromise changes the project
    t3, _ = table(2, seq=[0.0])
    t3.team("1")["tricks"] = ["objection", "objection"]
    t3.team("2").update(stamps=[{"o": "info", "r": 1}], folder=["map"])
    t3.play("1", "objection", "2")
    t3.defend("2", "report")
    assert len(t3.team("2")["stamps"]) == 1 and t3.team("2")["folder"] == []


def test_objection_compromise_changes_the_project():
    t, _ = table(2, seq=[0.1])
    t.team("1")["tricks"] = ["objection"]
    t.team("2")["stamps"] = [{"o": "info", "r": 1}]
    t.play("1", "objection", "2")
    t.defend("2", "compromise")
    assert len(t.team("2")["stamps"]) == 1 and t.team("2")["compromise"] == t.team("2")["project"]


# ---------------------------------------------------------------- events and mini-games
def test_events_regulation_migration_openday(monkeypatch):
    t, _ = table(2)
    t.team("1")["folder"] = ["map"]
    monkeypatch.setattr(sj, "EVENT_CHANCE", 1.0)
    monkeypatch.setattr(t.rng, "choice", lambda seq: "regulation" if "regulation" in seq else seq[0])
    t.st["round"] = 2
    t._new_round()
    assert t.event() == "regulation" and t.team("1")["folder"] == []
    monkeypatch.setattr(t.rng, "choice", lambda seq: "migration" if "migration" in seq else seq[0])
    t.st["round"] = 4
    t._new_round()
    assert t.event() == "migration"
    force_card(t, monkeypatch, "i_yes")
    at_desk(t, "1", "info")
    assert t.team("1")["stamps"] == [] and t.team("1")["stats"]["computer_no"] == 1
    t.end_turn("1")
    monkeypatch.setattr(t.rng, "choice", lambda seq: "openday" if "openday" in seq else seq[0])
    t.st["round"] = 5
    t.st["closed"] = ["green"]
    t._new_round()
    assert t.event() == "openday" and t.closed("building") is None and t.closed("green") is None
    assert all(s["kind"] == "free" for s in t.st["scenes"].values())


def test_minigames_form_stamp_speak(monkeypatch):
    t, clock = table(2)
    force_card(t, monkeypatch, "g_leaves")
    at_desk(t, "1", "green")
    m = t.st["cur"]["mini"]
    assert t.st["stage"] == "mini" and m["game"] == "form" and len(m["boxes"]) == 3
    with pytest.raises(CommunityError):
        t.mini("2", {"ticked": 3})
    t.mini("1", {"ticked": 3})
    assert t.st["cur"]["result"] == "mini_ok" and len(t.team("1")["stamps"]) == 1
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    # stamping: the server knows where the marker is
    t.st["round"] = 2
    force_card(t, monkeypatch, "b_selfstamp")
    at_desk(t, "1", "building")
    m = t.st["cur"]["mini"]
    target = m["start"] + m["center"] * m["period"] + sj.LATENCY
    clock.t = target
    t.mini("1", {})
    assert t.st["cur"]["result"] == "mini_ok"
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    force_card(t, monkeypatch, "i_speak")
    at_desk(t, "1", "info")
    m = t.st["cur"]["mini"]
    wrong = next(i for i, o in enumerate(m["options"]) if o != m["item"])
    t.mini("1", {"answer": wrong})
    assert t.st["cur"]["result"] == "mini_no" and len(t.team("1")["stamps"]) == 2


def test_minigame_runs_out_and_off_rule(monkeypatch):
    t, clock = table(2)
    force_card(t, monkeypatch, "i_speak")
    at_desk(t, "1", "info")
    clock.t += sj.MINI_SECONDS["speak"] + sj.MINI_GRACE + 1
    assert t.tick() and t.st["cur"]["result"] == "mini_no"
    t2, _ = table(2, minigames=False)
    force_card(t2, monkeypatch, "i_speak")
    at_desk(t2, "1", "info")
    assert t2.st["stage"] == "done" and t2.st["cur"]["mini"]["auto"]


# ---------------------------------------------------------------- the administration
def test_admin_mode_cards_toggle_and_defences():
    t, _ = table(3, mode="admin", admin="3")
    assert t.builders() == ["1", "2"] and "3" not in t.st["teams"] and len(t.st["admin_hand"]) == 3
    t.go("1", "coffee")
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    assert t.st["turn"] == "3" and t.st["stage"] == "admin"
    t.st["admin_hand"] = ["a_lunch", "a_form", "a_refer"]
    t.team("1")["tricks"] = []
    with pytest.raises(CommunityError):
        t.admin_card("3", 0, "3")                     # not on itself
    t.admin_card("3", 0, "1")
    assert len(t.st["admin_hand"]) == 3 and t.st["turn"] == "2" and t.st["log"][-1]["kind"] == "skipped"   # 1 has lunch
    t.go("2", "coffee")
    t.end_turn("2")
    t.st["admin_hand"] = ["a_form", "a_refer", "a_regulation"]
    t.admin_toggle("3", "green")
    assert t.closed("green") == "admin"
    t.go("1", "coffee")
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    t.team("2")["tricks"] = ["connections"]
    t.admin_card("3", 1, "2")                          # 🤝 blocks the referral
    assert t.st["last"]["blocked"] == "connections" and t.team("2")["sent_to"] is None
    t.go("1", "coffee")
    t.end_turn("1")
    t.go("2", "coffee")
    t.end_turn("2")
    t.admin_card("3", 0, "1")                          # an absurd form to fill first
    assert t.st["turn"] == "1" and t.st["stage"] == "mini" and t.st["cur"]["mini"]["why"] == "admin"
    t.mini("1", {"ticked": 3})
    assert t.st["stage"] == "go"


def test_admin_wins_after_the_rounds():
    t, _ = table(2, mode="admin", admin="2", length="short")
    for _ in range(sj.ADMIN_ROUNDS["short"]):
        t.go("1", "coffee")
        t.end_turn("1")
        if t.st["phase"] == "done":
            break
        t.admin_toggle("2", "info") if "info" not in t.st["closed"] else t.admin_toggle("2", "info")
    assert t.st["phase"] == "done" and t.st["admin_won"] and t.st["places"] == {"2": 1, "1": 2}


def test_win_at_n_stamps_and_moments(monkeypatch):
    t, _ = table(3, length="short")
    tm = t.team("2")
    tm["stats"] = {"ref_to": {"slow": 6}, "lunch": 2}
    t.team("1")["stamps"] = [{"o": "info", "r": 1}] * 4
    force_card(t, monkeypatch, "i_yes")
    at_desk(t, "1", "info")
    assert t.st["phase"] == "done" and t.st["winner"] == "1" and t.st["complete"] and t.st["places"]["1"] == 1
    assert {"k": "ref_to", "p": "2", "n": 6, "c": "slow"} in t.st["moments"]


@pytest.mark.parametrize("mode,length,level", [("teams", "short", "easy"), ("teams", "normal", "hard"), ("admin", "short", "normal")])
def test_bots_finish_games(mode, length, level, monkeypatch):
    monkeypatch.setattr(sj, "EVENT_CHANCE", 0.3)          # with the events as in the real game
    for seed in range(12):
        players = [{"id": f"bot{i}", "name": "B", "bot": True, "level": level} for i in range(1, 4)]
        st = {"kind": "stempeljagd", "rules": {**sj.DEFAULTS, "bot_ms": 0, "mode": mode, "length": length}, "players": players,
              "phase": "lobby", "admin_id": "bot3" if mode == "admin" else None}
        t = sj.Table(st, random.Random(seed), now=Clock())
        t.setup()
        t.tick()
        assert st["phase"] == "done" and st["complete"] and st["ranking"]


def test_bots_wait_for_their_reaction_time():
    players = [{"id": "1", "name": "P"}, {"id": "bot1", "name": "B", "bot": True, "level": "normal"}]
    st = {"kind": "stempeljagd", "rules": {**sj.DEFAULTS, "bot_ms": 2000, "projects": "random"}, "players": players, "phase": "lobby"}
    clock = Clock()
    t = sj.Table(st, random.Random(2), now=clock)
    t.setup()
    t.go("1", "coffee")
    t.end_turn("1")
    assert st["turn"] == "bot1" and not t.tick()
    clock.t += 2.1
    assert t.tick()


# ---------------------------------------------------------------- the table in the app
def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _force(fq, gid, fn):
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    s = json.loads(row["state"])
    fn(s)
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), gid)


def test_rules_cleaned_and_remembered(fq, kid):
    assert fq.stempeljagd.clean_rules("stempeljagd", {"bots": 9, "level": "x", "bot_ms": 99999, "length": "huge", "mode": "x",
                                                      "admin": "<b>", "minigames": 0, "projects": "?"}) == \
        {"bots": 3, "level": "normal", "bot_ms": 5000, "length": "normal", "mode": "teams", "admin": "bot", "minigames": False,
         "projects": "pick"}
    fq.stempeljagd.start("stempeljagd", kid, {"bots": 0, "level": "hard", "length": "long", "projects": "random"}, solo=True)
    r = fq.stempeljagd.default_rules()
    assert r["level"] == "hard" and r["length"] == "long"
    st = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='stempeljagd'")["state"])
    assert len(st["players"]) == 2 and st["phase"] == "play"                              # alone: at least one bot


def test_solo_against_bots_plays_to_the_end_without_coins(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    st = client.post("/api/community/stempeljagd/start", json={"solo": True, "bots": 2, "bot_ms": 0, "length": "short",
                                                              "projects": "random", "minigames": False}, headers=hm).json()
    assert st["solo"] and st["phase"] == "play" and len(st["players"]) == 3 and not st["coins_on"] and st["target"] == 5
    act = lambda **b: client.post("/api/community/stempeljagd/act", json=b, headers=hm).json()    # noqa: E731
    for _ in range(800):
        if st["phase"] == "done":
            break
        if not st["my_turn"]:
            st = client.get("/api/community/stempeljagd", headers=hm).json()
            continue
        s = st["stage"]
        if s == "go":
            st = act(action="go", counter=st["mine"]["allowed"][0] if len(st["mine"]["allowed"]) == 1 else "info")
        elif s == "appt":
            st = act(action="appt", yes=False)
        elif s == "argue":
            st = act(action="argue", key="polite")
        elif s == "queue":
            st = act(action="queue", key="wait")
        elif s == "card":
            st = act(action="react", use=True)
        elif s == "objection":
            st = act(action="defend", key="compromise")
        elif s == "mini":
            st = act(action="mini", ticked=3, answer=0)
        else:
            st = act(action="end_turn")
    assert st["phase"] == "done" and st["complete"] and all(p["coins"] == 0 for p in st["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'stempeljagd:%'")
    hist = fq.community.history(mia)
    assert hist[0]["kind"] == "stempeljagd" and hist[0]["data"]["target"] == 5


def test_family_table_coins_once_history_records_and_restart(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    assert client.get("/api/parent/game-rewards", headers=phd).json()["stempeljagd"] == [10, 5, 2]
    hm, hl = login(client, mia, "1111"), login(client, leo)
    st = client.post("/api/community/stempeljagd/start", json={"bots": 0, "bot_ms": 0, "projects": "pick"}, headers=hm).json()
    assert st["phase"] == "lobby" and not st["coins_on"]
    act = lambda h, **b: client.post("/api/community/stempeljagd/act", json=b, headers=h)      # noqa: E731
    assert act(hm, action="go", counter="coffee").status_code == 400                        # not started
    assert client.post("/api/community/stempeljagd/join", headers=hl).json()["coins_on"]
    assert client.post("/api/community/stempeljagd/begin", headers=hl).status_code == 403
    st = client.post("/api/community/stempeljagd/begin", headers=hm).json()
    assert st["phase"] == "projects"
    act(hm, action="project", key="pizza")
    assert act(hl, action="project", key="pizza").status_code == 400
    st = act(hl, action="project", key="slide").json()
    assert st["phase"] == "play" and st["turn"] == str(mia) and st["my_turn"] is False
    assert act(hl, action="go", counter="coffee").status_code == 400                         # not Leo's turn
    assert act(hm, action="nonsense").status_code == 400
    assert act(hm, action="go", counter="x" * 30).status_code == 422
    v = act(hm, action="go", counter="coffee").json()
    assert v["cur"]["result"] == "coffee" and v["stage"] == "done"
    gid = v["game"]
    # Leo cannot see Mia's trick cards
    lv = client.get("/api/community/stempeljagd", headers=hl).json()
    assert isinstance(lv["players"][0]["tricks"], int) and "tricks" in lv["mine"] and "hand" not in lv["mine"]
    act(hm, action="end_turn")
    # restart: a new object on the same database goes on
    from familyquest.stempeljagd import Stempeljagd
    assert Stempeljagd(fq.db, fq.community.add_history, fq.rewards).state("stempeljagd", leo)["turn"] == str(leo)
    # Leo's referrals – Mia gets the last stamp
    _force(fq, gid, lambda s: s["teams"][str(leo)]["stats"].update(referrals=6, ref_to={"slow": 6}))
    _force(fq, gid, lambda s: s["teams"][str(mia)].update(stamps=[{"o": "info", "r": 1}] * 6, tricks=["gift"]))
    act(hl, action="go", counter="coffee")
    act(hl, action="end_turn")
    fq.stempeljagd.rng = Rng([0.99])                                                    # the inspector is elsewhere
    v = act(hm, action="play", trick="gift").json()
    fq.stempeljagd.rng = None
    assert v["phase"] == "done" and v["complete"] and v["winner"] == str(mia)
    assert {p["id"]: (p["place"], p["coins"]) for p in v["players"]} == {str(mia): (1, 10), str(leo): (2, 5)}
    assert any(m["k"] == "ref_to" and m["p"] == str(leo) for m in v["moments"])
    before = fq.rewards.balance(mia, "coins")
    row = fq.db.q1("SELECT * FROM card_game WHERE id=?", gid)
    fq.stempeljagd._save(row, json.loads(row["state"]))                                 # paid once
    client.get("/api/community/stempeljagd", headers=hm)
    assert fq.rewards.balance(mia, "coins") == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE ?", f"stempeljagd:{gid}:%") == 2
    hist = fq.community.history(leo)
    assert hist[0]["kind"] == "stempeljagd" and hist[0]["data"]["referrals"] == 6 and hist[0]["data"]["place"] == 2
    assert fq.community.history(mia)[0]["data"]["seconds"] is not None
    # records for the facts quiz
    from familyquest import facts
    gens = {q["gen"] for q in facts.Facts(fq).games()}
    assert "stempeljagd_referrals" in gens and "stempeljagd_fastest" in gens


def test_ended_by_the_leader_without_coins_and_running_list(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/stempeljagd/start", json={"bots": 1, "bot_ms": 5000, "projects": "random"}, headers=hm)
    client.post("/api/community/stempeljagd/join", headers=hl)
    st = client.post("/api/community/stempeljagd/begin", headers=hm).json()
    assert len(st["players"]) == 3 and st["players"][2]["bot"]
    games = client.get("/api/parent/games/running", headers=ph).json()
    g = next(x for x in games if x["game"] == "stempeljagd")
    assert g["title"] == "Beat the Bureaucracy" and g["icon"] == "🏛️"
    assert client.post("/api/community/stempeljagd/end", headers=hl).status_code == 403
    assert client.post("/api/community/stempeljagd/nudge", headers=hl).status_code == 403
    v = client.post("/api/community/stempeljagd/nudge", headers=hm).json()            # Mia's step done like a bot
    assert v["phase"] == "play"
    v = client.post("/api/community/stempeljagd/end", headers=hm).json()
    assert v["phase"] == "done" and not v["complete"] and all(p["coins"] == 0 for p in v["players"])
    assert not fq.db.q1("SELECT id FROM ledger WHERE ref LIKE 'stempeljagd:%'")


def test_admin_mode_over_the_api(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/stempeljagd/start", json={"bots": 0, "bot_ms": 0, "mode": "admin", "admin": "host", "projects": "random"}, headers=hm)
    client.post("/api/community/stempeljagd/join", headers=hl)
    assert client.post("/api/community/stempeljagd/admin", json={"who": str(leo)}, headers=hl).status_code == 403
    assert client.post("/api/community/stempeljagd/admin", json={"who": "nobody"}, headers=hm).status_code == 400
    st = client.post("/api/community/stempeljagd/admin", json={"who": str(leo)}, headers=hm).json()
    assert st["rules"]["mode"] == "admin" and st["rules"]["admin"] == str(leo)
    st = client.post("/api/community/stempeljagd/begin", headers=hm).json()
    assert st["admin_id"] == str(leo) and [p["id"] for p in st["players"]] == [str(mia), str(leo)]
    client.post("/api/community/stempeljagd/act", json={"action": "go", "counter": "coffee"}, headers=hm)
    client.post("/api/community/stempeljagd/act", json={"action": "end_turn"}, headers=hm)
    lv = client.get("/api/community/stempeljagd", headers=hl).json()
    assert lv["stage"] == "admin" and lv["my_turn"] and len(lv["mine"]["hand"]) == 3
    v = client.post("/api/community/stempeljagd/act", json={"action": "admin_toggle", "counter": "green"}, headers=hl).json()
    assert v["closed"]["green"] == "admin" and v["turn"] == str(mia)
    # family vs a bot administration
    client.post("/api/community/stempeljagd/end", headers=hm)
    st = client.post("/api/community/stempeljagd/start", json={"solo": True, "bots": 0, "bot_ms": 0, "mode": "admin", "admin": "bot",
                                                              "projects": "random"}, headers=hm).json()
    assert st["admin_id"] == "botadmin" and len(st["players"]) == 2


def test_guests_join_and_play_but_cannot_lead(client):
    from test_api import setup_family
    from familyquest import netfilter
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    client.post("/api/community/stempeljagd/start", json={"bots": 0, "projects": "random"}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "stempeljagd"}, headers=hm).json()["invite"]
    assert client.get("/api/community/guest/info", params={"code": inv["code"]}).json()["title"] == "Beat the Bureaucracy"
    g = client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()
    hg = {"X-FQ-Token": g["token"]}
    for path in ("start", "begin", "end", "nudge", "admin"):
        assert client.post("/api/community/stempeljagd/" + path, json={"who": "bot"}, headers=hg).status_code in (401, 403), path
    st = client.post("/api/community/stempeljagd/begin", headers=hm).json()
    assert [p["guest"] for p in st["players"]] == [False, True] and not st["coins_on"]
    for p in ("", "/join", "/act"):
        assert netfilter.is_guest_path("/api/community/stempeljagd" + p), p
    for p in ("/start", "/begin", "/end", "/rules", "/nudge", "/admin"):
        assert not netfilter.is_guest_path("/api/community/stempeljagd" + p), p


def test_switched_off_and_familytime(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert "stempeljagd" in client.get("/api/me", headers=hm).json()["games_list"]
    from familyquest.familytime import GAMES
    assert "stempeljagd" in GAMES
    assert client.put("/api/parent/games", json={"access": {"stempeljagd": {"mode": "off"}}}, headers=phd).status_code == 200
    assert client.post("/api/community/stempeljagd/start", json={"solo": True}, headers=hm).status_code == 403
    assert client.get("/api/me", headers=hm).json()["community"]["stempeljagd"] is None


@pytest.mark.battery
def test_start_uses_a_battery_segment(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    before = client.get("/api/me", headers=hm).json()["battery"]["charge"]
    assert client.post("/api/community/stempeljagd/start", json={"solo": True, "bot_ms": 5000}, headers=hm).status_code == 200
    assert client.get("/api/me", headers=hm).json()["battery"]["charge"] == before - 1
