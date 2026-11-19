"""«Sign in with Home Assistant» in the app on the direct port (haauth.py, api/haauth.py) and Home Assistant-only parents."""
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from familyquest import haauth
from test_api import setup_family

USERS = {"code-mia": "u-mia", "code-papa": "u-papa", "code-anna": "u-anna", "code-nobody": "u-nobody"}
NAMES = {"u-mia": "Mia", "u-papa": "Papa", "u-anna": "Anna", "u-nobody": "Fremd"}


@pytest.fixture
def fake_ha(monkeypatch):
    """Home Assistant's /auth/token, /auth/revoke and the websocket «auth/current_user» – records what happens."""
    seen = {"token": [], "revoked": [], "access": []}
    issued = {}

    def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        if request.url.path == "/auth/token":
            seen["token"].append({k: v[0] for k, v in form.items()})
            code = form.get("code", [""])[0]
            if form.get("grant_type") != ["authorization_code"] or code not in USERS or not form.get("client_id"):
                return httpx.Response(400, json={"error": "invalid_request"})
            issued[f"acc-{code}"] = USERS[code]
            return httpx.Response(200, json={"access_token": f"acc-{code}", "refresh_token": f"ref-{code}", "token_type": "Bearer", "expires_in": 1800})
        if request.url.path == "/auth/revoke":
            seen["revoked"].append(form["token"][0])
            return httpx.Response(200)
        if request.url.path == "/auth/providers":
            return httpx.Response(200, json={"providers": [{"type": "homeassistant"}]})
        return httpx.Response(404)

    async def current_user(base, access_token):
        seen["access"].append((base, access_token))
        uid = issued[access_token]
        return {"id": uid, "name": NAMES[uid], "is_admin": uid == "u-papa"}

    monkeypatch.setattr(haauth, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(haauth, "current_user", current_user)
    haauth._used.clear()
    return seen


def _link(client, ph, pid, name, uid, role="kid", **extra):
    r = client.put(f"/api/parent/profiles/{pid}", json={"name": name, "role": role, "ha_user_id": uid, "ha_user_name": name, **extra}, headers=ph)
    assert r.status_code == 200, r.text


def _family(client, kids=True, on=True):
    ph, mia, leo = setup_family(client)
    papa = next(p for p in client.get("/api/profiles").json() if p["name"] == "Papa")["id"]
    _link(client, ph, mia, "Mia", "u-mia")
    _link(client, ph, papa, "Papa", "u-papa", "parent")
    client.put("/api/parent/settings", json={"kid_ha_login": kids, "ha_app_login": on}, headers=ph)
    return ph, mia, leo, papa


def _flow(client, code):
    r = client.post("/api/ha-auth/start", json={"base": "http://testserver/"})
    assert r.status_code == 200, r.text
    url, nonce = r.json()["url"], r.json()["nonce"]
    q = parse_qs(urlsplit(url).query)
    assert url.startswith("http://testserver:8123/auth/authorize?")
    assert q["client_id"] == ["http://testserver/"] and q["redirect_uri"] == ["http://testserver/ha-auth/callback"]
    assert q["response_type"] == ["code"]
    # Home Assistant sends the browser back: on to the app with code and state
    cb = client.get("/ha-auth/callback", params={"code": code, "state": q["state"][0]}, follow_redirects=False)
    assert cb.status_code == 303 and cb.headers["location"].startswith("../#/ha-auth?")
    back = parse_qs(cb.headers["location"].split("?", 1)[1])
    return client.post("/api/ha-auth/finish", json={"code": back["code"][0], "state": back["state"][0], "nonce": nonce}), q["state"][0], nonce


def test_off_by_default_and_hidden(client, fake_ha):
    ph, mia, leo, papa = _family(client, on=False)
    assert client.get("/api/info").json()["ha_app_login"] is False
    assert client.post("/api/ha-auth/start", json={"base": "http://testserver/"}).status_code == 404
    assert client.post("/api/ha-auth/finish", json={"code": "x", "state": "y", "nonce": "z"}).status_code == 404
    assert client.get("/ha-auth/callback", params={"code": "x"}, follow_redirects=False).status_code == 404
    client.put("/api/parent/settings", json={"ha_app_login": True}, headers=ph)
    assert client.get("/api/info").json()["ha_app_login"] is True
    # inside Home Assistant (ingress) the trusted headers are used instead – not offered there
    ingress = TestClient(client.app, client=("172.30.32.2", 50000))
    assert ingress.get("/api/info").json()["ha_app_login"] is False
    assert ingress.post("/api/ha-auth/start", json={"base": "http://testserver/"}).status_code == 404
    # nobody linked: not offered
    _link(client, ph, mia, "Mia", ""); _link(client, ph, papa, "Papa", "", "parent")
    assert client.get("/api/info").json()["ha_app_login"] is False


def test_kid_signs_in_and_tokens_are_revoked(client, fake_ha):
    ph, mia, leo, papa = _family(client)
    r, _, _ = _flow(client, "code-mia")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["profile"]["id"] == mia and "parent_token" not in d
    assert client.get("/api/me", headers={"X-FQ-Token": d["token"]}).json()["profile"]["name"] == "Mia"
    # a child never gets into the parent area with it
    assert client.get("/api/parent/meta", headers={"X-FQ-Parent": d["token"]}).status_code == 401
    # the exchange was done server side with the app as client_id; the Home Assistant tokens were revoked right away
    assert fake_ha["token"][-1] == {"grant_type": "authorization_code", "code": "code-mia", "client_id": "http://testserver/"}
    assert fake_ha["revoked"] == ["ref-code-mia"]
    # … and not kept anywhere
    db = client.app.state.fq.db
    dump = "\n".join(str(tuple(r)) for t in ("setting", "profile", "login_log") for r in db.q(f"SELECT * FROM {t}"))
    assert "acc-code-mia" not in dump and "ref-code-mia" not in dump
    assert db.val("SELECT COUNT(*) FROM login_log WHERE profile_id=? AND ok=1", mia, default=0) >= 1


def test_kid_only_with_the_option(client, fake_ha):
    _family(client, kids=False)
    r, _, _ = _flow(client, "code-mia")
    assert r.status_code == 403 and "not linked" in r.json()["detail"]
    assert fake_ha["revoked"] == ["ref-code-mia"]


def test_parent_gets_the_app_login_like_with_the_pin(client, fake_ha):
    ph, mia, leo, papa = _family(client)
    d = _flow(client, "code-papa")[0].json()
    assert d["profile"]["id"] == papa and d["parent_token"]
    assert client.get("/api/me", headers={"X-FQ-Token": d["token"]}).json()["profile"]["name"] == "Papa"
    # parent area only in Home Assistant: no parent token, the parent area stays closed on this port
    client.app.state.fq.db.set_setting("parent_ha_only", True)
    d = _flow(client, "code-papa")[0].json()
    assert "parent_token" not in d and d["token"]
    assert client.get("/api/parent/meta", headers={"X-FQ-Parent": ph["X-FQ-Parent"]}).status_code == 403


def test_unlinked_user_and_bad_codes(client, fake_ha):
    _family(client)
    r = _flow(client, "code-nobody")[0]
    assert r.status_code == 403 and r.json()["detail"] == "Your Home Assistant user is not linked with a profile – ask your parents"
    r = _flow(client, "code-wrong")[0]
    assert r.status_code == 403 and "did not accept" in r.json()["detail"]
    db = client.app.state.fq.db
    assert db.val("SELECT COUNT(*) FROM login_log WHERE ok=0", default=0) >= 2


def test_state_checks(client, fake_ha):
    _family(client)
    _, state, nonce = _flow(client, "code-mia")
    # used once only
    assert client.post("/api/ha-auth/finish", json={"code": "code-mia", "state": state, "nonce": nonce}).status_code == 403
    # another tab / device without the nonce cannot finish somebody else's flow
    r = client.post("/api/ha-auth/start", json={"base": "http://testserver/"}).json()
    st = parse_qs(urlsplit(r["url"]).query)["state"][0]
    assert client.post("/api/ha-auth/finish", json={"code": "code-mia", "state": st, "nonce": "guess"}).status_code == 403
    assert client.post("/api/ha-auth/finish", json={"code": "code-mia", "state": st + "x", "nonce": r["nonce"]}).status_code == 403
    # expired
    fq = client.app.state.fq
    old = haauth._serializer(fq)
    import time as _t
    real = _t.time
    try:
        _t.time = lambda: real() - haauth.STATE_MAX_AGE - 5
        s2, n2 = haauth.make_state(fq, "http://testserver/", "http://testserver:8123")
    finally:
        _t.time = real
    assert old.loads(s2)                     # signed fine …
    r2 = client.post("/api/ha-auth/finish", json={"code": "code-mia", "state": s2, "nonce": n2})
    assert r2.status_code == 403 and "too long" in r2.json()["detail"]
    # an app address of another host is refused
    assert client.post("/api/ha-auth/start", json={"base": "http://evil.example/"}).status_code == 400
    assert client.post("/api/ha-auth/start", json={"base": "javascript:alert(1)//"}).status_code == 400


def test_address_setting_and_test(client, fake_ha):
    ph, *_ = _family(client)
    assert client.put("/api/parent/settings", json={"ha_app_login_url": "ftp://x"}, headers=ph).status_code == 400
    assert client.put("/api/parent/settings", json={"ha_app_login": "yes"}, headers=ph).status_code == 400
    r = client.put("/api/parent/settings", json={"ha_app_login_url": "https://ha.example.org:8443/"}, headers=ph)
    assert r.status_code == 200 and r.json()["ha_app_login_url"] == "https://ha.example.org:8443"
    url = client.post("/api/ha-auth/start", json={"base": "http://testserver/"}).json()["url"]
    assert url.startswith("https://ha.example.org:8443/auth/authorize?")
    st = client.get("/api/parent/ha-app-login", headers=ph).json()
    assert st["on"] and st["url"] == "https://ha.example.org:8443" and {p["name"] for p in st["linked"]} == {"Mia", "Papa"}
    assert client.post("/api/parent/ha-app-login/test", json={"url": ""}, headers=ph).json() == {"url": "https://ha.example.org:8443", "server": True}
    client.put("/api/parent/settings", json={"ha_app_login_url": ""}, headers=ph)
    assert client.get("/api/parent/ha-app-login", headers=ph).json()["auto"] == "http://testserver:8123"
    assert client.get("/api/parent/ha-app-login").status_code == 401


def test_parent_without_pin_is_listed_with_ha_login(client, fake_ha):
    ph, mia, leo, papa = _family(client)
    # Anna: parent with only a Home Assistant user (no PIN)
    r = client.post("/api/parent/profiles", json={"name": "Anna", "role": "parent", "ha_user_id": "u-anna", "ha_user_name": "Anna"}, headers=ph)
    assert r.status_code == 200, r.text
    anna = r.json()["id"]
    prof = {p["name"]: p for p in client.get("/api/profiles").json()}
    assert prof["Anna"]["ha_login"] and not prof["Anna"]["has_pin"]
    assert prof["Papa"]["ha_login"] and prof["Papa"]["has_pin"] and prof["Mia"]["ha_login"] and "ha_login" not in prof["Leo"]
    # a PIN login is still impossible for her
    assert client.post("/api/login", json={"profile_id": anna}).status_code == 403
    assert _flow(client, "code-anna")[0].json()["profile"]["id"] == anna
    # feature off: hidden again like before
    client.put("/api/parent/settings", json={"ha_app_login": False}, headers=ph)
    assert "Anna" not in {p["name"] for p in client.get("/api/profiles").json()}
    assert all("ha_login" not in p for p in client.get("/api/profiles").json())


def test_setup_without_pin_only_through_home_assistant(client):
    assert client.post("/api/setup", json={"name": "Papa"}).status_code == 400
    assert client.post("/api/setup", json={"name": "Papa", "pin": "12"}).status_code == 400
    ingress = TestClient(client.app, client=("172.30.32.2", 50000))
    hdr = {"X-Remote-User-Id": "u-papa", "X-Remote-User-Name": "papa", "X-Remote-User-Display-Name": "Papa"}
    assert ingress.post("/api/setup", json={"name": "Papa"}).status_code == 400          # ingress, but no user
    r = ingress.post("/api/setup", json={"name": "Papa"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert not r.json()["profile"]["has_pin"]
    ph = {"X-FQ-Parent": r.json()["parent_token"]}
    me = next(p for p in ingress.get("/api/parent/profiles", headers={**ph, **hdr}).json() if p["name"] == "Papa")
    assert me["settings"]["ha_user_id"] == "u-papa"
    # the parent area opens with the Home Assistant user; the PIN login has nobody to match
    assert ingress.post("/api/parent/ha-login", headers=hdr).json()["parent_token"]
    assert client.post("/api/parent/login", json={"pin": "0000"}).status_code == 403
    # unlinking without a PIN would lock this parent out
    assert ingress.post("/api/parent/ha-link", json={"on": False}, headers={**ph, **hdr}).status_code == 400
    # a PIN added later in the profile works
    pid = me["id"]
    r = client.put(f"/api/parent/profiles/{pid}", json={"name": "Papa", "role": "parent", "pin": "4321"}, headers=ph)
    assert r.status_code == 200, r.text
    assert client.post("/api/parent/login", json={"pin": "4321"}).status_code == 200


def test_kid_without_pin_linked_signs_in_only_with_home_assistant(client, fake_ha):
    ph, mia, leo, papa = _family(client)
    assert client.post("/api/login", json={"profile_id": leo}).status_code == 200          # not linked: as before
    _link(client, ph, leo, "Leo", "u-leo")
    assert client.post("/api/login", json={"profile_id": leo}).status_code == 403
    assert next(p for p in client.get("/api/profiles").json() if p["id"] == leo)["ha_login"]
    client.put("/api/parent/settings", json={"ha_app_login": False}, headers=ph)
    assert client.post("/api/login", json={"profile_id": leo}).status_code == 200          # feature off: as before
