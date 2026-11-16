import httpx

from familyquest import calendar as cal_mod
from test_api import setup_family

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:abc-1@example
DTSTART;VALUE=DATE:20260704
DTEND;VALUE=DATE:20260810
SUMMARY:Sommerferien\\, Thurgau
END:VEVENT
BEGIN:VEVENT
UID:abc-2@example
DTSTART:20261120T180000
DTEND:20261120T200000
SUMMARY:Elternabend
DESCRIPTION:Schulhaus
  Mitte
END:VEVENT
END:VCALENDAR
"""


def test_parsers():
    ev = cal_mod.parse_ics(ICS)
    assert ev[0]["title"] == "Sommerferien, Thurgau" and ev[0]["start"] == "2026-07-04" and ev[0]["end"] == "2026-08-09"
    assert ev[1]["start"] == "2026-11-20T18:00" and not ev[1]["all_day"] and ev[1]["note"] == "Schulhaus Mitte"
    rows = cal_mod.parse_csv("Titel;Von;Bis\nSkilager;02.02.2026;06.02.2026\nZahnarzt;2026-03-03;\nkaputt;xx;\n")
    assert [(r["title"], r["start"], r["end"]) for r in rows] == [("Skilager", "2026-02-02", "2026-02-06"), ("Zahnarzt", "2026-03-03", "2026-03-03")]


def test_calendar_import_with_duplicates(client):
    ph, _, _ = setup_family(client)
    assert client.post("/api/parent/calendar", json={"title": "Geburtstag Mia", "start": "2026-05-12", "icon": "🎂"}, headers=ph).status_code == 200
    assert client.post("/api/parent/calendar", json={"title": "x", "start": "2026-05-12", "end": "2026-05-01"}, headers=ph).status_code == 400
    prev = client.post("/api/parent/calendar/parse", json={"name": "schule.ics", "text": ICS}, headers=ph).json()
    assert len(prev) == 2 and not any(e["duplicate"] for e in prev)
    r = client.post("/api/parent/calendar/import", json={"events": prev, "source": "file:schule.ics"}, headers=ph).json()
    assert r == {"added": 2, "duplicates": 0}
    again = client.post("/api/parent/calendar/parse", json={"name": "schule.ics", "text": ICS}, headers=ph).json()
    assert all(e["duplicate"] for e in again)                                         # same UID / title and dates
    assert client.post("/api/parent/calendar/import", json={"events": again, "source": "file:schule.ics"}, headers=ph).json()["duplicates"] == 2
    d = client.get("/api/parent/calendar?start=2026-07-01&end=2026-07-31", headers=ph).json()
    assert [e["title"] for e in d["events"]] == ["Sommerferien, Thurgau"] and d["sources"][0]["n"] == 2
    assert client.delete("/api/parent/calendar/source/file:schule.ics", headers=ph).json()["deleted"] == 2
    assert client.put("/api/parent/calendar/settings", json={"ha_calendars": ["light.x"]}, headers=ph).status_code == 400
    assert client.put("/api/parent/calendar/settings", json={"ha_calendars": ["calendar.familie"]}, headers=ph).json()["ha_calendars"] == ["calendar.familie"]


def test_holiday_template(client, monkeypatch):
    ph, _, _ = setup_family(client)
    data = {"/SchoolHolidays": [{"id": "s1", "startDate": "2026-07-04", "endDate": "2026-08-09", "type": "School",
                                  "name": [{"language": "DE", "text": "Sommerferien"}], "subdivisions": [{"code": "CH-TG", "shortName": "TG"}]}],
            "/PublicHolidays": [{"id": "p1", "startDate": "2026-08-01", "endDate": "2026-08-01", "type": "Public",
                                  "name": [{"language": "DE", "text": "Bundesfeiertag"}]}]}

    def handler(req):
        assert req.url.params["subdivisionCode"] == "CH-TG" and req.url.params["validFrom"] == "2026-01-01"
        return httpx.Response(200, json=data[req.url.path])
    real = httpx.Client
    monkeypatch.setattr(cal_mod.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    prev = client.get("/api/parent/calendar/holidays?canton=CH-TG&year=2026", headers=ph).json()
    assert [(e["title"], e["kind"]) for e in prev] == [("Sommerferien", "school"), ("Bundesfeiertag", "public")]
    client.post("/api/parent/calendar/import", json={"events": prev, "source": "holidays:CH-TG:2026"}, headers=ph)
    assert all(e["duplicate"] for e in client.get("/api/parent/calendar/holidays?canton=CH-TG&year=2026", headers=ph).json())
    assert client.get("/api/parent/calendar/holidays?canton=CH-XX&year=2026", headers=ph).status_code == 400


def test_familytime_and_offlinetime(client):
    from datetime import datetime, timedelta
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    now = datetime.now()
    f = lambda d: (now + d).strftime("%Y-%m-%dT%H:%M")
    # OfflineTime now, only for Leo: games locked, internet off
    r = client.post("/api/parent/calendar", json={"title": "Offline", "kind": "offlinetime", "start": f(timedelta(minutes=-10)), "end": f(timedelta(hours=1)),
                                                  "options": {"internet": True, "games": True, "profiles": [leo]}}, headers=ph)
    assert r.status_code == 200, r.text
    # FamilyTime in two hours for everybody
    client.post("/api/parent/calendar", json={"title": "Spielabend", "kind": "familytime", "start": f(timedelta(hours=2)), "end": f(timedelta(hours=4))}, headers=ph)
    me = client.get("/api/me", headers=hl).json()
    assert me["games_list"] == [] and [(x["kind"], x["active"]) for x in me["special_times"]] == [("offlinetime", True), ("familytime", False)]
    assert client.get("/api/community/bingo", headers=hl).status_code == 403
    assert client.get("/api/community/bingo", headers=hm).status_code == 200            # Mia is not in this OfflineTime
    assert [x["kind"] for x in client.get("/api/me", headers=hm).json()["special_times"]] == ["familytime"]
    assert client.app.state.fq.internet.offline(leo) and not client.app.state.fq.internet.offline(mia)
    ev = client.get(f"/api/parent/calendar?start={now.date()}&end={now.date()}", headers=ph).json()
    assert any(e["kind"] == "offlinetime" and e["options"]["profiles"] == [leo] for e in (ev.get("events", ev) if isinstance(ev, dict) else ev))


def test_planner_gets_the_family_calendars(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/parent/calendar", headers=ph, json={"title": "Skilager", "start": "2026-02-02", "end": "2026-02-06", "all_day": True})
    client.post("/api/parent/calendar", headers=ph, json={"title": "Zahnarzt", "start": "2026-02-03T14:00", "end": "2026-02-03T15:00", "all_day": False})
    cals = client.get("/api/planer/fq-calendars", headers=hm).json()
    assert cals[0]["entity"] == "familyquest"
    ev = client.get("/api/planer/fq-events?start=2026-02-02T00:00:00&end=2026-02-09T00:00:00", headers=hm).json()
    ski = next(e for e in ev if e["summary"].endswith("Skilager"))
    assert ski["start"] == {"date": "2026-02-02"} and ski["end"] == {"date": "2026-02-07"}       # all day: end exclusive
    assert any(e["start"] == {"dateTime": "2026-02-03T14:00"} for e in ev)
