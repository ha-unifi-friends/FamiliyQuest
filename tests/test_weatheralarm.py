from datetime import datetime

from familyquest.weatheralarm import alerts

NOW = datetime(2026, 11, 17, 7, 0)


def fc(hour, cond, chance=0, temp=8, wind=10):
    return {"datetime": f"2026-11-17T{hour:02d}:00:00", "condition": cond, "precipitation_probability": chance, "temperature": temp, "wind_speed": wind}


def test_rain_later_today():
    st = {"state": "cloudy", "attributes": {"temperature": 7, "temperature_unit": "°C"}}
    r = alerts(st, [fc(9, "cloudy", 20), fc(15, "rainy", 80)], {}, now=NOW)
    assert [h["key"] for h in r["hints"]] == ["rain"] and r["now"]["icon"] == "☁️" and r["now"]["chance"] == 80
    r = alerts(st, [fc(9, "cloudy", 20), fc(23, "rainy", 80)], {"weather_hours": 12}, now=NOW)      # too late: after 19:00
    assert r["hints"] == []


def test_storm_cold_hot_wind():
    st = {"state": "lightning-rainy", "attributes": {"temperature": 1}}
    keys = [h["key"] for h in alerts(st, [fc(10, "windy", 0, 2, 60)], {}, now=NOW)["hints"]]
    assert keys == ["storm", "rain", "wind", "cold"]
    keys = [h["key"] for h in alerts({"state": "sunny", "attributes": {"temperature": 31}}, [], {}, now=NOW)["hints"]]
    assert keys == ["hot"]
    assert alerts(None, [], {})["now"] is None
