import io

import yaml


def ph(client):
    return {"X-FQ-Parent": client.post("/api/setup", json={"name": "Mama", "pin": "4321"}).json()["parent_token"]}


def test_csv_import(client):
    h = ph(client)
    csv = "Deutsch;Französisch;Einheit\nder Apfel;la pomme;Obst\ndie Birne;la poire;Obst\nder Apfel;la pomme;Obst\ndie Katze;le chat;Tiere\n"
    r = client.post("/api/parent/import/file", files={"file": ("franz 5. Klasse obst.csv", csv.encode(), "text/csv")}, headers=h)
    assert r.status_code == 200, r.text
    t = r.json()["table"]
    assert t["columns"]["prompt"] == 0 and t["columns"]["answer"] == 1 and t["columns"]["unit"] == 2
    assert t["meta"]["fach"] == "franzoesisch" and t["meta"]["stufe"] == "5. Klasse" and t["meta"]["sprache"] == "fr"
    r = client.post("/api/parent/import/table", json={"upload_id": t["upload_id"], "meta": t["meta"], "columns": t["columns"]}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["drafts"][0]
    assert d["status"] == "draft"
    units = {u["id"]: u for u in d["units"]}
    assert units["obst"]["count"] == 2           # duplicate merged
    assert "eintippen" in units["obst"]["exercises"]


def test_xlsx_import(client):
    from openpyxl import Workbook
    h = ph(client)
    wb = Workbook()
    ws = wb.active
    ws.append(["Gemeinde", "Bezirk"])
    for g, b in [("Arbon", "Arbon"), ("Romanshorn", "Arbon"), ("Amriswil", "Arbon"), ("Sirnach", "Münchwilen"),
                 ("Aadorf", "Münchwilen"), ("Wängi", "Münchwilen")]:
        ws.append([g, b])
    buf = io.BytesIO()
    wb.save(buf)
    t = client.post("/api/parent/import/file", files={"file": ("geo thurgau.xlsx", buf.getvalue())}, headers=h).json()["table"]
    d = client.post("/api/parent/import/table", json={"upload_id": t["upload_id"], "meta": t["meta"],
                                                       "columns": {"prompt": 0, "answer": 1}}, headers=h).json()["drafts"][0]
    assert d["units"][0]["exercises"] == ["zuordnen"]      # few categories → drag & drop


def test_yaml_import_and_publish(client):
    h = ph(client)
    pack = {"id": "test-pack", "titel": "Test", "fach": "englisch", "sprache": "en",
            "einheiten": [{"id": "a", "karten": [{"de": "Hund", "en": "dog"}, {"de": "Katze", "en": "cat"}]}]}
    r = client.post("/api/parent/import/file", files={"file": ("t.yaml", yaml.safe_dump(pack).encode())}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["drafts"][0]["status"] == "draft"
    bad = client.post("/api/parent/import/file", files={"file": ("t.yaml", b"id: X Y\n")}, headers=h)
    assert bad.status_code == 400
    assert client.post("/api/parent/packs/test-pack/status", json={"status": "active"}, headers=h).status_code == 200
    raw = client.get("/api/parent/packs/test-pack/raw", headers=h).json()
    raw["data"]["einheiten"][0]["karten"].append({"de": "Maus", "en": "mouse"})
    r = client.put("/api/parent/packs/test-pack/raw", json={"data": raw["data"]}, headers=h)
    assert r.status_code == 200 and r.json()["summary"]["units"][0]["count"] == 3
    z = client.get("/api/parent/packs/test-pack/export", headers=h)
    assert z.status_code == 200 and z.content[:2] == b"PK"
    r = client.post("/api/parent/import/file", files={"file": ("test-pack.zip", z.content)}, headers=h)
    assert r.status_code == 200 and r.json()["drafts"][0]["replaces"]


def test_bundle_activation(client):
    h = ph(client)
    kid = client.post("/api/parent/profiles", json={"name": "Lia"}, headers=h).json()["id"]
    for p in client.get("/api/parent/packs", headers=h).json()["packs"]:
        if p["kind"] == "pack":
            client.post("/api/parent/packs/activate", json={"profile_id": kid, "pack_id": p["id"], "on": False}, headers=h)
    client.post("/api/parent/packs/activate", json={"profile_id": kid, "pack_id": "tg-5-klasse", "on": True}, headers=h)
    profs = {p["id"]: p for p in client.get("/api/parent/profiles", headers=h).json()}
    assert {"tg-5-klasse", "mathe-5kl", "geo-tg"} <= set(profs[kid]["packs"])


def test_json_import_and_export(client):
    import json
    h = ph(client)
    pack = {"id": "json-pack", "titel": "JSON", "fach": "englisch", "sprache": "en",
            "einheiten": [{"id": "a", "karten": [{"de": "Hund", "en": "dog"}, {"de": "Katze", "en": "cat"}]}]}
    # file upload
    r = client.post("/api/parent/import/file", files={"file": ("p.json", json.dumps(pack).encode())}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["drafts"][0]["id"] == "json-pack"
    # body (single, list and envelope)
    r = client.post("/api/parent/import/json", json=dict(pack, id="json-pack-2"), headers=h)
    assert r.status_code == 200, r.text
    r = client.post("/api/parent/import/json", json={"pakete": [dict(pack, id="json-pack-3"), dict(pack, id="json-pack-4")]}, headers=h)
    assert [d["id"] for d in r.json()["drafts"]] == ["json-pack-3", "json-pack-4"]
    assert client.post("/api/parent/import/json", json={"id": "Bad Id"}, headers=h).status_code == 400
    assert client.post("/api/parent/import/file", files={"file": ("p.json", b"{nope")}, headers=h).status_code == 400
    # export single pack as JSON and YAML, re-import the JSON
    j = client.get("/api/parent/packs/json-pack/export?format=json", headers=h)
    assert j.status_code == 200 and j.headers["content-type"].startswith("application/json")
    assert j.json()["einheiten"][0]["karten"][1]["en"] == "cat"
    assert client.get("/api/parent/packs/json-pack/export?format=yaml", headers=h).text.startswith("id: json-pack")
    assert client.get("/api/parent/packs/json-pack/export?format=xml", headers=h).status_code == 400
    # export everything and import it again
    allp = client.get("/api/parent/packs/export", headers=h).json()
    assert allp["format"] == "family-quest-packs" and any(p.get("stufenpaket") == "tg-5-klasse" for p in allp["pakete"])
    r = client.post("/api/parent/import/json", json=allp, headers=h)
    assert r.status_code == 200 and len(r.json()["drafts"]) == len(allp["pakete"])
    # zip with a JSON pack inside
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.json", json.dumps(dict(pack, id="zip-json")))
    r = client.post("/api/parent/import/file", files={"file": ("x.zip", buf.getvalue())}, headers=h)
    assert r.json()["drafts"][0]["id"] == "zip-json"
