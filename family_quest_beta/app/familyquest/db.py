"""SQLite storage: one file in /data, versioned migrations, tiny query helpers.

One connection shared by all request threads, guarded by a re-entrant lock;
`with db.tx():` groups several writes into one transaction.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .i18n import _t

MIGRATIONS: list[str] = [
    # 1 – base schema
    """
    CREATE TABLE profile(
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'kid',          -- kid | parent
        color TEXT NOT NULL DEFAULT '#4f8cff',
        avatar TEXT NOT NULL DEFAULT '{}',
        pin_hash TEXT,
        settings TEXT NOT NULL DEFAULT '{}',
        planer_person_id TEXT,
        archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE setting(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE pack(
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL DEFAULT 'pack',          -- pack | bundle
        title TEXT NOT NULL,
        subject TEXT,
        level TEXT,
        version TEXT,
        source TEXT NOT NULL DEFAULT 'upload',      -- builtin | share | upload | import | ai
        status TEXT NOT NULL DEFAULT 'active',      -- active | draft | disabled
        hash TEXT,
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE pack_profile(pack_id TEXT NOT NULL, profile_id INTEGER NOT NULL, PRIMARY KEY(pack_id, profile_id));
    CREATE TABLE item_state(
        profile_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        pack_id TEXT NOT NULL,
        unit_id TEXT NOT NULL,
        box INTEGER NOT NULL DEFAULT 0,
        due TEXT,
        correct INTEGER NOT NULL DEFAULT 0,
        wrong INTEGER NOT NULL DEFAULT 0,
        last_ok INTEGER,
        last_seen TEXT,
        PRIMARY KEY(profile_id, item_key)
    );
    CREATE INDEX item_state_unit ON item_state(profile_id, pack_id, unit_id);
    CREATE TABLE attempt(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        pack_id TEXT, unit_id TEXT, subject TEXT,
        kind TEXT,
        correct INTEGER NOT NULL,
        ms INTEGER,
        at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX attempt_profile ON attempt(profile_id, at);
    CREATE TABLE session(
        id TEXT PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        mode TEXT NOT NULL,
        data TEXT NOT NULL,
        finished INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE account(
        key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        unit TEXT NOT NULL DEFAULT '',
        icon TEXT NOT NULL DEFAULT '',
        spendable INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1,
        sort INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE ledger(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        account TEXT NOT NULL,
        amount REAL NOT NULL,
        event TEXT,
        reason TEXT,
        ref TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX ledger_profile ON ledger(profile_id, account, at);
    CREATE TABLE rule(
        id INTEGER PRIMARY KEY,
        event TEXT NOT NULL,
        account TEXT NOT NULL,
        amount REAL NOT NULL,
        daily_limit REAL,
        condition TEXT NOT NULL DEFAULT '{}',
        label TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE reward(
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'voucher',      -- voucher | internet_minutes | planer_points | ha_script | avatar_item
        account TEXT NOT NULL DEFAULT 'coins',
        cost REAL NOT NULL,
        approval INTEGER NOT NULL DEFAULT 1,
        weekly_limit INTEGER,
        icon TEXT NOT NULL DEFAULT '🎁',
        config TEXT NOT NULL DEFAULT '{}',
        active INTEGER NOT NULL DEFAULT 1,
        sort INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE redemption(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        reward_id INTEGER NOT NULL,
        cost REAL NOT NULL,
        account TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',    -- pending | approved | rejected | failed
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        decided_at TEXT
    );
    CREATE TABLE badge(profile_id INTEGER NOT NULL, badge TEXT NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now','localtime')), PRIMARY KEY(profile_id, badge));
    CREATE TABLE daily(
        profile_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        xp REAL NOT NULL DEFAULT 0,
        seconds INTEGER NOT NULL DEFAULT 0,
        lessons INTEGER NOT NULL DEFAULT 0,
        goal_met INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(profile_id, day)
    );
    CREATE TABLE goal(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER,                         -- NULL = family goal
        kind TEXT NOT NULL,                         -- unit | xp_week | family
        title TEXT NOT NULL,
        target REAL NOT NULL DEFAULT 0,
        account TEXT,
        pack_id TEXT, unit_id TEXT,
        week TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE unlock(profile_id INTEGER NOT NULL, item TEXT NOT NULL, PRIMARY KEY(profile_id, item));
    CREATE TABLE chore_seen(profile_id INTEGER NOT NULL, uid TEXT NOT NULL, day TEXT NOT NULL, PRIMARY KEY(profile_id, uid, day));
    """,
    # 2 – own chore plan (Ämtliplan)
    """
    CREATE TABLE chore(
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT NOT NULL DEFAULT '🧹',
        points REAL NOT NULL DEFAULT 10,
        account TEXT NOT NULL DEFAULT 'coins',
        frequency TEXT NOT NULL DEFAULT 'daily',     -- daily | weekdays | weekly | once
        weekdays TEXT NOT NULL DEFAULT '[]',         -- [0..6], Monday = 0 (frequency weekdays)
        date TEXT,                                   -- frequency once
        assign TEXT NOT NULL DEFAULT 'fixed',        -- fixed (everyone listed) | rotate (one after the other)
        rotate_every TEXT NOT NULL DEFAULT 'week',   -- day | week
        profiles TEXT NOT NULL DEFAULT '[]',
        kind TEXT NOT NULL DEFAULT 'bonus',          -- duty | bonus
        confirm INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1,
        sort INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE chore_task(
        id INTEGER PRIMARY KEY,
        chore_id INTEGER NOT NULL,
        profile_id INTEGER NOT NULL,
        period TEXT NOT NULL,                        -- day, or Monday of the week for weekly chores
        status TEXT NOT NULL DEFAULT 'open',         -- open | pending | done
        redo INTEGER NOT NULL DEFAULT 0,
        done_at TEXT, confirmed_at TEXT,
        UNIQUE(chore_id, profile_id, period)
    );
    CREATE INDEX chore_task_profile ON chore_task(profile_id, period);
    INSERT INTO rule(event, account, amount, label) VALUES('chores_week_all', 'coins', 20, 'All chores of the week done');
    """,
    # 3 – internet time managed by the app
    """
    CREATE TABLE internet_session(
        profile_id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL,
        deducted INTEGER NOT NULL DEFAULT 0,
        running INTEGER NOT NULL DEFAULT 0
    );
    """,
    # 4 – key/value JSON documents (Family Planer data, like the Home Assistant store)
    """
    CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
    # 5 – log of logins (failed ones are shown in the parent area with IP and device name)
    """
    CREATE TABLE login_log(
        id INTEGER PRIMARY KEY,
        at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        kind TEXT NOT NULL,                 -- profile | parent
        profile_id INTEGER,                 -- profile tried (parent area: the parent that logged in)
        ok INTEGER NOT NULL,
        ip TEXT,
        device TEXT,                        -- name of the device in Home Assistant (UniFi device tracker)
        mac TEXT                            -- MAC address of that device (UniFi device tracker)
    );
    CREATE INDEX login_log_ip ON login_log(ip, ok);
    CREATE INDEX login_log_at ON login_log(at);
    """,
    # 6 – community: family quiz, family council, personal history
    """
    CREATE TABLE quiz(
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        questions TEXT NOT NULL DEFAULT '[]',   -- [{"q", "a": [2–4 answers], "c": index of the right one, "t": seconds}]
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        archived INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE quiz_game(
        id INTEGER PRIMARY KEY,
        quiz_id INTEGER NOT NULL,
        host_id INTEGER,
        status TEXT NOT NULL DEFAULT 'lobby',   -- lobby | question | reveal | done
        idx INTEGER NOT NULL DEFAULT -1,        -- current question
        q_started REAL,                         -- unix time the current question started
        players TEXT NOT NULL DEFAULT '[]',
        questions TEXT NOT NULL DEFAULT '[]',   -- the questions of this game (chosen and shuffled at the start)
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );
    CREATE TABLE quiz_answer(
        game_id INTEGER NOT NULL, idx INTEGER NOT NULL, profile_id INTEGER NOT NULL,
        choice INTEGER NOT NULL, ms INTEGER NOT NULL, points INTEGER NOT NULL,
        PRIMARY KEY(game_id, idx, profile_id)
    );
    CREATE TABLE council_topic(
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        created_by INTEGER,
        status TEXT NOT NULL DEFAULT 'collect',  -- collect | vote | closed
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        closed_at TEXT,
        result TEXT                              -- JSON: winners and counts
    );
    CREATE TABLE council_proposal(
        id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL, profile_id INTEGER, text TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE council_vote(
        topic_id INTEGER NOT NULL, profile_id INTEGER NOT NULL, proposal_id INTEGER NOT NULL,
        PRIMARY KEY(topic_id, profile_id)
    );
    CREATE TABLE history(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        kind TEXT NOT NULL,                      -- quiz | council
        data TEXT NOT NULL DEFAULT '{}',         -- shown by the app in the viewer's language
        at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX history_profile ON history(profile_id, at);
    """,
    # 7 – family bingo (75 balls, 5 × 5 cards)
    """
    CREATE TABLE bingo_game(
        id INTEGER PRIMARY KEY,
        host_id INTEGER,
        status TEXT NOT NULL DEFAULT 'lobby',   -- lobby | running | done
        draw_order TEXT NOT NULL,               -- the 75 balls in the order they come
        interval REAL NOT NULL DEFAULT 8,       -- seconds per ball (spin + show)
        rules TEXT NOT NULL DEFAULT '{}',       -- set by who starts: {"interval": 8, "win": "line" | "two_lines" | "full"}
        started REAL,                           -- unix time of the first ball
        paused_at REAL,                         -- set while paused
        paused_total REAL NOT NULL DEFAULT 0,
        winner_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );
    CREATE TABLE bingo_card(
        game_id INTEGER NOT NULL, profile_id INTEGER NOT NULL,
        numbers TEXT NOT NULL,                  -- 25 numbers row by row, 0 = free field in the middle
        marks TEXT NOT NULL DEFAULT '[12]',     -- marked cells (indices 0–24), the free field is always marked
        blocked_until REAL NOT NULL DEFAULT 0,  -- after a false «Bingo!»
        PRIMARY KEY(game_id, profile_id)
    );
    """,
    # 8 – behaviour weather: what parents set per child (resets daily, the log feeds the 30-day graph)
    """
    CREATE TABLE weather_log(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        level TEXT NOT NULL,                     -- key of the weather level
        icon TEXT NOT NULL,
        rank INTEGER NOT NULL,                   -- 0 = best weather
        points REAL NOT NULL DEFAULT 0,
        by_id INTEGER,
        at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX weather_profile ON weather_log(profile_id, at);
    """,
    # 9 – family council: which majority a vote needs (relative | absolute | unanimous), and whether the winner
    #     needs at least one parent and one child (like a «majority of the cantons» – both sides of the family)
    """
    ALTER TABLE council_topic ADD COLUMN majority TEXT NOT NULL DEFAULT 'relative';
    ALTER TABLE council_topic ADD COLUMN both_sides INTEGER NOT NULL DEFAULT 0;
    """,
    # 10 – family calendar (own events, holiday templates, CSV / iCal imports)
    """
    CREATE TABLE family_event(
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        start TEXT NOT NULL,                     -- 2026-07-04 (all day) or 2026-11-20T18:00
        end TEXT NOT NULL,                       -- all day: the last day (included)
        all_day INTEGER NOT NULL DEFAULT 1,
        icon TEXT NOT NULL DEFAULT '',
        color TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'event',      -- event | school | public | birthday …
        note TEXT NOT NULL DEFAULT '',
        uid TEXT NOT NULL DEFAULT '',            -- iCal UID / template id: duplicate check
        source TEXT NOT NULL DEFAULT 'manual',   -- manual | holidays:CH-TG:2026 | file:<name>
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX family_event_start ON family_event(start);
    """,
    # 11 – Texas Hold'em (play chips only); the whole table is one JSON document
    """
    CREATE TABLE poker_game(
        id INTEGER PRIMARY KEY,
        host_id INTEGER,
        status TEXT NOT NULL DEFAULT 'lobby',   -- lobby | running | done
        state TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );
    """,
    # 12 – polls: a question, options, one or several answers, anonymous or with names
    """
    CREATE TABLE poll(
        id INTEGER PRIMARY KEY,
        question TEXT NOT NULL,
        created_by INTEGER,
        multi INTEGER NOT NULL DEFAULT 0,
        anonymous INTEGER NOT NULL DEFAULT 0,
        closes_at TEXT,                         -- 2026-11-20T18:00 (local) or NULL
        status TEXT NOT NULL DEFAULT 'open',    -- open | closed
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        closed_at TEXT
    );
    CREATE TABLE poll_option(id INTEGER PRIMARY KEY, poll_id INTEGER NOT NULL, text TEXT NOT NULL);
    CREATE TABLE poll_vote(poll_id INTEGER NOT NULL, profile_id INTEGER NOT NULL, option_id INTEGER NOT NULL,
                           PRIMARY KEY(poll_id, profile_id, option_id));
    """,
    # 13 – card games where you shed your cards (Tschau Sepp, Kartenkarussell): family table or alone against bots
    """
    CREATE TABLE card_game(
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,                     -- tschau | karussell
        host_id INTEGER,
        solo INTEGER NOT NULL DEFAULT 0,        -- 1: alone against bots (private)
        status TEXT NOT NULL DEFAULT 'lobby',   -- lobby | running | done
        state TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );
    """,
    # 14 – quiz: estimation and map questions (a number, or a pin on a map)
    """
    ALTER TABLE quiz_answer ADD COLUMN value REAL;
    ALTER TABLE quiz_answer ADD COLUMN lat REAL;
    ALTER TABLE quiz_answer ADD COLUMN lon REAL;
    """,
    # 15 – the children's own bots for the games (avatar area), shared with the family or not
    """
    CREATE TABLE bot(
        id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT NOT NULL DEFAULT '🤖',
        color TEXT NOT NULL DEFAULT '#5b5bd6',
        level TEXT NOT NULL DEFAULT 'normal',      -- easy | normal | hard
        shared INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    # 16 – «Errate den Song»: a speaker plays its playlist, who buzzes first answers, the others judge
    """
    CREATE TABLE song_game(
        id INTEGER PRIMARY KEY,
        host_id INTEGER,
        status TEXT NOT NULL DEFAULT 'lobby',        -- lobby | running | done
        state TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    );
    """,
    # 17 – calendar: FamilyTime and OfflineTime with their options (internet off, games locked, which children)
    """
    ALTER TABLE family_event ADD COLUMN options TEXT NOT NULL DEFAULT '{}';
    """,
    # 18 – Wichteln (secret gift giving): who gives whom, drawn at random – everybody only sees their own
    """
    CREATE TABLE wichtel(
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        created_by INTEGER,
        rules TEXT NOT NULL DEFAULT '{}',          -- {"no_parent_pairs": bool, "no_kid_pairs": bool}
        pairs TEXT NOT NULL,                       -- {"giver id": receiver id} – never sent as a whole
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,
    # 19 – Wichteln with a date: everybody gets a to-do in the planner and can tick it off
    """
    ALTER TABLE wichtel ADD COLUMN due TEXT;
    ALTER TABLE wichtel ADD COLUMN todos TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE wichtel ADD COLUMN done TEXT NOT NULL DEFAULT '{}';
    """,
    # 20 – own flash card decks per person (Leitner boxes like the packs)
    """
    CREATE TABLE deck(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        icon TEXT NOT NULL DEFAULT '📇',
        subject TEXT NOT NULL DEFAULT '',           -- cards added from a pack land in the deck of its subject
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX deck_profile ON deck(profile_id);
    CREATE TABLE deck_card(
        id INTEGER PRIMARY KEY,
        deck_id INTEGER NOT NULL,
        front TEXT NOT NULL,
        back TEXT NOT NULL,
        image TEXT NOT NULL DEFAULT '',
        emoji TEXT NOT NULL DEFAULT '',
        src TEXT NOT NULL DEFAULT '',               -- item key of the pack card it came from ('' = own card)
        box INTEGER NOT NULL DEFAULT 0,
        due TEXT,
        correct INTEGER NOT NULL DEFAULT 0,
        wrong INTEGER NOT NULL DEFAULT 0,
        last_seen TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX deck_card_deck ON deck_card(deck_id);
    """,
    # 21 – internet budget per child: minutes of the current period (day / week) already used
    """
    CREATE TABLE internet_allowance(
        profile_id INTEGER PRIMARY KEY,
        period TEXT NOT NULL,                      -- start of the period (ISO) the minutes belong to
        used INTEGER NOT NULL DEFAULT 0
    );
    """,
    # 22 – pet care: the pets of the avatar shop have bars that drop (pets.py); one living pet per kind and profile
    """
    CREATE TABLE pet(
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        kind TEXT NOT NULL,                        -- dog | cat | owl | parrot | degu (avatar item of the slot «pet»)
        name TEXT NOT NULL,
        born_at TEXT NOT NULL,                     -- the first time the pet appeared (age and stage count from here)
        hunger REAL NOT NULL DEFAULT 100,
        mood REAL NOT NULL DEFAULT 100,
        clean REAL NOT NULL DEFAULT 100,
        updated_at TEXT NOT NULL,                  -- the bars are valid at this time (decay is computed on read)
        zero_secs REAL NOT NULL DEFAULT 0,         -- unpaused seconds with all bars at 0 – 3 days and the pet dies
        zero_since TEXT,                           -- reached all-zero (the parents are told once)
        dead_at TEXT,
        seen INTEGER NOT NULL DEFAULT 0            -- the child saw the message that it died
    );
    CREATE INDEX pet_profile ON pet(profile_id, dead_at);
    """,
    # 23 – pet shop: outfits, houses and furniture belong to one pet (pets.SHOP); lost with the pet
    """
    CREATE TABLE pet_item(
        id INTEGER PRIMARY KEY,
        pet_id INTEGER NOT NULL,
        item TEXT NOT NULL,                        -- id of pets.SHOP
        used INTEGER NOT NULL DEFAULT 0,           -- outfit worn / house lived in / furniture placed
        worn_once INTEGER NOT NULL DEFAULT 0,      -- an outfit gave its mood bonus already
        bought_at TEXT NOT NULL,
        UNIQUE(pet_id, item)
    );
    """,
    # 24 – pet sitting (a family member looks after the pet, or the Family Quest pet hotel) and the hamster mining coins
    """
    ALTER TABLE pet ADD COLUMN sitter_id INTEGER;            -- a family member looks after the pet …
    ALTER TABLE pet ADD COLUMN sit_until TEXT;               -- … until this day (ISO date, inclusive)
    ALTER TABLE pet ADD COLUMN hotel_until TEXT;             -- in the pet hotel until this time: no decay, back fed and happy
    ALTER TABLE pet ADD COLUMN mined REAL NOT NULL DEFAULT 0;           -- hamster: coins not yet booked (fraction)
    ALTER TABLE pet ADD COLUMN mined_total INTEGER NOT NULL DEFAULT 0;  -- hamster: coins mined in all
    """,
    # 25 – pet hotel: the price per day that was paid (an early fetch pays back exactly that)
    """
    ALTER TABLE pet ADD COLUMN hotel_cost INTEGER NOT NULL DEFAULT 0;
    """,
    # 26 – more pets of one kind and babies: when a pet last had babies (a pair rests 14 days)
    """
    ALTER TABLE pet ADD COLUMN bred_at TEXT;
    """,
    # 27 – pranks from the shop (pranks.py): ink bombs bought and thrown
    """
    CREATE TABLE prank_charge(profile_id INTEGER PRIMARY KEY REFERENCES profile(id) ON DELETE CASCADE, n INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE prank(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, from_id INTEGER, to_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
                       at TEXT NOT NULL DEFAULT (datetime('now','localtime')), seen_at TEXT);
    CREATE INDEX prank_to ON prank(to_id, seen_at);
    """,
    # 28 – more pranks (the whoopee cushion): what is left per kind; the ink bombs move over
    """
    CREATE TABLE prank_stock(profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE, kind TEXT NOT NULL,
                             n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(profile_id, kind));
    INSERT INTO prank_stock(profile_id, kind, n) SELECT profile_id, 'ink', n FROM prank_charge WHERE n > 0;
    DROP TABLE prank_charge;
    """,
]

DEFAULT_ACCOUNTS = [
    # key, name (English source, translated in the UI), unit, icon, spendable, active, sort
    ("xp", "XP", "XP", "⭐", 0, 1, 0),
    ("coins", _t("Coins"), "", "🪙", 1, 1, 1),
    ("internet", _t("Internet minutes"), "min", "🌐", 1, 0, 2),
]

DEFAULT_RULES = [
    # event, account, amount, daily_limit, label
    ("answer_correct", "xp", 1, None, "Correct answer"),
    ("answer_fixed", "xp", 3, None, "Card that was wrong before"),
    ("answer_fast", "xp", 1, 20, "Fast answer in the quiz"),
    ("lesson_done", "xp", 10, None, "Lesson finished"),
    ("lesson_done", "coins", 10, 50, "Lesson finished"),
    ("daily_goal", "coins", 20, None, "Daily goal reached"),
    ("quiz_perfect", "coins", 5, 20, "Quiz round without mistakes"),
    ("badge", "xp", 25, None, "New badge"),
    ("chore_done", "coins", 10, None, "Chore done"),
    ("streak_7", "internet", 15, None, "7 day streak"),
]

DEFAULT_REWARDS = [
    # name, kind, account, cost, approval, weekly_limit, icon, config
    (_t("Ice cream"), "voucher", "coins", 80, 1, 2, "🍦", {}),
    (_t("30 minutes longer awake"), "voucher", "coins", 150, 1, 1, "🌙", {}),
    (_t("Choose the movie night film"), "voucher", "coins", 300, 1, 1, "🎬", {}),
    (_t("15 internet minutes"), "internet_minutes", "coins", 15, 0, None, "🌐", {"minutes": 15}),
]

DEFAULT_SETTINGS = {
    "levels": [0, 50, 150, 300, 500, 750, 1050, 1400, 1800, 2250, 2750, 3300, 3900, 4550, 5250, 6000, 6800, 7650, 8550, 9500],
    "family_visibility": "all",          # all | percent | goal
    "sound": True,
    "reminder_time": "",                 # "17:30" = learning reminder via HA
    "notify_service": "",                # e.g. notify.mobile_app_phone – approvals as push message
    "chore_reminder_time": "",           # "18:00" = announce open chores
    "planer_points": False,              # also book points to Family Planer
    "planer_points_factor": 1.0,
    "games": "all",                      # family games (quiz, bingo, card games): all | some (chosen children) | off – parents always
    "games_guests": True,                # guests may join family games with a QR code
    "games_profiles": [],                # with "some": the children who may play
    "games_access": None,                # per game {"mode", "profiles"} (services.games_access) – replaces the two above
    "parent_ha_only": False,             # parent area only through Home Assistant (linked HA user), no PIN login
    "allowed_networks": [],              # mini firewall: networks (CIDR) that may use the app – empty = all
    "guest_networks": [],                # guest Wi-Fi: only games with a QR code invitation (no family login)
    "parent_networks": [],               # … that may open the parent area – empty = all
    "calendar": None,                    # family calendar (calendar.py): Home Assistant calendars shown read-only
    "dashboard": None,                   # kiosk dashboard (dashboard.py)
    "translations": None,                # own texts and languages (translations.py)
    "weather": None,                     # behaviour weather – None = defaults (weather.DEFAULT)
    "themes": None,                      # season designs of the app header – None = defaults (themes.clean)
    "pet_food_cost": 2,                  # coins for feeding a pet once (pets.py)
    "pet_hotel_cost": 10,                # Family Quest pet hotel: coins per day (pets.py)
    "hamster_coins_per_day": 15,         # the hamster mines (default: 5 more than a day in the pet hotel) this many coins per day while it is healthy (pets.py)
    "pet_shop_currency": "coins",        # pet shop (outfits, houses, furniture): coins | xp | mixed (the child chooses)
    "lesson_perfect_coins": 5,           # coins for a lesson without a single mistake (on top of «lesson finished»)
    "game_rewards": {"paarjagd": [10, 5, 2], "werbinich": [10, 5, 2], "kartenlauf": [10, 5, 2], "stadtland": [10, 5, 2], "zeichnen": [10, 5, 2], "wuerfel": [10, 5, 2], "heimwaerts": [10, 5, 2], "jump": [10, 5, 2], "klatsch": [10, 5, 2], "verboten": [10, 5, 2], "jass": [10, 5, 2], "werwolf": [10, 5, 2], "schach": [10, 5, 2]},   # live games: coins for places 1, 2, 3 (pairhunt.py, whoami.py, kartenlauf.py, stadtland.py, zeichnen.py, wuerfel.py, heimwaerts.py, jump.py, klatsch.py, verboten.py; jass.py: place 1 only; werwolf.py: place 1 for the winning side; schach.py: [win against family, against the hard bot, against the normal bot]) – family tables with ≥ 2 people
    "memory": None,                      # pairs game: own photo sets and the family crest (memorygame.py)
    "planer_points_account": "coins",    # built-in planner: its points and this account are one balance ("" = separate)
}

DEFAULT_PROFILE_SETTINGS = {
    "daily_goal": 50,             # XP per day
    "lesson_length": 10,          # exercises per lesson
    "new_per_lesson": 5,          # new cards per lesson
    "learning_hours": "",         # "07:00-20:00" – empty = always
    "internet_entity": "",        # input_number / number entity that receives internet minutes
    "internet_daily_limit": 60,   # minutes per day from the shop
    "internet_rule": "",          # switch of a UniFi firewall/traffic rule – the app manages budget and start/stop
    "internet_rule_blocks": True, # True = the rule blocks the internet while the switch is on
    "internet_plan": None,        # budget per day/week, other weekdays, block times (internet.clean_plan)
    "auto_logout_min": 0,         # 0 = never
    "notify_service": "",         # parents: notify.mobile_app_xyz – approvals as push message to this phone
    "pin_kind": "",               # "symbols" = picture PIN (children), "digits" or "" = number PIN
    "symbol_set": [],             # picture PIN: the 12 symbols shown at login (not secret)
    "devices": [],                # Home Assistant entities this profile may control (devices.py)
}


def dict_row(cur: sqlite3.Cursor, row: tuple) -> dict:
    return {d[0]: row[i] for i, d in enumerate(cur.description)}


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = dict_row
        self.conn.execute("PRAGMA foreign_keys=ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.RLock()
        self._depth = 0
        self.migrate()

    # ---------- transactions ----------
    @contextmanager
    def tx(self) -> Iterator["Database"]:
        with self.lock:
            outer = self._depth == 0
            if outer:
                self.conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self
            except BaseException:
                self._depth -= 1
                if outer:
                    self.conn.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self.conn.execute("COMMIT")

    # ---------- helpers ----------
    def q(self, sql: str, *args: Any) -> list[dict]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def q1(self, sql: str, *args: Any) -> dict | None:
        with self.lock:
            return self.conn.execute(sql, args).fetchone()

    def val(self, sql: str, *args: Any, default: Any = None) -> Any:
        r = self.q1(sql, *args)
        if not r:
            return default
        v = next(iter(r.values()))
        return default if v is None else v

    def x(self, sql: str, *args: Any) -> int:
        """Run a write. INSERT → new rowid (0 when OR IGNORE skipped the row), else the number of changed rows."""
        with self.lock:
            cur = self.conn.execute(sql, args)
            if sql.lstrip()[:6].upper() == "INSERT":
                return cur.lastrowid if cur.rowcount > 0 else 0
            return cur.rowcount

    # ---------- settings ----------
    def get_setting(self, key: str, default: Any = None) -> Any:
        r = self.q1("SELECT value FROM setting WHERE key=?", key)
        if r is None:
            return DEFAULT_SETTINGS.get(key, default)
        return json.loads(r["value"])

    def set_setting(self, key: str, value: Any) -> None:
        self.x("INSERT INTO setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               key, json.dumps(value, ensure_ascii=False))

    def all_settings(self) -> dict:
        out = dict(DEFAULT_SETTINGS)
        for r in self.q("SELECT key, value FROM setting"):
            out[r["key"]] = json.loads(r["value"])
        return out

    # ---------- schema ----------
    def migrate(self) -> None:
        with self.lock:
            ver = self.conn.execute("PRAGMA user_version").fetchone()["user_version"]
            for i, sql in enumerate(MIGRATIONS[ver:], start=ver + 1):
                self.conn.executescript("BEGIN;" + sql + f";PRAGMA user_version={i};COMMIT;")
                if i == 1:
                    self._seed()

    def _seed(self) -> None:
        with self.tx():
            for a in DEFAULT_ACCOUNTS:
                self.x("INSERT INTO account(key,name,unit,icon,spendable,active,sort) VALUES(?,?,?,?,?,?,?)", *a)
            for ev, acc, amt, lim, label in DEFAULT_RULES:
                self.x("INSERT INTO rule(event,account,amount,daily_limit,label) VALUES(?,?,?,?,?)", ev, acc, amt, lim, label)
            for i, (name, kind, acc, cost, appr, wl, icon, cfg) in enumerate(DEFAULT_REWARDS):
                self.x("INSERT INTO reward(name,kind,account,cost,approval,weekly_limit,icon,config,sort) VALUES(?,?,?,?,?,?,?,?,?)",
                       name, kind, acc, cost, appr, wl, icon, json.dumps(cfg), i)


def profile_settings(profile: dict) -> dict:
    s = dict(DEFAULT_PROFILE_SETTINGS)
    try:
        s.update(json.loads(profile.get("settings") or "{}"))
    except ValueError:
        pass
    return s
