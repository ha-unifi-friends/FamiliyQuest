"""Pranks from the shop.

- **Ink bomb** («Tintenbombe», 500 coins, one throw per purchase): thrown at one or more family members – their app
  gets a screen smeared with ink that they wipe clean with the finger (web/kid.js). Nobody is hit more than once a day.
- **Whoopee cushion** («Furzkissen», 300 coins, three uses per purchase): a fart sound as an announcement on all
  speakers of the home (Home Assistant media players) at half volume.
"""
from __future__ import annotations

import json
import logging
import threading

from .i18n import _t

log = logging.getLogger(__name__)

# kind: (price, uses per purchase, ledger label)
KINDS = {"ink": (500, 1, _t("Ink bomb")), "fart": (300, 3, _t("Whoopee cushion"))}
FART_VOLUME = 0.5


class PrankError(ValueError):
    pass


class Pranks:
    def __init__(self, db, rewards, ha=lambda: None, sound_url=lambda name: None):
        self.db = db
        self.rewards = rewards
        self.ha = ha                       # () → the Home Assistant service (or None)
        self.sound_url = sound_url         # name → URL of web/sounds/<name>.mp3 the speakers can fetch (or None)

    def stock(self, pid: int, kind: str) -> int:
        return int(self.db.val("SELECT n FROM prank_stock WHERE profile_id=? AND kind=?", pid, kind, default=0) or 0)

    def charges(self, pid: int) -> int:            # ink bombs (kept for older callers)
        return self.stock(pid, "ink")

    def _hit_today(self, pid: int) -> bool:
        return bool(self.db.q1("SELECT 1 FROM prank WHERE to_id=? AND kind='ink' AND date(at)=date('now','localtime')", pid))

    def speakers_ready(self) -> bool:
        ha = self.ha()
        return bool(ha and getattr(ha, "connected", False) and self.sound_url("fart"))

    def state(self, pid: int) -> dict:
        family = [{"id": r["id"], "name": r["name"], "avatar": json.loads(r["avatar"] or "{}"), "role": r["role"],
                   "hit_today": self._hit_today(r["id"])}
                  for r in self.db.q("SELECT id, name, avatar, role FROM profile WHERE archived=0 AND id!=? ORDER BY role DESC, name", pid)]
        return {"price": KINDS["ink"][0], "charges": self.stock(pid, "ink"), "coins": self.rewards.balance(pid, "coins"), "family": family,
                "fart": {"price": KINDS["fart"][0], "uses": KINDS["fart"][1], "left": self.stock(pid, "fart"), "speakers": self.speakers_ready()}}

    def buy(self, pid: int, kind: str = "ink") -> dict:
        if kind not in KINDS:
            raise PrankError("Unknown prank")
        price, uses, label = KINDS[kind]
        with self.db.tx():                      # check and book in one step – a double tap cannot buy on credit
            if self.rewards.balance(pid, "coins") < price:
                raise PrankError("Not enough coins")
            self.rewards.book(pid, "coins", -float(price), "prank_buy", label, "prank")
            self.db.x("""INSERT INTO prank_stock(profile_id, kind, n) VALUES(?,?,?)
                         ON CONFLICT(profile_id, kind) DO UPDATE SET n = n + excluded.n""", pid, kind, uses)
        return self.state(pid)

    def throw(self, pid: int, targets) -> dict:
        if not isinstance(targets, list) or not targets:
            raise PrankError("Choose who gets the ink bomb")
        with self.db.tx():
            if self.stock(pid, "ink") < 1:
                raise PrankError("Buy an ink bomb first")
            hit = []
            for t in dict.fromkeys(targets):
                if not isinstance(t, int) or isinstance(t, bool) or t == pid:
                    continue
                if not self.db.q1("SELECT 1 FROM profile WHERE id=? AND archived=0", t) or self._hit_today(t):
                    continue
                self.db.x("INSERT INTO prank(kind, from_id, to_id) VALUES('ink',?,?)", pid, t)
                hit.append(t)
            if not hit:
                raise PrankError("Nobody can be hit – everybody chosen got ink today already")
            self.db.x("UPDATE prank_stock SET n = n - 1 WHERE profile_id=? AND kind='ink'", pid)   # one bomb for all chosen
        return {**self.state(pid), "hit": hit}

    def fart(self, pid: int) -> dict:
        """One use of the whoopee cushion: the sound on every speaker of the home (in the background)."""
        if not self.speakers_ready():
            raise PrankError("No speakers – Home Assistant and the direct access of the app are needed")
        ha, url = self.ha(), self.sound_url("fart")
        players = [p["entity_id"] for p in ha.media_players() if p.get("state") not in ("unavailable", "unknown", "off")]
        if not players:
            raise PrankError("No speaker is switched on")
        with self.db.tx():
            if self.stock(pid, "fart") < 1:
                raise PrankError("Buy a whoopee cushion first")
            self.db.x("UPDATE prank_stock SET n = n - 1 WHERE profile_id=? AND kind='fart'", pid)
        def play():
            for e in players:
                try:
                    ha.announce(e, url, volume=FART_VOLUME)
                except Exception as ex:  # noqa: BLE001 – a speaker without announcements is left out
                    log.info("no fart on %s: %s", e, ex)
        threading.Thread(target=play, daemon=True).start()
        return {**self.state(pid), "speakers": len(players)}

    def pending(self, pid: int) -> dict | None:
        r = self.db.q1("""SELECT k.id, k.kind, k.at, p.name, p.avatar FROM prank k LEFT JOIN profile p ON p.id = k.from_id
                          WHERE k.to_id=? AND k.seen_at IS NULL ORDER BY k.id LIMIT 1""", pid)
        if not r:
            return None
        return {"id": r["id"], "kind": r["kind"], "at": r["at"], "from": {"name": r["name"] or "?", "avatar": json.loads(r["avatar"] or "{}")}}

    def cleaned(self, pid: int, prank_id: int) -> dict:
        self.db.x("UPDATE prank SET seen_at=datetime('now','localtime') WHERE id=? AND to_id=? AND seen_at IS NULL", prank_id, pid)
        return {"ok": True, "next": self.pending(pid)}
