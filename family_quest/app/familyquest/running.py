"""Parent area: every game that is running just now – and ending one or all of them.

Family tables and tables alone against bots of all live games: the family quiz, bingo, guess the song, poker and the
games of the `card_game` table (Tschau Sepp, Kartenkarussell, Domino, Paarjagd, Wer bin ich?, Kartenlauf,
<<<<<<< HEAD
Stadt-Land-Fluss, Zeichnen & Raten, Fünf Würfel, Heimwärts, Jump, Klatsch den Beat, Verbotene Wörter, Jass, Werwölfe). Ending works like the «End» button of whoever leads the game.
||||||| d137a70
Stadt-Land-Fluss, Zeichnen & Raten, Fünf Würfel, Heimwärts, Jump, Heimwärts, Verbotene Wörter, Jass, Werwölfe). Ending works like the «End» button of whoever leads the game.
=======
Stadt-Land-Fluss, Zeichnen & Raten, Fünf Würfel, Heimwärts, Jump, Heimwärts, Verbotene Wörter, Jass, Werwölfe, Schach). Ending works like the «End» button of whoever leads the game.
Chess games can be paused (status "paused" – listed as paused); ending one ends it without a result and without coins.
>>>>>>> wt/schach
"""
from __future__ import annotations

import json

TITLES = {"tschau": "Tschau Sepp", "karussell": "Kartenkarussell", "domino": "Domino", "paarjagd": "Paarjagd",
          "werbinich": "Wer bin ich?", "kartenlauf": "Kartenlauf", "stadtland": "Stadt-Land-Fluss", "zeichnen": "Zeichnen & Raten",
          "wuerfel": "Fünf Würfel", "heimwaerts": "Heimwärts", "jump": "Jump", "klatsch": "Klatsch den Beat", "verboten": "Verbotene Wörter", "jass": "Jass", "werwolf": "Werwölfe", "schach": "Chess"}
ICONS = {"quiz": "🎯", "bingo": "🎱", "song": "🎵", "poker": "🃏", "tschau": "🂡", "karussell": "🎠", "domino": "🁫",
         "paarjagd": "🧠", "werbinich": "🎭", "kartenlauf": "🏁", "stadtland": "🏙️", "zeichnen": "🎨", "wuerfel": "🎲", "heimwaerts": "🏠", "jump": "🦘", "klatsch": "👏", "verboten": "🚫", "jass": "♣️", "werwolf": "🐺", "schach": "♟️"}


def _games(fq) -> dict:
    """The object that leads the tables of a card_game kind."""
    return {"tschau": fq.cards, "karussell": fq.cards, "domino": fq.domino, "paarjagd": fq.paarjagd,
            "werbinich": fq.werbinich, "kartenlauf": fq.kartenlauf, "stadtland": fq.stadtland, "zeichnen": fq.zeichnen,
            "wuerfel": fq.wuerfel, "heimwaerts": fq.heimwaerts, "jump": fq.jump, "klatsch": fq.klatsch, "verboten": fq.verboten, "jass": fq.jass, "werwolf": fq.werwolf, "schach": fq.schach}


def _name(fq, pid) -> str:
    return fq.db.val("SELECT name FROM profile WHERE id=?", pid, default="") or ""


def _people(players) -> int:
    return sum(1 for p in players or [] if not (isinstance(p, dict) and p.get("bot")))


def running(fq) -> list[dict]:
    out = []
    g = fq.community._game()
    if g:
        out.append({"key": "quiz", "game": "quiz", "icon": ICONS["quiz"], "title": (g.get("quiz") or {}).get("title") or "Quiz",
                    "status": g["status"], "solo": False, "host": _name(fq, g.get("host_id")), "players": len(g.get("players") or [])})
    b = fq.bingo._game()
    if b:
        out.append({"key": "bingo", "game": "bingo", "icon": ICONS["bingo"], "title": "Bingo", "status": b["status"], "solo": False,
                    "host": _name(fq, b.get("host_id")), "players": int(fq.db.val("SELECT COUNT(*) FROM bingo_card WHERE game_id=?", b["id"], default=0) or 0)})
    s = fq.songs._row()
    if s:
        st = json.loads(s["state"] or "{}")
        out.append({"key": "song", "game": "song", "icon": ICONS["song"], "title": "Errate den Song", "status": s["status"], "solo": False,
                    "host": _name(fq, s.get("host_id")), "players": _people(st.get("players"))})
    for r in fq.db.q("SELECT * FROM poker_game WHERE status!='done' ORDER BY id"):
        st = json.loads(r["state"] or "{}")
        out.append({"key": f"poker:{r['id']}", "game": "poker", "icon": ICONS["poker"], "title": "Texas Hold'em", "status": r["status"],
                    "solo": bool(st.get("solo")), "host": _name(fq, r["host_id"]), "players": _people(st.get("players"))})
    for r in fq.db.q("SELECT * FROM card_game WHERE status!='done' ORDER BY id"):
        if r["kind"] not in TITLES:
            continue
        st = json.loads(r["state"] or "{}")
        players = st.get("players")
        if isinstance(players, dict):                   # chess: {"w": …, "b": …}
            players = list({p["id"]: p for p in players.values() if p}.values())
        out.append({"key": f"card:{r['id']}", "game": r["kind"], "icon": ICONS[r["kind"]], "title": TITLES[r["kind"]], "status": r["status"],
                    "solo": bool(r["solo"]), "host": _name(fq, r["host_id"]), "players": _people(players)})
    return out


def end(fq, key: str) -> None:
    """End one game (key from running()) – as its leader would."""
    if key == "quiz":
        fq.community.abort()
    elif key == "bingo":
        fq.bingo.end()
    elif key == "song":
        fq.songs.end()
    elif key.startswith("poker:"):
        r = fq.db.q1("SELECT * FROM poker_game WHERE id=? AND status!='done'", int(key[6:]))
        if r:
            solo = bool(json.loads(r["state"] or "{}").get("solo"))
            fq.poker.end(r["host_id"] if solo else None)
    elif key.startswith("card:"):
        r = fq.db.q1("SELECT * FROM card_game WHERE id=? AND status!='done'", int(key[5:]))
        if r and r["kind"] == "schach":                 # several chess games at a time, also paused ones
            fq.schach.abort(r["id"])
        elif r and r["kind"] in TITLES:
            # the table's own end (scoring, coins …): own tables through their host, family tables through nobody's own table
            _games(fq)[r["kind"]].end(r["kind"], r["host_id"] if r["solo"] else -1)
            if fq.db.val("SELECT status FROM card_game WHERE id=?", r["id"]) != "done":       # safety net
                fq.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", r["id"])
    else:
        raise ValueError("Unknown game")


def end_all(fq) -> int:
    games = running(fq)
    for g in games:
        try:
            end(fq, g["key"])
        except Exception:  # noqa: BLE001 – one stubborn game must not keep the others running
            pass
    return len(games)
