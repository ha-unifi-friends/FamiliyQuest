"""Pack store: packs live in the database (JSON); folders are synced in at start."""
from __future__ import annotations

import json
import logging
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .. import generators
from ..i18n import _t
from ..db import Database
from .loader import PackError, content_hash, iter_dir, media_refs, pack_dict, parse_doc, store_media
from .schema import Bundle, Pack, card_key, card_view, skill_key

log = logging.getLogger("familyquest.packs")

# Subjects: English names (translated in the UI), colour and icon. Packs can name others.
SUBJECTS = {
    "deutsch": (_t("German"), "#e8590c", "📖"),
    "mathematik": (_t("Mathematics"), "#1c7ed6", "➗"),
    "nmg": (_t("Nature, people, society"), "#2f9e44", "🌍"),
    "geografie": (_t("Geography"), "#2f9e44", "🗺️"),
    "englisch": (_t("English"), "#c2255c", "🇬🇧"),
    "franzoesisch": (_t("French"), "#5f3dc4", "🇫🇷"),
    "italienisch": (_t("Italian"), "#0ca678", "🇮🇹"),
    "spanisch": (_t("Spanish"), "#f08c00", "🇪🇸"),
    "allgemeinwissen": (_t("General knowledge"), "#7048e8", "🧠"),
    "allgemein": (_t("General"), "#868e96", "📚"),
}


def subject_meta(key: str) -> dict:
    name, color, icon = SUBJECTS.get(key, (key.replace("-", " ").capitalize(), "#868e96", "📚"))
    return {"key": key, "name": name, "color": color, "icon": icon}


@dataclass
class UnitInfo:
    id: str
    title: str
    kind: str                          # cards | generator
    exercises: list[str]
    icon: str = ""
    description: str = ""
    items: list[dict] = field(default_factory=list)       # cards: {key, view, card}
    generator: str | None = None
    params: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)

    def keys(self, pack_id: str) -> list[str]:
        if self.kind == "cards":
            return [i["key"] for i in self.items]
        return [skill_key(pack_id, self.id, s) for s in self.skills]


@dataclass
class PackInfo:
    id: str
    kind: str
    title: str
    subject: str
    level: str
    status: str
    source: str
    version: str
    model: Pack | Bundle
    units: list[UnitInfo] = field(default_factory=list)

    def unit(self, unit_id: str) -> UnitInfo | None:
        return next((u for u in self.units if u.id == unit_id), None)

    @property
    def lang(self) -> str:
        return getattr(self.model, "sprache", "") or ""

    def summary(self) -> dict:
        m = self.model
        d = {"id": self.id, "kind": self.kind, "title": self.title, "subject": subject_meta(self.subject),
             "level": self.level, "status": self.status, "source": self.source, "version": self.version}
        if isinstance(m, Pack):
            d.update(lang=m.sprache, src_lang=m.quellsprache, private=m.privat, path=m.pfad, color=m.farbe or d["subject"]["color"],
                     standard=m.standard, self_service=m.selbst,
                     icon=m.icon or d["subject"]["icon"], description=m.beschreibung,
                     units=[{"id": u.id, "title": u.title, "kind": u.kind, "count": len(u.items) or len(u.skills),
                             "exercises": u.exercises, "icon": u.icon} for u in self.units])
        else:
            d.update(subjects=m.faecher, semesters=[s.model_dump() for s in m.semester], plan=m.lehrplan)
        return d


def build_info(row: dict) -> PackInfo:
    data = json.loads(row["data"])
    model = parse_doc(data)
    info = PackInfo(id=row["id"], kind=row["kind"], title=row["title"], subject=row["subject"] or "allgemein",
                    level=row["level"] or "", status=row["status"], source=row["source"], version=row["version"] or "1",
                    model=model)
    if isinstance(model, Pack):
        pd = model.model_dump()
        for u in model.einheiten:
            if u.generator:
                try:
                    g = generators.get(u.generator)
                    skills = g.skills(u.parameter)
                except (KeyError, ValueError, TypeError) as e:
                    log.warning("pack %s unit %s: %s", model.id, u.id, e)
                    skills = []
                info.units.append(UnitInfo(u.id, u.titel, "generator", u.uebungen or ["rechnen"], u.icon, u.beschreibung,
                                           generator=u.generator, params=u.parameter, skills=skills))
            else:
                items, seen = [], set()
                for c in u.karten:
                    v = card_view(pd, c)
                    if not v["answer"] and not v["prompt"]:
                        continue
                    k = card_key(model.id, u.id, c, v)
                    if k in seen:
                        continue
                    seen.add(k)
                    items.append({"key": k, "view": v, "card": c})
                ex = u.uebungen or (["zuordnen"] if u.model_extra and u.model_extra.get("typ") == "zuordnen"
                                    else ["auswahl", "eintippen", "paare", "karteikarte"])
                info.units.append(UnitInfo(u.id, u.titel, "cards", ex, u.icon, u.beschreibung, items=items))
    return info


class PackStore:
    def __init__(self, db: Database, media_dir: Path):
        self.db = db
        self.media_dir = media_dir
        self._cache: dict[str, PackInfo] = {}
        self._lock = threading.Lock()

    # ---------- write ----------
    def upsert(self, p: Pack | Bundle, source: str, status: str | None = None, media: dict | None = None,
               force: bool = False) -> tuple[str, str]:
        """Store a pack. Returns (id, what) with what in new|updated|unchanged|kept."""
        pid = p.id
        h = content_hash(p)
        row = self.db.q1("SELECT source, status, hash FROM pack WHERE id=?", pid)
        if row and row["hash"] == h and not force and (status is None or status == row["status"]):
            if media and not (self.media_dir / pid).is_dir():          # e.g. after a restore (backups leave them out)
                store_media(self.media_dir, pid, media, media_refs(p) or None)
            return pid, "unchanged"
        if row and not force and source in ("builtin", "share") and row["source"] not in ("builtin", "share"):
            return pid, "kept"            # edited / uploaded by a parent – folder copy does not override
        kind = "bundle" if isinstance(p, Bundle) else "pack"
        subject = None if isinstance(p, Bundle) else p.fach
        level = p.stufe
        st = status or (row["status"] if row else "active")
        self.db.x(
            """INSERT INTO pack(id,kind,title,subject,level,version,source,status,hash,data,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,title=excluded.title,subject=excluded.subject,
               level=excluded.level,version=excluded.version,source=excluded.source,status=excluded.status,
               hash=excluded.hash,data=excluded.data,updated_at=excluded.updated_at""",
            pid, kind, p.titel, subject, level, p.version, source, st, h, json.dumps(pack_dict(p), ensure_ascii=False))
        if media:
            store_media(self.media_dir, pid, media, media_refs(p) or None)
        self.invalidate(pid)
        return pid, ("updated" if row else "new")

    def set_status(self, pack_id: str, status: str) -> None:
        self.db.x("UPDATE pack SET status=? WHERE id=?", status, pack_id)
        self.invalidate(pack_id)

    def delete(self, pack_id: str) -> None:
        with self.db.tx():
            self.db.x("DELETE FROM pack WHERE id=?", pack_id)
            self.db.x("DELETE FROM pack_profile WHERE pack_id=?", pack_id)
        shutil.rmtree(self.media_dir / pack_id, ignore_errors=True)
        self.invalidate(pack_id)

    def invalidate(self, pack_id: str | None = None) -> None:
        with self._lock:
            if pack_id is None:
                self._cache.clear()
            else:
                self._cache.pop(pack_id, None)

    def sync_folders(self, folders: list[Path]) -> dict:
        stats = {"new": 0, "updated": 0, "unchanged": 0, "kept": 0}
        for i, folder in enumerate(folders):
            source = "builtin" if i == 0 else "share"
            for p, media in iter_dir(folder):
                try:
                    _, what = self.upsert(p, source, media=media)
                    stats[what] += 1
                except PackError as e:
                    log.warning("pack %s: %s", getattr(p, "id", "?"), e)
        log.info("packs synced: %s", stats)
        return stats

    # ---------- read ----------
    def get(self, pack_id: str) -> PackInfo | None:
        with self._lock:
            if pack_id in self._cache:
                return self._cache[pack_id]
        row = self.db.q1("SELECT * FROM pack WHERE id=?", pack_id)
        if not row:
            return None
        try:
            info = build_info(row)
        except PackError as e:
            log.warning("pack %s is broken: %s", pack_id, e)
            return None
        with self._lock:
            self._cache[pack_id] = info
        return info

    def all(self, status: str | None = None, kind: str | None = None) -> list[PackInfo]:
        sql, args = "SELECT id FROM pack WHERE 1=1", []
        if status:
            sql += " AND status=?"
            args.append(status)
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        sql += " ORDER BY subject, title"
        return [i for r in self.db.q(sql, *args) if (i := self.get(r["id"]))]

    def raw(self, pack_id: str) -> dict | None:
        r = self.db.q1("SELECT data FROM pack WHERE id=?", pack_id)
        return json.loads(r["data"]) if r else None

    # ---------- activation per profile ----------
    def for_profile(self, profile_id: int) -> list[PackInfo]:
        rows = self.db.q("""SELECT p.id FROM pack p JOIN pack_profile pp ON pp.pack_id=p.id
                            WHERE pp.profile_id=? AND p.status='active' AND p.kind='pack' ORDER BY p.subject, p.title""",
                         profile_id)
        return [i for r in rows if (i := self.get(r["id"]))]

    def activated(self, profile_id: int) -> set[str]:
        return {r["pack_id"] for r in self.db.q("SELECT pack_id FROM pack_profile WHERE profile_id=?", profile_id)}

    def activate(self, profile_id: int, pack_id: str, on: bool = True) -> None:
        info = self.get(pack_id)
        ids = [pack_id]
        if info and isinstance(info.model, Bundle):
            ids += info.model.pack_ids()
        with self.db.tx():
            for i in ids:
                if on:
                    self.db.x("INSERT OR IGNORE INTO pack_profile(pack_id,profile_id) VALUES(?,?)", i, profile_id)
                else:
                    self.db.x("DELETE FROM pack_profile WHERE pack_id=? AND profile_id=?", i, profile_id)

    def activate_defaults(self, profile_id: int) -> None:
        for r in self.db.q("SELECT id, data FROM pack WHERE status='active' AND kind='pack'"):
            if json.loads(r["data"] or "{}").get("standard", True) is False:
                continue                       # e.g. language courses: chosen by the learner
            self.db.x("INSERT OR IGNORE INTO pack_profile(pack_id,profile_id) VALUES(?,?)", r["id"], profile_id)
