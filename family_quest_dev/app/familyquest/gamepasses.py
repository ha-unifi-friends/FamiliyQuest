"""Games with a price for children (parent area › Games › ⚙️ Settings of a game).

Per game in the setting `games_access` (services.games_access): `price` (coins to buy it, 0 = no buying), `rent`
(coins to rent it, 0 = no renting) and `period` (day | week | month – how long a rent lasts). A game with price 0 and
rent 0 is free. Defaults where the parents never set a value (the key is missing in the stored entry – an explicit 0
stays 0): the quick games for in between rent for 100 coins a week, the games of the game corner for 20 coins a day
(DEFAULT_RENT), the one-armed bandit is also bought for DEFAULT_PRICE 250; every other game is free. With a price or a
rent a child must buy or rent it first (kid shop «🎮 Unlock games»); parents always play for free.

`preview` (default 1, 0–20): free tries before buying or renting. A try is used when the child starts or joins a table
of a family game (a rematch is a new try; once seated the table can be played to the end), opens a game of the game
corner (POST /api/me/games/try) or spins the one-armed bandit. The count per child and game is `previews_used` in
`game_pass`; a second start within TRY_SAME_S seconds (double tap, two devices) is the same try.

What a child got is one row per child and game in `game_pass`: `bought` (forever – also when the parents change the
price later) or `rent_until` (playable until then; renting again adds the period after the current end). Buying makes
a running rent pointless (bought wins). The coins are booked in the ledger in the same transaction
(events `game_buy` / `game_rent`, unique refs).
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from .i18n import _t

PERIODS = ("day", "week", "month")
DEFAULT_PRICE = {"slots": 250}          # the one-armed bandit: bought once, as before (it cost 150 then)
DEFAULT_PERIOD = "week"
QUICK = ("paarjagd", "wuerfel", "jump", "klatsch", "sternlauf", "snack", "verkehr")   # kid app: «Quick games for in between»
ARCADE = ("ttt", "sudoku", "patience", "pingpong", "cube", "slots")                  # the game corner (minigames.js)
DEFAULT_RENT = {**{g: (100, "week") for g in QUICK}, **{g: (20, "day") for g in ARCADE}}   # (coins, period)
DEFAULT_PREVIEW = 1                     # free tries before buying / renting
MAX_PREVIEW = 20
TRY_SAME_S = 10                         # a second start within this time: the same try (double tap, another device)
TRY_HOLD_S = 2 * 3600                   # after a try the game stays reachable (leave, results, a duel of the game corner)
MAX_PRICE = 100000
FMT = "%Y-%m-%d %H:%M:%S"


class PassError(ValueError):
    pass


def add_period(start: datetime, period: str) -> datetime:
    """Start + 1 day / 7 days / 1 calendar month (31 Jan + 1 month = 28/29 Feb, same time of day)."""
    if period == "day":
        return start + timedelta(days=1)
    if period == "week":
        return start + timedelta(days=7)
    y, m = (start.year + (start.month // 12), start.month % 12 + 1)
    return start.replace(year=y, month=m, day=min(start.day, calendar.monthrange(y, m)[1]))


def clean_price(v, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise PassError("Price: a whole number of coins (0 or more)") from None
    if not 0 <= n <= MAX_PRICE:
        raise PassError("Price: a whole number of coins (0 or more)")
    return n


def clean_preview(v, default: int = DEFAULT_PREVIEW) -> int:
    if v is None or v == "":
        return default
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise PassError("Free tries: 0 to 20") from None
    if not 0 <= n <= MAX_PREVIEW:
        raise PassError("Free tries: 0 to 20")
    return n


def default_rent(game: str) -> tuple[int, str]:
    return DEFAULT_RENT.get(game, (0, DEFAULT_PERIOD))


def priced(a: dict) -> bool:
    """Does this game cost something for children (buy or rent)?"""
    return int(a.get("price") or 0) > 0 or int(a.get("rent") or 0) > 0


class GamePasses:
    def __init__(self, db, rewards):
        self.db = db
        self.rewards = rewards
        self.now = datetime.now            # the tests move time

    def _rows(self, pid: int) -> dict[str, dict]:
        return {r["game"]: r for r in self.db.q("SELECT * FROM game_pass WHERE profile_id=?", pid)}

    def status(self, pid: int, game: str, row: dict | None = None, now: datetime | None = None) -> dict:
        """{"bought": bool, "rent_until": "…" | None (only a running rent), "left_s": seconds of the rent left}"""
        r = row if row is not None else self.db.q1("SELECT * FROM game_pass WHERE profile_id=? AND game=?", pid, game)
        now = now or self.now()
        bought = bool(r and r["bought"])
        until = r["rent_until"] if r and r["rent_until"] and not bought else None
        left = (datetime.strptime(until, FMT) - now).total_seconds() if until else 0
        if left <= 0:
            until, left = None, 0
        return {"bought": bought, "rent_until": until, "left_s": int(left)}

    def unlocked_set(self, pid: int, access: dict) -> set[str]:
        """The priced games this child may play now (bought or rented) – plus every game without a price."""
        rows, now = self._rows(pid), self.now()
        out = set()
        for g, a in access.items():
            if not priced(a):
                out.add(g)
                continue
            st = self.status(pid, g, rows.get(g) or {}, now) if g in rows else None
            if st and (st["bought"] or st["rent_until"]):
                out.add(g)
        return out

    def offers(self, pid: int, access: dict, games: list[str]) -> list[dict]:
        """For the kid shop and the locked tiles: every priced game in `games` (those the parents allow this child)."""
        rows, now = self._rows(pid), self.now()
        out = []
        for g in games:
            a = access.get(g) or {}
            if not priced(a):
                continue
            st = self.status(pid, g, rows.get(g) or {}, now) if g in rows else {"bought": False, "rent_until": None, "left_s": 0}
            out.append({"game": g, "price": int(a.get("price") or 0), "rent": int(a.get("rent") or 0),
                        "period": a.get("period") or DEFAULT_PERIOD, **st, "open": st["bought"] or bool(st["rent_until"]),
                        "preview": int(a.get("preview") or 0), "tries_left": self.tries_left(pid, g, a, rows.get(g) or {})})
        return out

    # ------------------------------------------------------------ free tries before buying / renting
    def tries_left(self, pid: int, game: str, a: dict, row: dict | None = None) -> int:
        r = row if row is not None else (self.db.q1("SELECT * FROM game_pass WHERE profile_id=? AND game=?", pid, game) or {})
        return max(0, int(a.get("preview") or 0) - int(r.get("previews_used") or 0))

    def _since(self, row: dict | None, now: datetime) -> float | None:
        """Seconds since the last try of this game (None: never)."""
        at = row and row.get("preview_at")
        return (now - datetime.strptime(at, FMT)).total_seconds() if at else None

    def trying(self, pid: int, game: str) -> bool:
        """A try of this game was used a short while ago (TRY_HOLD_S) – its game stays reachable."""
        s = self._since(self.db.q1("SELECT * FROM game_pass WHERE profile_id=? AND game=?", pid, game), self.now())
        return s is not None and -60 <= s < TRY_HOLD_S

    def use_try(self, pid: int, game: str, a: dict, same: bool = True) -> str | None:
        """Use one free try: "new" (counted), "same" (`same`: a try of this game began less than TRY_SAME_S ago – a
        double tap or a second device, not counted again) or None (no try left). Checked and counted in one
        transaction: parallel requests cannot use more tries than there are."""
        with self.db.tx():
            now = self.now()
            r = self.db.q1("SELECT * FROM game_pass WHERE profile_id=? AND game=?", pid, game)
            s = self._since(r, now)
            if same and s is not None and 0 <= s < TRY_SAME_S:
                return "same"
            if self.tries_left(pid, game, a, r or {}) <= 0:
                return None
            self.db.x("""INSERT INTO game_pass(profile_id, game, previews_used, preview_at) VALUES(?,?,1,?)
                         ON CONFLICT(profile_id, game) DO UPDATE SET previews_used=previews_used+1, preview_at=excluded.preview_at""",
                      pid, game, now.strftime(FMT))
        return "new"

    def give_back(self, pid: int, game: str) -> None:
        """The request that used a try failed (no table started): the try is back."""
        self.db.x("UPDATE game_pass SET previews_used=MAX(0, previews_used-1), preview_at=NULL WHERE profile_id=? AND game=?", pid, game)

    def buy(self, pid: int, game: str, a: dict, title: str) -> dict:
        """Buy the game for good. Checked and booked in one transaction – a double tap cannot pay twice."""
        price = int(a.get("price") or 0)
        with self.db.tx():
            if price <= 0:
                raise PassError("This game cannot be bought")
            if self.status(pid, game)["bought"]:
                raise PassError("You have this game already")
            if self.rewards.available(pid) < price:
                raise PassError("Not enough coins")
            self.rewards.book(pid, "coins", -float(price), "game_buy", _t("Game bought") + f": {title}", f"game:buy:{game}:{pid}")
            self.db.x("""INSERT INTO game_pass(profile_id, game, bought, bought_at) VALUES(?,?,1,?)
                         ON CONFLICT(profile_id, game) DO UPDATE SET bought=1, bought_at=excluded.bought_at""",
                      pid, game, self.now().strftime(FMT))
        return self.status(pid, game)

    def rent(self, pid: int, game: str, a: dict, title: str, seen_until: str | None = None) -> dict:
        """Rent (or extend) the game for one period. `seen_until`: the end the app showed – when it differs, the rent
        was already extended meanwhile (a second tap, another device) and nothing is booked."""
        cost, period = int(a.get("rent") or 0), a.get("period") or DEFAULT_PERIOD
        with self.db.tx():
            if cost <= 0 or period not in PERIODS:
                raise PassError("This game cannot be rented")
            now = self.now()
            st = self.status(pid, game, now=now)
            if st["bought"]:
                raise PassError("You have this game already")
            if seen_until is not None and (seen_until or None) != st["rent_until"]:
                raise PassError("The rent was just extended – look again")
            if self.rewards.available(pid) < cost:
                raise PassError("Not enough coins")
            start = datetime.strptime(st["rent_until"], FMT) if st["rent_until"] else now.replace(microsecond=0)
            until = add_period(start, period).strftime(FMT)
            self.rewards.book(pid, "coins", -float(cost), "game_rent", _t("Game rented") + f": {title}", f"game:rent:{game}:{pid}:{until}")
            self.db.x("""INSERT INTO game_pass(profile_id, game, rent_until) VALUES(?,?,?)
                         ON CONFLICT(profile_id, game) DO UPDATE SET rent_until=excluded.rent_until""", pid, game, until)
        return self.status(pid, game)
