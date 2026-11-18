"""Daily time limits per child: family games and learning (timelimits.py), internet budget ∞ (internet.py)."""
import json
from datetime import datetime

import pytest

from familyquest import timelimits
from familyquest.internet import clean_plan, period_of
from familyquest.timelimits import LimitError, clean_limit, limit_today
from test_api import setup_family


def _login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def _put(client, ph, pid, name, settings):
    return client.put(f"/api/parent/profiles/{pid}", headers=ph, json={"name": name, "role": "kid", "color": "#4f8cff", "settings": settings})


def test_clean_and_weekday_override():
    assert clean_limit(None) == {"all": None, "days": {}}
    assert clean_limit({"all": 60, "days": {"2": 30, "5": None, "6": 60}}) == {"all": 60, "days": {"2": 30, "5": None}}   # Sunday = all: docked
    for bad in ({"all": -1}, {"all": 1441}, {"all": "x"}, {"days": {"7": 10}}, {"days": [1]}, "60"):
        with pytest.raises(LimitError):
            clean_limit(bad)
    s = {"all": 60, "days": {"2": 30, "5": None}}
    assert limit_today(s, 0) == 60 and limit_today(s, 2) == 30 and limit_today(s, 5) is None
    assert limit_today({"all": None, "days": {}}, 3) is None and limit_today("broken", 3) is None


def test_settings_saved_and_validated(client):
    ph, mia, leo = setup_family(client)
    defaults = client.get("/api/parent/meta", headers=ph).json()["profile_defaults"]
    assert defaults["game_limit"] == {"all": None, "days": {}} and defaults["learn_limit"] == {"all": None, "days": {}}
    assert _put(client, ph, leo, "Leo", {"game_limit": {"all": 99999}}).status_code == 400
    r = _put(client, ph, leo, "Leo", {"game_limit": {"all": 45, "days": {"2": 90, "3": 45}}, "learn_limit": {"all": None, "days": {"6": 0}}})
    assert r.status_code == 200, r.text
    p = next(x for x in client.get("/api/parent/profiles", headers=ph).json() if x["id"] == leo)
    assert p["settings"]["game_limit"] == {"all": 45, "days": {"2": 90}}
    assert p["settings"]["learn_limit"] == {"all": None, "days": {"6": 0}}


def test_game_minutes_counted_once_per_minute(fq, kid):
    t = datetime(2026, 11, 18, 10, 5, 7)
    for s in (0, 20, 59):
        timelimits.touch(fq.db, kid, t.replace(second=s))
    timelimits.touch(fq.db, kid, t.replace(minute=6))
    assert timelimits.used(fq.db, kid, "game", t) == 2
    assert timelimits.used(fq.db, kid, "game", datetime(2026, 11, 19, 10, 0)) == 0      # a new day
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    assert timelimits.left(fq.db, prof, "game", t) is None                               # default: unlimited
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps({"game_limit": {"all": 30, "days": {"2": 3}}}), kid)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    assert timelimits.left(fq.db, prof, "game", t) == 1                                  # Wednesday: 3 minutes
    assert timelimits.left(fq.db, prof, "game", datetime(2026, 11, 19, 10, 0)) == 30


def test_new_games_refused_running_game_continues(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = _login(client, mia, "1111"), _login(client, leo)
    assert _put(client, ph, mia, "Mia", {"game_limit": {"all": 2}}).status_code == 200
    me = client.get("/api/me", headers=hm).json()
    assert me["time_left"]["games"] == 2 and me["time_left"]["learn"] is None
    st = client.post("/api/community/bingo/start", json={"interval": 8}, headers=hm).json()
    assert st["status"] == "lobby"
    assert timelimits.used(fq.db, mia, "game") == 1                                    # the request counted a minute
    client.post("/api/community/bingo/join", headers=hl)
    assert client.post("/api/community/bingo/begin", headers=hm).json()["status"] == "running"
    # the time runs out during the game
    fq.db.x("INSERT INTO play_minute(profile_id, day, minute) VALUES(?,?,?)", mia, datetime.now().date().isoformat(), 5000)
    me = client.get("/api/me", headers=hm).json()
    assert me["time_left"]["games"] == 0 and me["games_list"] == [] and not me["games"]
    assert client.get("/api/community/bingo", headers=hm).status_code == 200            # the running game goes on
    assert client.post("/api/community/bingo/mark", json={"cell": 0}, headers=hm).status_code in (200, 400)
    client.post("/api/community/bingo/end", headers=hm)
    r = client.post("/api/community/bingo/start", json={}, headers=hm)                   # but no new one
    assert r.status_code == 403 and "used up" in r.json()["detail"]
    assert client.post("/api/community/duel", json={"opponent": leo}, headers=hm).status_code == 403
    assert client.post("/api/me/playtime", headers=hm).json()["ok"] is False             # the game corner closes
    assert client.get("/api/me/slots", headers=hm).status_code == 403
    assert client.get("/api/me", headers=hl).json()["games_list"]                       # Leo: no limit


def test_heartbeat_counts_and_parents_unlimited(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = _login(client, mia, "1111")
    _put(client, ph, mia, "Mia", {"game_limit": {"all": 10}})
    r = client.post("/api/me/playtime", headers=hm).json()
    assert r["ok"] and r["time_left"]["games"] == 9
    client.post("/api/me/playtime", headers=hm)                                          # same minute: counted once
    assert timelimits.used(fq.db, mia, "game") == 1
    # a parent is never limited, even with a limit in the settings
    papa = fq.db.q1("SELECT * FROM profile WHERE role='parent'")
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps({"game_limit": {"all": 0}, "learn_limit": {"all": 0}}), papa["id"])
    assert client.get("/api/me", headers=ph).json()["time_left"] == {"games": None, "learn": None, "internet": None}
    assert client.post("/api/community/bingo/start", json={}, headers=ph).status_code == 200
    assert timelimits.used(fq.db, papa["id"], "game") == 0


def test_learning_refused_after_the_limit(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = _login(client, mia, "1111")
    _put(client, ph, mia, "Mia", {"learn_limit": {"all": 20}})
    s = client.post("/api/me/session", json={"mode": "daily"}, headers=hm)
    assert s.status_code == 200
    fq.rewards.add_time(mia, 20 * 60)                                                    # 20 minutes learned today
    assert client.get("/api/me", headers=hm).json()["time_left"]["learn"] == 0
    r = client.post("/api/me/session", json={"mode": "daily"}, headers=hm)
    assert r.status_code == 400 and "used up" in r.json()["detail"]
    assert client.post(f"/api/me/session/{s.json()['id']}/finish", headers=hm).status_code == 200   # a running lesson ends normally
    _put(client, ph, mia, "Mia", {"learn_limit": {"all": 20, "days": {str(datetime.now().weekday()): None}}})
    assert client.post("/api/me/session", json={"mode": "daily"}, headers=hm).status_code == 200    # today: unlimited


def test_internet_slider_round_trip(client, fq):
    p = clean_plan({"budget": None, "period": "day", "reset": "00:00", "days": {"5": 120, "6": None}})
    assert p["budget"] is None and p["days"] == {"5": 120, "6": None}
    assert period_of(p, datetime(2026, 11, 18, 12, 0))[2] is None                          # Wednesday: unlimited
    assert period_of(p, datetime(2026, 11, 21, 12, 0))[2] == 120                           # Saturday
    assert clean_plan({"period": "day"})["budget"] == 0                                    # old plans: no budget key = 0
    pid = fq.db.x("INSERT INTO profile(name, settings) VALUES('Mia', ?)",
                  json.dumps({"internet_rule": "switch.r", "internet_plan": {"budget": None, "period": "day", "reset": "00:00"}}))
    fq.internet.ensure_account()
    fq.internet.switcher = lambda e, on: None
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    a = fq.internet.allowance(prof)
    assert a["unlimited"] and a["total"] is None and a["left"] >= 1
    assert fq.internet.state(prof)["can_start"]
    assert fq.time_left(prof)["internet"] is None
    fq.db.x("UPDATE profile SET settings=? WHERE id=?",
            json.dumps({"internet_rule": "switch.r", "internet_plan": {"budget": 30, "period": "day", "reset": "00:00"}}), pid)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    assert fq.time_left(prof)["internet"] == 30
    # through the API: the parent area sends the slider value as budget / days
    ph, mia, leo = setup_family(client)
    r = _put(client, ph, leo, "Leo", {"internet_plan": {"budget": None, "period": "day", "reset": "00:00", "days": {"2": 45}, "blocks": []}})
    assert r.status_code == 200
    p = next(x for x in client.get("/api/parent/profiles", headers=ph).json() if x["id"] == leo)
    assert p["settings"]["internet_plan"]["budget"] is None and p["settings"]["internet_plan"]["days"] == {"2": 45}
