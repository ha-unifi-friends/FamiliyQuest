"""Home Assistant integration against a fake client (no network)."""
import asyncio
import json
import threading
from pathlib import Path

import pytest
import yaml

from familyquest.ha.service import HAService

ROOT = Path(__file__).resolve().parent.parent


class FakeClient:
    def __init__(self):
        self.connected = asyncio.Event()
        self.on_connect = []
        self.calls = []
        self.states_set = {}
        self.events = []
        self.subs = []
        self.items = {"todo.mia_chores": [{"uid": "u1", "summary": "Tisch decken", "status": "needs_action"},
                                          {"uid": "u2", "summary": "Abfall", "status": "completed"}]}
        self.state = {"input_number.mia_internet": {"state": "10", "attributes": {"max": 120}},
                      "sensor.mia_reliability": {"state": "80", "attributes": {"open_today": 1, "done_today": 1, "streak": 3,
                                                                              "week_done": 6, "week_total": 8}}}

    def subscribe(self, et, handler):
        self.subs.append((et, handler))

    async def command(self, msg, timeout=15):
        t = msg["type"]
        if t == "config/entity_registry/list":
            return [
                {"entity_id": "todo.mia_chores", "platform": "family_planer", "device_id": "d1", "unique_id": "E1_p1_chores"},
                {"entity_id": "sensor.mia_reliability", "platform": "family_planer", "device_id": "d1", "unique_id": "E1_p1_reliability"},
                {"entity_id": "sensor.mia_points", "platform": "family_planer", "device_id": "d1", "unique_id": "E1_p1_points"},
                {"entity_id": "light.kitchen", "platform": "hue", "device_id": "d9"},
                {"entity_id": "light.mia_desk", "platform": "hue", "area_id": "mia_room"},
                {"entity_id": "switch.mia_fan_child_lock", "platform": "x", "area_id": "mia_room", "entity_category": "config"},
            ]
        if t == "config/area_registry/list":
            return [{"area_id": "mia_room", "name": "Zimmer Mia"}, {"area_id": "kitchen", "name": "Küche"}]
        if t == "config/device_registry/list":
            return [{"id": "d1", "identifiers": [["family_planer", "E1_p1"]], "config_entries": ["E1"], "name": "Mia"},
                    {"id": "d9", "identifiers": [["hue", "x"]], "config_entries": ["H"], "name": "Lamp", "area_id": "kitchen"}]
        if t == "todo/item/list":
            return {"items": self.items.get(msg["entity_id"], [])}
        raise AssertionError(t)

    async def call(self, domain, service, data):
        self.calls.append((domain, service, data))
        if domain == "todo" and service == "update_item":
            for it in self.items[data["entity_id"]]:
                if it["uid"] == data["item"]:
                    it["status"] = data["status"]
        if service == "set_value":
            self.state[data["entity_id"]]["state"] = str(data["value"])

    async def get_state(self, eid):
        return self.state.get(eid)

    async def set_state(self, eid, state, attrs):
        self.states_set[eid] = (state, attrs)

    async def fire(self, event, data):
        self.events.append((event, data))

    async def config(self):
        return {"language": "de"}

    async def states(self):
        return [{"entity_id": k, **v} for k, v in self.state.items()] + list(getattr(self, "state_list", []))


@pytest.fixture
def ha(fq, kid):
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    client = FakeClient()
    svc = HAService(fq, client, loop)
    fq.ha = svc
    asyncio.run_coroutine_threadsafe(_connect(client), loop).result(5)
    asyncio.run_coroutine_threadsafe(svc.refresh_planer(), loop).result(5)
    yield svc, client
    loop.call_soon_threadsafe(loop.stop)


async def _connect(client):
    client.connected.set()


def test_planer_persons_and_chores(fq, kid, ha):
    svc, client = ha
    persons = svc.planer_persons()
    assert persons == [{"id": "p1", "name": "Mia", "chores": "todo.mia_chores", "reliability": "sensor.mia_reliability",
                        "points": "sensor.mia_points", "linked_to": None}]
    fq.db.x("UPDATE profile SET planer_person_id='p1' WHERE id=?", kid)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    chores = svc.chores(prof)
    assert [c["summary"] for c in chores] == ["Tisch decken", "Abfall"] and chores[1]["done"]
    assert svc.complete_chore(prof, "u1")
    assert fq.rewards.balance(kid, "coins") == 10
    assert not svc.complete_chore(prof, "nope")                 # unknown chore: nothing booked
    assert not svc.complete_chore(prof, "u2")                   # already done
    assert fq.rewards.balance(kid, "coins") == 10
    svc._award_chore(kid, "u1", {}, "Tisch decken")          # second time the same day: no double booking
    assert fq.rewards.balance(kid, "coins") == 10
    stats = svc.chore_stats(prof)
    assert stats["reliability"] == 80 and stats["week_percent"] == 75


def test_internet_minutes_action(fq, kid, ha):
    svc, client = ha
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps({"internet_entity": "input_number.mia_internet"}), kid)
    fq.rewards.book(kid, "coins", 100, "test")
    offer = next(o for o in fq.shop.offers(kid) if o["kind"] == "internet_minutes")
    red = fq.shop.redeem(kid, offer["id"])
    assert red["status"] == "approved"
    assert client.state["input_number.mia_internet"]["state"] == "25.0"
    assert ("input_number", "set_value", {"entity_id": "input_number.mia_internet", "value": 25.0}) in client.calls


def test_publish_sensors(fq, kid, ha):
    svc, client = ha
    fq.rewards.book(kid, "xp", 60, "test")
    fq.rewards.emit(kid, "answer_correct")
    asyncio.run_coroutine_threadsafe(svc._publish(kid), svc.loop).result(5)
    assert client.states_set["sensor.family_quest_mia_xp_heute"][0] == 61
    assert client.states_set["binary_sensor.family_quest_mia_tagesziel"][0] == "on"
    assert "sensor.family_quest_mia_coins" in client.states_set
    assert "sensor.family_quest_mia_streak" in client.states_set


def test_approval_push_and_action(fq, kid, ha):
    svc, client = ha
    fq.db.set_setting("notify_service", "notify.mobile_app_papa")
    fq.rewards.book(kid, "coins", 100, "test")
    ice = next(o for o in fq.shop.offers(kid) if o["name"] == "Ice cream")
    red = fq.shop.redeem(kid, ice["id"])
    import time
    time.sleep(0.2)
    push = [c for c in client.calls if c[0] == "notify"]
    assert push and push[0][1] == "mobile_app_papa"
    actions = push[0][2]["data"]["actions"]
    assert actions[0]["action"] == f"FQ_APPROVE_{red['id']}"
    asyncio.run_coroutine_threadsafe(svc._on_action({"data": {"action": f"FQ_APPROVE_{red['id']}"}}), svc.loop).result(5)
    assert fq.shop.get(red["id"])["status"] == "approved"


def test_addon_config_and_translations():
    cfg = yaml.safe_load((ROOT / "family_quest/config.yaml").read_text())
    assert cfg["ingress"] is True and cfg["slug"] == "family_quest"
    for f in (ROOT / "family_quest/translations").glob("*.yaml"):
        t = yaml.safe_load(f.read_text())
        assert set(t["configuration"]) == set(cfg["options"]), f.name


def test_beta_app_config():
    """Beta app next to the stable one: own slug and name, same options."""
    beta = ROOT / "family_quest_beta" / "config.yaml"
    if not beta.is_file():
        return
    b, s = yaml.safe_load(beta.read_text()), yaml.safe_load((ROOT / "family_quest/config.yaml").read_text())
    assert b["slug"] == "family_quest_beta" and b["name"] == "Family Quest Beta" and b["url"] == s["url"]
    assert set(b["options"]) == set(s["options"]) and (ROOT / "family_quest_beta" / "icon.png").is_file()
    assert "-beta." in str(b["version"])
    # direct access works out of the box once switched on – each app on its own host port
    assert s["ports"]["8099/tcp"] == 8099 and b["ports"]["8099/tcp"] == 8098


def test_chore_push_and_sensor(fq, kid, ha):
    svc, client = ha
    fq.db.set_setting("notify_service", "notify.mobile_app_papa")
    fq.chores.save({"name": "Tisch decken", "points": 5, "profiles": [kid], "confirm": True})
    tid = int(fq.chores.for_kid(kid)[0]["uid"][3:])
    fq.chores.mark_done(kid, tid)
    import time
    time.sleep(0.2)
    push = [c for c in client.calls if c[0] == "notify"]
    assert push and push[-1][2]["data"]["actions"][1]["action"] == f"FQ_CHORE_AGAIN_{tid}"
    asyncio.run_coroutine_threadsafe(svc._on_action({"data": {"action": f"FQ_CHORE_AGAIN_{tid}"}}), svc.loop).result(5)
    assert fq.chores.for_kid(kid)[0]["redo"]
    fq.chores.mark_done(kid, tid)
    asyncio.run_coroutine_threadsafe(svc._on_action({"data": {"action": f"FQ_CHORE_OK_{tid}"}}), svc.loop).result(5)
    assert fq.rewards.balance(kid, "coins") == 5
    asyncio.run_coroutine_threadsafe(svc._publish(kid), svc.loop).result(5)
    assert client.states_set["sensor.family_quest_mia_aemtli_offen"][0] == 0


def test_push_to_every_parent(fq, kid, ha):
    svc, client = ha
    import json as _j
    fq.db.x("INSERT INTO profile(name, role, pin_hash, settings) VALUES('Papa','parent','x',?)", _j.dumps({"notify_service": "notify.mobile_app_papa"}))
    fq.db.x("INSERT INTO profile(name, role, pin_hash, settings) VALUES('Mama','parent','x',?)", _j.dumps({"notify_service": "notify.mobile_app_mama"}))
    fq.db.set_setting("notify_service", "notify.mobile_app_papa")          # same phone only once
    assert svc._notify_services() == ["notify.mobile_app_papa", "notify.mobile_app_mama"]
    fq.chores.save({"name": "Abfall", "points": 5, "profiles": [kid]})
    fq.chores.mark_done(kid, int(fq.chores.for_kid(kid)[0]["uid"][3:]))
    import time
    time.sleep(0.2)
    assert sorted(c[1] for c in client.calls if c[0] == "notify") == ["mobile_app_mama", "mobile_app_papa"]


def test_sad_mood_push(fq, kid, ha):
    svc, client = ha
    fq.db.set_setting("notify_service", "notify.mobile_app_papa")
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    fq.mood_changed(prof, {}, {"eyes": "sad"})
    import time
    time.sleep(0.2)
    push = [c for c in client.calls if c[0] == "notify"]
    assert push and "traurig" in push[0][2]["message"] and "actions" not in push[0][2]["data"]
    assert any(e[0] == "family_quest_stimmung" for e in client.events)



def test_mood_text_push(fq, kid, ha):
    svc, client = ha
    fq.db.set_setting("notify_service", "notify.mobile_app_papa")
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    fq.mood_changed(prof, {}, {"eyes": "happy"}, "aufgeregt wegen dem Ausflug")
    import time
    time.sleep(0.2)
    push = [c for c in client.calls if c[0] == "notify"]
    assert push and push[-1][2]["message"] == "Mia: «Heute fühle ich mich aufgeregt wegen dem Ausflug»"


def test_planer_host_mirrors_home_assistant(fq, tmp_path):
    from familyquest.planer.host import PlanerHost

    class Client(FakeClient):
        async def call_response(self, domain, service, data):
            self.calls.append((domain, service, data))
            return {data["entity_id"]: {"items": [{"summary": "Milch", "status": "needs_action", "uid": "1"}]}}

    async def go():
        host = PlanerHost(fq)
        await host.start(ha_expected=True)
        assert not host.hass.started
        client = Client()
        client.state["todo.einkauf"] = {"state": "1", "attributes": {}}
        await host.on_ha_connect(client)
        assert host.hass.started and host.hass.states.get("todo.einkauf").state == "1"
        assert host.hass.config.language == "de"
        items = await host.planner._list_items("todo.einkauf")
        assert items[0]["summary"] == "Milch" and client.calls[-1][1] == "get_items"
        host.on_state_event({"data": {"entity_id": "todo.einkauf", "new_state": {"state": "2", "attributes": {}}}})
        assert host.hass.states.get("todo.einkauf").state == "2"
        await host.stop()
        assert fq.db.q1("SELECT 1 FROM kv WHERE key LIKE 'family_planer.%'")
    asyncio.run(go())


def test_app_starts_planer(client):
    fq = client.app.state.fq
    assert fq.planer_host and fq.planer_host.hass.started          # tests run without Home Assistant
    assert fq.planer_host.planner.data["settings"]["modules"]["week"] is True


def test_beta_channel_uses_own_entity_prefix(fq, kid, ha):
    """The beta app (slug family_quest_beta) must not overwrite the sensors of the stable app."""
    svc, client = ha
    svc.px = "family_quest_beta"
    asyncio.run_coroutine_threadsafe(svc._publish(kid), svc.loop).result(5)
    assert "sensor.family_quest_beta_mia_xp_heute" in client.states_set
    from familyquest import settings as st
    assert st._config_value("slug", "") == "family_quest"


def test_start_script_passes_the_supervisor_token(tmp_path, monkeypatch):
    """The s6-overlay only passes SUPERVISOR_TOKEN to programs started with-contenv (else: no Home Assistant)."""
    assert (ROOT / "family_quest/run.sh").read_text().startswith("#!/usr/bin/with-contenv")
    from familyquest import settings as st
    env = tmp_path / "env"
    env.mkdir()
    (env / "SUPERVISOR_TOKEN").write_text("abc\n")
    monkeypatch.setattr(st, "Path", lambda p: env if str(p) == "/run/s6/container_environment" else __import__("pathlib").Path(p))
    assert st._s6_env("SUPERVISOR_TOKEN") == "abc"


def test_devices_of_a_profile(fq, kid, ha):
    """A child switches and dims only the devices its parents gave it."""
    from familyquest import devices
    svc, client = ha
    client.state_list = [
        {"entity_id": "light.mia", "state": "off", "attributes": {"friendly_name": "Licht Mia", "supported_color_modes": ["brightness"]}},
        {"entity_id": "switch.radio", "state": "on", "attributes": {"friendly_name": "Radio"}},
    ]
    view = {d["entity_id"]: d for d in svc.device_states(["light.mia", "switch.radio", "light.gone"])}
    assert view["light.mia"]["dimmable"] and not view["light.mia"]["on"] and view["switch.radio"]["on"]
    assert not view["light.gone"]["available"]
    assert devices.service_call("light.mia", "brightness", 40) == ("light", "turn_on", {"entity_id": "light.mia", "brightness_pct": 40})
    assert devices.service_call("cover.blind", "stop") == ("cover", "stop_cover", {"entity_id": "cover.blind"})
    import pytest
    with pytest.raises(devices.DeviceError):
        devices.service_call("switch.radio", "brightness", 10)
    svc.control("light.mia", "on")
    assert ("light", "turn_on", {"entity_id": "light.mia"}) in client.calls


def test_areas_for_devices(fq, kid, ha):
    """A whole room: its lights and switches, by the entity's own area or its device's area."""
    svc, client = ha
    assert [a["name"] for a in svc.areas()] == ["Küche", "Zimmer Mia"]
    assert svc.area_entities("mia_room") == ["light.mia_desk"]            # config entities are left out
    assert svc.area_entities("kitchen") == ["light.kitchen"]
    from familyquest.api.kid import _devices
    import json
    prof = {"settings": json.dumps({"devices": ["area.kitchen", "switch.radio", "light.kitchen"]})}
    fq.ha = svc
    assert _devices(prof, fq) == ["light.kitchen", "switch.radio"]
