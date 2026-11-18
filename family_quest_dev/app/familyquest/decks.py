"""Own flash card decks: everybody keeps their own decks (e.g. «French words»), adds own cards or – with one click –
cards from the packs (language courses, geography, general knowledge), and repeats them with the Leitner boxes.

Status of a card: new (never repeated), due (should be known by now – repeat today), learning (box 1–2, not due),
known (box 3 and up, not due).
"""
from __future__ import annotations

import random
from datetime import date

from .learning.exercises import _media
from .learning.leitner import next_state
from .packs.registry import subject_meta

KNOWN_BOX = 3
MAX_DECKS, MAX_CARDS = 50, 2000
STUDY_NEW = 15          # new cards per round on top of the due ones
STUDY_MAX = 40


class DeckError(Exception):
    pass


def _today() -> str:
    return date.today().isoformat()


def status(card: dict, today: str | None = None) -> str:
    today = today or _today()
    if not card["box"]:
        return "new"
    if (card["due"] or "") <= today:
        return "due"
    return "known" if card["box"] >= KNOWN_BOX else "learning"


class Decks:
    def __init__(self, db, packs):
        self.db, self.packs = db, packs

    # ------------------------------------------------------------ decks
    def _deck(self, pid: int, did: int) -> dict:
        d = self.db.q1("SELECT * FROM deck WHERE id=? AND profile_id=?", did, pid)
        if not d:
            raise DeckError("Unknown deck")
        return d

    def list(self, pid: int) -> list[dict]:
        today = _today()
        out = []
        for d in self.db.q("SELECT * FROM deck WHERE profile_id=? ORDER BY name COLLATE NOCASE", pid):
            counts = {"new": 0, "due": 0, "learning": 0, "known": 0}
            for c in self.db.q("SELECT box, due FROM deck_card WHERE deck_id=?", d["id"]):
                counts[status(c, today)] += 1
            out.append({"id": d["id"], "name": d["name"], "icon": d["icon"], "subject": d["subject"],
                        "count": sum(counts.values()), **counts})
        return out

    def create(self, pid: int, name: str, icon: str = "📇", subject: str = "") -> int:
        name = str(name or "").strip()[:60]
        if not name:
            raise DeckError("Give the deck a name")
        if self.db.val("SELECT COUNT(*) FROM deck WHERE profile_id=?", pid, default=0) >= MAX_DECKS:
            raise DeckError("You already have enough decks")
        return self.db.x("INSERT INTO deck(profile_id, name, icon, subject) VALUES(?,?,?,?)",
                         pid, name, (str(icon or "") or "📇")[:8], subject[:40])

    def update(self, pid: int, did: int, name: str, icon: str) -> None:
        self._deck(pid, did)
        name = str(name or "").strip()[:60]
        if not name:
            raise DeckError("Give the deck a name")
        self.db.x("UPDATE deck SET name=?, icon=? WHERE id=?", name, (str(icon or "") or "📇")[:8], did)

    def delete(self, pid: int, did: int) -> None:
        self._deck(pid, did)
        with self.db.tx():
            self.db.x("DELETE FROM deck_card WHERE deck_id=?", did)
            self.db.x("DELETE FROM deck WHERE id=?", did)

    # ------------------------------------------------------------ cards
    def cards(self, pid: int, did: int) -> dict:
        d = self._deck(pid, did)
        today = _today()
        cards = [{"id": c["id"], "front": c["front"], "back": c["back"], "image": c["image"], "emoji": c["emoji"],
                  "box": c["box"], "due": c["due"], "correct": c["correct"], "wrong": c["wrong"],
                  "from_pack": bool(c["src"]), "status": status(c, today)}
                 for c in self.db.q("SELECT * FROM deck_card WHERE deck_id=? ORDER BY id DESC", did)]
        return {"deck": {"id": d["id"], "name": d["name"], "icon": d["icon"], "subject": d["subject"]}, "cards": cards}

    def _room(self, did: int, n: int = 1) -> None:
        if self.db.val("SELECT COUNT(*) FROM deck_card WHERE deck_id=?", did, default=0) + n > MAX_CARDS:
            raise DeckError("The deck is full")

    def add_card(self, pid: int, did: int, front: str, back: str) -> int:
        self._deck(pid, did)
        front, back = str(front or "").strip()[:300], str(back or "").strip()[:300]
        if not front or not back:
            raise DeckError("A card needs a front and a back")
        self._room(did)
        return self.db.x("INSERT INTO deck_card(deck_id, front, back) VALUES(?,?,?)", did, front, back)

    def _card(self, pid: int, cid: int) -> dict:
        c = self.db.q1("SELECT c.* FROM deck_card c JOIN deck d ON d.id=c.deck_id WHERE c.id=? AND d.profile_id=?", cid, pid)
        if not c:
            raise DeckError("Unknown card")
        return c

    def edit_card(self, pid: int, cid: int, front: str, back: str) -> None:
        self._card(pid, cid)
        front, back = str(front or "").strip()[:300], str(back or "").strip()[:300]
        if not front or not back:
            raise DeckError("A card needs a front and a back")
        self.db.x("UPDATE deck_card SET front=?, back=? WHERE id=?", front, back, cid)

    def delete_card(self, pid: int, cid: int) -> None:
        self._card(pid, cid)
        self.db.x("DELETE FROM deck_card WHERE id=?", cid)

    # ------------------------------------------------------------ from the packs
    def _deck_for(self, pid: int, pack, did: int | None) -> dict:
        if did:
            return self._deck(pid, did)
        d = self.db.q1("SELECT * FROM deck WHERE profile_id=? AND subject=? ORDER BY id LIMIT 1", pid, pack.subject)
        if d:
            return d
        m = subject_meta(pack.subject)
        return self._deck(pid, self.create(pid, m["name"], m["icon"], pack.subject))

    def add_items(self, pid: int, pack, items: list[dict], did: int | None = None) -> dict:
        """Pack cards into a deck (the deck of the pack's subject unless one is chosen). Cards already in it are skipped."""
        deck = self._deck_for(pid, pack, did)
        have = {r["src"] for r in self.db.q("SELECT src FROM deck_card WHERE deck_id=? AND src<>''", deck["id"])}
        new = [it for it in items if it["key"] not in have and (it["view"]["prompt"] or it["view"].get("image") or it["view"].get("emoji"))
               and it["view"]["answer"]]
        self._room(deck["id"], len(new))
        with self.db.tx():
            for it in new:
                v, m = it["view"], _media(pack.id, it["view"])
                self.db.x("INSERT INTO deck_card(deck_id, front, back, image, emoji, src) VALUES(?,?,?,?,?,?)",
                          deck["id"], (v["prompt"] or "")[:300], v["answer"][:300], m["image"], m["emoji"], it["key"])
        return {"deck": {"id": deck["id"], "name": deck["name"], "icon": deck["icon"], "subject": deck["subject"]}, "added": len(new),
                "already": len(items) - len(new)}

    def pack_items(self, pack, unit_id: str | None = None, keys: list[str] | None = None) -> list[dict]:
        out = []
        for u in pack.units:
            if u.kind != "cards" or (unit_id and u.id != unit_id):
                continue
            out += [it for it in u.items if keys is None or it["key"] in keys]
        return out

    # ------------------------------------------------------------ repeating
    def study(self, pid: int, did: int, mode: str = "due") -> list[dict]:
        """Due cards first (oldest first), then a few new ones – or, with mode «all», every card in random order."""
        self._deck(pid, did)
        rows = self.db.q("SELECT * FROM deck_card WHERE deck_id=?", did)
        today = _today()
        if mode == "all":
            pick = rows[:]
            random.shuffle(pick)
            pick = pick[:STUDY_MAX]
        else:
            due = sorted((c for c in rows if c["box"] and (c["due"] or "") <= today), key=lambda c: (c["due"] or "", c["box"]))
            new = [c for c in rows if not c["box"]]
            pick = (due + new[:STUDY_NEW])[:STUDY_MAX]
            random.shuffle(pick)
        return [{"id": c["id"], "front": c["front"], "back": c["back"], "image": c["image"], "emoji": c["emoji"],
                 "box": c["box"]} for c in pick]

    def grade(self, pid: int, cid: int, result: str) -> dict:
        if result not in ("correct", "almost", "wrong"):
            raise DeckError("Unknown answer")
        c = self._card(pid, cid)
        box, due = next_state(c["box"], result, date.today())
        self.db.x("""UPDATE deck_card SET box=?, due=?, correct=correct+?, wrong=wrong+?, last_seen=datetime('now','localtime')
                     WHERE id=?""", box, due, 1 if result == "correct" else 0, 1 if result == "wrong" else 0, cid)
        return {"box": box, "due": due, "status": status({"box": box, "due": due})}

    def due_total(self, pid: int) -> int:
        return self.db.val("""SELECT COUNT(*) FROM deck_card c JOIN deck d ON d.id=c.deck_id
                              WHERE d.profile_id=? AND c.box>0 AND c.due<=?""", pid, _today(), default=0)
