"""Internet time managed by the app (firewall rule switch, budget, start/stop)."""
import json
from datetime import datetime, timedelta

import pytest

from familyquest.internet import InternetError


@pytest.fixture
def child(fq):
    pid = fq.db.x("INSERT INTO profile(name, settings) VALUES('Mia', ?)",
                  json.dumps({"internet_rule": "switch.unifi_block_mia", "internet_rule_blocks": True}))
    fq.internet.ensure_account()
    calls = []
    fq.internet.switcher = lambda e, on: calls.append((e, on))
    return pid, calls


def prof(fq, pid):
    return fq.db.q1("SELECT * FROM profile WHERE id=?", pid)


def test_start_stop_and_rule(fq, child):
    pid, calls = child
    with pytest.raises(InternetError):
        fq.internet.start(prof(fq, pid))                       # no minutes yet
    fq.rewards.book(pid, "internet", 10, "test")
    st = fq.internet.start(prof(fq, pid))
    assert st["running"] and calls[-1] == ("switch.unifi_block_mia", False)   # blocking rule off = internet on
    assert fq.internet.balance(pid) == 9                       # first minute paid at once
    assert 540 < st["seconds_left"] <= 600
    st = fq.internet.stop(prof(fq, pid))
    assert not st["running"] and calls[-1] == ("switch.unifi_block_mia", True)


def test_minutes_are_deducted_and_empty_blocks(fq, child):
    pid, calls = child
    fq.rewards.book(pid, "internet", 3, "test")
    fq.internet.start(prof(fq, pid))
    # pretend the session started 150 s ago → 3 started minutes
    start = (datetime.now() - timedelta(seconds=150)).isoformat(timespec="seconds")
    fq.db.x("UPDATE internet_session SET started_at=? WHERE profile_id=?", start, pid)
    fq.internet.tick()
    assert fq.internet.balance(pid) == 0 and fq.internet.state(prof(fq, pid))["running"]
    # a minute later the 4th minute cannot be paid → blocked
    start = (datetime.now() - timedelta(seconds=200)).isoformat(timespec="seconds")
    fq.db.x("UPDATE internet_session SET started_at=? WHERE profile_id=?", start, pid)
    fq.internet.tick()
    assert not fq.internet.state(prof(fq, pid))["running"] and calls[-1] == ("switch.unifi_block_mia", True)


def test_allow_rule_polarity(fq):
    pid = fq.db.x("INSERT INTO profile(name, settings) VALUES('Leo', ?)",
                  json.dumps({"internet_rule": "switch.allow_leo", "internet_rule_blocks": False}))
    calls = []
    fq.internet.switcher = lambda e, on: calls.append((e, on))
    fq.rewards.book(pid, "internet", 5, "test")
    fq.internet.start(prof(fq, pid))
    assert calls[-1] == ("switch.allow_leo", True)


def test_shop_books_minutes_in_the_app(fq, child):
    pid, _ = child
    fq.rewards.book(pid, "coins", 100, "test")
    offer = next(o for o in fq.shop.offers(pid) if o["kind"] == "internet_minutes")
    red = fq.shop.redeem(pid, offer["id"])
    assert red["status"] == "approved" and fq.internet.balance(pid) == 15


def test_internet_api(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()["parent_token"]}
    assert client.post("/api/parent/profiles", json={"name": "Mia", "settings": {"internet_rule": "nope"}}, headers=ph).status_code == 400
    mia = client.post("/api/parent/profiles", json={"name": "Mia", "settings": {"internet_rule": "switch.unifi_mia"}}, headers=ph).json()["id"]
    client.post("/api/parent/book", json={"profile_id": mia, "account": "internet", "amount": 30}, headers=ph)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia}).json()["token"]}
    st = client.get("/api/me", headers=h).json()["internet"]
    assert st["minutes"] == 30 and not st["can_start"]                       # no Home Assistant in tests
    assert client.post("/api/me/internet/start", headers=h).status_code == 400
    assert client.post(f"/api/parent/internet/{mia}/stop", headers=ph).json()["internet"]["running"] is False
