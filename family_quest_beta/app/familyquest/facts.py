"""«Family Quest Facts» – a special family quiz whose questions come from the family's own data.

The questions are made fresh at every start (random choice and order): who did the most chores this week, the
family's total XP, the most popular game, the record in Jump, the shopping queen, the oldest pet … Every generator
looks at one source (ledger, daily, history, settings with personal bests, redemptions, pets, boards …) and gives
nothing when the data is missing or the answer is not clear (a tie, only one child, nothing happened yet).

Questions use the kinds of the family quiz: multiple choice (`q`, `a`, `c`) and estimates (`answer`, `min`, `max`,
`unit`). Their texts are English templates (`_t`, placeholders {0} …) translated with the app's own dictionaries
(web/i18n/<lang>.json) into every quiz language – the quiz is multilingual (`langs` / `tr`), so everybody can switch
the language of the questions in the game. German: de-CH (Zürich dialect, «Ämtli») when the starter uses the app in
Swiss German, else de-DE.

Privacy: only what the family sees of each other anyway. Nothing from the parents' private areas (internet logs,
mood notes, behaviour weather, login log). XP, levels, coins and learning time only with the family view setting
«Everything» (family_visibility = all), like the family comparison. Parents switch the quiz off with the setting
`quiz_facts` (parent area › Games › Family quiz).
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta

from .community import CommunityError, QUIZ_LANGS, shuffle_answers
from .i18n import _t
from .rewards.engine import SPEND_EVENTS, today

TITLE = _t("Family Quest Facts")
SETTING = "quiz_facts"
FOCUS = ("week", "all", "mixed")
COUNTS = (5, 10, 15, 20)
MIN_QUESTIONS = 3
# quiz language → app dictionary (web/i18n/<file>.json); German is chosen at the start (de-CH or de-DE)
LANG_FILES = {"en": "en", "de": "de-DE", "fr": "fr-FR", "it": "it-IT", "es": "es-ES", "nl": "nl-NL", "pl": "pl-PL",
              "pt": "pt-BR", "sv": "sv-SE"}
GAME_TITLES = {"quiz": "Family quiz", "bingo": "Bingo", "song": "Guess the song", "poker": "Texas Hold'em"}
CARD_TITLES = {"Tschau Sepp": "tschau", "Kartenkarussell": "karussell"}      # history «cards»: data.game → kind
# personal bests kept in settings by the games: (setting, game kind, unit)
BESTS = (("jump_best", "jump", ""), ("sternlauf_best", "sternlauf", ""), ("snack_best", "snack", ""),
         ("verkehr_best", "verkehr", ""), ("klatsch_best", "klatsch", "%"))
SHOP_EVENTS = ("redeem", "avatar", "pet_shop", "prank_buy", "slots_buy")
GUEST = "guest"                                       # a «who» answer: one of the guests
NOT_EARNED = ("refund", "manual", "adjust", "slots_win", "slots_bet")   # coins that are no «earned this week»


# ---------------------------------------------------------------- texts: a str stays, a tuple (template, *args) is translated
def tr(text, d: dict) -> str:
    if isinstance(text, tuple):
        tpl, *args = text
        s = d.get(tpl) or tpl
        for i, a in enumerate(args):
            s = s.replace("{" + str(i) + "}", tr(a, d))
        return s
    return str(text)


def dictionaries(fq, lang: str | None) -> tuple[str, dict[str, dict]]:
    """The quiz languages with their dictionaries; the base is the language of who starts (two letters)."""
    from .translations import BUILTIN, builtin_dict
    tl = fq.translations
    lang = str(lang or "")
    base_file = lang if lang in BUILTIN else (tl.base_of(lang) or "de-DE") if lang.startswith("x-") else "de-DE"
    files = dict(LANG_FILES)
    if base_file.startswith("de-"):
        files["de"] = base_file
    out = {}
    for code, f in files.items():
        if code not in QUIZ_LANGS:
            continue
        d = dict(builtin_dict(f)) if f != "en" else {}
        own = lang if (lang.startswith("x-") and tl.base_of(lang) == f) else f
        try:
            d.update({k: v for k, v in tl.overrides(own).items() if v})
        except Exception:  # noqa: BLE001 – own texts are a bonus
            pass
        out[code] = d
    base = base_file[:2] if base_file[:2] in out else "de"
    return base, out


# ---------------------------------------------------------------- helpers
def nice_max(n: float) -> int:
    """A round upper end for an estimate: 1, 2, 5 × 10^k at least twice the answer."""
    want = max(10.0, float(n) * 2)
    k = 1
    while True:
        for m in (1, 2, 5):
            if m * k >= want:
                return m * k
        k *= 10


def near_numbers(n: int, k: int = 3) -> list[int]:
    """Plausible wrong numbers around n (never negative, never n)."""
    n = int(n)
    step = max(1, round(abs(n) * 0.25))
    pool = [n - 2 * step, n - step, n + step, n + 2 * step, n + 3 * step]
    pool = [x for x in dict.fromkeys(pool) if x >= 0 and x != n]
    random.shuffle(pool)
    out = pool[:k]
    extra = n + 4 * step
    while len(out) < k:
        out.append(extra)
        extra += step
    return out


class Facts:
    """The question generators over one database; `people` are the family (children and parents, not guests)."""

    def __init__(self, fq):
        self.fq = fq
        self.db = fq.db
        self.people = self.db.q("SELECT id, name, role, created_at FROM profile WHERE archived=0 AND role IN ('kid','parent') ORDER BY id")
        self.kids = [p for p in self.people if p["role"] == "kid"]
        self.name = {p["id"]: p["name"] for p in self.people}
        self.guests = {r["id"] for r in self.db.q("SELECT id FROM profile WHERE role='guest'")}
        self.open = (self.db.get_setting("family_visibility") or "all") == "all"
        t = today()
        mon = t - timedelta(days=t.weekday())
        self.ranges = {"today": (t, t + timedelta(days=1)), "week": (mon, t + timedelta(days=1)),
                       "last_week": (mon - timedelta(days=7), mon), "7days": (t - timedelta(days=6), t + timedelta(days=1))}
        self._hist = None

    # ---------- building blocks
    def who(self, gen: str, scope: str, q, counts: dict, pool: list[dict] | None = None, guests: bool = False) -> list[dict]:
        """«Who …?»: the person with the clearly highest count (> 0) – answers: the others of the pool (and «A guest»)."""
        pool = self.people if pool is None else pool
        if len(pool) < 2:
            return []
        ids = {p["id"] for p in pool}
        vals = {pid: v for pid, v in counts.items() if (pid in ids or (guests and pid == GUEST)) and v}
        if not vals:
            return []
        ranked = sorted(vals.items(), key=lambda x: -x[1])
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            return []                                   # a tie: no clear answer
        top = ranked[0][0]
        label = lambda pid: (_t("A guest"),) if pid == GUEST else self.name[pid]       # noqa: E731
        others = [p["id"] for p in pool if p["id"] != top]
        random.shuffle(others)
        wrong = [label(x) for x in others[:3]]
        if guests and top != GUEST and len(wrong) < 3 and self.guests:
            wrong.append(label(GUEST))
        return [{"gen": gen, "scope": scope, "q": q, "right": label(top), "wrong": wrong}]

    @staticmethod
    def number(gen: str, scope: str, q, n: float, estimate: bool = False, unit="") -> list[dict]:
        n = int(round(n))
        if estimate:
            return [{"gen": gen, "scope": scope, "q": q, "answer": n, "min": 0, "max": nice_max(n), "unit": unit}]
        return [{"gen": gen, "scope": scope, "q": q, "right": str(n), "wrong": [str(x) for x in near_numbers(n)]}]

    @staticmethod
    def pick(gen: str, scope: str, q, right, others: list) -> list[dict]:
        """Choose one thing (a game, a pet, a reward …) – needs at least one other answer."""
        seen, wrong = {json.dumps(right)}, []
        for o in others:
            if json.dumps(o) not in seen:
                seen.add(json.dumps(o))
                wrong.append(o)
        if not wrong:
            return []
        random.shuffle(wrong)
        return [{"gen": gen, "scope": scope, "q": q, "right": right, "wrong": wrong[:3]}]

    def span(self, key: str) -> tuple[str, str]:
        a, b = self.ranges[key]
        return a.isoformat(), b.isoformat()

    def history(self) -> list[dict]:
        if self._hist is None:
            self._hist = []
            for r in self.db.q("SELECT profile_id, kind, data, at FROM history WHERE kind NOT IN ('council','familytime')"):
                try:
                    r["data"] = json.loads(r["data"] or "{}")
                except ValueError:
                    r["data"] = {}
                g = self.game_of(r)
                if g:
                    r["game"] = g
                    self._hist.append(r)
        return self._hist

    @staticmethod
    def game_of(r: dict) -> str | None:
        from .running import TITLES
        k = r["kind"]
        if k == "cards":
            return CARD_TITLES.get(str(r["data"].get("game") or ""))
        return k if k in TITLES or k in GAME_TITLES else None

    @staticmethod
    def game_title(kind: str):
        from .running import TITLES
        return (TITLES.get(kind) or GAME_TITLES.get(kind) or kind,)

    def games_played(self, since: str | None = None, until: str | None = None) -> dict:
        """Games that ended (with their history entries): {game key: game kind} – one per table, not per player."""
        out = {}
        for r in self.history():
            if (since and r["at"] < since) or (until and r["at"] >= until):
                continue
            key = (r["game"], r["data"].get("game") if r["kind"] == "quiz" else r["at"][:19])
            out[key] = r["game"]
        return out

    @staticmethod
    def won(d: dict) -> bool:
        return d.get("won") is True or d.get("place") == 1 or d.get("result") == "win"

    def person(self, pid) -> str | int | None:
        return GUEST if pid in self.guests else pid if pid in self.name else None

    def ledger_count(self, where: str, *args, distinct: str = "id") -> dict:
        return {r["profile_id"]: r["n"] for r in self.db.q(
            f"SELECT profile_id, COUNT(DISTINCT {distinct}) AS n FROM ledger WHERE {where} GROUP BY profile_id", *args)}

    # ================================================================ generators
    # chores (own chore plan and Family Planer chores: ledger event chore_done)
    def chores(self) -> list[dict]:
        out = []
        texts = {"today": (_t("Who of the kids has done the most chores today?"), "week"),
                 "week": (_t("Who of the kids has done the most chores this week?"), "week"),
                 "last_week": (_t("Who of the kids did the most chores last week?"), "week")}
        for key, (q, scope) in texts.items():
            a, b = self.span(key)
            counts = self.ledger_count("event='chore_done' AND amount>0 AND at>=? AND at<?", a, b, distinct="ref")
            out += self.who("chores_" + key, scope, (q,), counts, self.kids)
        a, b = self.span("week")
        week = sum(self.ledger_count("event='chore_done' AND amount>0 AND at>=? AND at<?", a, b, distinct="ref").values())
        if week:
            out += self.number("chores_week_total", "week", (_t("How many chores has the family done this week?"),), week)
        allc = self.ledger_count("event='chore_done' AND amount>0", distinct="ref")
        if sum(allc.values()) >= 5:
            out += self.number("chores_total", "all", (_t("How many chores have been done in Family Quest so far?"),),
                               sum(allc.values()), estimate=True, unit=(_t("chores"),))
        out += self.who("chores_champion", "all", (_t("Who has done the most chores of all time?"),), allc, self.kids)
        return out

    # XP, levels, streaks, coins (only with the family view «Everything»)
    def xp(self) -> list[dict]:
        if not self.open:
            return []
        out = []
        rw = self.fq.rewards
        total = {p["id"]: rw.total_xp(p["id"]) for p in self.people}
        out += self.who("xp_most", "all", (_t("Who has the most XP?"),), total)
        if sum(total.values()) >= 20:
            out += self.number("xp_total", "all", (_t("How many XP does the whole family have together?"),), sum(total.values()),
                               estimate=True, unit="XP")
        a, b = self.span("week")
        week = {r["profile_id"]: r["s"] for r in self.db.q(
            f"SELECT profile_id, SUM(amount) s FROM ledger WHERE account='xp' AND amount>0 AND at>=? AND at<? "
            f"AND COALESCE(event,'') NOT IN ({','.join('?' * len(SPEND_EVENTS))}) GROUP BY profile_id", a, b, *SPEND_EVENTS)}
        out += self.who("xp_week", "week", (_t("Who has earned the most XP this week?"),), week)
        levels = [(p, rw.level(p["id"])["level"]) for p in self.kids if total.get(p["id"])]
        if levels:
            p, lvl = random.choice(levels)
            out.append({"gen": "level_of", "scope": "all", "q": (_t("Which level has {0} reached?"), p["name"]),
                        "right": str(lvl), "wrong": [str(x) for x in near_numbers(lvl) if x >= 1][:3] or [str(lvl + 1)]})
        out += self.who("streak", "week", (_t("Who has the longest streak of daily goals right now?"),),
                        {p["id"]: rw.streak(p["id"]) for p in self.kids}, self.kids)
        earned = {r["profile_id"]: r["s"] for r in self.db.q(
            f"SELECT profile_id, SUM(amount) s FROM ledger WHERE account='coins' AND amount>0 AND at>=? AND at<? "
            f"AND COALESCE(event,'') NOT IN ({','.join('?' * len(NOT_EARNED))}) AND COALESCE(ref,'') NOT LIKE 'fp:init%' "
            f"GROUP BY profile_id", a, b, *NOT_EARNED)}
        out += self.who("coins_week", "week", (_t("Who has earned the most coins this week?"),), earned)
        out += self.who("coins_rich", "all", (_t("Who has the most coins right now?"),),
                        {p["id"]: rw.balance(p["id"], "coins") for p in self.people})
        badges = {r["profile_id"]: r["n"] for r in self.db.q("SELECT profile_id, COUNT(*) n FROM badge GROUP BY profile_id")}
        out += self.who("badges_most", "all", (_t("Who has collected the most badges?"),), badges)
        nb = sum(v for k, v in badges.items() if k in self.name)
        if nb:
            out += self.number("badges_total", "all", (_t("How many badges has the family collected in all?"),), nb)
        return out

    # learning (daily table: seconds and lessons; attempts)
    def learning(self) -> list[dict]:
        if not self.open:
            return []
        out = []
        a, b = self.span("week")
        rows = self.db.q("SELECT profile_id, SUM(seconds) s, SUM(lessons) l FROM daily WHERE day>=? AND day<? GROUP BY profile_id", a, b)
        out += self.who("learn_time_week", "week", (_t("Who has learned the longest this week?"),), {r["profile_id"]: r["s"] for r in rows})
        out += self.who("lessons_week", "week", (_t("Who has finished the most lessons this week?"),), {r["profile_id"]: r["l"] for r in rows})
        minutes = round(sum(r["s"] or 0 for r in rows if r["profile_id"] in self.name) / 60)
        if minutes >= 5:
            out += self.number("learn_minutes_week", "week", (_t("How many minutes has the family learned this week?"),), minutes,
                               estimate=True, unit=(_t("minutes"),))
        lessons = int(self.db.val("SELECT SUM(lessons) FROM daily", default=0) or 0)
        if lessons >= 3:
            out += self.number("lessons_total", "all", (_t("How many lessons have been finished in Family Quest so far?"),), lessons,
                               estimate=lessons > 30, unit=(_t("lessons"),))
        right = {r["profile_id"]: r["n"] for r in self.db.q(
            "SELECT profile_id, COUNT(*) n FROM attempt WHERE correct=1 AND at>=? AND at<? GROUP BY profile_id", a, b)}
        out += self.who("right_answers_week", "week", (_t("Who has given the most right answers while learning this week?"),), right)
        return out

    # games (history: one entry per player and game)
    def games(self) -> list[dict]:
        out = []
        h = self.history()
        if not h:
            return out
        for key, q in (("week", _t("How many games have been played this week?")),
                       ("last_week", _t("How many games were played last week?")),
                       ("7days", _t("How many games have been played in the last 7 days?"))):
            a, b = self.span(key)
            n = len(self.games_played(a, b))
            if n:
                out += self.number("games_" + key, "week", (q,), n)
        alls = self.games_played()
        if len(alls) >= 5:
            out += self.number("games_total", "all", (_t("How many games have been played in Family Quest so far?"),), len(alls),
                               estimate=True, unit=(_t("games"),))
        for gen, scope, games, q in (("popular_all", "all", alls, _t("Which game has been played the most?")),
                                     ("popular_week", "week", self.games_played(*self.span("week")), _t("Which game has been played the most this week?"))):
            per = {}
            for kind in games.values():
                per[kind] = per.get(kind, 0) + 1
            ranked = sorted(per.items(), key=lambda x: -x[1])
            if len(ranked) >= 2 and ranked[0][1] > ranked[1][1]:
                from .running import TITLES
                others = [k for k, _ in ranked[1:]] + random.sample(list(TITLES), len(TITLES))
                out += self.pick(gen, scope, (q,), self.game_title(ranked[0][0]), [self.game_title(k) for k in others if k != ranked[0][0]])
        wins_all, wins_week, played = {}, {}, {}
        a, b = self.span("week")
        for r in h:
            who = self.person(r["profile_id"])
            if who is None:
                continue
            played[who] = played.get(who, 0) + 1
            if self.won(r["data"]) and int(r["data"].get("players") or r["data"].get("of") or 2) >= 2:
                wins_all[who] = wins_all.get(who, 0) + 1
                if a <= r["at"] < b:
                    wins_week[who] = wins_week.get(who, 0) + 1
        out += self.who("wins_all", "all", (_t("Who has won the most games in Family Quest?"),), wins_all, guests=True)
        out += self.who("wins_week", "week", (_t("Who has won the most games this week?"),), wins_week, guests=True)
        out += self.who("played_most", "all", (_t("Who has played the most games?"),), played, guests=True)
        quiz = {}
        for r in h:
            if r["game"] == "quiz" and r["data"].get("won") and self.person(r["profile_id"]) is not None:
                quiz[self.person(r["profile_id"])] = quiz.get(self.person(r["profile_id"]), 0) + 1
        out += self.who("quiz_wins", "all", (_t("Who has won the most family quizzes?"),), quiz, guests=True)
        chess = {}
        for r in h:
            if r["game"] == "schach" and r["data"].get("result") == "win" and r["profile_id"] in self.name:
                chess[r["profile_id"]] = chess.get(r["profile_id"], 0) + 1
        out += self.who("chess_wins", "all", (_t("Who has won the most chess games?"),), chess)
        last = max((r for r in h if self.won(r["data"]) and int(r["data"].get("players") or r["data"].get("of") or 2) >= 2
                    and r["at"] >= self.span("7days")[0]), key=lambda r: r["at"], default=None)
        if last and self.person(last["profile_id"]) is not None:
            same = {self.person(r["profile_id"]) for r in h if r["at"][:19] == last["at"][:19] and r["game"] == last["game"] and self.won(r["data"])}
            if len(same) == 1:                          # one winner (not a team)
                out += self.who("last_winner", "week", (_t("Who won the last family game ({0})?"), self.game_title(last["game"])),
                                {self.person(last["profile_id"]): 1}, guests=True)
        dice = {}
        for r in h:
            if r["game"] == "wuerfel" and self.person(r["profile_id"]) is not None:
                pts = int(r["data"].get("points") or 0)
                k = self.person(r["profile_id"])
                dice[k] = max(dice.get(k, 0), pts)
        if dice and max(dice.values()) > 0:
            title = self.game_title("wuerfel")
            out += self.number("dice_record", "all", (_t("What is the highest score ever reached in {0}?"), title), max(dice.values()))
            out += self.who("dice_record_who", "all", (_t("Who holds the record in {0}?"), title), dice, guests=True)
        return out

    # personal bests of the arcade-like games (settings <game>_best, family only)
    def records(self) -> list[dict]:
        out = []
        for key, kind, unit in BESTS:
            best = {int(k): int(v or 0) for k, v in (self.db.get_setting(key) or {}).items() if str(k).isdigit() and int(k) in self.name}
            if not best or not max(best.values()):
                continue
            title = self.game_title(kind)
            top = max(best.values())
            q = [{"gen": "record_" + kind, "scope": "all", "q": (_t("What is the family record in {0}?"), title),
                  "right": f"{top}{unit}", "wrong": [f"{x}{unit}" for x in near_numbers(top) if not unit or x <= 100]}]
            if len(q[0]["wrong"]) >= 1:
                out += q
            out += self.who("record_who_" + kind, "all", (_t("Who holds the record in {0}?"), title), best)
        spins = int(self.db.val("SELECT COUNT(*) FROM ledger WHERE event='slots_bet'", default=0) or 0)
        if spins >= 3:
            out += self.number("slots_spins", "all", (_t("How often has the slot machine been played?"),), spins)
        wins = {r["profile_id"]: r["m"] for r in self.db.q("SELECT profile_id, MAX(amount) m FROM ledger WHERE event='slots_win' GROUP BY profile_id")}
        out += self.who("slots_jackpot", "all", (_t("Who has won the biggest prize at the slot machine?"),), wins)
        return out

    # shop: rewards, avatar items, pet shop, pranks, the slot machine
    def shop(self) -> list[dict]:
        out = []
        ev = ",".join("?" * len(SHOP_EVENTS))
        bought = {r["profile_id"]: r["n"] for r in self.db.q(
            f"SELECT profile_id, COUNT(*) n FROM ledger WHERE account='coins' AND amount<0 AND event IN ({ev}) GROUP BY profile_id", *SHOP_EVENTS)}
        for r in self.db.q("SELECT profile_id, COUNT(*) n FROM ledger WHERE account='coins' AND event='refund' AND amount>0 GROUP BY profile_id"):
            bought[r["profile_id"]] = bought.get(r["profile_id"], 0) - r["n"]
        family = {k: v for k, v in bought.items() if k in self.name and v > 0}
        n = sum(family.values())
        if n:
            out += self.number("shop_items", "all", (_t("How many things have been bought in the shop so far?"),), n, estimate=n > 12,
                               unit=(_t("items"),))
            spent = -float(self.db.val(f"SELECT SUM(amount) FROM ledger WHERE account='coins' AND amount<0 AND event IN ({ev})", *SHOP_EVENTS, default=0) or 0)
            spent -= float(self.db.val("SELECT SUM(amount) FROM ledger WHERE account='coins' AND event='refund' AND amount>0", default=0) or 0)
            if spent > 0:
                out += self.number("shop_coins", "all", (_t("How many coins have been spent in the shop so far?"),), spent,
                                   estimate=True, unit=(_t("coins"),))
        out += self.who("shopping_queen", "all", (_t("Who is the shopping queen or king of the family?"),), family)
        a, b = self.span("week")
        week = int(self.db.val(f"SELECT COUNT(*) FROM ledger WHERE account='coins' AND amount<0 AND event IN ({ev}) AND at>=? AND at<?",
                               *SHOP_EVENTS, a, b, default=0) or 0)
        if week:
            out += self.number("shop_week", "week", (_t("How many things have been bought in the shop this week?"),), week)
        rows = self.db.q("""SELECT r.name, COUNT(*) n FROM redemption d JOIN reward r ON r.id=d.reward_id
                            WHERE d.status NOT IN ('rejected','failed') GROUP BY d.reward_id ORDER BY n DESC""")
        if rows and (len(rows) == 1 or rows[0]["n"] > rows[1]["n"]):
            others = [x["name"] for x in rows[1:]] + [x["name"] for x in self.db.q("SELECT name FROM reward WHERE active=1")]
            out += self.pick("reward_top", "all", (_t("Which reward has been chosen most often in the shop?"),), (rows[0]["name"],),
                             [(x,) for x in others if x != rows[0]["name"]])
        from .rewards import avatar as av
        items = {}
        for r in self.db.q("SELECT profile_id, item FROM unlock"):
            if r["item"] in av.ITEMS and av.ITEMS[r["item"]][1] != "pet":
                items[r["profile_id"]] = items.get(r["profile_id"], 0) + 1
        out += self.who("avatar_items", "all", (_t("Who has unlocked the most avatar items?"),), items)
        pranks = {r["from_id"]: r["n"] for r in self.db.q("SELECT from_id, COUNT(*) n FROM prank WHERE from_id IS NOT NULL GROUP BY from_id")}
        out += self.who("pranks_thrown", "all", (_t("Who has played the most pranks on the others?"),), pranks)
        hit = {r["to_id"]: r["n"] for r in self.db.q("SELECT to_id, COUNT(*) n FROM prank GROUP BY to_id")}
        out += self.who("pranks_hit", "all", (_t("Who has been pranked the most?"),), hit)
        return out

    # pets
    def pets(self) -> list[dict]:
        out = []
        from .pets import KINDS
        from .rewards import avatar as av
        rows = [r for r in self.db.q("SELECT * FROM pet") if r["profile_id"] in self.name and r["kind"] in KINDS]
        alive = [r for r in rows if not r["dead_at"]]
        if not rows:
            return out
        if alive:
            out += self.number("pets_total", "all", (_t("How many pets live in the family right now?"),), len(alive))
        per = {}
        for r in alive:
            per[r["profile_id"]] = per.get(r["profile_id"], 0) + 1
        out += self.who("pets_most", "all", (_t("Who has the most pets?"),), per)
        dead = {}
        for r in rows:
            if r["dead_at"]:
                dead[r["profile_id"]] = dead.get(r["profile_id"], 0) + 1
        out += self.who("pets_lost", "all", (_t("Who has lost the most pets?"),), dead)
        if len(alive) >= 2:
            old = sorted(alive, key=lambda r: r["born_at"])
            if old[0]["born_at"][:10] < old[1]["born_at"][:10]:          # a clear day ahead
                label = lambda r: f"{KINDS[r['kind']][0]} {r['name']} ({self.name[r['profile_id']]})"    # noqa: E731
                out += self.pick("pet_oldest", "all", (_t("Which pet is the oldest?"),), label(old[0]), [label(r) for r in old[1:]])
        kinds = {}
        for r in alive:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        ranked = sorted(kinds.items(), key=lambda x: -x[1])
        if ranked and ranked[0][1] >= 2 and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
            name = lambda k: (av.ITEMS[k][0],) if k in av.ITEMS else k        # noqa: E731
            out += self.pick("pet_kind", "all", (_t("Which kind of pet is the most common in the family?"),), name(ranked[0][0]),
                             [name(k) for k in random.sample(list(KINDS), len(KINDS)) if k != ranked[0][0]])
        babies = 0
        for r in rows:
            if any(o["id"] != r["id"] and o["kind"] == r["kind"] and o["profile_id"] == r["profile_id"] and o["bred_at"]
                   and o["bred_at"][:16] <= r["born_at"][:16] <= (_add_minute(o["bred_at"])) for o in rows):
                babies += 1
        if babies:
            out += self.number("pet_babies", "all", (_t("How many pet babies have been born in the family?"),), babies)
        mined = sum(int(r["mined_total"] or 0) for r in rows if r["kind"] == "hamster")
        if mined >= 5:
            out += self.number("hamster", "all", (_t("How many coins have the hamsters mined in their wheel?"),), mined,
                               estimate=True, unit=(_t("coins"),))
        # who looks after their pets best: the average of the care bars of the living pets at home (hotel and paused left out)
        care = {}
        for pid in {r["profile_id"] for r in alive}:
            try:
                views = [v for v in self.fq.pets.list(pid) if not v.get("paused")]
            except Exception:  # noqa: BLE001
                views = []
            if views:
                care[pid] = round(sum((v["hunger"] + v["mood"] + v["clean"]) / 3 for v in views) / len(views))
        ranked = sorted(care.items(), key=lambda x: -x[1])
        if len(ranked) >= 2 and ranked[0][1] - ranked[1][1] >= 5:
            out += self.who("pet_care", "week", (_t("Whose pets are the best cared for right now (fed, happy and clean)?"),), care)
        return out

    # the rest of the family life: boards, polls, council, quizzes, Wichteln, FamilyTime, birthdays, guests, cards
    def family(self) -> list[dict]:
        out = []
        notes = int(self.db.val("""SELECT COUNT(*) FROM board_item i JOIN board b ON b.id=i.board_id
                                   WHERE i.kind='note' AND i.deleted=0 AND b.archived=0""", default=0) or 0)
        if notes:
            out += self.number("board_notes", "all", (_t("How many sticky notes hang on our bulletin boards?"),), notes)
        polls = int(self.db.val("SELECT COUNT(*) FROM poll", default=0) or 0)
        if polls:
            out += self.number("polls", "all", (_t("How many polls has the family made?"),), polls)
        topics = int(self.db.val("SELECT COUNT(*) FROM council_topic", default=0) or 0)
        if topics:
            out += self.number("council", "all", (_t("How many topics has the family council discussed?"),), topics)
        quizzes = int(self.db.val("SELECT COUNT(*) FROM quiz WHERE archived=0", default=0) or 0)
        if quizzes:
            out += self.number("quizzes", "all", (_t("How many family quizzes do we have?"),), quizzes)
        wichtel = int(self.db.val("SELECT COUNT(*) FROM wichtel", default=0) or 0)
        if wichtel:
            out += self.number("wichteln", "all", (_t("How many times has the family drawn lots for Wichteln?"),), wichtel)
        ft = int(self.db.val("SELECT COUNT(*) FROM family_event WHERE kind='familytime'", default=0) or 0)
        if ft:
            out += self.number("familytime", "all", (_t("How many FamilyTimes are in the family calendar?"),), ft)
        last = self.db.q1("""SELECT g.title, g.choice FROM ft_game g JOIN family_event e ON e.id=g.event_id
                             WHERE g.status='set' AND g.title IS NOT NULL AND e.start <= ? ORDER BY e.start DESC LIMIT 1""",
                          datetime.now().isoformat(timespec="minutes"))
        if last:
            from .running import TITLES
            right = (last["title"],)
            out += self.pick("familytime_game", "all", (_t("Which game was set for the last FamilyTime?"),), right,
                             [self.game_title(k) for k in random.sample(list(TITLES), len(TITLES)) if (TITLES[k],) != right])
        out += self.birthdays()
        if len(self.people) >= 2:
            ranked = sorted(self.people, key=lambda p: p["created_at"] or "", reverse=True)
            if (ranked[0]["created_at"] or "")[:10] > (ranked[1]["created_at"] or "")[:10]:
                out += self.who("newest", "all", (_t("Who joined Family Quest last?"),), {ranked[0]["id"]: 1})
        guests = int(self.db.val("SELECT COUNT(*) FROM profile WHERE role='guest'", default=0) or 0)
        if guests:
            out += self.number("guests", "all", (_t("How many guests have joined our games so far?"),), guests)
        cards = {r["profile_id"]: r["n"] for r in self.db.q(
            "SELECT d.profile_id, COUNT(*) n FROM deck_card c JOIN deck d ON d.id=c.deck_id WHERE c.src='' GROUP BY d.profile_id")}
        out += self.who("flash_cards", "all", (_t("Who has written the most own flash cards?"),), cards)
        played = int(self.db.val("""SELECT COUNT(*) FROM quiz_game g WHERE g.status='done'
                                    AND EXISTS(SELECT 1 FROM quiz_answer a WHERE a.game_id=g.id)""", default=0) or 0)
        if played:
            out += self.number("quiz_games", "all", (_t("How many family quizzes have been played so far?"),), played)
        return out

    def birthdays(self) -> list[dict]:
        rows = self.db.q("SELECT title, start FROM family_event WHERE kind='birthday'")
        t = today()
        nxt = {}
        for r in rows:
            try:
                d = date.fromisoformat(r["start"][:10])
            except ValueError:
                continue
            try:
                when = d.replace(year=t.year)
            except ValueError:                          # 29 February
                when = date(t.year, 3, 1)
            if when < t:
                when = when.replace(year=t.year + 1) if not (when.month == 2 and when.day == 29) else date(t.year + 1, 3, 1)
            title = r["title"].strip()
            if title and (title not in nxt or when < nxt[title]):
                nxt[title] = when
        ranked = sorted(nxt.items(), key=lambda x: x[1])
        if len(ranked) < 2 or ranked[0][1] == ranked[1][1]:
            return []
        return self.pick("birthday_next", "all", (_t("Which birthday in the family calendar comes next?"),), ranked[0][0],
                         [x[0] for x in ranked[1:]])

    GENERATORS = ("chores", "xp", "learning", "games", "records", "shop", "pets", "family")

    def candidates(self) -> list[dict]:
        out = []
        for name in self.GENERATORS:
            out += getattr(self, name)()
        return out


def _add_minute(iso: str) -> str:
    try:
        return (datetime.fromisoformat(iso[:19]) + timedelta(minutes=1)).isoformat()[:16]
    except ValueError:
        return iso[:16]


# kinds that often have the same answer: at most one of them per game
GROUPS = {"games_week": "games_recent", "games_7days": "games_recent", "popular_week": "popular", "popular_all": "popular",
          "chores_today": "chores_now", "chores_week": "chores_now", "wins_week": "wins", "wins_all": "wins"}


def choose(cands: list[dict], count: int, focus: str = "mixed") -> list[dict]:
    """A random selection: at most one question per kind first (variety), the focus first (this week / all time)."""
    focus = focus if focus in FOCUS else "mixed"
    by_gen: dict[str, list[dict]] = {}
    for c in cands:
        by_gen.setdefault(GROUPS.get(c["gen"], c["gen"]), []).append(c)
    gens = list(by_gen)
    random.shuffle(gens)
    if focus != "mixed":
        gens.sort(key=lambda g: by_gen[g][0]["scope"] != focus)          # stable: the focus first, random within
    picked = [random.choice(by_gen[g]) for g in gens][:count]
    random.shuffle(picked)
    return picked


def to_quiz(item: dict, base: str, dicts: dict[str, dict]) -> dict:
    """One generated question → the quiz format with its texts in every language."""
    more = [k for k in dicts if k != base]
    if "answer" in item:
        q = {"kind": "estimate", "q": tr(item["q"], dicts[base]), "answer": item["answer"], "min": item["min"], "max": item["max"],
             "step": 1, "unit": tr(item.get("unit") or "", dicts[base]), "t": 30}
        q["tr"] = {k: {"q": tr(item["q"], dicts[k]), **({"unit": tr(item["unit"], dicts[k])} if item.get("unit") else {})} for k in more}
        return q
    answers = [item["right"], *item["wrong"][:3]]
    q = {"q": tr(item["q"], dicts[base]), "a": [tr(a, dicts[base]) for a in answers], "c": 0, "t": 20,
         "tr": {k: {"q": tr(item["q"], dicts[k]), "a": [tr(a, dicts[k]) for a in answers]} for k in more}}
    return shuffle_answers(q)


def enabled(db) -> bool:
    v = db.get_setting(SETTING)
    return v is None or bool(v)


def info(fq) -> dict:
    return {"enabled": enabled(fq.db), "title": TITLE, "counts": list(COUNTS), "focus": list(FOCUS)}


def build(fq, count: int = 10, focus: str = "mixed", lang: str | None = None) -> tuple[list[dict], dict]:
    base, dicts = dictionaries(fq, lang)
    picked = choose(Facts(fq).candidates(), max(1, min(int(count or 10), 30)), focus)
    if len(picked) < MIN_QUESTIONS:
        raise CommunityError("Not enough to ask yet – play, learn and do chores first, then the facts quiz has questions")
    more = [k for k in dicts if k != base]
    questions = fq.community.clean_questions([to_quiz(x, base, dicts) for x in picked], more)
    langs = {"base": base, "more": more, "title": {k: tr((TITLE,), dicts[k]) for k in more}}
    return questions, langs


def start(fq, host: int, count: int = 10, focus: str = "mixed", lang: str | None = None) -> int:
    """Start the facts quiz: new questions from the data now; the game is a family quiz like any other."""
    if not enabled(fq.db):
        raise CommunityError("The quiz «Family Quest Facts» is switched off")
    c = fq.community
    with c.lock:
        if c._game():
            raise CommunityError("A family quiz is already running")
        questions, langs = build(fq, count, focus, lang)
        # the game needs a quiz row (title and languages): one hidden row, not in the list of quizzes
        row = fq.db.q1("SELECT id FROM quiz WHERE archived=1 AND created_by IS NULL AND title=? ORDER BY id LIMIT 1", TITLE)
        lj = json.dumps(langs, ensure_ascii=False)
        if row:
            qid = row["id"]
            fq.db.x("UPDATE quiz SET langs=? WHERE id=?", lj, qid)
        else:
            qid = fq.db.x("INSERT INTO quiz(title, questions, created_by, archived, langs) VALUES(?, '[]', NULL, 1, ?)", TITLE, lj)
        return fq.db.x("INSERT INTO quiz_game(quiz_id, host_id, players, questions) VALUES(?,?,?,?)",
                       qid, host, json.dumps([host]), json.dumps(questions, ensure_ascii=False))
