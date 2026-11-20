"""📈 Analytics (analytics.py, api/analytics.py): aggregation on seeded data, the whitelist (400), parents only,
saved reports («My reports») and the built-in templates."""
from __future__ import annotations

import json
from datetime import date

import pytest

from familyquest.analytics import (COMMON_DIMS, DATASETS, MAX_ROWS, TEMPLATES, Analytics, AnalyticsError, build_sql,
                                   clean_spec)
from test_api import setup_family

TODAY = date(2026, 11, 19)          # a Thursday – its week starts on Monday 2026-11-16


def seed(db, mia: int, leo: int) -> None:
    L = "INSERT INTO ledger(profile_id, account, amount, event, at) VALUES(?,?,?,?,?)"
    db.x(L, mia, "coins", 10, "chore_done", "2026-11-17 10:00:00")
    db.x(L, mia, "coins", 5, "lesson_done", "2026-11-19 08:00:00")
    db.x(L, mia, "coins", -8, "shop", "2026-11-18 08:00:00")
    db.x(L, mia, "coins", 7, "chore_done", "2026-11-10 09:00:00")      # the week before
    db.x(L, leo, "coins", 20, "chore_done", "2026-11-16 09:00:00")
    db.x(L, leo, "xp", 30, "lesson_done", "2026-11-16 09:00:00")
    db.x(L, leo, "internet", -15, "internet_used", "2026-11-16 09:00:00")
    db.x(L, mia, "coins", 999, "chore_done", "2025-01-01 09:00:00")    # outside «this year»
    A = "INSERT INTO attempt(profile_id, item_key, subject, kind, correct, ms, at) VALUES(?,?,?,?,?,?,?)"
    for ok in (1, 1, 1, 0):
        db.x(A, mia, "k", "mathematik", "eintippen", ok, 30000, "2026-11-18 17:00:00")
    db.x(A, leo, "k", "deutsch", "auswahl", 1, 60000, "2026-11-18 17:00:00")
    H = "INSERT INTO history(profile_id, kind, data, at) VALUES(?,?,?,?)"
    db.x(H, mia, "jump", json.dumps({"place": 1, "coins": 10}), "2026-11-18 18:00:00")
    db.x(H, leo, "jump", json.dumps({"place": 2, "coins": 5}), "2026-11-18 18:00:00")
    db.x(H, mia, "cards", json.dumps({"game": "Tschau Sepp", "place": 1}), "2026-11-17 18:00:00")
    db.x(H, mia, "council", json.dumps({"topic": "Ferien"}), "2026-11-17 18:00:00")     # not a game
    db.x("INSERT INTO weather_log(profile_id, level, icon, rank, points, at) VALUES(?,?,?,?,?,?)", mia, "sun", "☀️", 0, 5, "2026-11-18 12:00:00")
    db.x("INSERT INTO weather_log(profile_id, level, icon, rank, points, at) VALUES(?,?,?,?,?,?)", mia, "storm", "⛈️", 3, -10, "2026-11-19 12:00:00")
    for m in range(25):
        db.x("INSERT INTO play_minute(profile_id, day, minute) VALUES(?,?,?)", leo, "2026-11-18", 600 + m)
    sid = db.x("INSERT INTO story(title, author_id, data, visibility, type) VALUES('Geheimes Tagebuch', ?, '{}', 'me', 'picture')", mia)
    pub = db.x("INSERT INTO story(title, author_id, data, visibility, type) VALUES('Drachenburg', ?, '{}', 'family', 'adventure')", leo)
    db.x("INSERT INTO story_read(story_id, profile_id, finished, updated_at) VALUES(?,?,1,'2026-11-18 10:00:00')", sid, mia)
    db.x("INSERT INTO story_read(story_id, profile_id, finished, updated_at) VALUES(?,?,1,'2026-11-18 10:00:00')", pub, mia)


@pytest.fixture
def fam(fq):
    mia = fq.db.x("INSERT INTO profile(name, role) VALUES('Mia','kid')")
    leo = fq.db.x("INSERT INTO profile(name, role) VALUES('Leo','kid')")
    fq.db.x("INSERT INTO profile(name, role) VALUES('Gast','guest')")
    seed(fq.db, mia, leo)
    return fq, mia, leo


def q(fq, **spec):
    return Analytics(fq.db, fq.weather).query({"range": "30d", **spec}, today=TODAY)


def test_coins_per_child_and_week(fam):
    fq, mia, leo = fam
    r = q(fq, dataset="ledger", rows=["week"], columns=["child"], data=["coins", "count"])
    got = {(row[0], row[1]): row[2:] for row in r["rows"]}
    assert got == {("2026-11-09", mia): [7, 1], ("2026-11-16", mia): [7, 3], ("2026-11-16", leo): [20, 3]}
    assert r["dims"][1]["labels"] == {str(mia): "Mia", str(leo): "Leo"} and r["dims"][1]["order"] == [str(mia), str(leo)]
    assert r["measures"] == [{"key": "coins", "unit": "coins"}, {"key": "count", "unit": ""}]
    # earned / spent, internet used, the child filter, the ranges
    r = q(fq, dataset="ledger", rows=["child"], data=["coins_earned", "coins_spent", "internet_used", "xp"])
    assert {row[0]: row[1:] for row in r["rows"]} == {mia: [22, 8, 0, 0], leo: [20, 0, 15, 30]}
    assert q(fq, dataset="ledger", data=["coins"], profiles=[leo])["rows"] == [[20]]
    assert q(fq, dataset="ledger", data=["coins"], range="7d")["rows"] == [[27]]
    assert q(fq, dataset="ledger", data=["coins"], range="year")["rows"] == [[34]]
    assert q(fq, dataset="ledger", data=["coins"], range="all")["rows"] == [[1033]]


def test_other_datasets(fam):
    fq, mia, leo = fam
    r = q(fq, dataset="learning", rows=["subject"], data=["answers", "correct", "accuracy", "minutes"])
    assert r["rows"] == [["deutsch", 1, 1, 100, 1], ["mathematik", 4, 3, 75, 2]]
    assert r["dims"][0]["labels"] == {"deutsch": "German", "mathematik": "Mathematics"}
    r = q(fq, dataset="games", rows=["game"], data=["count", "wins", "coins"])
    assert r["rows"] == [["Tschau Sepp", 1, 1, 0], ["jump", 2, 1, 15]]          # the council is no game
    assert r["dims"][0]["labels"]["jump"] == "Jump"
    r = q(fq, dataset="weather", rows=["weather"], data=["count", "points"])
    assert sorted(r["rows"]) == [["storm", 1, -10], ["sun", 1, 5]] and r["dims"][0]["order"] == ["sun", "storm"]
    assert r["dims"][0]["labels"]["sun"] == "☀️ Sunny"
    assert q(fq, dataset="gametime", rows=["child", "weekday"], data=["minutes"])["rows"] == [[leo, 2, 25]]
    # books: the private one is not counted, and no title anywhere
    r = q(fq, dataset="reading", rows=["book_type"], data=["books"])
    assert r["rows"] == [["adventure", 1]] and "Drachenburg" not in json.dumps(r) and "Tagebuch" not in json.dumps(r)
    # guests are never part of a report
    assert all(row[0] in (mia, leo) for row in q(fq, dataset="ledger", rows=["child"], data=["count"], range="all")["rows"])


def test_whitelist_and_sql_shape():
    for bad in [{"dataset": "profile"}, {"dataset": "ledger", "rows": ["pin_hash"], "data": ["count"]},
                {"dataset": "ledger", "data": ["SUM(amount)"]}, {"dataset": "ledger", "data": ["count"], "range": "1 OR 1"},
                {"dataset": "ledger", "rows": ["child"], "columns": ["child"], "data": ["count"]},
                {"dataset": "ledger", "rows": ["day", "week", "month", "year"], "data": ["count"]},
                {"dataset": "ledger", "data": ["count"], "profiles": ["1; DROP TABLE ledger"]},
                {"dataset": "ledger", "data": ["count"], "chart": "<svg>"}, {"dataset": "learning", "rows": ["account"], "data": ["answers"]}]:
        with pytest.raises(AnalyticsError):
            clean_spec(bad)
    spec = clean_spec({"dataset": "ledger", "rows": ["week"], "data": ["coins"], "profiles": [3, 2]})
    sql, args = build_sql(spec, TODAY)
    assert args == ["2026-10-21", "2026-11-20", 2, 3] and f"LIMIT {MAX_ROWS + 1}" in sql      # the day after: «<»


def test_read_only_and_row_cap(fam, monkeypatch):
    fq, mia, _ = fam
    from familyquest import analytics
    an = Analytics(fq.db)
    with pytest.raises(Exception):
        an._run("DELETE FROM ledger", [])
    assert fq.db.val("SELECT COUNT(*) FROM ledger") == 8
    fq.db.x("INSERT INTO ledger(profile_id, account, amount) VALUES(?, 'coins', 1)", mia)    # writes work again afterwards
    monkeypatch.setattr(analytics, "MAX_ROWS", 2)
    r = an.query({"dataset": "ledger", "rows": ["day"], "data": ["count"], "range": "all"}, today=TODAY)
    assert r["truncated"] and len(r["rows"]) == 2


def test_api_parent_only_whitelist_400_and_reports_round_trip(client):
    ph, mia, leo = setup_family(client)
    seed(client.app.state.fq.db, mia, leo)
    kid = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    for hdr in ({}, kid):
        assert client.get("/api/parent/analytics/meta", headers=hdr).status_code in (401, 403)
        assert client.post("/api/parent/analytics/query", json={"dataset": "ledger", "data": ["count"]}, headers=hdr).status_code in (401, 403)
        assert client.get("/api/parent/analytics/reports", headers=hdr).status_code in (401, 403)
    m = client.get("/api/parent/analytics/meta", headers=ph).json()
    assert set(m["datasets"]) == set(DATASETS) and len(m["templates"]) >= 10 and [p["name"] for p in m["profiles"]] == ["Mia", "Leo", "Papa"]
    r = client.post("/api/parent/analytics/query", json={"dataset": "ledger", "rows": ["child"], "data": ["coins"], "range": "all"}, headers=ph)
    assert r.status_code == 200 and {x[0]: x[1] for x in r.json()["rows"]}[leo] == 20
    for bad in [{"dataset": "sqlite_master", "data": ["count"]}, {"dataset": "ledger", "rows": ["l.amount"], "data": ["count"]},
                {"dataset": "ledger", "data": ["count) FROM profile --"]}, {"dataset": "ledger"}, ["ledger"]]:
        assert client.post("/api/parent/analytics/query", json=bad, headers=ph).status_code in (400, 422), bad
    # saved reports: save, list, rename, change, delete – the spec is checked like a query
    spec = {"dataset": "games", "rows": ["game"], "columns": ["child"], "data": ["count"], "range": "year", "chart": "stacked"}
    r = client.post("/api/parent/analytics/reports", json={"name": "  Spiele   im Jahr ", "spec": spec}, headers=ph)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert client.get("/api/parent/analytics/reports", headers=ph).json() == [{"id": rid, "name": "Spiele im Jahr", "spec": {**spec, "group": [], "profiles": []}}]
    assert client.post("/api/parent/analytics/reports", json={"name": "x", "spec": {**spec, "rows": ["evil"]}}, headers=ph).status_code == 400
    assert client.post("/api/parent/analytics/reports", json={"name": " ", "spec": spec}, headers=ph).status_code == 400
    assert client.put(f"/api/parent/analytics/reports/{rid}", json={"name": "Games"}, headers=ph).json()["name"] == "Games"
    assert client.put(f"/api/parent/analytics/reports/{rid}", json={"spec": {**spec, "chart": "pie"}}, headers=ph).json()["spec"]["chart"] == "pie"
    assert client.put("/api/parent/analytics/reports/nope", json={"name": "x"}, headers=ph).status_code == 404
    assert client.put(f"/api/parent/analytics/reports/{rid}", json={"name": "x"}, headers=kid).status_code in (401, 403)
    assert client.get("/api/parent/analytics/meta", headers=ph).json()["reports"][0]["name"] == "Games"
    # in the backup (the whole database, settings included)
    assert client.app.state.fq.db.get_setting("analytics_reports")[0]["id"] == rid
    assert client.delete(f"/api/parent/analytics/reports/{rid}", headers=ph).json() == {"ok": True}
    assert client.get("/api/parent/analytics/reports", headers=ph).json() == []
    assert client.delete(f"/api/parent/analytics/reports/{rid}", headers=ph).status_code == 404


def test_templates_are_valid_and_run(fam):
    fq, _, _ = fam
    keys = [t["key"] for t in TEMPLATES]
    assert len(keys) == len(set(keys)) >= 15
    covered = {t["spec"]["dataset"] for t in TEMPLATES}
    assert covered == set(DATASETS), set(DATASETS) - covered
    for t in TEMPLATES:
        spec = clean_spec(t["spec"])
        assert spec["data"] and (spec["rows"] or spec["columns"]), t["key"]
        r = Analytics(fq.db, fq.weather).query(spec, today=TODAY)
        assert isinstance(r["rows"], list), t["key"]
    # every dimension and measure has its label in the UI (web/parent-analytics.js)
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "family_quest/app/web/parent-analytics.js").read_text(encoding="utf-8")
    for k, ds in DATASETS.items():
        for key in [k, *ds["dims"], *ds["measures"]]:
            assert f"{key}:" in js or f'"{key}":' in js, key
    for key in COMMON_DIMS:
        assert f"{key}:" in js, key


def test_period_overrides_the_range(fam):
    fq, mia, leo = fam
    # the timeline filter of a dashboard: a fixed period instead of the range of the report
    r = q(fq, dataset="ledger", rows=["child"], data=["coins"], range="all", **{"from": "2026-11-16", "to": "2026-11-17"})
    assert {x[0]: x[1] for x in r["rows"]} == {mia: 10, leo: 20} and (r["from"], r["to"]) == ("2026-11-16", "2026-11-17")
    assert q(fq, dataset="ledger", data=["coins"], **{"from": "2025-01-01", "to": "2025-12-31"})["rows"] == [[999]]
    for bad in [{"from": "2026-11-17", "to": "2026-11-16"}, {"from": "2026-02-30", "to": "2026-03-01"},
                {"from": "2026-11-16"}, {"from": "x' OR 1=1", "to": "2026-11-16"}]:
        with pytest.raises(AnalyticsError):
            clean_spec({"dataset": "ledger", "data": ["count"], **bad})


def test_dashboards_crud_and_layout_round_trip(client):
    ph, mia, leo = setup_family(client)
    kid = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.get("/api/parent/analytics/dashboards", headers=kid).status_code in (401, 403)
    assert client.post("/api/parent/analytics/dashboards", json={"name": "x"}, headers=kid).status_code in (401, 403)
    ds = client.get("/api/parent/analytics/dashboards", headers=ph).json()
    assert [d["id"] for d in ds] == ["std"] and 4 <= len(ds[0]["tiles"]) <= 6
    assert all(t["ref"].startswith("t:") for t in ds[0]["tiles"])
    tpl = {t["key"] for t in TEMPLATES}
    assert all(t["ref"][2:] in tpl for t in ds[0]["tiles"])
    rep = client.post("/api/parent/analytics/reports", json={"name": "Mine", "spec": {"dataset": "daily", "rows": ["day"], "data": ["xp"]}}, headers=ph).json()
    d = client.post("/api/parent/analytics/dashboards", json={"name": "Schule"}, headers=ph).json()
    tiles = [{"ref": "r:" + rep["id"], "w": 4, "h": "l", "title": "Mein XP"}, {"ref": "t:coins_week", "w": 1, "h": "s", "chart": "pie"}]
    r = client.put(f"/api/parent/analytics/dashboards/{d['id']}", json={"tiles": tiles, "period": {"type": "week", "from": "2026-11-16", "to": "2026-11-22"}}, headers=ph)
    assert r.status_code == 200, r.text
    got = r.json()
    assert [(t["ref"], t["w"], t["h"], t["title"], t.get("chart")) for t in got["tiles"]] == [("r:" + rep["id"], 4, "l", "Mein XP", None), ("t:coins_week", 1, "s", "", "pie")]
    assert got["period"] == {"type": "week", "from": "2026-11-16", "to": "2026-11-22"}
    # the ids stay when the layout is saved again (moved)
    again = client.put(f"/api/parent/analytics/dashboards/{d['id']}", json={"tiles": got["tiles"][::-1]}, headers=ph).json()
    assert [t["id"] for t in again["tiles"]] == [t["id"] for t in got["tiles"]][::-1]
    listed = {x["id"]: x for x in client.get("/api/parent/analytics/dashboards", headers=ph).json()}
    assert listed[d["id"]]["tiles"] == again["tiles"] and listed[d["id"]]["period"]["type"] == "week"
    for bad in [{"tiles": [{"ref": "t:nope"}]}, {"tiles": [{"ref": "t:coins_week", "w": 5}]}, {"tiles": [{"ref": "t:coins_week", "h": "xl"}]},
                {"tiles": [{"ref": "t:coins_week", "chart": "radar"}]}, {"period": {"type": "decade"}}, {"period": {"type": "custom"}},
                {"period": {"type": "custom", "from": "2026-12-01", "to": "2026-11-01"}}, {"tiles": [{"ref": "t:coins_week"}] * 25}]:
        assert client.put(f"/api/parent/analytics/dashboards/{d['id']}", json=bad, headers=ph).status_code == 400, bad
    assert client.put(f"/api/parent/analytics/dashboards/{d['id']}", json={"name": "Lernen"}, headers=ph).json()["name"] == "Lernen"
    assert client.put("/api/parent/analytics/dashboards/std", json={"period": {"type": "year"}}, headers=ph).json()["period"] == {"type": "year"}
    assert client.delete("/api/parent/analytics/dashboards/std", headers=ph).status_code == 400
    assert client.delete(f"/api/parent/analytics/dashboards/{d['id']}", headers=ph).json() == {"ok": True}
    assert [x["id"] for x in client.get("/api/parent/analytics/dashboards", headers=ph).json()] == ["std"]
    assert client.delete(f"/api/parent/analytics/dashboards/{d['id']}", headers=ph).status_code == 404


def test_ui_info_texts_and_translations():
    """The ⓘ of the Analytics page (PARENT_INFO entries added in parent-analytics.js) and every text of it in 9 languages;
    the saved reports are called «My reports» everywhere."""
    import re
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "family_quest/app/web"
    js = (web / "parent-analytics.js").read_text(encoding="utf-8")
    info = js[js.index("Object.assign(PARENT_INFO, {"):js.index("\n});\n")]
    keys = set(re.findall(r'^  \[T\("([^"]+)"\)\]:', info, re.M))
    assert {"Analytics", "Dashboards", "Templates", "My reports", "Ad-hoc report", "Add report"} <= keys
    for title in ["Templates", "My reports", "Ad-hoc report", "Dashboards", "Add report", "Analytics"]:
        assert f'T("{title}")' in js.replace(info, "")          # the heading exists on the page
    assert "Custom templates" not in js
    texts = set(re.findall(r'\bT\("((?:[^"\\]|\\.)*)"\)', js))
    for lang in ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]:
        d = json.loads((web / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        missing = sorted(t for t in texts if json.loads('"' + t + '"') not in d)
        assert not missing, (lang, missing[:5])
    de = json.loads((web / "i18n" / "de-DE.json").read_text(encoding="utf-8"))
    ch = json.loads((web / "i18n" / "de-CH.json").read_text(encoding="utf-8"))
    assert de["My reports"] == "Meine Berichte" and ch["My reports"] == "Mini Bricht"


def test_bubble_chart_and_its_template(fam):
    """«Bubbles»: Rows = x categories, Columns = y categories, the first measure = the area – a known chart type, its
    template (game time by weekday and child) is valid and gives a weekday × child matrix."""
    from familyquest.analytics import CHARTS
    fq, mia, leo = fam
    assert "bubble" in CHARTS
    tpl = next(t for t in TEMPLATES if t["key"] == "gametime_matrix")
    assert tpl["spec"]["chart"] == "bubble" and tpl["spec"]["rows"] == ["weekday"] and tpl["spec"]["columns"] == ["child"]
    spec = clean_spec(tpl["spec"])
    assert spec["chart"] == "bubble"
    for m in range(25):
        fq.db.x("INSERT INTO play_minute(profile_id, day, minute) VALUES(?, '2026-11-16', ?)", mia, 600 + m)
    for m in range(10):
        fq.db.x("INSERT INTO play_minute(profile_id, day, minute) VALUES(?, '2026-11-17', ?)", leo, 600 + m)
    r = Analytics(fq.db, fq.weather).query(spec, today=TODAY)
    got = {(row[0], row[1]): row[2] for row in r["rows"]}
    assert got[(0, mia)] == 25 and got[(1, leo)] == 10, got                 # Monday · Mia, Tuesday · Leo
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "family_quest/app/web"
    js = (web / "parent-analytics.js").read_text(encoding="utf-8")
    assert '["bubble", T("Bubbles")' in js and 'type === "bubble"' in js
    for lang in ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]:
        d = json.loads((web / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["Bubbles"] and d["Game time by weekday and child"], lang


def test_bubble_tile_on_a_dashboard(client):
    ph = setup_family(client)[0]
    d = client.post("/api/parent/analytics/dashboards", json={"name": "Spielzeit"}, headers=ph).json()
    tiles = [{"ref": "t:gametime_matrix", "w": 2, "h": "m"}, {"ref": "t:coins_week", "w": 2, "h": "m", "chart": "bubble"}]
    r = client.put(f"/api/parent/analytics/dashboards/{d['id']}", json={"tiles": tiles}, headers=ph)
    assert r.status_code == 200, r.text
    assert [(t["ref"], t.get("chart")) for t in r.json()["tiles"]] == [("t:gametime_matrix", None), ("t:coins_week", "bubble")]
