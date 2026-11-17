"""Bulletin boards: endless pin boards of the family – sticky notes, texts, freehand lines and simple shapes.

Every family member may open and change every board (guests never: the API only takes family logins). Who made a
board – or a parent – renames, archives or removes it. An archived board can still be looked at, but not changed.

Sync: every change raises the version counter of its board and stamps the item with it. A client sends its changes
and the version it knows (`since`) in one request and gets back everything that changed since then – removed items too
(they stay as «deleted» rows for a while, so the others see them go and «undo» can bring them back). Last write wins
per item. When many removed rows pile up the oldest are purged and `floor` remembers up to where: a client that is
older than that loads the whole board again.

Presence (who is on the board, their pointer, what they see and which item they edit) lives only in memory and runs
out after PRESENCE_TTL seconds without a request.
"""
from __future__ import annotations

import json
import math
import threading
import time

from .community import CommunityError
from .i18n import _t

KINDS = ("note", "text", "stroke", "shape")
SHAPES = ("rect", "ellipse", "arrow", "line")
COLORS = 8                       # colour index 0…7 – the palettes are in the app (boards.js)
MAX_BOARDS = 200
MAX_ITEMS = 2000                 # items on one board (not counting removed ones)
MAX_BYTES = 3_000_000            # data of one board
MAX_OPS = 200                    # changes in one request
MAX_POINTS = 600                 # points of one line (more are thinned out)
NOTE_TEXT = 1000
TEXT_TEXT = 2000
TITLE = 60
COORD = 1_000_000                # the board is endless – but not quite
KEEP_DELETED = 1000              # removed items kept for undo and sync …
PURGE_AT = 1500                  # … purged down to KEEP_DELETED when there are more than this
PRESENCE_TTL = 10.0


def _num(v, lo: float, hi: float, default: float = 0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return min(hi, max(lo, f))


def _int(v, lo: int, hi: int, default: int = 0) -> int:
    return int(round(_num(v, lo, hi, default)))


def _text(v, n: int) -> str:
    return str(v or "").replace("\r\n", "\n").replace("\x00", "")[:n]


def clean(kind: str, data: dict, old: dict | None = None) -> dict:
    """A valid item of this kind: the new fields over the old ones, every field checked and limited."""
    if kind not in KINDS:
        raise CommunityError("This item is no longer on the board")
    if not isinstance(data, dict):
        raise CommunityError("This item is no longer on the board")
    d = dict(old or {})
    d.update(data)
    out = {"x": _int(d.get("x"), -COORD, COORD), "y": _int(d.get("y"), -COORD, COORD), "c": _int(d.get("c"), 0, COLORS - 1)}
    if kind == "note":
        out.update(w=_int(d.get("w"), 40, 2000, 200), h=_int(d.get("h"), 40, 2000, 200), t=_text(d.get("t"), NOTE_TEXT))
    elif kind == "text":
        out.update(w=_int(d.get("w"), 40, 4000, 320), s=_int(d.get("s"), 10, 400, 32), t=_text(d.get("t"), TEXT_TEXT))
    elif kind == "shape":
        f = d.get("f") if d.get("f") in SHAPES else "rect"
        lo = -20000 if f in ("arrow", "line") else 4
        out.update(f=f, w=_int(d.get("w"), lo, 20000, 160), h=_int(d.get("h"), lo, 20000, 100), sw=_int(d.get("sw"), 1, 60, 4))
    else:                                                       # stroke: points relative to x/y, flat [x0, y0, x1, y1, …]
        pts = d.get("p")
        if not isinstance(pts, list) or len(pts) < 2:
            raise CommunityError("A line needs points")
        pts = [_int(v, -50000, 50000) for v in pts[: len(pts) // 2 * 2]]
        n = len(pts) // 2
        if n > MAX_POINTS:                                      # thin out evenly, keep the last point
            step = n / MAX_POINTS
            idx = sorted({min(n - 1, int(i * step)) for i in range(MAX_POINTS - 1)} | {n - 1})
            pts = [v for i in idx for v in (pts[2 * i], pts[2 * i + 1])]
        out.update(w=_int(d.get("w"), 1, 80, 4), p=pts)
    return out


class Boards:
    def __init__(self, db):
        self.db = db
        self.lock = threading.Lock()
        self.presence: dict[int, dict[int, dict]] = {}          # board → person → {at, x, y, view, edit}
        self.now = time.monotonic                               # tests replace the clock

    # ---------------------------------------------------------------- boards
    def _board(self, bid: int) -> dict:
        b = self.db.q1("SELECT * FROM board WHERE id=?", bid)
        if not b:
            raise CommunityError("Unknown board")
        return b

    @staticmethod
    def _may_manage(prof: dict, b: dict) -> bool:
        return prof["role"] == "parent" or b["created_by"] == prof["id"]

    def people(self) -> dict[int, dict]:
        """Everybody who can make items (also archived profiles: their items keep their name)."""
        return {p["id"]: {"id": p["id"], "name": p["name"], "color": p["color"], "avatar": json.loads(p["avatar"] or "{}")}
                for p in self.db.q("SELECT id, name, color, avatar FROM profile WHERE archived IN (0, 1)")}

    def create(self, prof: dict, title: str, emoji: str = "📌") -> int:
        title = _text(title, TITLE).strip()
        if not title:
            raise CommunityError("Give the board a title")
        if int(self.db.val("SELECT COUNT(*) FROM board", default=0)) >= MAX_BOARDS:
            raise CommunityError("There are too many boards – remove an old one first")
        # version 1: «since 0» always means «everything»
        return self.db.x("INSERT INTO board(title, emoji, created_by, version) VALUES(?,?,?,1)", title, _text(emoji, 16).strip() or "📌", prof["id"])

    def update(self, prof: dict, bid: int, title: str | None = None, emoji: str | None = None, archived: bool | None = None) -> None:
        with self.db.tx():
            b = self._board(bid)
            if not self._may_manage(prof, b):
                raise CommunityError("Only who made it or a parent")
            if title is not None:
                title = _text(title, TITLE).strip()
                if not title:
                    raise CommunityError("Give the board a title")
                b["title"] = title
            if emoji is not None:
                b["emoji"] = _text(emoji, 16).strip() or "📌"
            if archived is not None:
                b["archived"] = int(bool(archived))
            self.db.x("UPDATE board SET title=?, emoji=?, archived=?, version=version+1, updated_at=datetime('now','localtime') WHERE id=?",
                      b["title"], b["emoji"], b["archived"], bid)

    def delete(self, prof: dict, bid: int) -> None:
        b = self._board(bid)
        if not self._may_manage(prof, b):
            raise CommunityError("Only who made it or a parent")
        with self.db.tx():
            self.db.x("DELETE FROM board_item WHERE board_id=?", bid)
            self.db.x("DELETE FROM board_seen WHERE board_id=?", bid)
            self.db.x("DELETE FROM board WHERE id=?", bid)
        with self.lock:
            self.presence.pop(bid, None)

    def list(self, prof: dict) -> list[dict]:
        names = self.people()
        out = []
        for b in self.db.q("""SELECT b.*, (SELECT COUNT(*) FROM board_item i WHERE i.board_id=b.id AND i.deleted=0) AS items,
                                     (SELECT COUNT(*) FROM board_item i WHERE i.board_id=b.id AND i.deleted=0
                                        AND i.version > COALESCE((SELECT s.version FROM board_seen s WHERE s.board_id=b.id AND s.profile_id=?), 0)
                                        AND COALESCE(i.updated_by, 0) != ?) AS fresh
                              FROM board b ORDER BY b.archived, b.updated_at DESC, b.id DESC""", prof["id"], prof["id"]):
            out.append({"id": b["id"], "title": b["title"], "emoji": b["emoji"], "created_by": b["created_by"],
                        "author": (names.get(b["created_by"]) or {}).get("name", "?"), "archived": bool(b["archived"]),
                        "items": b["items"], "new": b["fresh"], "updated_at": b["updated_at"],
                        "manage": self._may_manage(prof, b),
                        "here": [names[p] for p in self.here(b["id"]) if p in names]})
        return out

    def new_count(self, pid: int) -> int:
        """Boards with something new from the others since this person last looked (the badge on the Family page)."""
        return int(self.db.val("""SELECT COUNT(*) FROM board b WHERE b.archived=0 AND EXISTS(
                                     SELECT 1 FROM board_item i WHERE i.board_id=b.id AND i.deleted=0 AND COALESCE(i.updated_by, 0) != ?
                                       AND i.version > COALESCE((SELECT s.version FROM board_seen s WHERE s.board_id=b.id AND s.profile_id=?), 0))""",
                               pid, pid, default=0))

    # ---------------------------------------------------------------- items
    @staticmethod
    def _out(r: dict) -> dict:
        return {"id": r["id"], "k": r["kind"], "d": json.loads(r["data"]) if not r["deleted"] else None, "z": r["z"],
                "by": r["created_by"], "ub": r["updated_by"], "v": r["version"], "del": bool(r["deleted"])}

    def _apply(self, prof: dict, b: dict, ops: list, ids: dict) -> list[str]:
        """Run the changes in order – a wrong one is skipped (and named), the others count. Inside the transaction."""
        errors: list[str] = []
        bid = b["id"]
        live = int(self.db.val("SELECT COUNT(*) FROM board_item WHERE board_id=? AND deleted=0", bid, default=0))
        size = int(self.db.val("SELECT COALESCE(SUM(size), 0) FROM board_item WHERE board_id=? AND deleted=0", bid, default=0))
        top = int(self.db.val("SELECT COALESCE(MAX(z), 0) FROM board_item WHERE board_id=?", bid, default=0))
        ver = b["version"]

        def item(ref) -> dict:
            iid = ids.get(str(ref), ref) if isinstance(ref, str) else ref
            try:
                iid = int(iid)
            except (TypeError, ValueError):
                raise CommunityError("This item is no longer on the board") from None
            r = self.db.q1("SELECT * FROM board_item WHERE id=? AND board_id=?", iid, bid)
            if not r:
                raise CommunityError("This item is no longer on the board")
            return r

        for op in ops[:MAX_OPS]:
            if not isinstance(op, dict):
                continue
            kind = op.get("op")
            try:
                if kind == "add":
                    if live >= MAX_ITEMS:
                        raise CommunityError("The board is full – remove something first")
                    k = op.get("kind")
                    d = clean(k, op.get("data") or {})
                    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
                    if size + len(raw) > MAX_BYTES:
                        raise CommunityError("The board is full – remove something first")
                    ver += 1
                    top += 1
                    iid = self.db.x("""INSERT INTO board_item(board_id, kind, data, z, size, created_by, updated_by, version)
                                       VALUES(?,?,?,?,?,?,?,?)""", bid, k, raw, top, len(raw), prof["id"], prof["id"], ver)
                    live += 1
                    size += len(raw)
                    if op.get("tmp") is not None:
                        ids[str(op["tmp"])] = iid
                elif kind in ("set", "front", "del", "restore"):
                    r = item(op.get("id"))
                    if kind == "restore":
                        if not r["deleted"]:
                            continue
                        if live >= MAX_ITEMS or size + r["size"] > MAX_BYTES:
                            raise CommunityError("The board is full – remove something first")
                        ver += 1
                        top += 1
                        self.db.x("UPDATE board_item SET deleted=0, z=?, version=?, updated_by=?, updated_at=datetime('now','localtime') WHERE id=?",
                                  top, ver, prof["id"], r["id"])
                        live += 1
                        size += r["size"]
                        continue
                    if r["deleted"]:
                        continue                                # removed meanwhile by somebody else: nothing to change
                    ver += 1
                    if kind == "del":
                        self.db.x("UPDATE board_item SET deleted=1, version=?, updated_by=?, updated_at=datetime('now','localtime') WHERE id=?",
                                  ver, prof["id"], r["id"])
                        live -= 1
                        size -= r["size"]
                    elif kind == "front":
                        top += 1
                        self.db.x("UPDATE board_item SET z=?, version=?, updated_by=? WHERE id=?", top, ver, prof["id"], r["id"])
                    else:
                        d = clean(r["kind"], op.get("data") or {}, json.loads(r["data"]))
                        raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
                        if size - r["size"] + len(raw) > MAX_BYTES:
                            raise CommunityError("The board is full – remove something first")
                        self.db.x("UPDATE board_item SET data=?, size=?, version=?, updated_by=?, updated_at=datetime('now','localtime') WHERE id=?",
                                  raw, len(raw), ver, prof["id"], r["id"])
                        size += len(raw) - r["size"]
                else:
                    raise CommunityError("Unknown change")
            except CommunityError as e:
                errors.append(str(e))
                if kind == "add" and op.get("tmp") is not None:
                    ids[str(op["tmp"])] = None
        if ver != b["version"]:
            self.db.x("UPDATE board SET version=?, updated_at=datetime('now','localtime') WHERE id=?", ver, bid)
            b["version"] = ver
        return errors

    def _purge(self, b: dict) -> None:
        n = int(self.db.val("SELECT COUNT(*) FROM board_item WHERE board_id=? AND deleted=1", b["id"], default=0))
        if n <= PURGE_AT:
            return
        cut = self.db.val("""SELECT version FROM board_item WHERE board_id=? AND deleted=1 ORDER BY version DESC LIMIT 1 OFFSET ?""",
                          b["id"], KEEP_DELETED)
        if cut is None:
            return
        self.db.x("DELETE FROM board_item WHERE board_id=? AND deleted=1 AND version<=?", b["id"], cut)
        self.db.x("UPDATE board SET floor=MAX(floor, ?) WHERE id=?", cut, b["id"])
        b["floor"] = max(b["floor"], cut)

    def sync(self, prof: dict, bid: int, since: int = 0, ops: list | None = None, presence: dict | None = None) -> dict:
        """Send own changes, get everything newer than `since` (all of it when `since` is 0 or too old)."""
        ids: dict[str, int | None] = {}
        errors: list[str] = []
        with self.db.tx():
            b = self._board(bid)
            if ops:
                if b["archived"]:
                    errors.append(_t("This board is archived – it can only be looked at"))
                    for op in ops:
                        if isinstance(op, dict) and op.get("op") == "add" and op.get("tmp") is not None:
                            ids[str(op["tmp"])] = None
                else:
                    errors += self._apply(prof, b, ops, ids)
                    self._purge(b)
            since = max(0, int(since or 0))
            full = since <= 0 or since < b["floor"] or since > b["version"]
            if full:
                rows = self.db.q("SELECT * FROM board_item WHERE board_id=? AND deleted=0 ORDER BY z", bid)
            else:
                rows = self.db.q("SELECT * FROM board_item WHERE board_id=? AND version>? ORDER BY z", bid, since)
            self.db.x("""INSERT INTO board_seen(board_id, profile_id, version) VALUES(?,?,?)
                         ON CONFLICT(board_id, profile_id) DO UPDATE SET version=excluded.version WHERE board_seen.version != excluded.version""", bid, prof["id"], b["version"])
        self.touch(prof, bid, presence)
        out = {"board": {"id": b["id"], "title": b["title"], "emoji": b["emoji"], "archived": bool(b["archived"]),
                         "created_by": b["created_by"], "manage": self._may_manage(prof, b)},
               "version": b["version"], "full": full, "items": [self._out(r) for r in rows], "ids": ids, "errors": errors,
               "presence": self.others(bid, prof["id"])}
        if full:
            out["people"] = list(self.people().values())
        return out

    # ---------------------------------------------------------------- presence (memory only)
    def touch(self, prof: dict, bid: int, p: dict | None) -> None:
        p = p if isinstance(p, dict) else {}
        view = p.get("view") if isinstance(p.get("view"), list) and len(p.get("view")) == 4 else None
        ent = {"at": self.now(), "id": prof["id"],
               "x": _num(p["x"], -COORD, COORD) if p.get("x") is not None else None,
               "y": _num(p["y"], -COORD, COORD) if p.get("y") is not None else None,
               "view": [round(_num(v, -COORD * 10, COORD * 10), 1) for v in view] if view else None,
               "edit": _int(p["edit"], 0, 2 ** 62) if isinstance(p.get("edit"), (int, float)) else None}
        with self.lock:
            self.presence.setdefault(bid, {})[prof["id"]] = ent

    def leave(self, prof: dict, bid: int) -> None:
        with self.lock:
            self.presence.get(bid, {}).pop(prof["id"], None)

    def here(self, bid: int) -> list[int]:
        """Who is on the board just now (requests within PRESENCE_TTL)."""
        now = self.now()
        with self.lock:
            room = self.presence.get(bid, {})
            for pid in [k for k, v in room.items() if now - v["at"] > PRESENCE_TTL]:
                del room[pid]
            return list(room)

    def others(self, bid: int, pid: int) -> list[dict]:
        self.here(bid)
        with self.lock:
            return [{k: v for k, v in e.items() if k != "at"} for e in self.presence.get(bid, {}).values() if e["id"] != pid]
