"""Wiring of all services plus the read models for dashboard and family view."""
from __future__ import annotations

import json
import random
import logging
from datetime import date, datetime, timedelta

from .api.auth import Throttle, Tokens
from .bingo import Bingo
from .poker import Poker
from .cardgames import CardGames
from .channel import ChannelGames, feature_visible
from .community import Community
from .chores import Chores
from .internet import InternetTime
from . import memo
from .db import Database, login_mode, profile_settings
from . import timelimits
from .learning.lesson import Learning
from .packs.registry import PackStore, subject_meta
from .rewards import avatar as av
from .rewards.engine import Rewards, today
from .rewards.shop import Shop
from .settings import Settings
from .weather import Weather
from .translations import Translations
from .dashboard import Dashboard
from .guests import Guests
from .calendar import FamilyCalendar
from .familytime import FamilyTimeGames

log = logging.getLogger("familyquest")


class FamilyQuest:
    def __init__(self, settings: Settings, db: Database | None = None):
        self.settings = settings
        self.db = db or Database(settings.db_path)
        self.packs = PackStore(self.db, settings.media_dir)
        self.rewards = Rewards(self.db)
        av.set_overrides(self.db.get_setting("shop_items", {}))          # the parents' changes to the shop
        if self.db.q1("SELECT 1 FROM setting WHERE key='xp_items_from'") is None:   # «new» XP count from today on
            self.db.set_setting("xp_items_from", int(self.db.val("SELECT MAX(id) FROM ledger", default=0) or 0))
        self.learning = Learning(self.db, self.packs, self.rewards)
        from .decks import Decks
        self.decks = Decks(self.db, self.packs)
        self.shop = Shop(self.db, self.rewards)
        self.chores = Chores(self.db, self.rewards)
        self.internet = InternetTime(self.db, self.rewards)
        self.community = Community(self.db, self.rewards)
        self.bingo = Bingo(self.db, self.rewards, self.community.add_history)
        self.poker = Poker(self.db, self.community.add_history)
        self.cards = CardGames(self.db, self.community.add_history)
        from .domino import Domino
        self.domino = Domino(self.db, self.community.add_history)
        from .pairhunt import Pairhunt
        self.paarjagd = Pairhunt(self.db, self.community.add_history, self.rewards)
        from .whoami import Whoami
        self.werbinich = Whoami(self.db, self.community.add_history, self.rewards)
        from .kartenlauf import Kartenlauf
        self.kartenlauf = Kartenlauf(self.db, self.community.add_history, self.rewards)
        from .stadtland import Stadtland
        self.stadtland = Stadtland(self.db, self.community.add_history, self.rewards)
        from .zeichnen import Zeichnen
        self.zeichnen = Zeichnen(self.db, self.community.add_history, self.rewards)
        from .wuerfel import Wuerfel
        self.wuerfel = Wuerfel(self.db, self.community.add_history, self.rewards)
        from .heimwaerts import Heimwaerts
        self.heimwaerts = Heimwaerts(self.db, self.community.add_history, self.rewards)
        from .jump import Jump
        self.jump = Jump(self.db, self.community.add_history, self.rewards)
        from .sternlauf import Sternlauf
        self.sternlauf = Sternlauf(self.db, self.community.add_history, self.rewards)
        from .snack import Snack
        self.snack = Snack(self.db, self.community.add_history, self.rewards)
        from .verkehr import Verkehr
        self.verkehr = Verkehr(self.db, self.community.add_history, self.rewards)
        from .langstrecke import Langstrecke
        self.langstrecke = Langstrecke(self.db, self.community.add_history, self.rewards)
        from .klatsch import Klatsch
        self.klatsch = Klatsch(self.db, self.community.add_history, self.rewards)
        from .verboten import Verboten
        self.verboten = Verboten(self.db, self.community.add_history, self.rewards)
        from .jass import Jass
        self.jass = Jass(self.db, self.community.add_history, self.rewards)
        from .werwolf import Werwolf
        self.werwolf = Werwolf(self.db, self.community.add_history, self.rewards)
        from .schach import Schach
        self.schach = Schach(self.db, self.community.add_history, self.rewards)
        from .dorfmarkt import Dorfmarkt
        self.dorfmarkt = Dorfmarkt(self.db, self.community.add_history, self.rewards)
        from .escape import Escape
        self.escape = Escape(self.db, self.community.add_history, self.rewards)
        from .stempeljagd import Stempeljagd
        self.stempeljagd = Stempeljagd(self.db, self.community.add_history, self.rewards)   # «Beat the Bureaucracy»
        # games without bots (parent area › Games): the engines ask before bots take a seat (cardgames.CardGames.bots_off)
        for eng in (self.cards, self.domino, self.paarjagd, self.kartenlauf, self.wuerfel, self.heimwaerts, self.jump, self.sternlauf, self.snack, self.verkehr, self.langstrecke, self.klatsch,
                    self.jass, self.werwolf, self.dorfmarkt, self.stempeljagd):
            eng.no_bots = self.table_without_bots
        from .songquiz import SongQuiz
        self.lan_base = None      # http://<Home Assistant IP>:<port of the direct access> – for sounds on speakers
        self.songs = SongQuiz(self.db, self.community.add_history, lambda: self.ha,
                              lambda name: f"{self.lan_base}/sounds/{name}.mp3" if self.lan_base else None)
        from .pets import Pets
        self.pets = Pets(self.db, self.rewards)
        from .gamepasses import GamePasses
        self.passes = GamePasses(self.db, self.rewards)          # games with a price for children (gamepasses.py)
        from .battery import Battery
        self.battery = Battery(self.db, self.rewards)              # game battery of the children, party mode (battery.py)
        self.rewards.listeners.append(self.battery.on_reward)    # daily goal / chore done: charge segments
        from .slots import Slots
        self.slots = Slots(self.db, self.rewards)
        self.slots.settings = lambda: self.games_access()["slots"]       # price, rent, luck (parent area › Games)
        self.slots.unlocked = lambda pid: self.game_unlocked(pid, "slots")
        # free tries (gamepasses.py `preview`): one spin each before buying / renting
        self.slots.tries = lambda pid: self.passes.tries_left(pid, "slots", self.games_access()["slots"])
        self.slots.try_play = lambda pid: self.passes.use_try(pid, "slots", self.games_access()["slots"], same=False) == "new"
        from .pranks import Pranks
        self.pranks = Pranks(self.db, self.rewards, lambda: self.ha,
                             lambda name: f"{self.lan_base}/sounds/{name}.mp3" if self.lan_base else None)
        self.pets.away = self._away_days
        from .bots import Bots
        self.bots = Bots(self.db)
        self.bots.pets = self.pets
        from .wichteln import Wichteln
        self.wichteln = Wichteln(self.db, lambda: self.planer_host)
        from .boards import Boards
        self.boards = Boards(self.db)
        from .stories import Stories
        self.stories = Stories(self.db, self.rewards, settings.media_dir)
        # the adventure games of the library are a game of their own (parent area › Games): switched off for a child,
        # it can neither play nor write them – parents always
        self.stories.games_ok = lambda prof: prof.get("role") == "parent" or "adventuregame" in self.games_for(prof)
        from .codelab import Codelab
        self.codelab = Codelab(self.db, self.rewards)              # 💡 Code Workshop (codelab.py) – learning time
        self.codelab.hours_ok = self._learning_hours_ok
        from .duel import Duels
        self.duels = Duels(lambda pid: (self.db.q1("SELECT name FROM profile WHERE id=?", pid) or {"name": "?"})["name"])
        from .pong4 import Doubles
        self.pong4 = Doubles(self.duels.names)
        self.weather = Weather(self.db, self.rewards)
        self.translations = Translations(self.db)
        self.kiosk = Dashboard(self)
        self.guests = Guests(self)
        self.calendar = FamilyCalendar(self)
        self.familytime = FamilyTimeGames(self)
        from .deals import Deals
        self.deals = Deals(self)                                    # children trade with each other and with parents (deals.py)
        self.chores.deals = self.deals
        self.pets.locked = lambda pet_id: self.deals.locked("pet", pet_id)
        self.internet.offline = lambda pid: self.calendar.blocks(pid, "internet")
        self.shop.internet = self.internet
        self.tokens = Tokens(settings.secret)
        self.tokens.fingerprint = self._login_fingerprint
        self.throttle = Throttle()
        self.ha = None            # set by main when Home Assistant is available (ha.service.HAService)
        self.planer_host = None   # Family Planer core (planer.host.PlanerHost), started by main
        self.on_mood: list = []   # fn(profile_row) – a child set its avatar to «sad»

    def _learning_hours_ok(self, prof: dict) -> bool:
        """Within the learning hours of the profile (profile setting «learning_hours», as for the lessons)?"""
        from .learning.lesson import LearnError, Learning
        try:
            Learning._check_hours(profile_settings(prof))
        except LearnError:
            return False
        return True

    def _away_days(self, pid: int) -> set[str]:
        """Days the Family Planer has this profile away on holiday («away» decision) – pet care pauses then."""
        host = self.planer_host
        bridge = getattr(host, "bridge", None) if host else None
        person = bridge.person_of(pid) if bridge else None
        if not person:
            return set()
        return set((getattr(host.planner, "away", None) or {}).get(person) or ())

    # ---------------------------------------------------------------- profiles
    def avatar_public(self, p: dict, avatar: dict) -> dict:
        """The avatar as the clients draw it: with the crown of the day and the age / stage of the pet."""
        st = profile_settings(p)
        a = av.with_crown(avatar, st.get("crown_until"), champion=bool(st.get("champion")))
        kind = (a.get("items") or {}).get("pet")
        pet = self.pets.badge(p["id"], kind) if kind else None
        return {**a, "pet": pet} if pet else a

    def profile_public(self, p: dict) -> dict:
        st = profile_settings(p)
        crown = st.get("crown_until")
        out = {"id": p["id"], "name": p["name"], "role": p["role"], "color": p["color"],
               "avatar": self.avatar_public(p, json.loads(p["avatar"] or "{}") or av.DEFAULT_AVATAR), "has_pin": bool(p["pin_hash"]),
               "crown": bool(crown and crown >= date.today().isoformat()),
               "auto_logout_min": st["auto_logout_min"], "pin_kind": "digits" if p["pin_hash"] else "",
               "login": login_mode(p, st)}               # how it signs in: none | pin | ha | pin_ha (db.login_mode)
        if p["pin_hash"] and st.get("pin_kind") == "symbols" and st.get("symbol_set"):
            # picture PIN: the login shows exactly these 12 symbols, shuffled every time (not secret)
            out.update(pin_kind="symbols", symbol_set=random.sample(st["symbol_set"], len(st["symbol_set"])))
        return out

    # the games that can be played with bots (alone against bots, bots at the table, chess / Tic-Tac-Toe / Ping-Pong
    # against the computer, Werwölfe filled up with bots) – the parents can switch the bots off per game
    # games still in development (channel.DEV_GAMES) are left out outside the dev channel
    BOT_GAMES = ChannelGames(("poker", "tschau", "karussell", "domino", "paarjagd", "kartenlauf", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "langstrecke", "klatsch", "jass", "werwolf", "schach", "dorfmarkt", "stempeljagd", "ttt", "pingpong"))
    GAMES = ChannelGames(("quiz", "bingo", "song", "poker", "tschau", "karussell", "domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "sternlauf", "snack", "verkehr", "langstrecke", "klatsch", "verboten", "jass", "werwolf", "schach", "dorfmarkt", "escape", "stempeljagd", "ttt", "sudoku", "patience", "pingpong", "slots", "cube",
                          "adventuregame"))
    # games that were open before they became a game of their own (the adventure games of the library): open when the
    # parents never decided on them – not switched off like a really new game after an update
    OPEN_WHEN_NEW = frozenset({"adventuregame"})
    # games without coins: no price, no rent (the adventure games – content of the family, like the library)
    FREE_GAMES = frozenset({"adventuregame"})

    def _login_fingerprint(self, pid: int) -> str | None:
        p = self.db.q1("SELECT created_at, pin_hash, archived FROM profile WHERE id=?", pid)
        if not p:
            return None
        import hashlib
        return hashlib.sha256(f"{p['created_at']}|{p['pin_hash'] or ''}|{p['archived']}".encode()).hexdigest()[:12]

    def games_access(self) -> dict:
        """_games_access once per request (memo.py) – a copy per call (the parent area changes and saves it)."""
        return {g: dict(a) for g, a in memo.get("games_access", self._games_access).items()}

    def _games_access(self) -> dict:
        """Per game: {"mode": all | some | off, "profiles": [...], "bots": bool, "price": coins, "rent": coins,
        "period": day | week | month} (+ "luck" 1–10 for the one-armed bandit) – from the older single switch when not
        set yet. Price and rent: what a child pays to buy / rent the game (gamepasses.py) – 0 and 0 = free; "preview":
        free tries before buying / renting. A value the parents never set (key missing) takes the default of
        gamepasses.py (DEFAULT_PRICE, DEFAULT_RENT, DEFAULT_PREVIEW) – an explicit 0 stays 0."""
        from . import gamepasses as gp
        DEFAULT_PERIOD, DEFAULT_PRICE = gp.DEFAULT_PERIOD, gp.DEFAULT_PRICE   # noqa: N806 – read at call time (tests)
        from .slots import DEFAULT_LUCK
        acc = self.db.get_setting("games_access")

        def num(v, default: int, lo: int = 0, hi: int = 100000) -> int:
            try:
                return min(hi, max(lo, int(v)))
            except (TypeError, ValueError):
                return default

        def money(g: str, a: dict) -> dict:
            period = a.get("period")
            rent, rent_period = gp.DEFAULT_RENT.get(g, (0, DEFAULT_PERIOD))
            if "preview" not in a and not int(a.get("rent") or 0):
                # saved by beta 13 (before free tries existed): its rent 0 was only the shown default – use the new one
                a = {k: v for k, v in a.items() if k not in ("rent", "period")}
            if "rent" not in a and "period" not in a:
                period = rent_period
            out = {"price": num(a.get("price", DEFAULT_PRICE.get(g, 0)), DEFAULT_PRICE.get(g, 0)), "rent": num(a.get("rent", rent), rent),
                   "period": period if period in ("day", "week", "month") else rent_period,
                   "preview": num(a.get("preview", gp.DEFAULT_PREVIEW), gp.DEFAULT_PREVIEW, 0, gp.MAX_PREVIEW)}
            if g == "slots":
                out["luck"] = num(a.get("luck", DEFAULT_LUCK), DEFAULT_LUCK, 1, 10)
            if g in self.FREE_GAMES:
                out.update(price=0, rent=0)
            return out
        if not acc:
            mode = self.db.get_setting("games") or "all"
            old = {"mode": mode if mode in ("all", "some", "off") else "all", "profiles": list(self.db.get_setting("games_profiles") or [])}
            return {g: {**old, "bots": True, **money(g, {})} for g in self.GAMES}
        # a game that came with an update (not in the stored setting yet): open only if the parents left every game
        # open – if they restricted any game, a new one starts switched off until they decide
        stored = [(acc.get(g) or {}).get("mode", "all") for g in self.GAMES if g in acc]
        new_mode = "all" if all(m == "all" for m in stored) else "off"
        return {g: {"mode": (acc.get(g) or {}).get("mode", "all") if g in acc else "all" if g in self.OPEN_WHEN_NEW else new_mode,
                    "profiles": list((acc.get(g) or {}).get("profiles") or []),
                    "bots": (acc.get(g) or {}).get("bots") is not False or g not in self.BOT_GAMES,
                    **money(g, acc.get(g) or {})} for g in self.GAMES}

    def games_without_bots(self, prof: dict) -> list[str]:
        """The games this profile may play only without bots (parent area › Games: «active without bots») – parents
        are not bound, like they can always play every game."""
        if prof.get("role") == "parent":
            return []
        return [g for g, a in self.games_access().items() if not a.get("bots", True)]

    def bots_allowed(self, prof: dict, game: str) -> bool:
        return game not in self.games_without_bots(prof)

    def table_without_bots(self, kind: str, people: list) -> bool:
        """For the game engines: may no bot sit at this table? Not when a parent plays along (parents decide)."""
        if (self.games_access().get(kind) or {}).get("bots", True):
            return False
        ids = [int(x) for x in people if str(x).isdecimal()]
        if ids and self.db.q1(f"SELECT id FROM profile WHERE role='parent' AND id IN ({','.join('?' * len(ids))})", *ids):
            return False
        return True

    # ---------------------------------------------------------------- party mode (battery.py, Party)
    def party_for(self, prof: dict) -> dict | None:
        """The party mode for this child just now ({"unlock", "battery", "limits", "until", …}) – None: not in party."""
        return self.battery.party.for_kid(prof)

    def party_unlocks(self, prof: dict) -> bool:
        p = self.party_for(prof)
        return bool(p and p["unlock"])

    def party_lifts(self, prof: dict) -> bool:
        """Party mode with «also lift limits»: the daily game time, game block times and the OfflineTime game lock do
        not count for games."""
        p = self.party_for(prof)
        return bool(p and p["limits"])

    def game_status(self, prof: dict, now: datetime | None = None) -> dict:
        """The daily game time as the app, the parent area and Home Assistant show it: {"left": minutes (None:
        unlimited – parents, no limit, a party that lifts the limits), "unlimited", "used_up", "party"}."""
        lifted = prof.get("role") == "kid" and self.party_lifts(prof)
        left = None if lifted else timelimits.left(self.db, prof, "game", now)
        return {"left": left, "unlimited": left is None, "used_up": left == 0, "party": lifted}

    def game_used_up(self, prof: dict) -> bool:
        """The daily game time of this child is used up (not during a party that lifts the limits)."""
        return self.game_status(prof)["used_up"]

    def use_charge(self, prof: dict, game: str) -> tuple[str | None, int | None]:
        """Starting a game costs a segment of the game battery (battery.py): "free", "same", "new" (+ log id) or None."""
        return self.battery.use(prof, game)

    def _games_blocked(self, prof: dict, time: bool = True) -> bool:
        """No game at all just now for this child: game time of today used up (`time`), OfflineTime, block time.
        A party with «also lift limits» lifts all of it for games – except a block time of the whole app."""
        lift = prof.get("role") == "kid" and self.party_lifts(prof)
        if time and not lift and timelimits.used_up(self.db, prof, "game"):
            return True
        if not lift and self.calendar.blocks(prof["id"], "games"):  # OfflineTime: the games of the app are locked
            return True
        blk = self.internet.block(prof)                            # block time of the internet plan: games or the whole app
        return bool(blk and (blk["mode"] == "app" or (blk["mode"] == "games" and not lift)))

    def games_open_to(self, prof: dict, party: bool = True) -> list[str]:
        """The games the parents switched on for this profile (parent area › Games) – price, time and blocks aside.
        `party`: the party mode «unlock all games» opens all of them (not for buying or renting: that is for good)."""
        if prof["role"] == "parent" or (party and self.party_unlocks(prof)):     # party mode «unlock all games»
            return list(self.GAMES)
        return [g for g, a in self.games_access().items() if a["mode"] == "all" or (a["mode"] == "some" and prof["id"] in a["profiles"])]

    def games_for(self, prof: dict, time: bool = True) -> list[str]:
        """The games this profile may play: parents all, children as set in the parent area (per game) and – for a
        game with a price – once bought or while rented (gamepasses.py).
        `time`: a child whose game time of today is used up (timelimits.py) may start or join none."""
        if prof["role"] == "parent":
            return list(self.GAMES)
        if self._games_blocked(prof, time):
            return []
        if self.party_unlocks(prof):
            return list(self.GAMES)
        acc = self.games_access()
        paid = self.passes.unlocked_set(prof["id"], acc)
        return [g for g in self.games_open_to(prof) if g in paid]

    def game_unlocked(self, pid: int, game: str) -> bool:
        """Parents always; a child when the game has no price or the child bought / rented it (or in party mode)."""
        p = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        if not p or p["role"] == "parent":
            return bool(p)
        if self.party_unlocks(p):
            return True
        return game in self.passes.unlocked_set(pid, {game: self.games_access()[game]})

    def game_offers(self, prof: dict) -> list[dict]:
        """The priced games this child may play once bought or rented (kid shop, locked tiles) – with what it has."""
        if prof["role"] == "parent" or self.party_unlocks(prof):
            return []
        return self.passes.offers(prof["id"], self.games_access(), self.games_open_to(prof))

    def game_trial(self, prof: dict, game: str, time: bool = False) -> dict | None:
        """A game with a price this child has not bought / rented, but may try (gamepasses.py `preview`):
        {"left": free tries left, "member": seated at a running table of it, "active": a try began a short while ago}
        – None for parents, games switched off for the child, free or unlocked games and while games are blocked."""
        if prof.get("role") != "kid" or game not in self.GAMES or self._games_blocked(prof, time):
            return None
        if self.party_unlocks(prof) or game not in self.games_open_to(prof):    # party «all games open»: no try needed
            return None
        a = self.games_access()[game]
        from .gamepasses import priced
        if not priced(a) or game in self.passes.unlocked_set(prof["id"], {game: a}):
            return None
        return {"left": self.passes.tries_left(prof["id"], game, a), "member": self._seated(prof["id"], game),
                "active": self.passes.trying(prof["id"], game)}

    def _seated(self, pid: int, game: str) -> bool:
        """Sits at a running table of this game (alone or with the family)."""
        from . import running
        return any(t["game"] == game and t["status"] != "done" and str(pid) in (t.get("members") or []) for t in running.running(self))

    def trial_games(self, prof: dict) -> dict[str, dict]:
        """The locked games with a price this child may try now or plays on a try: {game: {"left", "member"}}."""
        if prof.get("role") != "kid" or self._games_blocked(prof, False):
            return {}
        offers = [o for o in self.game_offers(prof) if not o["open"]]
        if not offers:
            return {}
        from . import running
        seated = {t["game"] for t in running.running(self) if t["status"] != "done" and str(prof["id"]) in (t.get("members") or [])}
        return {o["game"]: {"left": o["tries_left"], "member": o["game"] in seated} for o in offers
                if o["tries_left"] > 0 or o["game"] in seated}

    def use_game_try(self, prof: dict, game: str, same: bool = True) -> str | None:
        """Use a free try of a locked game (gamepasses.use_try): "new", "same" or None."""
        return self.passes.use_try(prof["id"], game, self.games_access()[game], same)

    def parent_tables(self, prof: dict, time: bool = True) -> dict[str, dict]:
        """Family tables a PARENT opened that this child may sit at although the game is locked for it (switched off,
        not bought, not rented): {game: {"member": bool, "joinable": bool}}. Starting own tables stays locked.
        Time limits (`time` as in games_for), OfflineTime and block times still count."""
        if prof["role"] == "parent" or self._games_blocked(prof, time):
            return {}
        from . import running
        ok = set(self.games_for(prof, time))
        out: dict[str, dict] = {}
        parents = None
        for t in running.running(self):
            if t["solo"] or t["game"] in ok or t["status"] == "done":
                continue
            if parents is None:
                parents = {r["id"] for r in self.db.q("SELECT id FROM profile WHERE role='parent'")}
            if t.get("host_id") not in parents:
                continue
            member = str(prof["id"]) in (t.get("members") or [])
            joinable = t["status"] != "paused" and running._joinable(self, t)
            if member or joinable:
                cur = out.setdefault(t["game"], {"member": False, "joinable": False})
                cur["member"] |= member
                cur["joinable"] |= joinable
        return out

    def _community_summary(self, prof: dict) -> dict:
        """Running games and open votes for the start page – only the games this profile may play."""
        pid, ok = prof["id"], set(self.games_for(prof)) | set(self.parent_tables(prof))   # + tables a parent opened
        ok |= set(self.trial_games(prof))                    # + locked games with a free try left or played on a try
        out = self.community.summary(pid)
        if "quiz" not in ok:
            out["quiz"] = None
        out["bingo"] = self.bingo.summary(pid) if "bingo" in ok else None
        out["poker"] = self.poker.summary(pid) if "poker" in ok else None
        out["song"] = self.songs.summary(pid) if "song" in ok else None
        for k in ("tschau", "karussell"):
            out[k] = self.cards.summary(k, pid) if k in ok else None
        out["domino"] = self.domino.summary("domino", pid) if "domino" in ok else None
        out["paarjagd"] = self.paarjagd.summary("paarjagd", pid) if "paarjagd" in ok else None
        out["werbinich"] = self.werbinich.summary("werbinich", pid) if "werbinich" in ok else None
        out["kartenlauf"] = self.kartenlauf.summary("kartenlauf", pid) if "kartenlauf" in ok else None
        out["stadtland"] = self.stadtland.summary("stadtland", pid) if "stadtland" in ok else None
        out["zeichnen"] = self.zeichnen.summary("zeichnen", pid) if "zeichnen" in ok else None
        out["wuerfel"] = self.wuerfel.summary("wuerfel", pid) if "wuerfel" in ok else None
        out["heimwaerts"] = self.heimwaerts.summary("heimwaerts", pid) if "heimwaerts" in ok else None
        out["jump"] = self.jump.summary("jump", pid) if "jump" in ok else None
        out["sternlauf"] = self.sternlauf.summary("sternlauf", pid) if "sternlauf" in ok else None
        out["snack"] = self.snack.summary("snack", pid) if "snack" in ok else None
        out["verkehr"] = self.verkehr.summary("verkehr", pid) if "verkehr" in ok else None
        out["langstrecke"] = self.langstrecke.summary("langstrecke", pid) if "langstrecke" in ok else None
        out["klatsch"] = self.klatsch.summary("klatsch", pid) if "klatsch" in ok else None
        out["verboten"] = self.verboten.summary("verboten", pid) if "verboten" in ok else None
        out["jass"] = self.jass.summary("jass", pid) if "jass" in ok else None
        out["werwolf"] = self.werwolf.summary("werwolf", pid) if "werwolf" in ok else None
        out["schach"] = self.schach.summary("schach", pid) if "schach" in ok else None
        out["dorfmarkt"] = self.dorfmarkt.summary("dorfmarkt", pid) if "dorfmarkt" in ok else None
        out["escape"] = self.escape.summary("escape", pid) if "escape" in ok else None
        out["stempeljagd"] = self.stempeljagd.summary("stempeljagd", pid) if "stempeljagd" in ok else None
        out["duel"] = self.duels.summary(pid) if "ttt" in ok else None
        out["pong4"] = self.pong4.summary(pid) if "pingpong" in ok else None
        out["boards_new"] = self.boards.new_count(pid)       # bulletin boards: not a game, for everybody of the family
        out["familytime"] = self.familytime.summary(prof)            # FamilyTime: a wish or a vote is missing
        return out

    def games_allowed(self, prof: dict, game: str | None = None, time: bool = True) -> bool:
        """This game (or, without one, any family game) for this profile? `time=False`: the daily game time does not
        count (a game the child is already in may be played to the end)."""
        allowed = self.games_for(prof, time)
        return game in allowed if game else bool(allowed)

    def kids(self) -> list[dict]:
        return self.db.q("SELECT * FROM profile WHERE role='kid' AND archived=0 ORDER BY id")

    # ---------------------------------------------------------------- dashboard
    def subjects(self, pid: int) -> list[dict]:
        tiles = []
        for pack in self.packs.for_profile(pid):
            prog = self.learning.pack_progress(pid, pack)
            s = pack.summary()
            nxt = next((u for u in prog["units"] if u["id"] == prog["next"]), None)
            tiles.append({"pack": pack.id, "title": pack.title, "subject": s["subject"], "color": s.get("color"),
                          "icon": s.get("icon"), "stars": prog["stars"], "max_stars": prog["max_stars"],
                          "percent": prog["percent"], "due": prog["due"], "next": nxt, "status": s.get("status", "active")})
        return tiles

    def avatar_state(self, pid: int) -> tuple[int, set[str], set[str]]:
        self.pets.sync(pid)                 # a pet earned with a badge becomes an unlock (and a living pet)
        level = self.rewards.level(pid)["level"]
        badges = {b["id"] for b in self.rewards.badges(pid)}
        bought = {r["item"] for r in self.db.q("SELECT item FROM unlock WHERE profile_id=?", pid)}
        return level, badges, bought

    def dashboard(self, prof: dict) -> dict:
        pid = prof["id"]
        ps = profile_settings(prof)
        bal = self.rewards.balances(pid)
        accounts = [a for a in self.rewards.accounts() if a["key"] != "xp"]
        offers = self.shop.offers(pid)
        nxt = sorted([o for o in offers if not o["can"] and o["missing"] > 0 and o["kind"] != "avatar_item"],
                     key=lambda o: o["missing"])
        goals = self.goals_for(pid)
        chores = self.all_chores(prof)
        return {
            "prank": self.pranks.pending(pid),            # an ink bomb waiting for this profile (web/kid.js)
            "profile": self.profile_public(prof),
            "level": self.rewards.level(pid),
            "streak": self.rewards.streak(pid),
            "xp_today": self.rewards.xp_today(pid),
            "daily_goal": int(ps["daily_goal"]),
            "balances": bal,
            "accounts": accounts,
            "next_reward": nxt[0] if nxt else None,
            "badges": self.badge_overview(pid),
            "subjects": self.subjects(pid),
            "goals": goals,
            "family_goal": self.family_goal(),
            "chores": chores,
            "games": self.games_allowed(prof),
            "games_list": self.games_for(prof),
            "games_nobots": self.games_without_bots(prof),        # these only without bots (no «alone against bots»)
            "games_locked": [o for o in self.game_offers(prof) if not o["open"]],   # to buy / rent first (🔒 tiles)
            "games_tables": sorted(self.parent_tables(prof)),     # locked, but a parent opened a table to join
            "games_trial": self.trial_games(prof),                # locked: free tries left / playing on a try
            "community": self._community_summary(prof),
            "has_devices": bool(profile_settings(prof).get("devices")) and bool(self.ha and self.ha.connected),
            "internet": self.internet.state(prof),
            "time_left": self.time_left(prof),
            "offline_lock": self._offline_lock(prof),
            "weather": self.weather.current(pid) if prof.get("role") != "parent" else None,
            "special_times": self.calendar.special(pid) if prof.get("role") != "parent" else self.calendar.special(None),
            "weather_alarm": self.kiosk.weather_alarm() if self.kiosk.config().get("kids_alarm") else None,
            "pending": [r for r in self.shop.list("pending", pid)],
            "pets": self.pets.summary(pid),
            "battery": self.battery.state(prof),              # game battery (battery.py) – None for parents
            "party": self.party_public(prof),                 # party mode for this child (banner, disco theme)
            "deals": self.deals.summary(prof),                # deals waiting for an answer, news (deals.py)
            "coins_reserved": self.rewards.reserved(pid),     # promised in a deal that stands – cannot be spent
            "coins_available": self.rewards.available(pid),   # what can be spent («enough coins?» in the app)
            "stories": self.stories.enabled_for(prof),        # adventure books (stories.py) – off per child by the parents
            # 💡 Code Workshop (codelab.py) – only in the dev channel (channel.DEV_FEATURES), off per child by the parents
            "codelab": feature_visible("codelab") and self.codelab.enabled_for(prof),
        }

    def party_public(self, prof: dict) -> dict | None:
        p = self.party_for(prof)
        if not p:
            return None
        from .themes import DISCO
        return {"until": p["until"], "unlock": p["unlock"], "battery": p["battery"], "limits": p["limits"], "theme": DISCO}

    def time_left(self, prof: dict) -> dict:
        """Minutes left today: family games, learning, internet – None = unlimited (parents always)."""
        net = self.internet.state(prof) if prof.get("role") == "kid" else None
        unlimited = not net or (net.get("budget") or {}).get("unlimited")
        return {"games": self.game_status(prof)["left"], "learn": timelimits.left(self.db, prof, "learn"),
                "internet": None if unlimited else net["minutes"]}

    def _offline_lock(self, prof: dict) -> dict | None:
        """Block time «only a message»: the app shows that it is OfflineTime (children only)."""
        if prof.get("role") == "parent":
            return None
        blk = self.internet.block(prof)
        return {"until": blk["until"]} if blk and blk["mode"] == "app" else None

    # ---------------------------------------------------------------- mood
    @staticmethod
    def is_sad(avatar: dict) -> bool:
        """Sad, sick, angry or worried – the parents are told quietly."""
        a = avatar or {}
        return a.get("eyes") in ("sad", "angry") or a.get("mouth") in ("sad", "wavy")

    def mood_changed(self, prof: dict, old: dict, new: dict, text: str | None = None, mood: str | None = None) -> None:
        """Avatar switched to sad and/or a new «today I feel …» text → remember it and quietly tell the parents.

        Sad without text: once per day. A new text: at most every 10 minutes (no notification storm).
        """
        from datetime import datetime
        s = json.loads(prof["settings"] or "{}")
        now_dt = datetime.now()
        stamp = now_dt.isoformat(timespec="minutes")
        was, now = self.is_sad(old), self.is_sad(new)
        changed = False
        notify = False
        if now and not was:
            s["mood_sad_since"] = stamp
            changed = True
            if s.get("mood_notified") != stamp[:10]:
                s["mood_notified"] = stamp[:10]
                notify = True
        elif was and not now and s.pop("mood_sad_since", None):
            changed = True
        if mood is not None and mood != s.get("mood"):
            s["mood"], s["mood_at"] = (mood[:8] or None), stamp       # the emoji the child picked
            changed = True
        new_text = None
        if text is not None:
            text = " ".join(str(text).split())[:200]
            if text != (s.get("mood_text") or ""):
                s["mood_text"], s["mood_text_at"] = text, stamp
                changed = True
                if text:
                    last = s.get("mood_text_notified")
                    if not last or (now_dt - datetime.fromisoformat(last)).total_seconds() >= 600:
                        s["mood_text_notified"] = stamp
                        new_text = text
                        notify = True
        if changed:
            self.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(s), prof["id"])
        if notify:
            for fn in self.on_mood:
                try:
                    fn(prof, now, new_text)
                except Exception:  # noqa: BLE001
                    log.exception("mood listener failed")

    # ---------------------------------------------------------------- badges
    def badge_overview(self, pid: int) -> list[dict]:
        """All badges with how to get them, progress and the avatar items they unlock."""
        from .rewards.engine import BADGES
        earned = {b["id"]: b["at"] for b in self.rewards.badges(pid)}
        lessons = int(self.db.val("SELECT SUM(lessons) FROM daily WHERE profile_id=?", pid, default=0))
        chores = int(self.db.val("SELECT COUNT(DISTINCT ref) + COALESCE((SELECT SUM(n) FROM ledger_folded WHERE profile_id=? AND event='chore_done'), 0) FROM ledger WHERE profile_id=? AND event='chore_done'",
                                 pid, pid, default=0))   # + chores folded by a clean-up (privacy.py)
        streak, xp = self.rewards.streak(pid), self.rewards.total_xp(pid)
        best = {"any": 0, "times": 0, "french": 0, "geo": 0}
        for pack in self.packs.for_profile(pid):
            st = self.learning.states(pid, pack.id)
            for u in pack.units:
                s = self.learning.unit_stars(pid, pack, u, st)
                best["any"] = max(best["any"], s)
                if u.generator == "einmaleins":
                    best["times"] = max(best["times"], s)
                if pack.subject == "franzoesisch":
                    best["french"] = max(best["french"], s)
                if pack.subject in ("nmg", "geografie") and "tg" in pack.id.split("-"):
                    best["geo"] = max(best["geo"], s)
        progress = {"first_lesson": (lessons, 1), "ten_lessons": (lessons, 10), "quiz_ace": (0, 1),
                    "streak_7": (streak, 7), "streak_30": (streak, 30), "xp_1000": (xp, 1000),
                    "unit_master": (best["any"], 5), "times_tables_pro": (best["times"], 5),
                    "french_star": (best["french"], 5), "geo_thurgau": (best["geo"], 5), "chores_50": (chores, 50)}
        unlocks: dict[str, list[str]] = {}
        for iid, (name, _slot, rule) in av.ITEMS.items():
            if "badge" in rule:
                unlocks.setdefault(rule["badge"], []).append(name)
        out = []
        for bid, (name, icon, how) in BADGES.items():
            value, target = progress.get(bid, (0, 1))
            done = bid in earned
            out.append({"id": bid, "name": name, "icon": icon, "how": how, "earned": done, "at": earned.get(bid),
                        "value": target if done else min(value, target), "target": target, "unlocks": unlocks.get(bid, [])})
        out.sort(key=lambda b: (not b["earned"], -(b["value"] / b["target"])))
        return out

    # ---------------------------------------------------------------- chores
    def all_chores(self, prof: dict) -> list[dict] | None:
        """Today's chores of a child: own chore plan plus the Family Planer (if linked)."""
        own = self.chores.for_kid(prof["id"])
        built_in = self.planer_host.chores_for(prof["id"]) if self.planer_host else []
        planer = self.ha.chores(prof) if self.ha else None
        if planer is None and not own and not built_in and not self.chores.list(active_only=True) \
                and not (self.planer_host and self.planer_host.planner.data.get("chores")):
            return None
        return own + built_in + [dict(c, source="planer") for c in planer or []]

    def chore_stats(self, prof: dict) -> dict | None:
        own = self.chores.stats(prof["id"])
        planer = self.ha.chore_stats(prof) if self.ha else None
        if own and planer and planer.get("week_percent") is not None:
            own = dict(own, week_percent=round((own["week_percent"] + planer["week_percent"]) / 2),
                       reliability=round((own["reliability"] + (planer.get("reliability") or own["reliability"])) / 2))
        return own or planer

    # ---------------------------------------------------------------- goals
    def goals_for(self, pid: int) -> list[dict]:
        out = []
        for g in self.db.q("SELECT * FROM goal WHERE profile_id=? AND active=1 AND kind='unit' ORDER BY id", pid):
            pack = self.packs.get(g["pack_id"] or "")
            unit = pack.unit(g["unit_id"]) if pack and g["unit_id"] else None
            if not pack:
                continue
            if unit:
                st = self.learning.unit_stars(pid, pack, unit)
                target = int(g["target"] or 5)
                out.append({"id": g["id"], "title": g["title"] or f"{pack.title} – {unit.title}", "pack": pack.id,
                            "unit": unit.id, "value": st, "target": target, "done": st >= target,
                            "color": pack.summary().get("color")})
            else:
                prog = self.learning.pack_progress(pid, pack)
                target = int(g["target"] or 100)
                out.append({"id": g["id"], "title": g["title"] or pack.title, "pack": pack.id, "unit": None,
                            "value": prog["percent"], "target": target, "done": prog["percent"] >= target,
                            "percent": True, "color": pack.summary().get("color")})
        return out

    def family_goal(self) -> dict | None:
        g = self.db.q1("SELECT * FROM goal WHERE profile_id IS NULL AND kind='family' AND active=1 ORDER BY id DESC LIMIT 1")
        if not g:
            return None
        acc = g["account"] or "xp"
        value = float(self.db.val("""SELECT SUM(l.amount) FROM ledger l JOIN profile p ON p.id=l.profile_id
                                     WHERE p.role='kid' AND l.account=? AND l.amount>0 AND l.at>=?""",
                                  acc, g["created_at"], default=0))
        return {"id": g["id"], "title": g["title"], "account": acc, "value": value, "target": g["target"],
                "done": value >= g["target"]}

    # ---------------------------------------------------------------- family view
    def week_stats(self, pid: int, start, end) -> dict:
        prof = self.db.q1("SELECT * FROM profile WHERE id=?", pid)
        goal = int(profile_settings(prof)["daily_goal"])
        rows = self.db.q("SELECT * FROM daily WHERE profile_id=? AND day>=? AND day<=?", pid, start.isoformat(), end.isoformat())
        days = (min(end, today()) - start).days + 1
        xp = sum(r["xp"] for r in rows)
        pct = 100 * sum(min(1.0, r["xp"] / max(1, goal)) for r in rows) / max(1, days)
        return {"xp": xp, "goal_percent": round(pct), "days_met": sum(r["goal_met"] for r in rows),
                "minutes": round(sum(r["seconds"] for r in rows) / 60)}

    def family(self) -> dict:
        t = today()
        monday = t - timedelta(days=t.weekday())
        last_monday = monday - timedelta(days=7)
        vis = self.db.get_setting("family_visibility")
        members = []
        for k in self.kids():
            pid = k["id"]
            ps = profile_settings(k)
            tiles = self.subjects(pid)
            progress = round(sum(x["percent"] for x in tiles) / len(tiles)) if tiles else 0
            week = self.week_stats(pid, monday, t)
            last = self.week_stats(pid, last_monday, monday - timedelta(days=1))
            chores = self.chore_stats(k)
            m = {"profile": self.profile_public(k),
                 "today_percent": min(100, round(100 * self.rewards.xp_today(pid) / max(1, int(ps["daily_goal"])))),
                 "week_percent": week["goal_percent"], "streak": self.rewards.streak(pid), "progress": progress,
                 "chores": chores, "last_week_score": self._score(last["goal_percent"], (chores or {}).get("week_percent"))}
            if vis == "all":
                m.update(level=self.rewards.level(pid)["level"], xp_week=week["xp"], minutes_week=week["minutes"])
            members.append(m)
        winner = None
        if members and any(m["last_week_score"] > 0 for m in members):
            winner = max(members, key=lambda m: m["last_week_score"])["profile"]["id"]
        if vis == "goal":
            members = [{"profile": m["profile"]} for m in members]
        return {"visibility": vis, "members": members, "winner": winner, "family_goal": self.family_goal()}

    @staticmethod
    def _score(learn_pct: float, chores_pct: float | None) -> float:
        if chores_pct is None:
            return float(learn_pct)
        return round((float(learn_pct) + float(chores_pct)) / 2, 1)

    # ---------------------------------------------------------------- parent overview
    def overview(self) -> list[dict]:
        out = []
        t = today()
        monday = t - timedelta(days=t.weekday())
        for k in self.kids():
            pid = k["id"]
            out.append({
                "profile": self.profile_public(k),
                "level": self.rewards.level(pid),
                "streak": self.rewards.streak(pid),
                "balances": self.rewards.balances(pid),
                "week": self.week_stats(pid, monday, t),
                "subjects": self.learning.time_per_subject(pid, 7),
                "weak": self.learning.weak_spots(pid),
                "packs": [{"id": s["pack"], "title": s["title"], "percent": s["percent"], "due": s["due"],
                           "color": s["color"]} for s in self.subjects(pid)],
                "chores": self.chore_stats(k),
                "internet": self.internet.state(k),
                "sad_since": json.loads(k["settings"] or "{}").get("mood_sad_since"),
                "mood_text": json.loads(k["settings"] or "{}").get("mood_text") or None,
                "mood": json.loads(k["settings"] or "{}").get("mood") or None,
                "mood_text_at": json.loads(k["settings"] or "{}").get("mood_text_at"),
                "pets": self.pets.list(pid),
                "pets_paused": self.pets.paused_by_parents(pid),
            })
        return out

    def subject_list(self) -> list[dict]:
        keys = sorted({p.subject for p in self.packs.all(kind="pack")})
        return [subject_meta(k) for k in keys]
