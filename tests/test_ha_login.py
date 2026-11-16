from fastapi.testclient import TestClient

from test_api import setup_family

HA = {"X-Remote-User-Id": "abc123", "X-Remote-User-Name": "raphael", "X-Remote-User-Display-Name": "Raphael"}


def test_parent_area_with_home_assistant_user(client):
    ph, mia, _ = setup_family(client)
    ingress = TestClient(client.app, client=("172.30.32.2", 50000))
    # not linked yet: the app knows the HA user, but asks for the PIN
    r = ingress.post("/api/parent/ha-login", headers=HA).json()
    assert r["ha_user"]["name"] == "Raphael" and not r["linked"] and "parent_token" not in r
    # headers from the direct port (not the Supervisor proxy) are not trusted
    assert client.post("/api/parent/ha-login", headers=HA).json()["ha_user"] is None
    assert client.post("/api/parent/ha-link", json={"on": True}, headers={**ph, **HA}).status_code == 400
    # link through ingress, then the parent area opens without PIN
    assert ingress.post("/api/parent/ha-link", json={"on": True}, headers={**ph, **HA}).json()["ha_user_name"] == "Raphael"
    r = ingress.post("/api/parent/ha-login", headers=HA).json()
    assert r["linked"] and r["profile"]["name"] == "Papa"
    hh = {"X-FQ-Parent": r["parent_token"]}
    assert ingress.get("/api/parent/meta", headers={**hh, **HA}).json()["my_ha_user"] == "Raphael"
    # «only through Home Assistant»: refused from the direct port, allowed through ingress
    assert client.put("/api/parent/settings", json={"parent_ha_only": True}, headers=ph).status_code == 400
    assert ingress.put("/api/parent/settings", json={"parent_ha_only": True}, headers={**hh, **HA}).status_code == 200
    assert client.post("/api/parent/login", json={"pin": "1234"}).status_code == 403
    # the app port knows it: no parent area there, even with an old parent token
    assert client.get("/api/parent/meta", headers=ph).status_code == 403
    assert client.get("/api/info").json()["parent_ha_only"] and not client.get("/api/info").json()["via_ha"]
    assert ingress.get("/api/info").json()["via_ha"]
    papa = next(p for p in client.get("/api/profiles").json() if p["name"] == "Papa")["id"]
    assert "parent_token" not in client.post("/api/login", json={"profile_id": papa, "pin": "1234"}).json()   # learn along only
    # unlinking the last linked parent switches «only through Home Assistant» off again
    ingress.post("/api/parent/ha-link", json={"on": False}, headers={**hh, **HA})
    assert client.post("/api/parent/login", json={"pin": "1234"}).status_code == 200


def test_parent_with_home_assistant_user_and_no_pin(client):
    ph, _, _ = setup_family(client)
    assert client.post("/api/parent/profiles", json={"name": "Mama", "role": "parent"}, headers=ph).status_code == 400
    r = client.post("/api/parent/profiles", json={"name": "Mama", "role": "parent", "ha_user_id": "u-mama", "ha_user_name": "Mama"}, headers=ph)
    assert r.status_code == 200, r.text
    assert "Mama" not in [p["name"] for p in client.get("/api/profiles").json()]          # no PIN: no login in the app
    ingress = TestClient(client.app, client=("172.30.32.2", 50000))
    r = ingress.post("/api/parent/ha-login", headers={"X-Remote-User-Id": "u-mama", "X-Remote-User-Name": "mama"}).json()
    assert r["linked"] and r["profile"]["name"] == "Mama"
    # a PIN later: then Mama can also log in in the app on another device
    mama = r["profile"]["id"]
    assert client.put(f"/api/parent/profiles/{mama}", json={"name": "Mama", "role": "parent", "pin": "5678"}, headers=ph).status_code == 200
    assert "Mama" in [p["name"] for p in client.get("/api/profiles").json()]
    # removing the HA user and the PIN together is refused
    assert client.put(f"/api/parent/profiles/{mama}", json={"name": "Mama", "role": "parent", "pin": "", "ha_user_id": ""}, headers=ph).status_code == 400


def test_ha_panel_link(client, monkeypatch):
    """The «only in Home Assistant» page links to http(s)://<host>:<HA port>/<add-on slug>."""
    assert client.get("/api/ha-panel").json() == {}            # outside Home Assistant: no link
    import familyquest.netinfo as ni

    class R:
        def __init__(self, d): self.d = d
        def json(self): return {"data": self.d}

    class C:
        def __init__(self, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, path):
            return R({"slug": "8fb20791_family_quest_beta"} if "addons" in path else {"port": 8123, "ssl": False})

    monkeypatch.setattr(ni.httpx, "AsyncClient", C)
    monkeypatch.setattr(ni, "_PANEL", {})
    client.app.state.fq.settings.ha_token = "x"
    try:
        assert client.get("/api/ha-panel").json() == {"slug": "8fb20791_family_quest_beta", "port": 8123, "ssl": False}
    finally:
        client.app.state.fq.settings.ha_token = None


def test_release_notes(client):
    from test_api import setup_family
    ph, _, _ = setup_family(client)
    assert client.get("/api/parent/changelog").status_code in (401, 403)
    assert "## " in client.get("/api/parent/changelog", headers=ph).json()["text"]


def test_ingress_opens_the_parent_area_and_app_has_its_own_address(client, monkeypatch):
    import familyquest.api.auth as auth
    assert "kid.js" in client.get("/").text and "kid.js" in client.get("/app").text      # direct port: the app
    assert client.get("/app/", follow_redirects=False).headers["location"] == "../app"
    monkeypatch.setattr(auth, "INGRESS_IP", "testclient")                                # through Home Assistant
    assert "parent.js" in client.get("/").text and "kid.js" in client.get("/app").text
