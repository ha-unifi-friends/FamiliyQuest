"""Live weather and daylight of the season scenes (seasonlive.py): mapping like FPSEASON.weather / the planner card,
the shared weather entity of the planner, the sun switch, the cache and the endpoints."""
from datetime import date

from familyquest import seasonlive
from test_api import setup_family


def test_weather_mapping_like_fpseason():
    w = seasonlive.weather_of("rainy", {"temperature": 7.6, "temperature_unit": "°C", "wind_speed": 5, "wind_speed_unit": "m/s"})
    assert w == {"state": "rainy", "kind": "rainy", "icon": "🌧️", "temp": 8, "unit": "°C", "wind": 18.0}
    assert seasonlive.weather_of("snowy-rainy", {})["kind"] == "snowy"
    assert seasonlive.weather_of("hail", {})["kind"] == "pouring"
    assert seasonlive.weather_of("lightning-rainy", {})["kind"] == "lightning"
    assert seasonlive.weather_of("sunny", {"temperature": "x"})["temp"] is None
    assert seasonlive.weather_of("strange", {})["kind"] == "cloudy"
    assert seasonlive.weather_of("unavailable", {}) is None and seasonlive.weather_of(None, {}) is None


def test_sun_mapping_like_planer_card():
    assert seasonlive.light_of("below_horizon", {"elevation": -20}) == {"night": True, "dusk": None, "elevation": -20}
    assert seasonlive.light_of("above_horizon", {"elevation": 40}) == {"night": False, "dusk": None, "elevation": 40}
    assert seasonlive.light_of("above_horizon", {"elevation": 3, "rising": False})["dusk"] == "dusk"
    assert seasonlive.light_of("below_horizon", {"elevation": -1, "rising": True}) == {"night": False, "dusk": "dawn", "elevation": -1}
    assert seasonlive.light_of("unknown", {}) is None


def _states(client, **states):
    host = client.app.state.fq.planer_host
    for eid, (st, attrs) in states.items():
        host.hass.states.set(eid.replace("__", "."), st, attrs)
    seasonlive.clear(client.app.state.fq)


def test_endpoint_live(client):
    ph, mia, leo = setup_family(client)
    kid = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.get("/api/season-live").status_code == 401
    # no Home Assistant, no entity: nothing live – the clock decides
    assert client.get("/api/season-live", headers=kid).json() is None
    d = client.get("/api/parent/season-live", headers=ph).json()
    assert d["weather"] is None and d["sun"] is True and d["live"] is None
    # rain by day
    assert client.put("/api/parent/season-live", headers=ph, json={"weather": "sensor.x"}).status_code == 400
    r = client.put("/api/parent/season-live", headers=ph, json={"weather": "weather.home"})
    assert r.status_code == 200 and r.json()["weather"] == "weather.home"
    # one setting with the planner cards (season_cfg.weather)
    assert client.app.state.fq.planer_host.planner.season_settings()["weather"] == "weather.home"
    _states(client, weather__home=("rainy", {"temperature": 12, "wind_speed": 20}), sun__sun=("above_horizon", {"elevation": 30}))
    d = client.get("/api/season-live", headers=kid).json()
    assert d["wx"]["kind"] == "rainy" and d["wx"]["temp"] == 12 and d["night"] is False and d["dusk"] is None
    assert d["jz"] in ("fruehling", "sommer", "herbst", "winter") and d["storm"] == 50
    assert "weather.home" not in str(d) and "entity" not in str(d)
    # cached: a change in Home Assistant shows after the cache time
    client.app.state.fq.planer_host.hass.states.set("weather.home", "snowy", {})
    assert client.get("/api/season-live", headers=kid).json()["wx"]["kind"] == "rainy"
    # snow at night
    _states(client, weather__home=("snowy", {"temperature": -3}), sun__sun=("below_horizon", {"elevation": -25}))
    d = client.get("/api/season-live", headers=kid).json()
    assert d["wx"]["kind"] == "snowy" and d["night"] is True
    # sunny at sunset
    _states(client, weather__home=("sunny", {"temperature": 21}), sun__sun=("above_horizon", {"elevation": 2, "rising": False}))
    d = client.get("/api/season-live", headers=kid).json()
    assert d["wx"]["kind"] == "sunny" and d["night"] is False and d["dusk"] == "dusk"
    # day and night by the clock: the sun is not read
    d = client.put("/api/parent/season-live", headers=ph, json={"sun": False}).json()
    assert d["sun"] is False and d["weather"] == "weather.home"
    d = client.get("/api/season-live", headers=kid).json()
    assert d["wx"]["kind"] == "sunny" and d["night"] is None and d["dusk"] is None
    # only the sun: still live (day / night), no weather
    client.put("/api/parent/season-live", headers=ph, json={"weather": None, "sun": True})
    assert client.app.state.fq.planer_host.planner.season_settings()["weather"] is None
    d = client.get("/api/season-live", headers=kid).json()
    assert d["wx"] is None and d["night"] is False
    # settings round trip
    d = client.get("/api/parent/season-live", headers=ph).json()
    assert d["weather"] is None and d["sun"] is True
    # weather entity that does not exist (yet) and no sun: nothing live
    client.put("/api/parent/season-live", headers=ph, json={"weather": "weather.gone", "sun": False})
    assert client.get("/api/season-live", headers=kid).json() is None
    assert client.put("/api/parent/season-live", json={"sun": True}).status_code in (401, 403)


def test_jz():
    from familyquest import themes
    assert themes.jz(date(2026, 1, 5)) == "winter" and themes.jz(date(2026, 11, 19)) == "herbst"
