"""The explicit sign-in of a profile (profile setting «login»: none | pin | ha | pin_ha) – chosen in the profile dialog,
checked when saved and enforced on every login path."""
import json

from fastapi.testclient import TestClient

from familyquest.db import Database
from test_api import setup_family
from test_ha_app_login import _flow, fake_ha  # noqa: F401 – the fixture

MIA = {"X-Remote-User-Id": "u-mia", "X-Remote-User-Name": "mia", "X-Remote-User-Display-Name": "Mia"}
PAPA = {"X-Remote-User-Id": "u-papa", "X-Remote-User-Name": "papa", "X-Remote-User-Display-Name": "Papa"}


def _ingress(client):
    return TestClient(client.app, client=("172.30.32.2", 50000))


def _papa(client):
    return next(p for p in client.get("/api/profiles").json() if p["name"] == "Papa")["id"]


def _put(client, ph, pid, name, login, role="kid", **extra):
    return client.put(f"/api/parent/profiles/{pid}", json={"name": name, "role": role, "login": login, **extra}, headers=ph)


def _mode(client, pid):
    return next(p for p in client.get("/api/profiles").json() + [{"id": None}] if p["id"] == pid).get("login")


def _row(client, pid):
    return client.app.state.fq.db.q1("SELECT * FROM profile WHERE id=?", pid)


# ---------------------------------------------------------------- validation
def test_validation_in_the_dialog_rules(client):
    ph, mia, leo = setup_family(client)
    papa = _papa(client)
    assert _put(client, ph, leo, "Leo", "magic").status_code == 400
    # Home Assistant options need a user
    assert _put(client, ph, leo, "Leo", "ha").status_code == 400
    assert _put(client, ph, leo, "Leo", "pin_ha", pin="1234").status_code == 400
    # PIN options need a PIN – unless the profile has one
    assert _put(client, ph, leo, "Leo", "pin").status_code == 400
    assert _put(client, ph, leo, "Leo", "pin_ha", ha_user_id="u-leo", ha_user_name="Leo").status_code == 400
    assert _put(client, ph, mia, "Mia", "pin").status_code == 200                        # keeps her PIN
    assert _put(client, ph, leo, "Leo", "pin", pin="2222").status_code == 200
    # parents never «No sign-in»
    assert _put(client, ph, papa, "Papa", "none", "parent").status_code == 400
    r = client.post("/api/parent/profiles", json={"name": "Eva", "role": "parent", "login": "none", "pin": "1234"}, headers=ph)
    assert r.status_code == 400
    r = client.post("/api/parent/profiles", json={"name": "Eva", "role": "parent", "login": "ha"}, headers=ph)
    assert r.status_code == 400
    r = client.post("/api/parent/profiles", json={"name": "Eva", "role": "parent", "login": "ha", "ha_user_id": "u-eva", "ha_user_name": "Eva"}, headers=ph)
    assert r.status_code == 200 and r.json()["login"] == "ha" and not r.json()["has_pin"]
    # a new child: «No sign-in» without anything
    r = client.post("/api/parent/profiles", json={"name": "Ben", "login": "none"}, headers=ph)
    assert r.status_code == 200 and r.json()["login"] == "none"


def test_choice_removes_what_it_does_not_use(client):
    ph, mia, leo = setup_family(client)
    # Home Assistant only: the PIN is gone
    assert _put(client, ph, mia, "Mia", "ha", ha_user_id="u-mia", ha_user_name="Mia").status_code == 200
    assert _row(client, mia)["pin_hash"] is None and _mode(client, mia) == "ha"
    # PIN or Home Assistant: needs a new PIN now, keeps the user
    assert _put(client, ph, mia, "Mia", "pin_ha").status_code == 400
    assert _put(client, ph, mia, "Mia", "pin_ha", pin="3333").status_code == 200
    st = json.loads(_row(client, mia)["settings"])
    assert st["ha_user_id"] == "u-mia" and st["login"] == "pin_ha"
    # PIN: the Home Assistant user is unlinked (also when the client still sends it)
    assert _put(client, ph, mia, "Mia", "pin", ha_user_id="u-mia", ha_user_name="Mia").status_code == 200
    st = json.loads(_row(client, mia)["settings"])
    assert "ha_user_id" not in st and st["login"] == "pin" and _row(client, mia)["pin_hash"]
    # No sign-in: PIN and user gone
    assert _put(client, ph, mia, "Mia", "none").status_code == 200
    assert _row(client, mia)["pin_hash"] is None and _mode(client, mia) == "none"


# ---------------------------------------------------------------- each mode on each login path
def test_mode_none(client, fake_ha):
    ph, mia, leo = setup_family(client)
    assert _mode(client, leo) == "none"
    assert client.post("/api/login", json={"profile_id": leo}).status_code == 200
    assert client.post("/api/login", json={"profile_id": leo, "pin": "9999"}).status_code == 200


def test_mode_pin_refuses_home_assistant(client, fake_ha):
    ph, mia, leo = setup_family(client)
    client.put("/api/parent/settings", json={"ha_app_login": True}, headers=ph)
    assert _put(client, ph, mia, "Mia", "pin_ha", ha_user_id="u-mia", ha_user_name="Mia").status_code == 200
    assert _put(client, ph, mia, "Mia", "pin").status_code == 200
    # the user is unlinked – and even a link written into the settings behind its back does not count
    fq = client.app.state.fq
    st = json.loads(_row(client, mia)["settings"]); st.update(ha_user_id="u-mia", ha_user_name="Mia")
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), mia)
    assert client.post("/api/login", json={"profile_id": mia}).status_code == 403
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200
    ing = _ingress(client)
    assert ing.post("/api/ha-login", headers=MIA).json() == {"linked": False}
    assert ing.get("/api/info", headers=MIA).json()["ha_kid"] is None
    assert client.post("/api/ha-auth/start", json={"base": "http://testserver/"}).status_code == 404   # nobody may use it


def test_mode_ha_refuses_the_pin(client, fake_ha):
    ph, mia, leo = setup_family(client)
    client.put("/api/parent/settings", json={"ha_app_login": True}, headers=ph)
    assert _put(client, ph, mia, "Mia", "ha", ha_user_id="u-mia", ha_user_name="Mia").status_code == 200
    # a PIN hash left behind (e.g. an old database) does not open it
    fq = client.app.state.fq
    from familyquest.api.auth import hash_pin
    fq.db.x("UPDATE profile SET pin_hash=? WHERE id=?", hash_pin("1111"), mia)
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 403
    assert client.post("/api/login", json={"profile_id": mia}).status_code == 403
    assert _ingress(client).post("/api/login", json={"profile_id": mia}, headers=MIA).status_code == 403
    # the child cannot set a PIN itself either
    r = _ingress(client).post("/api/ha-login", headers=MIA).json()
    assert r["linked"] and r["profile"]["login"] == "ha"
    kh = {"X-FQ-Token": r["token"]}
    assert client.post("/api/me/pin", json={"old_pin": "1111", "pin": "4444"}, headers=kh).status_code == 403
    # Home Assistant: sidebar and «Sign in with Home Assistant»
    res, _, _ = _flow(client, "code-mia")
    assert res.status_code == 200 and res.json()["profile"]["id"] == mia
    assert next(p for p in client.get("/api/profiles").json() if p["id"] == mia)["ha_login"]


def test_mode_pin_ha_both(client, fake_ha):
    ph, mia, leo = setup_family(client)
    client.put("/api/parent/settings", json={"ha_app_login": True}, headers=ph)
    assert _put(client, ph, mia, "Mia", "pin_ha", ha_user_id="u-mia", ha_user_name="Mia").status_code == 200
    assert client.post("/api/login", json={"profile_id": mia}).status_code == 403
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200
    assert _ingress(client).post("/api/ha-login", headers=MIA).json()["linked"]
    assert _flow(client, "code-mia")[0].status_code == 200


def test_parent_modes_on_every_path(client, fake_ha):
    ph, mia, leo = setup_family(client)
    papa = _papa(client)
    ing = _ingress(client)
    # pin: parent area PIN, app PIN – no Home Assistant
    assert client.post("/api/parent/login", json={"pin": "1234"}).status_code == 200
    assert ing.post("/api/parent/ha-login", headers=PAPA).json().get("linked") is False
    # pin_ha: both
    r = _put(client, ph, papa, "Papa", "pin_ha", "parent", ha_user_id="u-papa", ha_user_name="Papa")
    assert r.status_code == 200
    ph = {"X-FQ-Parent": r.json()["parent_token"]}
    client.put("/api/parent/settings", json={"ha_app_login": True}, headers=ph)
    assert client.post("/api/parent/login", json={"pin": "1234"}).status_code == 200
    assert ing.post("/api/parent/ha-login", headers=PAPA).json()["linked"]
    assert _flow(client, "code-papa")[0].json().get("parent_token")
    # ha: the PIN no longer opens anything (also a PIN hash left behind)
    r = _put(client, ph, papa, "Papa", "ha", "parent", ha_user_id="u-papa", ha_user_name="Papa")
    assert r.status_code == 200
    ph = {"X-FQ-Parent": r.json()["parent_token"]}
    from familyquest.api.auth import hash_pin
    client.app.state.fq.db.x("UPDATE profile SET pin_hash=? WHERE id=?", hash_pin("1234"), papa)
    ph = {"X-FQ-Parent": client.app.state.fq.tokens.make(papa, "parent")}
    assert client.post("/api/parent/login", json={"pin": "1234"}).status_code == 403
    assert client.post("/api/login", json={"profile_id": papa, "pin": "1234"}).status_code == 403
    assert ing.post("/api/parent/ha-login", headers=PAPA).json()["linked"]
    assert _flow(client, "code-papa")[0].status_code == 200
    # listed in the app only with «Sign in with Home Assistant» on
    assert next(p for p in client.get("/api/profiles").json() if p["id"] == papa)["login"] == "ha"
    client.put("/api/parent/settings", json={"ha_app_login": False}, headers=ph)
    assert papa not in [p["id"] for p in client.get("/api/profiles").json()]


def test_ha_link_of_the_parent_area_keeps_the_choice(client):
    ph, mia, leo = setup_family(client)
    papa = _papa(client)
    ing = _ingress(client)
    assert ing.post("/api/parent/ha-link", json={"on": True}, headers={**ph, **PAPA}).status_code == 200
    assert _mode(client, papa) == "pin_ha"
    assert ing.post("/api/parent/ha-link", json={"on": False}, headers={**ph, **PAPA}).status_code == 200
    assert _mode(client, papa) == "pin"


def test_kid_setting_its_own_pin_leaves_no_sign_in(client):
    ph, mia, leo = setup_family(client)
    kh = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    r = client.post("/api/me/pin", json={"pin": "5555"}, headers=kh)
    assert r.status_code == 200 and r.json()["profile"]["login"] == "pin"
    assert client.post("/api/login", json={"profile_id": leo}).status_code == 403
    assert client.post("/api/login", json={"profile_id": leo, "pin": "5555"}).status_code == 200


def test_profile_list_shows_the_sign_in(client):
    ph, mia, leo = setup_family(client)
    assert _put(client, ph, leo, "Leo", "ha", ha_user_id="u-leo", ha_user_name="Leo").status_code == 200
    app = {p["name"]: p["login"] for p in client.get("/api/profiles").json()}
    assert app == {"Mia": "pin", "Leo": "ha", "Papa": "pin"}
    parent = {p["name"]: (p["login"], p["settings"]["login"]) for p in client.get("/api/parent/profiles", headers=ph).json()}
    assert parent["Leo"] == ("ha", "ha") and parent["Mia"] == ("pin", "pin")


def test_old_clients_without_a_choice_follow_pin_and_user(client):
    ph, mia, leo = setup_family(client)
    r = client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "ha_user_id": "u-mia", "ha_user_name": "Mia"}, headers=ph)
    assert r.json()["login"] == "pin_ha"
    r = client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin": ""}, headers=ph)
    assert r.json()["login"] == "ha"


# ---------------------------------------------------------------- migration
def test_migration_derives_the_sign_in_once(tmp_path):
    from familyquest.api.auth import hash_pin
    path = tmp_path / "fq.db"
    db = Database(path)
    rows = [("Both", "kid", True, "u1"), ("Pin", "kid", True, None), ("Ha", "kid", False, "u2"), ("Tap", "kid", False, None),
            ("ParentHa", "parent", False, "u3"), ("Lost", "parent", False, None), ("ParentPin", "parent", True, None)]
    for name, role, pin, uid in rows:
        st = {"daily_goal": 33, **({"ha_user_id": uid, "ha_user_name": name} if uid else {})}
        db.x("INSERT INTO profile(name, role, color, pin_hash, settings) VALUES(?,?,?,?,?)", name, role, "#000",
             hash_pin("1234") if pin else None, json.dumps(st))
    db.x("INSERT INTO profile(name, role, color, settings) VALUES('Chosen', 'kid', '#000', ?)", json.dumps({"login": "pin"}))
    db.conn.close()
    db = Database(path)                                      # the start migrates
    got = {r["name"]: json.loads(r["settings"]) for r in db.q("SELECT * FROM profile")}
    assert {k: v["login"] for k, v in got.items()} == {"Both": "pin_ha", "Pin": "pin", "Ha": "ha", "Tap": "none",
                                                       "ParentHa": "ha", "Lost": "pin", "ParentPin": "pin", "Chosen": "pin"}
    assert got["Both"]["daily_goal"] == 33 and got["Both"]["ha_user_id"] == "u1"            # nothing else changed
    assert db.val("SELECT COUNT(*) FROM profile WHERE pin_hash IS NOT NULL") == 3
