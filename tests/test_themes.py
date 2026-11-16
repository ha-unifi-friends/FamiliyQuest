"""Season designs: seasons, Halloween and Christmas by date, own designs first, switched off designs skipped."""
from datetime import date

import pytest

from familyquest import themes
from test_api import setup_family


def test_dates_and_priority():
    assert themes.active(None, date(2026, 4, 10))["id"] == "spring"
    assert themes.active(None, date(2026, 7, 1))["id"] == "summer"
    assert themes.active(None, date(2026, 10, 5))["vis"] == "herbst"
    assert themes.active(None, date(2026, 10, 31))["id"] == "halloween"      # event wins over autumn
    assert themes.active(None, date(2026, 12, 24))["id"] == "christmas"
    assert themes.active(None, date(2027, 1, 15))["id"] == "winter"          # over the new year
    assert themes.active(None, date(2026, 10, 31))["jz"] == "herbst"
    off = {"builtin": {"halloween": {"on": False}}}
    assert themes.active(off, date(2026, 10, 31))["id"] == "autumn"
    own = {"own": [{"name": "Geburtstag Mia", "icon": "🎂", "vis": "geburtstag", "from": "31.10.", "to": "31.10.", "accent": "#ff00aa"}]}
    a = themes.active(own, date(2026, 10, 31))
    assert a["name"] == "Geburtstag Mia" and a["vis"] == "geburtstag" and a["accent"] == "#ff00aa"
    moved = {"builtin": {"christmas": {"from": "11-25", "to": "12-26"}}}
    assert themes.active(moved, date(2026, 11, 28))["id"] == "christmas"
    with pytest.raises(themes.ThemeError):
        themes.clean({"own": [{"name": "", "from": "01-01", "to": "01-02"}]})


def test_api(client):
    ph, mia, leo = setup_family(client)
    d = client.get("/api/parent/themes", headers=ph).json()
    assert len(d["designs"]) == 6 and "halloween" in d["visuals"]
    r = client.put("/api/parent/themes", headers=ph, json={"own": [{"name": "Ferien", "icon": "🏝️", "vis": "sommer", "from": "01-01", "to": "12-31"}]})
    assert r.status_code == 200 and r.json()["active"]["name"] == "Ferien"
    assert client.get("/api/info").json()["season"]["name"] == "Ferien"
    assert client.put("/api/parent/themes", headers=ph, json={"own": [{"name": "x", "from": "13-40", "to": "01-01"}]}).status_code == 400
