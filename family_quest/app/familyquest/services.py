"""Wiring of all services plus the read models for dashboard and family view."""
from __future__ import annotations

import json
import random
import logging
from datetime import date, timedelta

from .api.auth import Throttle, Tokens
from .bingo import Bingo
from .poker import Poker
from .cardgames import CardGames
from .community import Community
from .chores import Chores
from .internet import InternetTime
from .db import Database, profile_settings
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

log = logging.getLogger("familyquest")


class FamilyQuest:
    def __init__(self, settings: Settings, db: Database | None = None):
        self.settings = settings
        self.db = db or Database(settings.db_path)
        self.packs = PackStore(self.db, settings.media_dir)
        self.rewards = Rewards(self.db)
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
        from .verboten import Verboten
        self.verboten = Verboten(self.db, self.community.add_history, self.rewards)
        from .jass import Jass
        self.jass = Jass(self.db, self.community.add_history, self.rewards)
        from .werwolf import Werwolf
        self.werwolf = Werwolf(self.db, self.community.add_history, self.rewards)
        from .songquiz import SongQuiz
        self.lan_base = None      # http://<Home Assistant IP>:<port of the direct access> – for sounds on speakers
        self.songs = SongQuiz(self.db, self.community.add_history, lambda: self.ha,
                              lambda name: f"{self.lan_base}/sounds/{name}.mp3" if self.lan_base else None)
        from .pets import Pets
        self.pets = Pets(self.db, self.rewards)
        from .slots import Slots
        self.slots = Slots(self.db, self.rewards)
        from .pranks import Pranks
        self.pranks = Pranks(self.db, self.rewards, lambda: self.ha,
                             lambda name: f"{self.lan_base}/sounds/{name}.mp3" if self.lan_base else None)
        self.pets.away = self._away_days
        from .bots import Bots
        self.bots = Bots(self.db)
        self.bots.pets = self.pets
        from .wichteln import Wichteln
        self.wichteln = Wichteln(self.db, lambda: self.planer_host)
        from .duel import Duels
        self.duels = Duels(lambda pid: (self.db.q1("SELECT name FROM profile WHERE id=?", pid) or {"name": "?"})["name"])
        from .pong4 import Doubles
        self.pong4 = Doubles(self.duels.names)
        self.weather = Weather(self.db, self.rewards)
        self.translations = Translations(self.db)
        self.kiosk = Dashboard(self)
        self.guests = Guests(self)
        self.calendar = FamilyCalendar(self)
        self.internet.offline = lambda pid: self.calendar.blocks(pid, "internet")
        self.shop.internet = self.internet
        self.tokens = Tokens(settings.secret)
        self.tokens.fingerprint = self._login_fingerprint
        self.throttle = Throttle()
        self.ha = None            # set by main when Home Assistant is available (ha.service.HAService)
        self.planer_host = None   # Family Planer core (planer.host.PlanerHost), started by main
        self.on_mood: list = []   # fn(profile_row) – a child set its avatar to «sad»

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
               "auto_logout_min": st["auto_logout_min"], "pin_kind": "digits" if p["pin_hash"] else ""}
        if p["pin_hash"] and st.get("pin_kind") == "symbols" and st.get("symbol_set"):
            # picture PIN: the login shows exactly these 12 symbols, shuffled every time (not secret)
            out.update(pin_kind="symbols", symbol_set=random.sample(st["symbol_set"], len(st["symbol_set"])))
        return out

    GAMES = ("quiz", "bingo", "song", "poker", "tschau", "karussell", "domino", "paarjagd", "werbinich", "kartenlauf", "stadtland", "zeichnen", "wuerfel", "heimwaerts", "jump", "verboten", "jass", "werwolf", "ttt", "sudoku", "patience", "pingpong", "slots")

    def _login_fingerprint(self, pid: int) -> str | None:
        p = self.db.q1("SELECT created_at, pin_hash, archived FROM profile WHERE id=?", pid)
        if not p:
            return None
        import hashlib
        return hashlib.sha256(f"{p['created_at']}|{p['pin_hash'] or ''}|{p['archived']}".encode()).hexdigest()[:12]

    def games_access(self) -> dict:
        """Per game: {"mode": all | some | off, "profiles": [...]} – from the older single switch when not set yet."""
        acc = self.db.get_setting("games_access")
        if not acc:
            mode = self.db.get_setting("games") or "all"
            old = {"mode": mode if mode in ("all", "some", "off") else "all", "profiles": list(self.db.get_setting("games_profiles") or [])}
            return {g: dict(old) for g in self.GAMES}
        # a game that came with an update (not in the stored setting yet): open only if the parents left every game
        # open – if they restricted any game, a new one starts switched off until they decide
        stored = [(acc.get(g) or {}).get("mode", "all") for g in self.GAMES if g in acc]
        new_mode = "all" if all(m == "all" for m in stored) else "off"
        return {g: {"mode": (acc.get(g) or {}).get("mode", "all") if g in acc else new_mode,
                    "profiles": list((acc.get(g) or {}).get("profiles") or [])} for g in self.GAMES}

    def games_for(self, prof: dict) -> list[str]:
        """The games this profile may play: parents all, children as set in the parent area (per game)."""
        if prof["role"] == "parent":
            return list(self.GAMES)
        if self.calendar.blocks(prof["id"], "games"):              # OfflineTime: the games of the app are locked
            return []
        blk = self.internet.block(prof)                            # block time of the internet plan: games or the whole app
        if blk and blk["mode"] in ("games", "app"):
            return []
        return [g for g, a in self.games_access().items() if a["mode"] == "all" or (a["mode"] == "some" and prof["id"] in a["profiles"])]

    def _community_summary(self, prof: dict) -> dict:
        """Running games and open votes for the start page – only the games this profile may play."""
        pid, ok = prof["id"], set(self.games_for(prof))
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
        out["verboten"] = self.verboten.summary("verboten", pid) if "verboten" in ok else None
        out["jass"] = self.jass.summary("jass", pid) if "jass" in ok else None
        out["werwolf"] = self.werwolf.summary("werwolf", pid) if "werwolf" in ok else None
        out["duel"] = self.duels.summary(pid) if "ttt" in ok else None
        out["pong4"] = self.pong4.summary(pid) if "pingpong" in ok else None
        return out

    def games_allowed(self, prof: dict, game: str | None = None) -> bool:
        """This game (or, without one, any family game) for this profile?"""
        allowed = self.games_for(prof)
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
                          "percent": prog["percent"], "due": prog["due"], "next": nxt})
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
            "community": self._community_summary(prof),
            "has_devices": bool(profile_settings(prof).get("devices")) and bool(self.ha and self.ha.connected),
            "internet": self.internet.state(prof),
            "offline_lock": self._offline_lock(prof),
            "weather": self.weather.current(pid) if prof.get("role") != "parent" else None,
            "special_times": self.calendar.special(pid) if prof.get("role") != "parent" else self.calendar.special(None),
            "weather_alarm": self.kiosk.weather_alarm() if self.kiosk.config().get("kids_alarm") else None,
            "pending": [r for r in self.shop.list("pending", pid)],
            "pets": self.pets.summary(pid),
        }

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
        chores = int(self.db.val("SELECT COUNT(DISTINCT ref) FROM ledger WHERE profile_id=? AND event='chore_done'", pid, default=0))
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
