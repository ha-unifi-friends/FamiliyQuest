"""Own chore plan (Ämtliplan)."""
from datetime import date, timedelta

import pytest

from familyquest.chores import ChoreError, Chores, monday


@pytest.fixture
def kids(fq):
    a = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    b = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    return a, b


def test_daily_fixed_with_confirmation(fq, kids):
    mia, leo = kids
    fq.chores.save({"name": "Tisch decken", "points": 5, "profiles": [mia, leo], "confirm": True})
    t = fq.chores.for_kid(mia)
    assert [c["summary"] for c in t] == ["Tisch decken"] and len(fq.chores.for_kid(leo)) == 1
    tid = int(t[0]["uid"][3:])
    with pytest.raises(ChoreError):
        fq.chores.mark_done(leo, tid)                      # not Leo's task
    assert fq.chores.mark_done(mia, tid)["status"] == "pending"
    assert fq.rewards.balance(mia, "coins") == 0
    assert [p["id"] for p in fq.chores.pending()] == [tid]
    assert fq.chores.decide(tid, False)["status"] == "open"   # «Nochmals»
    assert fq.chores.for_kid(mia)[0]["redo"]
    fq.chores.mark_done(mia, tid)
    assert fq.chores.decide(tid, True)["status"] == "done"
    assert fq.rewards.balance(mia, "coins") == 5
    fq.chores.decide(tid, True)                              # no double booking
    assert fq.rewards.balance(mia, "coins") == 5


def test_without_confirmation_books_at_once(fq, kids):
    mia, _ = kids
    fq.chores.save({"name": "Bett machen", "points": 3, "profiles": [mia], "confirm": False, "kind": "duty"})
    tid = int(fq.chores.for_kid(mia)[0]["uid"][3:])
    assert fq.chores.mark_done(mia, tid)["status"] == "done"
    assert fq.rewards.balance(mia, "coins") == 3


def test_rotation_and_weekdays(fq, kids):
    mia, leo = kids
    rot = {"id": 1, "frequency": "weekly", "weekdays": [], "date": None, "assign": "rotate", "rotate_every": "week",
           "profiles": [mia, leo]}
    d = date(2026, 11, 16)
    assert Chores.due_on(rot, d) == "2026-11-16" and Chores.due_on(rot, d + timedelta(days=3)) == "2026-11-16"
    a = Chores.assignees(rot, d, [mia, leo])
    b = Chores.assignees(rot, d + timedelta(days=7), [mia, leo])
    assert len(a) == 1 and a != b                                    # next week the other child
    daily = dict(rot, frequency="daily", rotate_every="day")
    assert Chores.assignees(daily, d, [mia, leo]) != Chores.assignees(daily, d + timedelta(days=1), [mia, leo])
    wd = dict(rot, frequency="weekdays", weekdays=[0, 2], assign="fixed")
    assert Chores.due_on(wd, d) and not Chores.due_on(wd, d + timedelta(days=1))
    once = dict(rot, frequency="once", date="2026-11-20")
    assert Chores.due_on(once, date(2026, 11, 20)) and not Chores.due_on(once, d)
    week = fq.chores.week(d)
    assert len(week["days"]) == 7


def test_week_bonus(fq, kids):
    mia, _ = kids
    fq.chores.save({"name": "Abfall", "points": 10, "frequency": "weekly", "profiles": [mia], "confirm": False})
    tid = int(fq.chores.for_kid(mia)[0]["uid"][3:])
    fq.chores.mark_done(mia, tid)
    bonus = fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND event='chores_week_all'", mia)
    assert bonus == 20 and fq.rewards.balance(mia, "coins") == 30
    stats = fq.chores.stats(mia)
    assert stats["week_percent"] == 100


def test_validation(fq, kids):
    mia, _ = kids
    for bad in ({"name": "", "profiles": [mia]}, {"name": "x", "profiles": []}, {"name": "x", "profiles": [mia], "frequency": "weekdays"},
                {"name": "x", "profiles": [mia], "frequency": "once"}, {"name": "x", "profiles": [mia], "frequency": "yearly"}):
        with pytest.raises(ChoreError):
            fq.chores.save(bad)


def test_chores_api(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()["parent_token"]}
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    r = client.post("/api/parent/chores", json={"name": "Zimmer aufräumen", "icon": "🛏️", "points": 20, "profiles": [mia]}, headers=ph)
    assert r.status_code == 200, r.text
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia}).json()["token"]}
    me = client.get("/api/me", headers=h).json()
    uid = me["chores"][0]["uid"]
    r = client.post(f"/api/me/chores/{uid}/done", headers=h).json()
    assert r["status"] == "pending" and r["chores"][0]["pending"]
    ov = client.get("/api/parent/overview", headers=ph).json()
    tid = ov["chores_pending"][0]["id"]
    assert client.post(f"/api/parent/chores/tasks/{tid}", json={"ok": True}, headers=ph).json()["status"] == "done"
    assert client.get("/api/me", headers=h).json()["balances"]["coins"] == 20
    plan = client.get("/api/parent/chores", headers=ph).json()
    assert plan["chores"][0]["name"] == "Zimmer aufräumen" and len(plan["week"]["days"]) == 7
    assert client.post("/api/me/chores/fq:99999/done", headers=h).status_code == 400
