"""Internet budget per child: minutes per day / week, other weekdays, reset time, block times with modes."""
import json
from datetime import datetime

import pytest

from familyquest.internet import InternetError, block_at, clean_plan, period_of
from test_api import setup_family

PLAN = {"budget": 60, "period": "day", "reset": "04:00", "days": {"5": 120, "6": 120},
        "blocks": [{"days": [0, 1, 2, 3, 4], "from": "20:00", "to": "07:00", "mode": "app"},
                   {"days": [2], "from": "14:00", "to": "15:00", "mode": "games"}]}


def test_periods_and_weekdays():
    p = clean_plan(PLAN)
    s, e, b = period_of(p, datetime(2026, 11, 18, 3, 0))          # Wednesday 03:00 – still Tuesday's day
    assert s == datetime(2026, 11, 17, 4, 0) and e == datetime(2026, 11, 18, 4, 0) and b == 60
    assert period_of(p, datetime(2026, 11, 21, 10, 0))[2] == 120  # Saturday
    w = clean_plan({"budget": 300, "period": "week", "reset": "00:00", "reset_day": 0})
    s, e, b = period_of(w, datetime(2026, 11, 19, 12, 0))        # Thursday → week since Monday
    assert s == datetime(2026, 11, 16, 0, 0) and b == 300
    with pytest.raises(InternetError):
        clean_plan({"blocks": [{"days": [], "from": "20:00", "to": "07:00"}]})


def test_block_times_over_midnight():
    p = clean_plan(PLAN)
    assert block_at(p, datetime(2026, 11, 16, 21, 0))["until"] == "2026-11-17T07:00"   # Monday evening
    assert block_at(p, datetime(2026, 11, 17, 6, 30))["mode"] == "app"                  # Tuesday morning (from Monday)
    assert block_at(p, datetime(2026, 11, 21, 6, 30)) is not None                       # Saturday morning: from Friday
    assert block_at(p, datetime(2026, 11, 22, 6, 30)) is None                           # Sunday morning: Saturday has none
    assert block_at(p, datetime(2026, 11, 18, 14, 30))["mode"] == "games"
    assert block_at(p, datetime(2026, 11, 18, 12, 0)) is None


def test_budget_is_used_first(fq):
    plan = {"budget": 5, "period": "day", "reset": "00:00"}
    pid = fq.db.x("INSERT INTO profile(name, settings) VALUES('Mia', ?)",
                  json.dumps({"internet_rule": "switch.r", "internet_plan": plan}))
    fq.internet.ensure_account()
    fq.internet.switcher = lambda e, on: None
    fq.rewards.book(pid, "internet", 3, "test")                    # earned in the shop
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", pid)
    st = fq.internet.state(prof)
    assert st["minutes"] == 8 and st["budget"]["left"] == 5 and st["extra"] == 3
    fq.internet.start(prof)                                       # first minute from the budget
    assert fq.internet.allowance(prof)["used"] == 1 and fq.internet.balance(pid) == 3
    fq.db.x("UPDATE internet_session SET deducted=-5 WHERE profile_id=?", pid)   # 6 more minutes due
    fq.internet.tick(pid)
    assert fq.internet.allowance(prof)["left"] == 0 and fq.internet.balance(pid) == 1


def test_plan_api_and_app_lock(client, monkeypatch):
    ph, mia, leo = setup_family(client)
    r = client.put(f"/api/parent/profiles/{leo}", headers=ph, json={"name": "Leo", "role": "kid", "color": "#4f8cff",
                   "settings": {"internet_plan": {"budget": 30, "blocks": [{"days": [9], "from": "x", "to": "y"}]}}})
    assert r.status_code == 400
    plan = {"budget": 30, "blocks": [{"days": list(range(7)), "from": "00:00", "to": "23:59", "mode": "app"}]}
    r = client.put(f"/api/parent/profiles/{leo}", headers=ph, json={"name": "Leo", "role": "kid", "color": "#4f8cff",
                   "settings": {"internet_plan": plan}})
    assert r.status_code == 200, r.text
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    me = client.get("/api/me", headers=hl).json()
    assert me["offline_lock"] and me["games_list"] == []
    # enforced on the server too: everything else of the app answers 423 during the lock
    assert client.get("/api/me/decks", headers=hl).status_code == 423
    assert client.get("/api/me", headers=hl).status_code == 200
