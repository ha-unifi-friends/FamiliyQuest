"""Family calendar: special events the parents enter, templates (school holidays and public holidays of every Swiss
canton), CSV and iCal import with a duplicate check, and calendars of Home Assistant shown read-only.

Own events are stored in `family_event`. Dates are ISO strings: all-day events «2026-07-04» … «2026-08-09» (the end
day is included), events with a time «2026-11-20T18:00». A duplicate is the same title (ignoring case and spaces)
with the same start and end, or the same iCal UID.
School and public holidays come from the free OpenHolidays API (openholidaysapi.org, no account) and are only
fetched when a parent asks for a template.
"""
from __future__ import annotations

import json

import csv
import io
import re
import time
from datetime import date, datetime, timedelta

import httpx

OPENHOLIDAYS = "https://openholidaysapi.org"
# the 26 cantons (ISO 3166-2:CH) – names stay as they are (proper names)
CANTONS = {
    "CH-AG": "Aargau", "CH-AI": "Appenzell Innerrhoden", "CH-AR": "Appenzell Ausserrhoden", "CH-BE": "Bern / Berne",
    "CH-BL": "Basel-Landschaft", "CH-BS": "Basel-Stadt", "CH-FR": "Fribourg / Freiburg", "CH-GE": "Genève",
    "CH-GL": "Glarus", "CH-GR": "Graubünden / Grigioni", "CH-JU": "Jura", "CH-LU": "Luzern",
    "CH-NE": "Neuchâtel", "CH-NW": "Nidwalden", "CH-OW": "Obwalden", "CH-SG": "St. Gallen", "CH-SH": "Schaffhausen",
    "CH-SO": "Solothurn", "CH-SZ": "Schwyz", "CH-TG": "Thurgau", "CH-TI": "Ticino", "CH-UR": "Uri",
    "CH-VD": "Vaud", "CH-VS": "Valais / Wallis", "CH-ZG": "Zug", "CH-ZH": "Zürich",
}
KEY = "calendar"
MAX_TEXT = 120


class CalendarError(ValueError):
    pass


def _norm(title: str) -> str:
    return " ".join(str(title or "").lower().split())


def _day(v: str) -> str:
    """«2026-07-04», «04.07.2026», «4.7.26», «20260704» → «2026-07-04» (ValueError otherwise)."""
    v = str(v or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return date.fromisoformat(v).isoformat()
    if re.fullmatch(r"\d{8}", v):
        return date(int(v[:4]), int(v[4:6]), int(v[6:])).isoformat()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})", v)
    if m:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return date(y, int(m[2]), int(m[1])).isoformat()
    raise ValueError(v)


def _when(v: str) -> tuple[str, bool]:
    """A date or a date with time → (ISO string, all_day)."""
    v = str(v or "").strip().replace(" ", "T", 1) if re.match(r"^\S+ \d{1,2}:\d{2}", str(v or "").strip()) else str(v or "").strip()
    if "T" in v:
        d, t = v.split("T", 1)
        hh, mm = t[:5].split(":")
        return f"{_day(d)}T{int(hh):02d}:{int(mm):02d}", False
    return _day(v), True


def clean_event(e: dict) -> dict:
    title = str(e.get("title") or "").strip()[:MAX_TEXT]
    if not title:
        raise CalendarError("The event needs a title")
    try:
        start, all_day = _when(e.get("start"))
        end, _ = _when(e.get("end") or e.get("start"))
    except (ValueError, TypeError):
        raise CalendarError("Dates must look like 2026-07-04 or 04.07.2026") from None
    if not all_day and "T" not in end:
        end = end + start[10:]
    if all_day and "T" in end:
        end = end[:10]
    if end < start:
        raise CalendarError("The end is before the start")
    kind = str(e.get("kind") or "event")[:20]
    o = e.get("options") if isinstance(e.get("options"), dict) else {}
    options = {}
    if kind == "offlinetime":           # what OfflineTime does: internet off and / or app games locked – for whom
        options = {"internet": bool(o.get("internet")), "games": bool(o.get("games")),
                   "profiles": sorted({int(x) for x in o.get("profiles") or [] if str(x).isdigit()})}
    return {"title": title, "start": start, "end": end, "all_day": all_day,
            "icon": str(e.get("icon") or "").strip()[:8], "color": str(e.get("color") or "")[:9],
            "kind": kind, "note": str(e.get("note") or "").strip()[:500],
            "uid": str(e.get("uid") or "")[:200], "options": options}


# ---------------------------------------------------------------- parsers
def parse_csv(text: str) -> list[dict]:
    """Rows title;start;end (header optional, «;» or «,» or tab). Header names: title/summary/name/titel,
    start/date/from/von/datum, end/to/bis."""
    text = text.lstrip("﻿")
    if not text.strip():
        raise CalendarError("The file is empty")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    head = [c.strip().lower() for c in rows[0]]
    names = {"title": ("title", "summary", "name", "titel", "ereignis", "event"), "start": ("start", "date", "from", "von", "datum", "beginn"),
             "end": ("end", "to", "bis", "ende")}
    idx = {k: next((head.index(n) for n in ns if n in head), None) for k, ns in names.items()}
    if idx["title"] is not None and idx["start"] is not None:
        rows = rows[1:]
    else:
        idx = {"title": 0, "start": 1, "end": 2}
    out = []
    for r in rows:
        get = lambda k: r[idx[k]].strip() if idx[k] is not None and idx[k] < len(r) else ""   # noqa: E731
        try:
            out.append(clean_event({"title": get("title"), "start": get("start"), "end": get("end") or get("start")}))
        except CalendarError:
            continue
    return out


def _ics_unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _ics_text(v: str) -> str:
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse_ics(text: str) -> list[dict]:
    """VEVENTs of an iCal file. All-day events (VALUE=DATE): DTEND is the day after in iCal → stored inclusive."""
    out, ev = [], None
    for line in _ics_unfold(text):
        if line == "BEGIN:VEVENT":
            ev = {}
            continue
        if line == "END:VEVENT":
            if ev and ev.get("DTSTART"):
                try:
                    out.append(_ics_event(ev))
                except (CalendarError, ValueError):
                    pass
            ev = None
            continue
        if ev is None or ":" not in line:
            continue
        name, value = line.split(":", 1)
        key, *params = name.split(";")
        ev[key.upper()] = (value, [p.upper() for p in params])
    return out


def _ics_dt(value: str, params: list[str]) -> tuple[str, bool]:
    v = value.strip()
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", v):
        return _day(v[:8]), True
    m = re.fullmatch(r"(\d{8})T(\d{2})(\d{2})(\d{2})?(Z)?", v)
    if not m:
        raise ValueError(v)
    if m[5]:                                        # UTC → local time of this computer
        dt = datetime(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:]), int(m[2]), int(m[3]))
        dt = dt.replace(tzinfo=__import__("datetime").timezone.utc).astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M"), False
    return f"{_day(m[1])}T{m[2]}:{m[3]}", False


def _ics_event(ev: dict) -> dict:
    start, all_day = _ics_dt(*ev["DTSTART"])
    if "DTEND" in ev:
        end, _ = _ics_dt(*ev["DTEND"])
        if all_day:
            end = (date.fromisoformat(end) - timedelta(days=1)).isoformat()
            end = max(end, start)
    else:
        end = start
    title = _ics_text(ev.get("SUMMARY", ("",))[0]) or "?"
    return clean_event({"title": title, "start": start, "end": end, "uid": ev.get("UID", ("",))[0],
                        "note": _ics_text(ev.get("DESCRIPTION", ("",))[0])})


# ---------------------------------------------------------------- the calendar
class FamilyCalendar:
    def __init__(self, fq):
        self.fq = fq
        self.db = fq.db
        self._ha_cache: dict = {}
        self._holiday_cache: dict = {}

    # ---------- settings
    def settings(self) -> dict:
        return {"ha_calendars": [], **(self.db.get_setting(KEY) or {})}

    def save_settings(self, c: dict) -> dict:
        cals = [str(x) for x in c.get("ha_calendars") or []]
        if any(not x.startswith("calendar.") for x in cals):
            raise CalendarError("Calendars: calendar entities, e.g. calendar.family")
        out = {**self.settings(), "ha_calendars": cals[:20]}
        self.db.set_setting(KEY, out)
        self._ha_cache = {}
        return out

    # ---------- own events
    def add(self, e: dict, source: str = "manual") -> int:
        e = clean_event(e)
        return self.db.x("""INSERT INTO family_event(title, start, end, all_day, icon, color, kind, note, uid, source, options)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", e["title"], e["start"], e["end"], int(e["all_day"]), e["icon"],
                         e["color"], e["kind"], e["note"], e["uid"], source, json.dumps(e["options"]))

    def update(self, eid: int, e: dict) -> None:
        e = clean_event(e)
        if not self.db.x("""UPDATE family_event SET title=?, start=?, end=?, all_day=?, icon=?, color=?, kind=?, note=?, options=? WHERE id=?""",
                         e["title"], e["start"], e["end"], int(e["all_day"]), e["icon"], e["color"], e["kind"], e["note"],
                         json.dumps(e["options"]), eid):
            raise CalendarError("Unknown event")

    def delete(self, eid: int) -> None:
        self.db.x("DELETE FROM family_event WHERE id=?", eid)

    def delete_source(self, source: str) -> int:
        return self.db.x("DELETE FROM family_event WHERE source=?", source)

    def own(self, start: str, end: str) -> list[dict]:
        """Own events that touch the days start … end (ISO dates, end included)."""
        rows = self.db.q("""SELECT * FROM family_event WHERE substr(start,1,10) <= ? AND substr(end,1,10) >= ?
                            ORDER BY start, title""", end, start)
        return [{**r, "all_day": bool(r["all_day"]), "readonly": False, "options": json.loads(r.get("options") or "{}")} for r in rows]

    # ---------- FamilyTime and OfflineTime
    @staticmethod
    def _bounds(e: dict) -> tuple[datetime, datetime]:
        if e["all_day"]:
            return datetime.fromisoformat(e["start"][:10]), datetime.fromisoformat(e["end"][:10]) + timedelta(days=1)
        return datetime.fromisoformat(e["start"]), datetime.fromisoformat(e["end"])

    def special(self, pid: int | None = None, now: datetime | None = None, hours: int = 24) -> list[dict]:
        """FamilyTime / OfflineTime that run now or start within `hours` – for this child (None: everybody)."""
        now = now or datetime.now()
        out = []
        for e in self.own(now.date().isoformat(), (now + timedelta(hours=hours)).date().isoformat()):
            if e["kind"] not in ("familytime", "offlinetime"):
                continue
            who = e["options"].get("profiles") or []
            if pid is not None and who and pid not in who:
                continue
            a, b = self._bounds(e)
            if b <= now or a > now + timedelta(hours=hours):
                continue
            out.append({"id": e["id"], "kind": e["kind"], "title": e["title"], "icon": e["icon"], "start": a.isoformat(timespec="minutes"),
                        "end": b.isoformat(timespec="minutes"), "active": a <= now, "options": e["options"]})
        return sorted(out, key=lambda x: x["start"])

    def blocks(self, pid: int, what: str, now: datetime | None = None) -> dict | None:
        """The OfflineTime that switches off `what` (internet | games) for this child right now."""
        return next((e for e in self.special(pid, now, 0) if e["active"] and e["kind"] == "offlinetime" and e["options"].get(what)), None)

    def sources(self) -> list[dict]:
        return self.db.q("""SELECT source, COUNT(*) n, MIN(start) first, MAX(end) last FROM family_event
                            WHERE source <> 'manual' GROUP BY source ORDER BY source""")

    # ---------- duplicates and import
    def check(self, events: list[dict]) -> list[dict]:
        """Mark every event that is already in the calendar (or twice in the list)."""
        have = {(_norm(r["title"]), r["start"], r["end"]) for r in self.db.q("SELECT title, start, end FROM family_event")}
        uids = {r["uid"] for r in self.db.q("SELECT uid FROM family_event WHERE uid <> ''")}
        seen: set = set()
        out = []
        for e in events:
            k = (_norm(e["title"]), e["start"], e["end"])
            dup = k in have or k in seen or bool(e.get("uid") and e["uid"] in uids)
            seen.add(k)
            out.append({**e, "duplicate": dup})
        return out

    def import_events(self, events: list[dict], source: str) -> dict:
        added = dups = 0
        for e in self.check([clean_event(x) for x in events]):
            if e["duplicate"]:
                dups += 1
                continue
            self.add(e, source)
            added += 1
        return {"added": added, "duplicates": dups}

    # ---------- templates: school and public holidays (OpenHolidays API)
    def holidays(self, canton: str, year: int, school: bool = True, public: bool = True, lang: str = "DE") -> list[dict]:
        if canton not in CANTONS:
            raise CalendarError("Unknown canton")
        key = (canton, year, school, public, lang)
        hit = self._holiday_cache.get(key)
        if hit and time.time() - hit[0] < 6 * 3600:
            return hit[1]
        out = []
        params = {"countryIsoCode": "CH", "subdivisionCode": canton, "languageIsoCode": lang,
                  "validFrom": f"{year}-01-01", "validTo": f"{year}-12-31"}
        try:
            with httpx.Client(base_url=OPENHOLIDAYS, timeout=15, headers={"Accept": "application/json"}) as c:
                for kind, path, on in (("school", "/SchoolHolidays", school), ("public", "/PublicHolidays", public)):
                    if not on:
                        continue
                    r = c.get(path, params=params)
                    r.raise_for_status()
                    for h in r.json():
                        out.append(self._holiday(h, kind, canton, lang))
        except (httpx.HTTPError, ValueError) as e:
            raise CalendarError(f"The holiday service cannot be reached: {e}") from None
        out = [e for e in out if e]
        out.sort(key=lambda e: e["start"])
        self._holiday_cache[key] = (time.time(), out)
        return out

    @staticmethod
    def _holiday(h: dict, kind: str, canton: str, lang: str) -> dict | None:
        names = h.get("name") or []
        name = next((n.get("text") for n in names if str(n.get("language", "")).upper() == lang), None) \
            or next((n.get("text") for n in names), "")
        subs = [s.get("shortName") or s.get("code") for s in h.get("subdivisions") or []]
        region = ", ".join(x for x in subs if x and x not in (canton, canton[3:]))
        try:
            return clean_event({"title": name + (f" ({region})" if region and kind == "school" else ""), "start": h["startDate"],
                                "end": h.get("endDate") or h["startDate"], "kind": kind, "icon": "🏖️" if kind == "school" else "🎉",
                                "uid": f"oh:{h.get('id', '')}:{canton}"})
        except (CalendarError, KeyError):
            return None

    # ---------- Home Assistant calendars (read-only)
    def ha_events(self, start: str, end: str) -> list[dict]:
        cals = self.settings()["ha_calendars"]
        ha = self.fq.ha
        if not cals or not ha or not ha.connected:
            return []
        key = (tuple(cals), start, end)
        hit = self._ha_cache.get(key)
        if hit and time.time() - hit[0] < 120:
            return hit[1]
        try:
            ev = ha.calendar_range(cals, datetime.fromisoformat(start), datetime.fromisoformat(end) + timedelta(days=1))
        except Exception:  # noqa: BLE001 – a calendar that does not answer must not break the page
            ev = hit[1] if hit else []
        ev = [{**e, "readonly": True, "start": e["start"][:16], "end": (e["end"] or e["start"])[:16]} for e in ev]
        self._ha_cache[key] = (time.time(), ev)
        return ev

    def range(self, start: str, end: str) -> list[dict]:
        return sorted(self.own(start, end) + self.ha_events(start, end), key=lambda e: (e["start"], e["title"]))
