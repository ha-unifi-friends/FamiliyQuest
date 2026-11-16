from test_api import setup_family


def test_own_texts_override_and_csv(client):
    ph, _, _ = setup_family(client)
    d = client.get("/api/parent/translations/de-DE", headers=ph).json()
    assert "Weather" in d["keys"] and d["standard"]["Weather"] == "Wetter" and d["own"] == {}
    client.put("/api/parent/translations/de-DE", json={"texts": {"Weather": "Stimmungswetter"}}, headers=ph)
    assert client.get("/i18n/custom/de-DE.json").json() == {"Weather": "Stimmungswetter"}
    # English texts can be overwritten too
    client.put("/api/parent/translations/en", json={"texts": {"Weather": "Mood weather"}}, headers=ph)
    assert client.get("/i18n/custom/en.json").json()["Weather"] == "Mood weather"
    # CSV round trip (Excel style: BOM and ;)
    csv = client.get("/api/parent/translations/de-DE/csv", headers=ph)
    assert csv.status_code == 200 and csv.text.startswith("﻿key;standard;translation")
    assert "Weather;Wetter;Stimmungswetter" in csv.text
    r = client.post("/api/parent/translations/de-DE/csv", headers=ph,
                    json={"csv": "key,translation\nWeather,\nSunny,Sünneli\n"}).json()
    assert r["imported"] == 1 and r["own"] == {"Sunny": "Sünneli"}       # empty = back to the standard
    assert client.get("/api/parent/translations/de-DE", headers=ph).status_code == 200
    assert client.get("/api/parent/translations", headers={}).status_code in (401, 403)


def test_own_language(client):
    ph, _, _ = setup_family(client)
    l = client.post("/api/parent/translations/languages", json={"name": "Bärndütsch", "base": "de-CH", "flag": "🐻"}, headers=ph).json()
    assert l["code"] == "x-barndutsch"
    assert client.get("/i18n/languages.json").json()[0]["name"] == "Bärndütsch"
    # the dictionary of a custom language is the one of its base language, own texts on top
    assert client.get("/i18n/x-barndutsch.json").json()["Weather"] == client.get("/i18n/de-CH.json").json()["Weather"]
    assert client.get("/i18n/planer/x-barndutsch.json").status_code in (200, 404)
    client.put(f"/api/parent/translations/{l['code']}", json={"texts": {"Weather": "Wätter, gäu"}}, headers=ph)
    assert client.get(f"/i18n/custom/{l['code']}.json").json() == {"Weather": "Wätter, gäu"}
    assert client.get("/api/parent/translations", headers=ph).json()["counts"][l["code"]] == 1
    assert client.post("/api/parent/translations/languages", json={"name": "X", "base": "tlh"}, headers=ph).status_code == 400
    assert client.put("/api/parent/translations/x-nope", json={"texts": {"a": "b"}}, headers=ph).status_code == 400
    client.delete(f"/api/parent/translations/languages/{l['code']}", headers=ph)
    assert client.get("/i18n/languages.json").json() == []
    assert client.get(f"/i18n/{l['code']}.json").status_code == 404
