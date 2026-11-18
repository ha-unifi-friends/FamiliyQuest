"""FamilyTime games: wishes, a vote, a tie, parents decide, a game bought with coins (familyquest/familytime.py)."""
from datetime import datetime, timedelta

import pytest

from familyquest.community import CommunityError
from test_api import setup_family


def _people(fq):
    papa = fq.db.x("INSERT INTO profile(name, role) VALUES('Papa','parent')")
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    leo = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    get = lambda i: fq.db.q1("SELECT * FROM profile WHERE id=?", i)      # noqa: E731
    return get(papa), get(mia), get(leo)


def _ft(fq, days=3, hour=18):
    d = (datetime.now() + timedelta(days=days)).date().isoformat()
    return fq.calendar.add({"title": "FamilyTime", "kind": "familytime", "start": f"{d}T{hour:02d}:00", "end": f"{d}T{hour + 2:02d}:00"})


def _ev(fq, prof, eid):
    return next(e for e in fq.familytime.state(prof)["events"] if e["id"] == eid)


def _history(fq, pid):
    return [h for h in fq.community.history(pid) if h["kind"] == "familytime"]


def test_wishes_and_a_single_wish_is_set_directly(fq):
    papa, mia, leo = _people(fq)
    eid = _ft(fq)
    ft = fq.familytime
    ev = _ev(fq, mia, eid)
    assert ev["status"] == "wish" and ev["wishes_open"] and ev["can_buy"] and not ev["game"]
    assert fq.familytime.summary(mia)["state"] == "wish"
    ft.wish(mia, eid, game="tschau")
    ft.wish(mia, eid, title="  Monopoly  ")                    # changed: one wish per person
    assert [w["title"] for w in _ev(fq, mia, eid)["wishes"]] == ["Monopoly"]
    assert fq.familytime.summary(mia) is None                   # nothing missing for Mia any more
    ft.wish(leo, eid, title="monopoly")                         # the same board game: one option
    with pytest.raises(CommunityError):
        ft.wish(leo, eid, title="x" * 0)
    with pytest.raises(CommunityError):
        ft.wish(leo, eid, game="nope")
    assert len(_ev(fq, papa, eid)["wishes"]) == 2
    with pytest.raises(CommunityError):
        ft.start_vote(mia, eid)                                 # only parents
    assert ft.start_vote(papa, eid) == "set"                    # one distinct game: set directly
    g = _ev(fq, mia, eid)["game"]
    assert g["title"] == "Monopoly" and g["how"] == "single" and g["by"] == "Mia" and not g["app"]
    with pytest.raises(CommunityError):
        ft.wish(leo, eid, game="jass")                          # wishes closed
    assert _history(fq, leo["id"])[0]["data"]["game"] == "Monopoly"
    assert len(_history(fq, papa["id"])) == 1
    # the game shows in the calendar banner (special times)
    assert fq.calendar.special(mia["id"], hours=24 * 5)[0]["game"]["title"] == "Monopoly"


def test_long_text_is_cut_and_title_kept(fq):
    papa, mia, _ = _people(fq)
    eid = _ft(fq)
    fq.familytime.wish(mia, eid, title="A" * 100)
    assert len(_ev(fq, mia, eid)["wishes"][0]["title"]) == 60


def test_vote_and_tie(fq):
    papa, mia, leo = _people(fq)
    ft = fq.familytime
    eid = _ft(fq)
    ft.wish(mia, eid, game="tschau")
    ft.wish(leo, eid, title="Monopoly")
    with pytest.raises(CommunityError):
        ft.vote(mia, eid, "g:tschau")                           # no vote yet
    assert ft.start_vote(papa, eid) == "vote"
    assert ft.summary(mia)["state"] == "vote"
    ev = _ev(fq, mia, eid)
    assert {o["key"] for o in ev["options"]} == {"g:tschau", "t:monopoly"} and "votes" not in ev["options"][0]
    with pytest.raises(CommunityError):
        ft.vote(mia, eid, "t:uno")                              # only the wishes
    assert ft.vote(mia, eid, "g:tschau")["status"] == "vote"
    assert ft.vote(mia, eid, "t:monopoly")["status"] == "vote"  # changed
    assert ft.vote(leo, eid, "g:tschau")["status"] == "vote"
    assert _ev(fq, papa, eid)["missing"] == ["Papa"]
    with pytest.raises(CommunityError):
        ft.end_vote(mia, eid)                                   # only parents end it
    assert ft.end_vote(papa, eid) == "tie"                      # 1 : 1
    ev = _ev(fq, papa, eid)
    assert ev["status"] == "tie" and all(o["tie"] for o in ev["options"])
    with pytest.raises(CommunityError):
        ft.set_game(mia, eid, choice="g:tschau")                # parents decide
    ft.set_game(papa, eid, random=True)
    g = _ev(fq, mia, eid)["game"]
    assert g["how"] == "random" and g["title"] in ("Tschau Sepp", "Monopoly")


def test_vote_with_a_winner_and_end_by_parent(fq):
    papa, mia, leo = _people(fq)
    ft = fq.familytime
    eid = _ft(fq)
    ft.wish(mia, eid, game="tschau")
    ft.wish(leo, eid, title="Uno")
    ft.wish(papa, eid, game="tschau")
    ft.start_vote(papa, eid)
    ft.vote(mia, eid, "t:uno")
    ft.vote(leo, eid, "t:uno")
    assert ft.end_vote(papa, eid) == "set"
    g = _ev(fq, leo, eid)["game"]
    assert g["title"] == "Uno" and g["how"] == "vote"


def test_auto_close_before_the_event_and_random_at_start(fq):
    papa, mia, leo = _people(fq)
    ft = fq.familytime
    eid = _ft(fq, days=3)
    start = datetime.fromisoformat(_ev(fq, mia, eid)["start"])
    # within 24 h before the start the wish window is closed
    with pytest.raises(CommunityError):
        ft.wish(mia, eid, game="jass", now=start - timedelta(hours=23))
    ft.tick(start - timedelta(hours=23))                       # no wishes: nothing to vote on, the wishes stay closed
    assert not _ev(fq, mia, eid)["wishes_open"] and ft.game_of(eid) is None
    # a later event: wishes, then the clock passes the window → the vote starts by itself
    eid2 = _ft(fq, days=5)
    ft.wish(mia, eid2, game="jass")
    ft.wish(leo, eid2, game="schach")
    start = datetime.fromisoformat(_ev(fq, mia, eid2)["start"])
    ft.tick(start - timedelta(hours=23))
    assert fq.db.val("SELECT status FROM ft_game WHERE event_id=?", eid2) == "vote"
    ft.vote(mia, eid2, "g:jass")
    ft.vote(leo, eid2, "g:schach")
    ft.tick(start + timedelta(minutes=1))                      # the event starts with a tie: 🎲
    assert ft.game_of(eid2)["how"] == "random"


def test_parent_set_skip_clear(fq):
    papa, mia, leo = _people(fq)
    ft = fq.familytime
    eid = _ft(fq)
    ft.wish(mia, eid, game="tschau")
    ft.wish(leo, eid, title="Uno")
    ft.skip(papa, eid)
    ev = _ev(fq, mia, eid)
    assert ev["status"] == "skipped" and not ev["wishes_open"] and not ev["game"] and ev["can_buy"]
    ft.set_game(papa, eid, title="Memory")
    g = ft.game_of(eid)
    assert g["title"] == "Memory" and g["how"] == "parent" and g["by"] == "Papa"
    with pytest.raises(CommunityError):
        ft.set_game(papa, eid, game="jass")                     # remove it first
    ft.remove_game(papa, eid)
    assert ft.game_of(eid) is None and len(_ev(fq, papa, eid)["wishes"]) == 2
    ft.clear(papa, eid)
    ev = _ev(fq, papa, eid)
    assert ev["status"] == "wish" and not ev["wishes"] and ev["wishes_open"]
    with pytest.raises(CommunityError):
        ft.skip(mia, eid)
    with pytest.raises(CommunityError):
        ft.clear(leo, eid)


def test_buy_a_game_refused_when_set_and_refund(fq):
    papa, mia, leo = _people(fq)
    ft = fq.familytime
    eid = _ft(fq)
    ft.wish(leo, eid, game="jass")
    with pytest.raises(CommunityError):
        ft.buy(mia, eid, game="tschau")                         # not enough coins
    fq.rewards.book(mia["id"], "coins", 200, "test")
    with pytest.raises(CommunityError):
        ft.buy(papa, eid, game="tschau")                        # parents set it directly
    r = ft.buy(mia, eid, game="tschau")
    assert r["price"] == 150 and fq.rewards.balance(mia["id"], "coins") == 50
    g = ft.game_of(eid)
    assert g["how"] == "bought" and g["by"] == "Mia" and g["price"] == 150
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE event='familytime_game' AND profile_id=?", mia["id"]) == 1
    fq.rewards.book(leo["id"], "coins", 500, "test")
    with pytest.raises(CommunityError):
        ft.buy(leo, eid, title="Uno")                           # a game is set already
    with pytest.raises(CommunityError):
        ft.wish(leo, eid, game="schach")                        # ends the wishes
    assert fq.rewards.balance(leo["id"], "coins") == 500
    ft.remove_game(papa, eid)                                   # the parent removes it: the coins come back
    assert fq.rewards.balance(mia["id"], "coins") == 200
    ft.buy(mia, eid, title="Uno")
    fq.calendar.delete(eid)                                     # deleting the event gives them back too
    assert fq.rewards.balance(mia["id"], "coins") == 200
    assert not fq.db.q("SELECT * FROM ft_game") and not fq.db.q("SELECT * FROM ft_wish")


def test_settings_price_and_switch(fq):
    papa, mia, _ = _people(fq)
    ft = fq.familytime
    eid = _ft(fq)
    fq.rewards.book(mia["id"], "coins", 100, "test")
    fq.db.set_setting("familytime_game_price", 80)
    assert ft.state(mia)["price"] == 80
    fq.db.set_setting("familytime_game_price", 0)
    assert not _ev(fq, mia, eid)["can_buy"]
    with pytest.raises(CommunityError):
        ft.buy(mia, eid, game="jass")
    fq.db.set_setting("familytime_game_price", 80)
    fq.db.set_setting("familytime_wishes", False)
    assert ft.state(mia)["events"] == [] and ft.summary(mia) is None
    assert ft.state(papa)["events"]                             # parents still see it (and the switch)
    with pytest.raises(CommunityError):
        ft.wish(mia, eid, game="jass")
    with pytest.raises(CommunityError):
        ft.buy(mia, eid, game="jass")
    fq.db.set_setting("familytime_wishes", True)
    ft.buy(mia, eid, game="jass")
    assert fq.rewards.balance(mia["id"], "coins") == 20


def test_children_only_wish_their_games(fq):
    papa, mia, _ = _people(fq)
    acc = fq.games_access()
    acc["jass"] = {"mode": "off", "profiles": []}
    fq.db.set_setting("games_access", acc)
    eid = _ft(fq)
    assert "jass" not in [g["key"] for g in fq.familytime.state(mia)["games"]]
    with pytest.raises(CommunityError):
        fq.familytime.wish(mia, eid, game="jass")
    fq.familytime.wish(papa, eid, game="jass")                  # parents may wish every game


def test_api_permissions(client):
    ph, mia, leo = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    d = (datetime.now() + timedelta(days=4)).date().isoformat()
    eid = client.post("/api/parent/calendar", json={"title": "FamilyTime", "kind": "familytime", "start": d + "T17:00", "end": d + "T19:00"},
                      headers=ph).json()["id"]
    st = client.get("/api/community/familytime", headers=h).json()
    assert st["enabled"] and st["price"] == 150 and st["events"][0]["id"] == eid
    assert client.get("/api/me/community", headers=h).json()["familytime"]["state"] == "wish"
    assert client.post(f"/api/community/familytime/{eid}/wish", json={"game": "tschau"}, headers=h).status_code == 200
    assert client.post(f"/api/community/familytime/{eid}/wish", json={"title": "Uno"}, headers=hl).status_code == 200
    # a child cannot run the parent controls
    for path in ("start", "skip", "clear", "remove", "end"):
        assert client.post(f"/api/community/familytime/{eid}/{path}", headers=h).status_code == 400
    assert client.post(f"/api/community/familytime/{eid}/set", json={"title": "X"}, headers=h).status_code == 400
    assert client.post(f"/api/community/familytime/{eid}/start", headers=ph).json()["status"] == "vote"
    assert client.post(f"/api/community/familytime/{eid}/vote", json={"choice": "t:uno"}, headers=h).status_code == 200
    # the game is shown in the parent calendar and in the planner's view of the calendar
    client.post(f"/api/community/familytime/{eid}/set", json={"choice": "t:uno"}, headers=ph)
    cal = client.get(f"/api/parent/calendar?start={d}&end={d}", headers=ph).json()["events"]
    assert cal[0]["game"]["title"] == "Uno"
    assert "Uno" in client.get(f"/api/planer/fq-events?start={d}&end={d}", headers=h).json()[0]["summary"]
    # settings through the parent area
    client.put("/api/parent/settings", json={"familytime_game_price": 99, "familytime_vote_hours": 12}, headers=ph)
    st = client.get("/api/community/familytime", headers=h).json()
    assert st["price"] == 99 and st["vote_hours"] == 12
    # guests (QR invitation) are no family members
    assert client.get("/api/community/familytime").status_code == 401
