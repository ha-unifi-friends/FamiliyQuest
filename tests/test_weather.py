from datetime import date, datetime, timedelta

from test_api import setup_family


def test_weather_set_bonus_malus_and_privacy(client):
    ph, mia, leo = setup_family(client)
    d = client.get("/api/parent/weather", headers=ph).json()
    assert [l["icon"] for l in d["config"]["levels"]] == ["☀️", "⛅", "🌧️", "⛈️"] and d["config"]["reset"] == "12:00"
    k = {x["profile"]["id"]: x for x in d["kids"]}
    assert k[mia]["current"]["key"] == "sun" and len(k[mia]["days"]) == 30
    coins = client.post(f"/api/parent/weather/{mia}", json={"level": "rain"}, headers=ph).json()
    assert coins["current"]["icon"] == "🌧️" and coins["balances"]["coins"] == -5
    assert coins["days"][-1]["icon"] == "🌧️"
    r = client.post(f"/api/parent/weather/{mia}", json={"level": "sun"}, headers=ph).json()
    assert r["balances"]["coins"] == 0 and r["days"][-1]["icon"] == "🌧️"      # the graph shows the worst of the day
    assert client.post(f"/api/parent/weather/{mia}", json={"level": "hail"}, headers=ph).status_code == 400
    # each child sees only its own weather
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    dash = client.get("/api/me", headers=h).json()
    assert dash["weather"]["icon"] == "☀️"
    assert "weather" not in str(client.get("/api/family", headers=h).json())
    assert client.get("/api/parent/weather", headers=h).status_code in (401, 403)


def test_weather_config_and_reset(client):
    ph, mia, _ = setup_family(client)
    cfg = {"levels": [{"icon": "🌈", "name": "Regenbogen", "points": 10}, {"icon": "🌫️", "name": "Nebel", "points": -2}],
           "reset": "07:30", "account": "coins"}
    r = client.put("/api/parent/weather/config", json=cfg, headers=ph)
    assert r.status_code == 200 and r.json()["default"] == r.json()["levels"][0]["key"]
    assert client.put("/api/parent/weather/config", json={**cfg, "reset": "25h"}, headers=ph).status_code == 400
    assert client.put("/api/parent/weather/config", json={**cfg, "levels": cfg["levels"][:1]}, headers=ph).status_code == 400


def test_weather_lazy_reset(fq, kid):
    w = fq.weather
    w.set(kid, "storm")
    assert w.current(kid)["key"] == "storm"
    later = w.last_reset() + timedelta(days=1, minutes=1)
    assert w.current(kid, later)["key"] == "sun"            # back to the default after the reset time
    assert fq.rewards.balances(kid)["coins"] == -10         # the reset books nothing
