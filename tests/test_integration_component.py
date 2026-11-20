"""The custom component (app/ha_integration/familyquest) against small stand-ins of Home Assistant.

Home Assistant itself is too heavy to install for the tests: the few classes the component uses are replaced by
minimal stubs here, then the platforms are set up with the real state of the add-on (integration.state)."""
import asyncio
import enum
import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import pytest

from familyquest import integration
from familyquest.settings import APP_DIR

COMPONENT = APP_DIR / "ha_integration" / "familyquest"
T = TypeVar("T")


def _mod(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m


def _stubs() -> dict[str, types.ModuleType]:
    class HomeAssistantError(Exception):
        pass

    class ConfigEntryAuthFailed(HomeAssistantError):
        pass

    class ServiceValidationError(HomeAssistantError):
        def __init__(self, *a, **kw):
            super().__init__(kw.get("translation_key"))

    class Unauthorized(HomeAssistantError):
        def __init__(self, context=None, **kw):
            super().__init__("unauthorized")

    class UnknownUser(Unauthorized):
        pass

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator(Generic[T]):
        def __init__(self, hass, logger, *, config_entry=None, name=None, update_interval=None):
            self.hass, self.config_entry, self.name, self.update_interval = hass, config_entry, name, update_interval
            self.data = None
            self.last_update_success = True
            self.listeners = []
            self.refreshes = 0

        def async_add_listener(self, fn):
            self.listeners.append(fn)
            return lambda: self.listeners.remove(fn)

        async def async_request_refresh(self):
            self.refreshes += 1

    class CoordinatorEntity(Generic[T]):
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

        @property
        def unique_id(self):
            return self._attr_unique_id

    class Entity:
        pass

    class SensorStateClass(enum.StrEnum):
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    @dataclass(frozen=True, kw_only=True)
    class EntityDescription:
        key: str
        translation_key: str | None = None
        icon: str | None = None
        native_unit_of_measurement: str | None = None
        state_class: Any = None
        device_class: Any = None

    class UnitOfTime(enum.StrEnum):
        DAYS = "d"
        MINUTES = "min"

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kw):
            super().__init_subclass__(**kw)
            cls.DOMAIN = domain

    class ConfigEntry(Generic[T]):
        pass

    class ConfigEntryState(enum.Enum):
        LOADED = "loaded"

    cv = _mod("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda d: None,
              string=str, boolean=bool)
    mods = {
        "homeassistant": _mod("homeassistant"),
        "homeassistant.config_entries": _mod("homeassistant.config_entries", ConfigEntry=ConfigEntry,
                                             ConfigEntryState=ConfigEntryState, ConfigFlow=ConfigFlow, ConfigFlowResult=dict),
        "homeassistant.core": _mod("homeassistant.core", HomeAssistant=object, ServiceCall=object, ServiceResponse=dict,
                                   SupportsResponse=enum.Enum("SupportsResponse", "NONE OPTIONAL ONLY"), callback=lambda f: f),
        "homeassistant.exceptions": _mod("homeassistant.exceptions", HomeAssistantError=HomeAssistantError,
                                         ConfigEntryAuthFailed=ConfigEntryAuthFailed, ServiceValidationError=ServiceValidationError,
                                         Unauthorized=Unauthorized, UnknownUser=UnknownUser),
        "homeassistant.const": _mod("homeassistant.const", PERCENTAGE="%", UnitOfTime=UnitOfTime),
        "homeassistant.helpers": _mod("homeassistant.helpers", config_validation=cv),
        "homeassistant.helpers.config_validation": cv,
        "homeassistant.helpers.aiohttp_client": _mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: None),
        "homeassistant.helpers.typing": _mod("homeassistant.helpers.typing", ConfigType=dict),
        "homeassistant.helpers.update_coordinator": _mod("homeassistant.helpers.update_coordinator",
                                                         DataUpdateCoordinator=DataUpdateCoordinator, UpdateFailed=UpdateFailed,
                                                         CoordinatorEntity=CoordinatorEntity),
        "homeassistant.helpers.device_registry": _mod("homeassistant.helpers.device_registry", DeviceInfo=dict),
        "homeassistant.helpers.entity": _mod("homeassistant.helpers.entity", Entity=Entity),
        "homeassistant.helpers.entity_platform": _mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=object),
        "homeassistant.components": _mod("homeassistant.components"),
        "homeassistant.components.sensor": _mod("homeassistant.components.sensor", SensorEntity=Entity,
                                                SensorEntityDescription=EntityDescription, SensorStateClass=SensorStateClass),
        "homeassistant.components.binary_sensor": _mod("homeassistant.components.binary_sensor", BinarySensorEntity=Entity,
                                                       BinarySensorEntityDescription=EntityDescription),
        "homeassistant.components.switch": _mod("homeassistant.components.switch", SwitchEntity=Entity),
    }
    try:
        import voluptuous  # noqa: F401
    except ImportError:
        mods["voluptuous"] = _mod("voluptuous", Schema=lambda *a, **k: None, Required=lambda *a, **k: a[0],
                                  Optional=lambda *a, **k: a[0], All=lambda *a: None, Coerce=lambda t: t, Range=lambda **k: None)
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        mods["aiohttp"] = _mod("aiohttp", ClientSession=object, ClientResponse=object, ClientError=OSError)
    return mods


@pytest.fixture
def comp(monkeypatch):
    """The component loaded as package «fq_ha_component» (its own name would clash with the app package)."""
    for name, m in _stubs().items():
        monkeypatch.setitem(sys.modules, name, m)
    spec = importlib.util.spec_from_file_location("fq_ha_component", COMPONENT / "__init__.py",
                                                  submodule_search_locations=[str(COMPONENT)])
    pkg = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "fq_ha_component", pkg)
    spec.loader.exec_module(pkg)
    out = {"pkg": pkg}
    for sub in ("const", "api", "coordinator", "entity", "sensor", "binary_sensor", "switch", "config_flow"):
        out[sub] = importlib.import_module(f"fq_ha_component.{sub}")
    yield out
    for k in [k for k in sys.modules if k.startswith("fq_ha_component")]:
        sys.modules.pop(k, None)


class FakeApi:
    def __init__(self, fq):
        self.fq, self.actions, self.fail = fq, [], None

    async def state(self):
        if self.fail:
            raise self.fail
        return await asyncio.to_thread(integration.state, self.fq)       # the app's side: a worker thread there too

    async def action(self, action, **data):
        self.actions.append((action, data))
        return await asyncio.to_thread(integration.action, self.fq, {"action": action, **data})


class Entry:
    entry_id = "E1"

    def __init__(self):
        self.unload = []

    def async_on_unload(self, fn):
        self.unload.append(fn)


def _setup(comp, fq):
    entry = Entry()
    api = FakeApi(fq)
    coord = comp["coordinator"].FamilyQuestCoordinator(None, entry, api)
    coord.data = asyncio.run(api.state())
    entry.runtime_data = coord
    added = []
    for plat in ("sensor", "binary_sensor", "switch"):
        asyncio.run(comp[plat].async_setup_entry(None, entry, added.extend))
    return entry, coord, api, added


@pytest.fixture
def family(fq):
    mia = fq.db.x("INSERT INTO profile(name, role) VALUES('Mia', 'kid')")
    leo = fq.db.x("INSERT INTO profile(name, role) VALUES('Leo', 'kid')")
    fq.db.x("INSERT INTO profile(name, role) VALUES('Papa', 'parent')")
    s = {"internet_rule": "switch.mia_block", "internet_rule_blocks": True}
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(s), mia)
    fq.internet.ensure_account()
    fq.internet.switcher = lambda e, on: None
    fq.rewards.book(mia, "coins", 7, "manual", "t")
    fq.rewards.book(mia, "internet", 20, "manual", "t")
    return mia, leo


def test_entities_devices_and_values(comp, fq, family):
    mia, leo = family
    entry, coord, api, added = _setup(comp, fq)
    inst = coord.instance
    by_id = {e.unique_id: e for e in added}
    assert len(by_id) == len(added)                                       # unique ids are unique
    # family device
    assert by_id[f"{inst}_family_running_games"].native_value == 0
    assert by_id[f"{inst}_family_total_xp"]._attr_device_info["identifiers"] == {("familyquest", f"{inst}_family")}
    # child devices: one per child, linked to the family device
    s = by_id[f"{inst}_{mia}_balance_coins"]
    # built-in account with its default name: translated by Home Assistant (balance_coins), an own name stays as it is
    assert s.native_value == 7 and s._attr_translation_key == "balance_coins" and not hasattr(s, "_attr_translation_placeholders")
    own = comp["sensor"].BalanceSensor(coord, mia, {"key": "stars", "name": "Sterne"})
    assert own._attr_translation_key == "balance" and own._attr_translation_placeholders == {"account": "Sterne"}
    renamed = comp["sensor"].BalanceSensor(coord, mia, {"key": "coins", "name": "Batzen"})
    assert renamed._attr_translation_key == "balance" and renamed._attr_translation_placeholders == {"account": "Batzen"}
    assert s._attr_device_info["name"] == "Mia" and s._attr_device_info["via_device"] == ("familyquest", f"{inst}_family")
    assert by_id[f"{inst}_{mia}_balance_internet"].native_value == 20
    assert by_id[f"{inst}_{mia}_internet_minutes"].native_value == 20
    assert by_id[f"{inst}_{mia}_game_time_left"].native_value is None              # ∞ → unknown + attribute
    assert by_id[f"{inst}_{mia}_game_time_left"].extra_state_attributes["unlimited"] is True
    assert by_id[f"{inst}_{mia}_goal_met"].is_on is False
    assert by_id[f"{inst}_{mia}_internet_blocked"].is_on is True
    assert by_id[f"{inst}_{mia}_internet"].is_on is False
    # Leo has no internet time: no internet sensor, binary sensor or switch
    assert f"{inst}_{leo}_internet" not in by_id and f"{inst}_{leo}_internet_minutes" not in by_id
    assert f"{inst}_{leo}_streak" in by_id and f"{inst}_{leo}_offline_time" in by_id
    # parents get no device
    assert not any("Papa" == (e._attr_device_info or {}).get("name") for e in added)


def test_switch_and_new_children(comp, fq, family):
    mia, leo = family
    entry, coord, api, added = _setup(comp, fq)
    sw = next(e for e in added if e.unique_id.endswith(f"_{mia}_internet"))
    asyncio.run(sw.async_turn_on())
    assert api.actions[-1] == ("internet_start", {"child": mia}) and coord.refreshes == 1
    coord.data = asyncio.run(api.state())
    assert sw.is_on is True
    asyncio.run(sw.async_turn_off())
    coord.data = asyncio.run(api.state())
    assert sw.is_on is False
    # a new child appears with the next update: its entities are added once
    n = len(added)
    fq.db.x("INSERT INTO profile(name, role) VALUES('Nina', 'kid')")
    coord.data = asyncio.run(api.state())
    for fn in list(coord.listeners):
        fn()
    new = added[n:]
    assert new and all("_balance_" in e.unique_id or e._attr_device_info["name"] == "Nina" for e in new)
    for fn in list(coord.listeners):
        fn()
    assert len(added) == n + len(new)
    # a child that is gone becomes unavailable
    fq.db.x("UPDATE profile SET archived=1 WHERE name='Nina'")
    coord.data = asyncio.run(api.state())
    assert not new[0].available
    for fn in entry.unload:
        fn()
    assert coord.listeners == []


def test_coordinator_errors_and_actions(comp, fq, family):
    mia, leo = family
    entry, coord, api, added = _setup(comp, fq)
    api_mod = comp["api"]
    exc = sys.modules["homeassistant.exceptions"]
    upd = sys.modules["homeassistant.helpers.update_coordinator"]
    api.fail = api_mod.FamilyQuestAuthError("Wrong integration token")
    with pytest.raises(exc.ConfigEntryAuthFailed):
        asyncio.run(coord._async_update_data())
    api.fail = api_mod.FamilyQuestError("timeout")
    with pytest.raises(upd.UpdateFailed):
        asyncio.run(coord._async_update_data())
    api.fail = None
    assert asyncio.run(coord._async_update_data())["children"]
    asyncio.run(coord.async_action("add_points", child="Leo", account="coins", amount=5, reason="HA"))
    assert fq.rewards.balance(leo, "coins") == 5


def test_actions_are_admin_services(comp, fq, family):
    """add_points / approve_*: Home Assistant admins and automations (no user) only – like async_register_admin_service."""
    mia, leo = family
    entry, coord, api, added = _setup(comp, fq)
    entry.state = sys.modules["homeassistant.config_entries"].ConfigEntryState.LOADED
    exc = sys.modules["homeassistant.exceptions"]
    users = {"admin": types.SimpleNamespace(is_admin=True), "kid": types.SimpleNamespace(is_admin=False)}
    services = {}

    async def get_user(uid):
        return users.get(uid)
    hass = types.SimpleNamespace(
        services=types.SimpleNamespace(async_register=lambda dom, name, fn, schema=None, supports_response=None:
                                       services.__setitem__(name, fn)),
        config_entries=types.SimpleNamespace(async_entries=lambda dom: [entry]),
        auth=types.SimpleNamespace(async_get_user=get_user))
    assert asyncio.run(comp["pkg"].async_setup(hass, {}))
    assert set(services) == set(comp["pkg"].SERVICE_SCHEMAS)

    def call(user):
        return types.SimpleNamespace(service="add_points", return_response=True, context=types.SimpleNamespace(user_id=user),
                                     data={"child": "Leo", "account": "coins", "amount": 3, "reason": "HA"})
    with pytest.raises(exc.Unauthorized):
        asyncio.run(services["add_points"](call("kid")))
    with pytest.raises(exc.UnknownUser):
        asyncio.run(services["add_points"](call("gone")))
    assert fq.rewards.balance(leo, "coins") == 0
    assert asyncio.run(services["add_points"](call("admin")))["ok"]
    asyncio.run(services["add_points"](call(None)))                  # an automation
    assert fq.rewards.balance(leo, "coins") == 6


def test_constants_match_the_addon(comp):
    const = comp["const"]
    assert const.DOMAIN == integration.DOMAIN == json.loads((COMPONENT / "manifest.json").read_text())["domain"]
    assert const.DEFAULT_URL.endswith(f":{integration.PORT}")
    assert set(comp["pkg"].SERVICE_SCHEMAS) <= set(integration.ACTIONS)
    assert comp["config_flow"].FamilyQuestConfigFlow.DOMAIN == "familyquest"
