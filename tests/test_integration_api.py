"""Family Quest HA integration: token, API /api/integration/…, parent settings, install into a config folder."""
import json
import re

import pytest

from familyquest import integration
from familyquest.settings import APP_DIR

from test_api import setup_family

COMPONENT = APP_DIR / "ha_integration" / "familyquest"


@pytest.fixture
def ha_config(tmp_path, monkeypatch):
    cfg = tmp_path / "ha_config"
    cfg.mkdir()
    monkeypatch.setattr(integration, "HA_CONFIG", cfg)
    monkeypatch.setenv("FQ_ADDON_HOST", "a0d7b954-family-quest")
    return cfg


def _switch_on(client, ph):
    r = client.put("/api/parent/integration", json={"enabled": True}, headers=ph)
    assert r.status_code == 200, r.text
    return r.json()


def test_off_by_default_and_token_hashed(client, ha_config):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    st = client.get("/api/parent/integration", headers=ph).json()
    assert st["enabled"] is False and st["has_token"] is False and not st["component"]["installed"]
    assert not (ha_config / "custom_components").exists()                 # nothing copied while off
    assert client.get("/api/integration/state", headers={"Authorization": "Bearer x"}).status_code == 403
    on = _switch_on(client, ph)
    token = on["token"]
    assert token.startswith("fqi_") and len(token) > 40
    assert on["url"] == "http://a0d7b954-family-quest:8099"
    stored = fq.db.get_setting("ha_integration")
    assert token not in json.dumps(stored) and stored["token_hash"] == integration._hash(token)
    # the hash is not part of the normal settings
    assert "ha_integration" not in client.get("/api/parent/settings", headers=ph).json()
    assert "ha_integration" not in client.put("/api/parent/settings", json={"sound": True}, headers=ph).json()
    # switching on again does not show (or change) the token
    assert _switch_on(client, ph)["token"] is None
    # parents only
    assert client.get("/api/parent/integration").status_code == 401
    assert client.put("/api/parent/integration", json={"enabled": False}).status_code == 401


def test_auth(client, ha_config):
    ph, mia, leo = setup_family(client)
    token = _switch_on(client, ph)["token"]
    assert client.get("/api/integration/state").status_code == 401
    assert client.get("/api/integration/state", headers={"Authorization": "Bearer fqi_wrong"}).status_code == 401
    # a parent or kid login is no integration token
    assert client.get("/api/integration/state", headers=ph).status_code == 401
    assert client.get("/api/integration/state", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    # a new token: the old one stops working
    new = client.post("/api/parent/integration/token", headers=ph).json()["token"]
    assert new != token
    assert client.get("/api/integration/state", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/integration/state", headers={"Authorization": f"Bearer {new}"}).status_code == 200
    # off → 403 even with the right token; on again → the same token works again
    client.put("/api/parent/integration", json={"enabled": False}, headers=ph)
    assert client.get("/api/integration/state", headers={"Authorization": f"Bearer {new}"}).status_code == 403
    assert client.post("/api/integration/action", json={"action": "add_points", "child": mia, "amount": 5},
                       headers={"Authorization": f"Bearer {new}"}).status_code == 403
    assert client.post("/api/parent/integration/token", headers=ph).status_code == 400
    _switch_on(client, ph)
    assert client.get("/api/integration/state", headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_wrong_tokens_are_throttled(client, ha_config):
    ph, mia, leo = setup_family(client)
    token = _switch_on(client, ph)["token"]
    codes = [client.get("/api/integration/state", headers={"Authorization": "Bearer nope"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_state_per_child(client, ha_config):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    token = _switch_on(client, ph)["token"]
    auth = {"Authorization": f"Bearer {token}"}
    fq.rewards.book(mia, "coins", 12, "manual", "test")
    fq.rewards.book(mia, "xp", 60, "answer_correct", "test")
    fq.db.x("UPDATE daily SET seconds=600, lessons=2 WHERE profile_id=?", mia)
    p = fq.db.q1("SELECT settings FROM profile WHERE id=?", leo)
    s = json.loads(p["settings"] or "{}")
    s["game_limit"] = {"all": 0, "days": {}}
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(s), leo)
    st = client.get("/api/integration/state", headers=auth).json()
    assert st["instance"] and st["version"] == "test"
    assert [a["key"] for a in st["accounts"]] == ["coins"]                 # spendable, active accounts only
    kids = {c["name"]: c for c in st["children"]}
    assert set(kids) == {"Mia", "Leo"}                                     # parents are no devices
    m = kids["Mia"]
    assert m["balances"]["coins"] == 12 and m["xp_today"] == 60 and m["goal_met"] and m["goal_percent"] == 100
    assert m["lessons_today"] == 2 and m["learn_minutes_today"] == 10 and m["total_xp"] == 60 and m["level"] >= 1
    assert m["internet"] is None and m["game_unlimited"] and m["game_left"] is None and not m["game_used_up"]
    assert m["offline_time"] is False
    assert kids["Leo"]["game_left"] == 0 and kids["Leo"]["game_used_up"]
    assert st["family"]["total_xp"] == 60 and st["family"]["running_games"] == 0 and st["family"]["open_votes"] == 0
    assert client.get("/api/parent/integration", headers=ph).json()["last_poll"]


def test_actions(client, ha_config):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    token = _switch_on(client, ph)["token"]
    auth = {"Authorization": f"Bearer {token}"}
    act = lambda **b: client.post("/api/integration/action", json=b, headers=auth)
    r = act(action="add_points", child="mia", account="coins", amount=10, reason="Garden")
    assert r.status_code == 200, r.text
    assert fq.rewards.balance(mia, "coins") == 10
    assert fq.db.q1("SELECT * FROM ledger WHERE profile_id=? AND account='coins'", mia)["ref"] == "ha_integration"
    assert act(action="add_points", child=leo, amount=-3).status_code == 200 and fq.rewards.balance(leo, "coins") == -3
    # whitelist and checks
    assert act(action="delete_profile", child=mia).status_code == 400
    assert act(action="add_points", child="Papa", amount=5).status_code == 400          # not a child
    assert act(action="add_points", child="Nobody", amount=5).status_code == 400
    assert act(action="add_points", child=mia, account="nope", amount=5).status_code == 400
    assert act(action="add_points", child=mia, amount=10 ** 6).status_code == 400
    assert act(action="add_points", child=mia, amount="NaN").status_code == 400
    assert act(action="add_points", child=mia, amount=0).status_code == 400
    assert act(action="internet_start", child=mia).status_code == 400                   # internet not set up
    # chore waiting for approval
    fq.chores.save({"name": "Tisch decken", "points": 5, "profiles": [mia], "confirm": True})
    tid = int(fq.chores.for_kid(mia)[0]["uid"][3:])
    fq.chores.mark_done(mia, tid)
    st = client.get("/api/integration/state", headers=auth).json()
    assert st["family"]["pending_approvals"] == 1 and st["pending_chores"][0]["task_id"] == tid
    assert act(action="approve_chore", task_id=tid).json()["status"] == "done"
    assert fq.rewards.balance(mia, "coins") == 15
    assert act(action="approve_chore", task_id=999999).status_code == 400
    assert act(action="approve_reward", redemption_id=999999).status_code == 400


def test_internet_switch(client, ha_config):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    calls = []
    fq.internet.switcher = lambda e, on: calls.append((e, on))
    p = fq.db.q1("SELECT settings FROM profile WHERE id=?", mia)
    s = json.loads(p["settings"] or "{}")
    s.update(internet_rule="switch.mia_block", internet_rule_blocks=True)
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(s), mia)
    fq.internet.ensure_account()
    fq.rewards.book(mia, "internet", 30, "manual", "test")
    token = _switch_on(client, ph)["token"]
    auth = {"Authorization": f"Bearer {token}"}
    net = {c["name"]: c for c in client.get("/api/integration/state", headers=auth).json()["children"]}["Mia"]["internet"]
    assert net["blocked"] and not net["running"] and net["minutes"] == 30 and not net["unlimited"]
    assert client.post("/api/integration/action", json={"action": "internet_start", "child": mia}, headers=auth).status_code == 200
    assert calls[-1] == ("switch.mia_block", False)
    net = {c["name"]: c for c in client.get("/api/integration/state", headers=auth).json()["children"]}["Mia"]["internet"]
    assert net["running"] and not net["blocked"]
    assert client.post("/api/integration/action", json={"action": "internet_stop", "child": "Mia"}, headers=auth).status_code == 200
    assert calls[-1] == ("switch.mia_block", True)


def test_install_and_remove(client, ha_config):
    ph, mia, leo = setup_family(client)
    on = _switch_on(client, ph)
    dst = ha_config / "custom_components" / "familyquest"
    assert on["install"]["installed"] and dst.is_dir()
    for name in ("__init__.py", "manifest.json", "config_flow.py", "sensor.py", "binary_sensor.py", "switch.py",
                 "services.yaml", "translations/en.json", "translations/de.json", "translations/fr.json"):
        assert (dst / name).is_file(), name
    man = json.loads((dst / "manifest.json").read_text())
    assert man["domain"] == "familyquest" and man["config_flow"] is True and man["requirements"] == []
    assert man["version"] == "0.0.0"                                        # «test» is no valid version
    assert json.loads((dst / "addon.json").read_text())["url"] == "http://a0d7b954-family-quest:8099"
    assert not list(dst.rglob("__pycache__"))
    st = client.get("/api/parent/integration", headers=ph).json()
    assert st["component"]["installed"] and st["config_writable"]
    # removing only while off
    assert client.delete("/api/parent/integration/component", headers=ph).status_code == 400
    client.put("/api/parent/integration", json={"enabled": False}, headers=ph)
    r = client.delete("/api/parent/integration/component", headers=ph).json()
    assert r["removed"] and not dst.exists()


def test_install_versions_and_start(fq, tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setattr(integration, "HA_CONFIG", cfg)
    r = integration.install("1.2.0", url="http://x:8099")
    assert r["changed"] and r["previous"] is None and r["version"] == "1.2.0"
    (cfg / "custom_components" / "familyquest" / "old_file.py").write_text("x")
    r = integration.install("1.2.0")
    assert not r["changed"] and not (cfg / "custom_components" / "familyquest" / "old_file.py").exists()
    integration.remove()
    integration.install_on_start(fq)                    # off: nothing is copied
    assert not (cfg / "custom_components" / "familyquest").exists()
    integration.set_enabled(fq, True)
    integration.install_on_start(fq)
    assert (cfg / "custom_components" / "familyquest" / "manifest.json").is_file()
    with pytest.raises(integration.IntegrationError):
        integration.install("1.0.0", base=tmp_path / "missing")


def test_supervisor_network_only(tmp_path, monkeypatch):
    """Inside the add-on (Home Assistant on, no direct access) only Home Assistant Core may call the API."""
    from fastapi.testclient import TestClient
    from familyquest.main import create_app
    from familyquest.settings import BUILTIN_PACKS, Settings
    monkeypatch.setattr(integration, "HA_CONFIG", tmp_path)
    st = Settings(data_dir=tmp_path, packs_dirs=[BUILTIN_PACKS], ha_enabled=True, ha_url="", ha_token=None,
                  secret=b"x" * 32, version="test")
    app = create_app(st)
    integration.set_enabled(app.state.fq, True)
    token = integration.new_token(app.state.fq)
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(app, client=("192.168.1.20", 5000)) as c:
        assert c.get("/api/integration/state", headers=auth).status_code == 403
    with TestClient(app, client=("172.30.32.2", 5000)) as c:          # ingress (browsers) – not Home Assistant Core
        assert c.get("/api/integration/state", headers=auth).status_code == 403
    app.state.fq.db.set_setting("allowed_networks", ["192.168.1.0/24"])  # the family firewall does not list the hassio net
    with TestClient(app, client=("172.30.32.1", 5000)) as c:
        assert c.get("/api/integration/state", headers=auth).status_code == 200
        assert c.get("/api/integration/state").status_code == 401
        assert c.get("/api/profiles").status_code == 403                 # the rest of the app stays closed


def test_component_python_compiles():
    files = sorted(COMPONENT.glob("*.py"))
    assert len(files) >= 8
    for f in files:
        compile(f.read_text(encoding="utf-8"), str(f), "exec")          # syntax only – Home Assistant is not installed here
    for f in [COMPONENT / "strings.json", *(COMPONENT / "translations").glob("*.json")]:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert {"config", "entity", "services"} <= set(d), f.name
    en = json.loads((COMPONENT / "translations" / "en.json").read_text())
    assert json.loads((COMPONENT / "strings.json").read_text()) == en
    def keys(d, pre=""):
        return {pre + k for k, v in d.items() for _ in [0]} | {x for k, v in d.items() if isinstance(v, dict) for x in keys(v, pre + k + ".")}
    def leaves(d):
        return [x for v in d.values() for x in (leaves(v) if isinstance(v, dict) else [v])]
    langs = {f.stem for f in (COMPONENT / "translations").glob("*.json")}
    # the languages of the app (Home Assistant codes): a French Home Assistant shows French entity names
    assert {"en", "de", "fr", "it", "es", "nl", "pl", "pt-BR", "sv"} <= langs
    for lang in langs - {"en"}:
        d = json.loads((COMPONENT / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
        assert keys(d) == keys(en), lang
        assert all(isinstance(v, str) and v.strip() for v in leaves(d)), lang
        for a, b in zip(leaves(en), leaves(d)):                 # placeholders like {account} kept
            assert set(re.findall(r"\{\w+\}", a)) == set(re.findall(r"\{\w+\}", b)), (lang, a, b)
