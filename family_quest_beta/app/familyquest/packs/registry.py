"""Pack store: packs live in the database (JSON); folders are synced in at start."""
from __future__ import annotations

import json
import logging
import shutil
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path

from .. import generators
from ..i18n import _t
from ..db import Database
from .loader import PackError, content_hash, iter_dir, media_refs, pack_dict, parse_doc, store_media
from . import i18n
from .schema import Bundle, Pack, card_key, card_view, localize_view, skill_key

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
    titles: dict = field(default_factory=dict)            # titel_i18n of the unit
    descriptions: dict = field(default_factory=dict)      # beschreibung_i18n of the unit

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
    src: str = ""                     # the prompt language shown (localized copies; "" = the canonical `quellsprache`)
    ui: str = ""                      # the viewer's language of a localized copy
    loc_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def unit(self, unit_id: str) -> UnitInfo | None:
        return next((u for u in self.units if u.id == unit_id), None)

    @property
    def lang(self) -> str:
        return getattr(self.model, "sprache", "") or ""

    @property
    def src_lang(self) -> str:
        """The language of the prompts as shown (the learner's language when the cards carry it)."""
        return self.src or getattr(self.model, "quellsprache", "") or "de"

    @property
    def src_langs(self) -> list[str]:
        """Every prompt language the cards carry (never the language that is learnt)."""
        m = self.model
        if not isinstance(m, Pack):
            return []
        return [l for l in dict.fromkeys([m.quellsprache, *m.quellsprachen]) if l and l != m.sprache]

    @property
    def optional(self) -> bool:
        return bool(getattr(self.model, "optional", False))

    def localized(self, lang: str, family: str = "") -> "PackInfo":
        """This pack in the viewer's language (cached). The card keys stay the canonical ones."""
        if not lang:
            return self
        ck = (lang, family)
        if ck in self.loc_cache:
            return self.loc_cache[ck]
        m = self.model
        title = i18n.pick(getattr(m, "titel_i18n", None), self.title, lang)
        level = i18n.pick(getattr(m, "stufe_i18n", None), self.level, lang)
        if not isinstance(m, Pack):
            out = replace(self, title=title, level=level, ui=lang, loc_cache={})
        else:
            src = i18n.source_lang(m.quellsprache, m.quellsprachen, m.sprache, lang, family)
            units = []
            for u in self.units:
                items = u.items
                if u.kind == "cards":
                    items = [dict(it, view=localize_view(it["view"], it["card"], src, m.quellsprache)) for it in u.items]
                units.append(replace(u, title=i18n.pick(u.titles, u.title, lang),
                                     description=i18n.pick(u.descriptions, u.description, lang), items=items))
            out = replace(self, title=title, level=level, units=units, src=src, ui=lang, loc_cache={})
        self.loc_cache[ck] = out
        return out

    def summary(self) -> dict:
        m = self.model
        d = {"id": self.id, "kind": self.kind, "title": self.title, "subject": subject_meta(self.subject),
             "level": self.level, "status": self.status, "source": self.source, "version": self.version,
             "optional": self.optional, "content_langs": list(getattr(m, "sprachen", []) or [])}
        if isinstance(m, Pack):
            descr = i18n.pick(m.beschreibung_i18n, m.beschreibung, self.ui) if self.ui else m.beschreibung
            d.update(lang=m.sprache, src_lang=self.src_lang, src_langs=self.src_langs, private=m.privat, path=m.pfad,
                     color=m.farbe or d["subject"]["color"], standard=m.standard, self_service=m.selbst,
                     icon=m.icon or d["subject"]["icon"], description=descr, descriptions=m.beschreibung_i18n or {},
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
                                           generator=u.generator, params=u.parameter, skills=skills,
                                           titles=u.titel_i18n or {}, descriptions=u.beschreibung_i18n or {}))
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
                info.units.append(UnitInfo(u.id, u.titel, "cards", ex, u.icon, u.beschreibung, items=items,
                                           titles=u.titel_i18n or {}, descriptions=u.beschreibung_i18n or {}))
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
        # optional packs of the app's folders (e.g. content in one language only) start under «More packs»
        st = status or (row["status"] if row else
                        ("available" if getattr(p, "optional", False) and source in ("builtin", "share") else "active"))
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
        self.retire_optional_once()
        return stats

    # ---------- optional packs («More packs»: status 'available' = in the library, not installed) ----------
    def _optional_ids(self) -> list[tuple[str, str, dict]]:
        """(id, status, data) of the optional packs from the app's folders – never a pack a parent changed."""
        out = []
        for r in self.db.q("SELECT id, status, data FROM pack WHERE source IN ('builtin','share')"):
            d = json.loads(r["data"] or "{}")
            if d.get("optional"):
                out.append((r["id"], r["status"], d))
        return out

    def _has_progress(self, pack_ids: list[str], profile_id: int | None = None) -> bool:
        if not pack_ids:
            return False
        marks = ",".join("?" * len(pack_ids))
        who, args = ("", []) if profile_id is None else (" AND profile_id=?", [profile_id])
        return bool(self.db.val(f"SELECT 1 FROM item_state WHERE pack_id IN ({marks}){who} LIMIT 1", *pack_ids, *args)
                    or self.db.val(f"SELECT 1 FROM attempt WHERE pack_id IN ({marks}){who} LIMIT 1", *pack_ids, *args))

    @staticmethod
    def _members(pid: str, data: dict) -> list[str]:
        """A pack's own id, a level pack's packs."""
        if data.get("stufenpaket"):
            return [p for s in data.get("semester") or [] for p in s.get("pakete") or []]
        return [pid]

    def retire_unused_optional(self) -> list[str]:
        """Optional packs that are installed but nobody has (no child, no progress) go back to «More packs»."""
        out = []
        for pid, st, d in self._optional_ids():
            if st != "active" or self.db.val("SELECT 1 FROM pack_profile WHERE pack_id=? LIMIT 1", pid):
                continue
            if d.get("stufenpaket") or not self._has_progress([pid]):
                self.set_status(pid, "available")
                out.append(pid)
        return out

    def retire_optional_once(self) -> None:
        """Update to optional packs (once): existing installations keep every optional pack a child has or learnt
        with; the others move to «More packs»."""
        if self.db.get_setting("packs_optional_v1"):
            return
        retired = self.retire_unused_optional()
        self.db.set_setting("packs_optional_v1", True)
        if retired:
            log.info("optional packs moved to «More packs»: %s", retired)

    def unassign_unused_optional(self) -> list[tuple[str, int]]:
        """Families whose language is not German: optional (German-only) packs that were switched on automatically
        and never used are switched off again – every pack with learning progress stays."""
        gone = []
        opt = self._optional_ids()
        for pid, _st, d in opt:
            members = [m for m in self._members(pid, d) if any(m == o[0] for o in opt)] if d.get("stufenpaket") else [pid]
            for r in self.db.q("SELECT profile_id FROM pack_profile WHERE pack_id=?", pid):
                if not self._has_progress(members, r["profile_id"]):
                    self.db.x("DELETE FROM pack_profile WHERE pack_id=? AND profile_id=?", pid, r["profile_id"])
                    gone.append((pid, r["profile_id"]))
        # packs nobody has any more go back to «More packs» – only those switched off here (not one a parent just added)
        touched = {g[0] for g in gone}
        for pid in touched:
            if not self.db.val("SELECT 1 FROM pack_profile WHERE pack_id=? LIMIT 1", pid) and not self._has_progress([pid]):
                self.db.x("UPDATE pack SET status='available' WHERE id=? AND status='active'", pid)
        return gone

    def family_lang(self) -> str:
        return i18n.base(self.db.get_setting("family_lang", "") or "")

    def note_family_lang(self, code: str | None) -> None:
        """The language of the parent area = the family language (prompt fallback). The first time it is known and
        it is not German, unused German-only packs that were switched on automatically are switched off."""
        lang = i18n.base(code)
        if not lang:
            return
        if self.family_lang() != lang:
            self.db.set_setting("family_lang", lang)
        if not self.db.get_setting("packs_optional_unassign_v1"):
            self.db.set_setting("packs_optional_unassign_v1", lang)
            if lang != "de":
                gone = self.unassign_unused_optional()
                if gone:
                    log.info("unused German-only packs switched off (family language %s): %s", lang, gone)
                    self.invalidate()

    def install(self, pack_id: str) -> None:
        """«More packs» › Add: the pack is offered in the family (children get it when a parent switches it on)."""
        info = self._get(pack_id)
        ids = [pack_id] + (info.model.pack_ids() if info and isinstance(info.model, Bundle) else [])
        for i in ids:
            self.db.x("UPDATE pack SET status='active' WHERE id=? AND (id=? OR status='available')", i, pack_id)
            self.invalidate(i)

    def uninstall(self, pack_id: str) -> None:
        """Back to «More packs»: switched off for every child – the learning progress stays (it is back when the pack
        is added again)."""
        with self.db.tx():
            self.db.x("DELETE FROM pack_profile WHERE pack_id=?", pack_id)
            self.db.x("UPDATE pack SET status='available' WHERE id=?", pack_id)
        self.invalidate(pack_id)

    # ---------- read ----------
    def get(self, pack_id: str, localize: bool = True) -> PackInfo | None:
        """The pack – in the viewer's language during a request (packs/i18n.py); `localize=False`: as written."""
        info = self._get(pack_id)
        lang = i18n.viewer() if localize else ""
        return info.localized(lang, self.family_lang()) if info and lang else info

    def _get(self, pack_id: str) -> PackInfo | None:
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
    def for_profile(self, profile_id: int, try_all: bool = True) -> list[PackInfo]:
        """The packs a profile learns with. Children: the active packs switched on for them. Parents: every pack –
        also drafts and switched-off ones, to try them out (try_all=False: only the active packs, e.g. daily lesson)."""
        if self.db.val("SELECT role FROM profile WHERE id=?", profile_id) == "parent":
            sql = "SELECT id FROM pack WHERE kind='pack'" + (" AND status<>'available'" if try_all else " AND status='active'")
            rows = self.db.q(sql + " ORDER BY status<>'active', subject, title")
        else:
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
                    # switched on for a child = added to the family (also the packs of a level pack)
                    self.db.x("UPDATE pack SET status='active' WHERE id=? AND status='available'", i)
                    self.db.x("INSERT OR IGNORE INTO pack_profile(pack_id,profile_id) VALUES(?,?)", i, profile_id)
                else:
                    self.db.x("DELETE FROM pack_profile WHERE pack_id=? AND profile_id=?", i, profile_id)
        if on:
            for i in ids:
                self.invalidate(i)

    def activate_defaults(self, profile_id: int) -> None:
        family = self.family_lang() or i18n.viewer()
        for r in self.db.q("SELECT id, data FROM pack WHERE status='active' AND kind='pack'"):
            d = json.loads(r["data"] or "{}")
            if d.get("standard", True) is False or d.get("optional"):
                continue                       # e.g. language courses: chosen by the learner; optional packs: by a parent
            if family and d.get("sprache") == family:
                continue                       # no French course for a French-speaking child
            self.db.x("INSERT OR IGNORE INTO pack_profile(pack_id,profile_id) VALUES(?,?)", r["id"], profile_id)
