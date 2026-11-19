"""Children sign in with their Home Assistant user (linked in the profile – no extra switch; through Home Assistant ingress)."""
from fastapi.testclient import TestClient

from test_api import setup_family

KID = {"X-Remote-User-Id": "u-mia", "X-Remote-User-Name": "mia", "X-Remote-User-Display-Name": "Mia"}
PAPA = {"X-Remote-User-Id": "u-papa", "X-Remote-User-Name": "papa", "X-Remote-User-Display-Name": "Papa"}


def _ingress(client):
    return TestClient(client.app, client=("172.30.32.2", 50000))


def _link(client, ph, pid, name, uid, role="kid"):
    return client.put(f"/api/parent/profiles/{pid}", json={"name": name, "role": role, "ha_user_id": uid, "ha_user_name": name}, headers=ph)


def test_one_home_assistant_user_per_profile(client):
    ph, mia, leo = setup_family(client)
    papa = next(p for p in client.get("/api/profiles").json() if p["name"] == "Papa")["id"]
    assert _link(client, ph, mia, "Mia", "u-mia").status_code == 200
    assert _link(client, ph, mia, "Mia", "u-mia").status_code == 200                  # unchanged: fine
    assert _link(client, ph, leo, "Leo", "u-mia").status_code == 400                  # kid ↔ kid
    assert _link(client, ph, papa, "Papa", "u-mia", "parent").status_code == 400      # parent ↔ kid
    r = client.post("/api/parent/profiles", json={"name": "Eva", "ha_user_id": "u-mia"}, headers=ph)
    assert r.status_code == 400
    assert _link(client, ph, papa, "Papa", "u-papa", "parent").status_code == 200
    assert _link(client, ph, leo, "Leo", "u-papa").status_code == 400                 # kid ↔ parent
    prof = {p["id"]: p for p in client.get("/api/parent/profiles", headers=ph).json()}
    assert prof[mia]["settings"]["ha_user_id"] == "u-mia" and prof[mia]["settings"]["ha_user_name"] == "Mia"
    # a parent cannot take a child's user with «link my user» either
    ingress = _ingress(client)
    assert ingress.post("/api/parent/ha-link", json={"on": True}, headers={**ph, **KID}).status_code == 400
    # an archived profile gives its user up; removing the link works
    client.app.state.fq.db.x("UPDATE profile SET archived=1 WHERE id=?", mia)
    assert _link(client, ph, leo, "Leo", "u-mia").status_code == 200
    assert _link(client, ph, leo, "Leo", "").status_code == 200
    assert "ha_user_id" not in {p["id"]: p for p in client.get("/api/parent/profiles", headers=ph).json()}[leo]["settings"]


def test_linked_kid_always_logs_in_with_home_assistant_user(client):
    ph, mia, leo = setup_family(client)
    ingress = _ingress(client)
    # not linked: nothing
    assert ingress.post("/api/ha-login", headers=KID).json() == {"linked": False}
    assert ingress.get("/api/info", headers=KID).json()["ha_kid"] is None
    assert _link(client, ph, mia, "Mia", "u-mia").status_code == 200
    # the former switch is gone: neither in the meta nor in the settings, and it changes nothing
    assert "kid_ha_login" not in client.get("/api/parent/meta", headers=ph).json()
    assert client.put("/api/parent/settings", json={"kid_ha_login": False}, headers=ph).status_code == 200
    assert "kid_ha_login" not in client.get("/api/parent/settings", headers=ph).json()
    # linked: through ingress the child is logged in without PIN (Mia has a PIN)
    assert ingress.get("/api/info", headers=KID).json()["ha_kid"] == {"id": mia, "name": "Mia"}
    r = ingress.post("/api/ha-login", headers=KID).json()
    assert r["linked"] and r["profile"]["id"] == mia and "parent_token" not in r
    kh = {"X-FQ-Token": r["token"]}
    assert client.get("/api/me", headers=kh).json()["profile"]["name"] == "Mia"
    # … but never the parent area
    assert ingress.get("/api/parent/meta", headers={**kh, **KID}).status_code == 401
    assert ingress.get("/api/parent/meta", headers={"X-FQ-Parent": r["token"], **KID}).status_code == 401
    p = ingress.post("/api/parent/ha-login", headers=KID).json()
    assert not p["linked"] and p["kid"] and "parent_token" not in p
    # an unknown Home Assistant user: nothing
    assert ingress.post("/api/ha-login", headers=PAPA).json() == {"linked": False}
    # the login is in the login log
    assert client.app.state.fq.db.val("SELECT COUNT(*) FROM login_log WHERE profile_id=? AND ok=1", mia, default=0) >= 1
    # unlinked again: no more logins
    _link(client, ph, mia, "Mia", "")
    assert ingress.post("/api/ha-login", headers=KID).json() == {"linked": False}


def test_headers_from_the_direct_port_are_ignored(client):
    ph, mia, _ = setup_family(client)
    _link(client, ph, mia, "Mia", "u-mia")
    assert client.post("/api/ha-login", headers=KID).json() == {"linked": False}
    assert client.get("/api/info", headers=KID).json()["ha_kid"] is None
    other = TestClient(client.app, client=("172.30.32.3", 50000))         # Supervisor network, but not the ingress proxy
    assert other.post("/api/ha-login", headers=KID).json() == {"linked": False}


def test_archived_and_blocked_kids(client, monkeypatch):
    ph, mia, _ = setup_family(client)
    _link(client, ph, mia, "Mia", "u-mia")
    ingress = _ingress(client)
    fq = client.app.state.fq
    tok = ingress.post("/api/ha-login", headers=KID).json()["token"]
    # block time «only a message» applies as with a PIN login
    monkeypatch.setattr(fq.internet, "block", lambda prof, now=None: {"mode": "app"})
    assert client.get("/api/me/shop", headers={"X-FQ-Token": tok}).status_code == 423
    monkeypatch.undo()
    # archived: no login, the old login ends
    fq.db.x("UPDATE profile SET archived=1 WHERE id=?", mia)
    assert ingress.post("/api/ha-login", headers=KID).json() == {"linked": False}
    assert client.get("/api/me", headers={"X-FQ-Token": tok}).status_code == 401


def test_ingress_start_page_per_home_assistant_user(client, monkeypatch):
    """panel_admin: false – every Home Assistant user sees the panel: the parent area for linked parents and
    administrators, the children's app for everybody else."""
    ph, mia, _ = setup_family(client)
    papa = next(p for p in client.get("/api/profiles").json() if p["name"] == "Papa")["id"]
    _link(client, ph, papa, "Papa", "u-papa", "parent")
    _link(client, ph, mia, "Mia", "u-mia")
    ingress = _ingress(client)
    assert "parent.js" in ingress.get("/").text                                       # no user header: as before
    assert "parent.js" in ingress.get("/", headers=PAPA).text                          # linked parent
    assert "kid.js" in ingress.get("/", headers=KID).text                              # linked child: its app
    other = {"X-Remote-User-Id": "u-guest", "X-Remote-User-Name": "guest"}
    assert "kid.js" in ingress.get("/", headers=other).text                            # not linked, not admin (unknown)
    assert "kid.js" in ingress.get("/", headers=KID).text
    assert "kid.js" in client.get("/", headers=PAPA).text                              # direct port: always the app

    class HA:
        connected = True
        def user_is_admin(self, uid): return uid == "u-admin"
    monkeypatch.setattr(client.app.state.fq, "ha", HA())
    assert "parent.js" in ingress.get("/", headers={"X-Remote-User-Id": "u-admin"}).text
    assert "kid.js" in ingress.get("/", headers=other).text
    assert "parent.js" in ingress.get("/eltern", headers=KID).text                      # the parent area itself: PIN login


def test_user_is_admin_from_home_assistant():
    from familyquest.ha.service import HAService

    class C:
        calls = 0
        async def command(self, msg, timeout=15):
            C.calls += 1
            assert msg == {"type": "config/auth/list"}
            return [{"id": "a", "is_admin": True}, {"id": "b", "is_admin": False, "group_ids": ["system-users"]}]

    svc = HAService.__new__(HAService)
    svc.client = C()
    import asyncio
    svc._sync = lambda coro, timeout=8: asyncio.run(coro)
    assert svc.user_is_admin("a") is True and svc.user_is_admin("b") is False and svc.user_is_admin("x") is False
    assert C.calls == 1                                                                # cached

    def fail(coro, timeout=8):
        coro.close()
        raise RuntimeError("down")
    svc2 = HAService.__new__(HAService)
    svc2._sync = fail
    svc2.client = C()
    assert svc2.user_is_admin("a") is None


def test_setup_through_ha_links_the_first_parent(client):
    """First start opened through Home Assistant: the first parent is linked with that HA user (no PIN in HA)."""
    direct = client
    client = _ingress(direct)
    hdr = {"x-remote-user-id": "u-papa", "x-remote-user-display-name": "Papa"}
    info = client.get("/api/info", headers=hdr).json()
    assert info["setup_needed"] and info["setup_ha_user"] == "Papa"
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}, headers=hdr)
    assert r.status_code == 200, r.text
    from familyquest.db import profile_settings
    p = client.app.state.fq.db.q1("SELECT * FROM profile WHERE role='parent'")
    assert profile_settings(p).get("ha_user_id") == "u-papa"
    assert client.get("/api/info", headers=hdr).json()["setup_ha_user"] is None
    # on the direct port the headers count for nothing
    assert direct.get("/api/info", headers=hdr).json()["setup_ha_user"] is None
