"""Review 2 (security): parent networks for every parent-token route, parent sessions that end, the PIN backoff per
profile."""
import time

import pytest
from fastapi.testclient import TestClient

from familyquest.api import auth
from test_api import setup_family


def _from(client, ip):
    return TestClient(client.app, client=(ip, 50000))


def test_parent_networks_hold_for_every_parent_token_route(client):
    """H1: a parent token from a network outside «parent networks» is refused everywhere – not only below
    /api/parent/ (the planner pass-throughs, the stories and code workshop settings …)."""
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    st = fq.planer_host.hass.states
    st.set("camera.door", "idle", {"access_token": "secret"})
    st.set("todo.zuhause", "3", {"friendly_name": "Zuhause"})
    fq.db.set_setting("parent_networks", ["10.0.0.0/8"])
    home, kids = _from(client, "10.0.0.5"), _from(client, "192.168.7.20")
    for path in ("/api/stories/settings", "/api/planer/import/sources", "/api/planer/shopping", "/api/parent/meta"):
        assert home.get(path, headers=ph).status_code == 200, path
        r = kids.get(path, headers=ph)
        assert r.status_code == 403 and r.json()["detail"] == "The parent area cannot be opened from this network", path
    assert kids.put("/api/stories/settings", json={}, headers=ph).status_code == 403
    assert kids.post("/api/planer/chores/take-over", json={}, headers=ph).status_code in (403, 422)
    # the full Home Assistant state dump only for a parent from the parent networks – elsewhere the children's view
    assert "camera.door" in {s["entity_id"] for s in home.get("/api/planer/ha/states", headers=ph).json()}
    r = kids.get("/api/planer/ha/states", headers=ph)
    assert r.status_code == 200 and "camera.door" not in {s["entity_id"] for s in r.json()}
    assert "todo.zuhause" in {s["entity_id"] for s in r.json()}


def test_parent_session_ends_even_with_refresh(client, monkeypatch):
    """H2: /refresh keeps the start of the session – after PARENT_SESSION_MAX the PIN is needed again."""
    ph, mia, _ = setup_family(client)
    now = [time.time()]
    monkeypatch.setattr(auth.time, "time", lambda: now[0])
    tok = client.post("/api/parent/login", json={"pin": "1234"}).json()["parent_token"]
    start = client.app.state.fq.tokens.session(tok)[0]
    while now[0] + 25 * 60 < start + auth.PARENT_SESSION_MAX:     # refreshed every 25 minutes …
        now[0] += 25 * 60
        r = client.post("/api/parent/refresh", headers={"X-FQ-Parent": tok})
        assert r.status_code == 200
        tok = r.json()["parent_token"]
        assert client.app.state.fq.tokens.session(tok)[0] == start      # … the session keeps its start
    now[0] = start + auth.PARENT_SESSION_MAX + 60
    assert client.get("/api/parent/meta", headers={"X-FQ-Parent": tok}).status_code == 401
    assert client.post("/api/parent/refresh", headers={"X-FQ-Parent": tok}).status_code == 401
    # through Home Assistant ingress (its own login behind it) the session may run longer
    ingress = TestClient(client.app, client=("172.30.32.2", 50000))
    tok = ingress.post("/api/parent/login", json={"pin": "1234"}).json()["parent_token"]
    end = now[0] + auth.PARENT_SESSION_MAX + 60
    while now[0] < end:
        now[0] += 25 * 60
        r = ingress.post("/api/parent/refresh", headers={"X-FQ-Parent": tok})
        assert r.status_code == 200
        tok = r.json()["parent_token"]
    # … but not when the token is carried to the app port
    assert client.post("/api/parent/refresh", headers={"X-FQ-Parent": tok}).status_code == 401


def test_log_out_everywhere_and_new_pin_end_the_logins(client):
    """H2: a per-profile session counter – «log out everywhere» and a new PIN end every login of the profile."""
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    other = {"X-FQ-Parent": client.post("/api/parent/login", json={"pin": "1234"}).json()["parent_token"]}
    papa_app = {"X-FQ-Token": client.post("/api/parent/app-token", headers=ph).json()["token"]}
    assert client.get("/api/me", headers=hm).status_code == 200
    # the parents log Mia out everywhere
    r = client.post("/api/parent/sessions/end", json={"profile_id": mia}, headers=ph)
    assert r.status_code == 200 and "parent_token" not in r.json()
    assert client.get("/api/me", headers=hm).status_code == 401
    assert client.get("/api/parent/meta", headers=ph).status_code == 200        # the parent stays in
    # the own profile: every other device is out, this one gets a fresh token
    r = client.post("/api/parent/sessions/end", json={}, headers=ph)
    fresh = {"X-FQ-Parent": r.json()["parent_token"]}
    assert client.get("/api/parent/meta", headers=other).status_code == 401
    assert client.get("/api/me", headers=papa_app).status_code == 401
    assert client.get("/api/parent/meta", headers=ph).status_code == 401
    assert client.get("/api/parent/meta", headers=fresh).status_code == 200
    assert client.post("/api/parent/sessions/end", json={"profile_id": 999}, headers=fresh).status_code == 404
    # a new PIN (by the parents) raises the counter too
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    fq = client.app.state.fq
    n = fq.db.val("SELECT sessions FROM profile WHERE id=?", mia)
    r = client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "role": "kid", "pin": "2222"}, headers=fresh)
    assert r.status_code == 200, r.text
    assert fq.db.val("SELECT sessions FROM profile WHERE id=?", mia) == n + 1
    assert client.get("/api/me", headers=hm).status_code == 401
    # a profile edit without a new PIN keeps the logins
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "2222"}).json()["token"]}
    client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia M.", "role": "kid", "login": "pin"}, headers=fresh)
    assert client.get("/api/me", headers=hm).status_code == 200


def test_a_parents_app_login_is_short(client, monkeypatch):
    """H2: the app login of a parent profile (also a planner admin) lasts PARENT_APP_TTL, a child's the usual 30 days."""
    from familyquest.api import planer
    ph, mia, _ = setup_family(client)
    now = [time.time()]
    monkeypatch.setattr(auth.time, "time", lambda: now[0])
    papa = client.app.state.fq.db.val("SELECT id FROM profile WHERE role='parent'")
    pt = client.post("/api/login", json={"profile_id": papa, "pin": "1234"}).json()["token"]
    kt = client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]
    assert planer._parent_in_app(client.app.state.fq, pt, "127.0.0.1")
    now[0] += auth.PARENT_APP_TTL + 60
    assert client.get("/api/me", headers={"X-FQ-Token": pt}).status_code == 401
    assert client.get("/api/me", headers={"X-FQ-Token": kt}).status_code == 200
    assert not planer._parent_in_app(client.app.state.fq, pt, "127.0.0.1")


def test_pin_backoff_per_profile_from_any_device(client, monkeypatch, caplog):
    """M1: after 5 wrong PINs in a row for a profile – from any address – a growing wait, logged; the right PIN after
    the wait clears it."""
    ph, mia, _ = setup_family(client)
    now = [time.time()]
    monkeypatch.setattr(auth.time, "time", lambda: now[0])
    for i in range(5):                                   # a new address for every guess: the per-device limit never hits
        r = _from(client, f"192.168.9.{i + 1}").post("/api/login", json={"profile_id": mia, "pin": f"000{i}"})
        assert r.status_code == 403
    assert "wrong PINs in a row" in caplog.text
    r = _from(client, "192.168.9.50").post("/api/login", json={"profile_id": mia, "pin": "1111"})
    assert r.status_code == 429                          # locked – even with the right PIN, from a new device
    now[0] += 61
    assert _from(client, "192.168.9.51").post("/api/login", json={"profile_id": mia, "pin": "0000"}).status_code == 403
    now[0] += 61                                         # the 6th wrong PIN: now two minutes
    assert _from(client, "192.168.9.52").post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 429
    now[0] += 60
    assert _from(client, "192.168.9.53").post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200
    assert _from(client, "192.168.9.54").post("/api/login", json={"profile_id": mia, "pin": "0001"}).status_code == 403
    # the parent PIN (tried against every parent) has its own counter – a child's wrong guesses never lock Mia out
    for i in range(5):
        assert _from(client, f"192.168.8.{i + 1}").post("/api/parent/login", json={"pin": f"999{i}"}).status_code == 403
    assert _from(client, "192.168.8.9").post("/api/parent/login", json={"pin": "1234"}).status_code == 429
    assert _from(client, "192.168.8.10").post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200


@pytest.mark.parametrize("bad", [{"dataset": ["x"]}, {"dataset": {"a": 1}}, {"dataset": "attempts", "measure": ["x"]}])
def test_analytics_refuses_unhashable_values(client, bad):
    """L6: a list or object where a name belongs is a 400, not a 500."""
    ph, _, _ = setup_family(client)
    r = client.post("/api/parent/analytics/query", json=bad, headers=ph)
    assert r.status_code == 400, r.text
