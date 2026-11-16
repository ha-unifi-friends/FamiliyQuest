"""Wichteln (secret gift giving): an occasion, who takes part and rules (parents not among each other, children not
among each other). On saving the app draws at random who gives a present to whom – nobody gives to themselves.
Everybody sees only whom they give to; the whole list is never shown, not even to who made it.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import date

from .community import CommunityError

TRIES = 5000
log = logging.getLogger("familyquest.wichteln")


def draw(people: list[dict], no_parent_pairs: bool = False, no_kid_pairs: bool = False, rng: random.Random | None = None) -> dict[int, int]:
    """{giver: receiver} – a random round with the rules, or CommunityError when the rules make it impossible."""
    rng = rng or random.Random()
    ids = [p["id"] for p in people]
    role = {p["id"]: p["role"] for p in people}

    def ok(a: int, b: int) -> bool:
        if a == b:
            return False
        if no_parent_pairs and role[a] == "parent" and role[b] == "parent":
            return False
        if no_kid_pairs and role[a] != "parent" and role[b] != "parent":
            return False
        return True

    for _ in range(TRIES):
        receivers = ids[:]
        rng.shuffle(receivers)
        if all(ok(a, b) for a, b in zip(ids, receivers)):
            return dict(zip(ids, receivers))
    raise CommunityError("With these rules nobody can be drawn – take more people or fewer rules")


class Wichteln:
    def __init__(self, db, planer=lambda: None):
        self.db = db
        self.planer = planer           # → PlanerHost or None: the date becomes a to-do of every participant

    def members(self) -> list[dict]:
        return self.db.q("SELECT id, name, role, avatar FROM profile WHERE archived=0 ORDER BY role DESC, name")

    def create(self, prof: dict, title: str, participants: list[int], no_parent_pairs: bool, no_kid_pairs: bool,
               due: str | None = None) -> int:
        title = str(title or "").strip()[:100]
        if not title:
            raise CommunityError("What is the occasion?")
        if due:
            try:
                due = date.fromisoformat(str(due)[:10]).isoformat()
            except ValueError:
                raise CommunityError("Unknown date") from None
        people = [m for m in self.members() if m["id"] in {int(x) for x in participants}]
        if len(people) < 2:
            raise CommunityError("Wichteln needs at least two people")
        pairs = draw(people, no_parent_pairs, no_kid_pairs)
        todos = {}
        host = self.planer()
        if due and host:
            d = date.fromisoformat(due)
            # never the receiver's name: the planner may hang on the wall for everybody
            text = f"🎁 Wichteln: {title[:50]} · {d.day}.{d.month}."
            for p in people:
                try:
                    tid = host.add_todo(p["id"], text)
                except Exception as e:  # noqa: BLE001 - the draw counts even without to-dos
                    log.warning("no Wichteln to-do for %s: %s", p["id"], e)
                    tid = None
                if tid:
                    todos[str(p["id"])] = tid
        return self.db.x("INSERT INTO wichtel(title, created_by, rules, pairs, due, todos) VALUES(?,?,?,?,?,?)", title, prof["id"],
                         json.dumps({"no_parent_pairs": bool(no_parent_pairs), "no_kid_pairs": bool(no_kid_pairs)}),
                         json.dumps({str(a): b for a, b in pairs.items()}), due or None, json.dumps(todos))

    def _done(self, r: dict, viewer: int) -> bool:
        """Ticked off – in the planner to-do when there is one (ticking there counts too), else here."""
        tid = json.loads(r["todos"] or "{}").get(str(viewer))
        host = self.planer()
        if tid and host:
            st = host.todo_done(tid)
            if st is not None:
                return st
        return bool(json.loads(r["done"] or "{}").get(str(viewer)))

    def set_done(self, prof: dict, wid: int, done: bool) -> None:
        r = self.db.q1("SELECT * FROM wichtel WHERE id=?", wid)
        if not r or str(prof["id"]) not in json.loads(r["pairs"]):
            raise CommunityError("Unknown Wichteln")
        d = json.loads(r["done"] or "{}")
        d[str(prof["id"])] = bool(done)
        self.db.x("UPDATE wichtel SET done=? WHERE id=?", json.dumps(d), wid)
        tid = json.loads(r["todos"] or "{}").get(str(prof["id"]))
        host = self.planer()
        if tid and host:
            host.set_todo(tid, bool(done))

    def list(self, viewer: int) -> list[dict]:
        """Every Wichteln with its people – and for the viewer only their own receiver."""
        names = {m["id"]: m for m in self.members()}
        out = []
        for r in self.db.q("SELECT w.*, p.name AS author FROM wichtel w LEFT JOIN profile p ON p.id=w.created_by ORDER BY w.id DESC"):
            pairs = json.loads(r["pairs"])
            mine = pairs.get(str(viewer))
            rec = names.get(mine)
            out.append({"id": r["id"], "title": r["title"], "author": r["author"], "created_by": r["created_by"],
                        "created_at": r["created_at"], "rules": json.loads(r["rules"] or "{}"), "due": r["due"],
                        "done": self._done(r, viewer) if mine is not None else False,
                        "people": [{"id": int(k), "name": (names.get(int(k)) or {}).get("name", "?")} for k in pairs],
                        "mine": {"id": rec["id"], "name": rec["name"], "avatar": json.loads(rec["avatar"] or "{}")} if rec else None})
        return out

    def delete(self, prof: dict, wid: int) -> None:
        r = self.db.q1("SELECT * FROM wichtel WHERE id=?", wid)
        if not r:
            raise CommunityError("Unknown Wichteln")
        if r["created_by"] != prof["id"] and prof["role"] != "parent":
            raise CommunityError("Only who made it or a parent")
        host = self.planer()
        for tid in json.loads(r["todos"] or "{}").values():
            if host:
                try:
                    host.delete_todo(tid)
                except Exception:  # noqa: BLE001
                    pass
        self.db.x("DELETE FROM wichtel WHERE id=?", wid)
