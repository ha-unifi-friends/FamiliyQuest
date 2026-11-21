"""«Errate den Song» – a music guessing game with a buzzer.

The game leader chooses a speaker (media player of Home Assistant) that already has a playlist; the app switches
shuffle on and only steers it: play, pause, next song. Who buzzes first stops the song and says artist and/or title
(the rule); then the app shows cover, artist and title from the speaker and the others vote whether it was right
(absolute majority or unanimous – decided as soon as the verdict is certain). Right +1, wrong −1. The game ends at the
target points or after the most songs.

Phases: lobby → playing → buzzed → reveal → result → playing … → done. Like the other family games the state is one
JSON document; every request moves it on (no background task).
"""
from __future__ import annotations

import json
import logging
import threading
import time

from .community import CommunityError

RULES_KEY = "game_rules.song"
DEFAULT_RULES = {"player": "", "answer": "both", "vote": "majority", "target": 10, "max_songs": 40, "reveal_delay": 5, "reveal_by": "others", "speaker_sound": True}
ANSWERS = ("artist", "title", "both", "either")


log = logging.getLogger("familyquest.songquiz")


class SongQuiz:
    def __init__(self, db, add_history=None, ha=lambda: None, sound_url=lambda name: None):
        self.db = db
        self.sound_url = sound_url         # name → URL of web/sounds/<name>.mp3 the speaker can fetch (or None)
        self.add_history = add_history
        self.ha = ha                       # () → the Home Assistant service (or None)
        self.lock = threading.Lock()

    # ---------- storage
    def _row(self):
        return self.db.q1("SELECT * FROM song_game WHERE status!='done' ORDER BY id DESC LIMIT 1")

    def _game(self):                       # the shape the guests module expects
        row = self._row()
        return {"id": row["id"], "status": row["status"]} if row else None

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE song_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status == "done" and self.add_history and not st.get("history_written"):
            st["history_written"] = True
            self.db.x("UPDATE song_game SET state=? WHERE id=?", json.dumps(st), row["id"])
            ranking = sorted(st["players"], key=lambda p: -p["points"])
            best = ranking[0]["points"] if ranking else 0
            try:
                self.add_history(0, "__family__", {"people": [p["id"] for p in ranking],
                                                   "winners": [p["id"] for p in ranking if best > 0 and p["points"] == best]})
            except Exception:  # noqa: BLE001
                pass
            for i, p in enumerate(ranking):
                try:
                    self.add_history(int(p["id"]), "song", {"place": i + 1, "players": len(ranking), "points": p["points"]})
                except Exception:  # noqa: BLE001
                    pass

    def default_rules(self) -> dict:
        return {**DEFAULT_RULES, **(self.db.get_setting(RULES_KEY) or {})}

    @staticmethod
    def clean_rules(r: dict) -> dict:
        def num(k, lo, hi):
            try:
                return max(lo, min(hi, int(r.get(k, DEFAULT_RULES[k]))))
            except (TypeError, ValueError):
                return DEFAULT_RULES[k]
        player = str(r.get("player") or "")
        if not player.startswith("media_player."):
            raise CommunityError("Choose a speaker")
        return {"player": player, "answer": r.get("answer") if r.get("answer") in ANSWERS else "both",
                "vote": "unanimous" if r.get("vote") == "unanimous" else "majority",
                "target": num("target", 1, 50), "max_songs": num("max_songs", 1, 200),
                "reveal_delay": num("reveal_delay", 0, 30),     # seconds after the buzz before the solution can be shown
                # who shows the solution: the others (everybody who did not buzz), who buzzed, or only the leader
                "reveal_by": r.get("reveal_by") if r.get("reveal_by") in ("others", "all", "leader") else "others",
                "speaker_sound": r.get("speaker_sound", True) is not False}         # «ping» / «brrr» on the speaker after the verdict   # who may show it: who buzzed too, or only the leader

    def may_lead(self, prof: dict) -> bool:
        row = self._row()
        return bool(row) and (prof["role"] == "parent" or row["host_id"] == prof["id"])

    def _media(self, st: dict, action: str) -> None:
        ha = self.ha()
        if not ha or not ha.connected:
            raise CommunityError("Home Assistant is not connected")
        try:
            ha.media(st["rules"]["player"], action)
        except CommunityError:
            raise
        except Exception as e:  # noqa: BLE001
            raise CommunityError("The speaker does not answer") from e

    def _person(self, pid: int) -> dict:
        p = self.db.q1("SELECT name, avatar FROM profile WHERE id=?", pid)
        return {"id": str(pid), "name": p["name"] if p else "?", "avatar": json.loads(p["avatar"] or "{}") if p else {}, "points": 0}

    # ---------- the leader
    def start(self, host: int, rules: dict) -> int:
        with self.lock:
            if self._row():
                raise CommunityError("A game is already running")
            r = self.clean_rules({**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(RULES_KEY, r)
            st = {"rules": r, "players": [self._person(host)], "phase": "lobby", "song": 0, "log": []}
            return self.db.x("INSERT INTO song_game(host_id, state) VALUES(?,?)", host, json.dumps(st))

    def join(self, pid: int) -> None:
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if any(p["id"] == str(pid) for p in st["players"]):
                return
            st["players"].append(self._person(pid))
            self._save(row, st)

    def _need(self):
        row = self._row()
        if not row:
            raise CommunityError("No game is running")
        return row

    def begin(self) -> None:
        """Shuffle on, the next song of the playlist – and go."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) < 2:
                raise CommunityError("At least two players – the others judge the answer")
            self._media(st, "shuffle")
            try:
                ha = self.ha()
                v = ha.media_info(st["rules"]["player"]).get("volume")
                st["volume"] = round(float(v) * 100) if v is not None else None
            except Exception:  # noqa: BLE001 – the volume is only shown
                st["volume"] = None
            self._next_song(st)
            self._save(row, st)

    def _next_song(self, st: dict) -> None:
        self._media(st, "next")
        self._media(st, "play")
        st.update(phase="playing", song=st.get("song", 0) + 1, buzzer=None, votes={}, solution=None, verdict=None, at=time.time(),
                  paused=False)                       # a new song always plays – also after skipping a paused one

    def next(self) -> None:
        """After the result (or to skip a song nobody knows): the next song."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] == "playing":                  # skip: show the solution without points
                st["phase"] = "reveal"
                st["skipped"] = True
                self._media(st, "pause")
                st["solution"] = self._solution(st)
                st["verdict"] = None
                st["phase"] = "result"
            elif st["phase"] in ("result",):
                if self._finished(st):
                    self._finish(st)
                else:
                    st.pop("skipped", None)
                    self._next_song(st)
            else:
                raise CommunityError("First the answer has to be judged")
            self._save(row, st)

    def pause(self, on: bool) -> None:
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "playing":
                return
            self._media(st, "pause" if on else "play")
            st["paused"] = bool(on)
            self._save(row, st)

    def end(self) -> None:
        with self.lock:
            row = self._row()
            if not row:
                return
            st = json.loads(row["state"])
            try:
                self._media(st, "pause")
            except CommunityError:
                pass
            self._finish(st)
            self._save(row, st)

    # ---------- the players
    def buzz(self, pid: int) -> bool:
        """The first one wins the buzzer – the song stops."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "playing" or st.get("paused") or not any(p["id"] == str(pid) for p in st["players"]):
                return False
            st.update(phase="buzzed", buzzer=str(pid), buzz_at=time.time())
            try:
                self._media(st, "pause")
            except CommunityError:
                pass
            self._save(row, st)
            return True

    def reveal(self, prof: dict) -> None:
        """The one who buzzed (or the leader) has said the answer: show artist and title to everybody."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "buzzed":
                raise CommunityError("Nobody has buzzed")
            leader = prof["role"] == "parent" or row["host_id"] == prof["id"]
            mode = st["rules"].get("reveal_by", "all")
            if mode == "leader" and not leader:
                raise CommunityError("Only the game leader shows the solution")
            if mode == "others" and not leader:
                if str(prof["id"]) == st["buzzer"]:
                    raise CommunityError("The others show the solution")
                if not any(p["id"] == str(prof["id"]) for p in st["players"]):
                    raise CommunityError("You do not play in this game")
            if mode == "all" and str(prof["id"]) != st["buzzer"] and not leader:
                raise CommunityError("Only who buzzed or the game leader")
            if time.time() < (st.get("buzz_at") or 0) + st["rules"].get("reveal_delay", 5):
                raise CommunityError("Wait for the countdown")       # first say the answer, then look
            st["solution"] = self._solution(st)
            st["phase"] = "reveal"
            st["votes"] = {}
            self._save(row, st)

    def vote(self, pid: int, right: bool) -> None:
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "reveal":
                raise CommunityError("There is nothing to judge right now")
            if str(pid) == st["buzzer"]:
                raise CommunityError("The others judge your answer")
            if not any(p["id"] == str(pid) for p in st["players"]):
                raise CommunityError("Join the game first")
            st["votes"][str(pid)] = bool(right)
            if self._settled(st):
                self._judge(st)
            self._save(row, st)

    @staticmethod
    def _settled(st: dict) -> bool:
        """The verdict is certain – no vote still missing can change it. Majority (absolute, of everybody who may
        judge): «right» from more than half of them, «wrong» once at least half said wrong (right cannot reach more
        than half any more). Unanimous: one «wrong» decides; «right» only when all said right. Else when all voted."""
        judges = [p["id"] for p in st["players"] if p["id"] != st["buzzer"]]
        votes = {j: st["votes"][j] for j in judges if j in st["votes"]}
        yes = sum(1 for v in votes.values() if v)
        no = len(votes) - yes
        if len(votes) == len(judges):
            return True
        if st["rules"]["vote"] == "unanimous":
            return no > 0
        return yes * 2 > len(judges) or no * 2 >= len(judges)

    def decide(self) -> None:
        """The leader closes the vote with the votes there are."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            if st["phase"] != "reveal":
                raise CommunityError("There is nothing to judge right now")
            self._judge(st)
            self._save(row, st)

    def _judge(self, st: dict) -> None:
        yes = sum(1 for v in st["votes"].values() if v)
        n = len(st["votes"])
        if n == 0:                                    # the leader closed the vote before anybody judged: no points
            st["verdict"] = {"right": None, "yes": 0, "of": 0}
            st["phase"] = "result"
            return
        if st["rules"]["vote"] == "unanimous":
            right = yes == n
        elif self._settled(st):                       # absolute majority of everybody who may judge
            right = yes * 2 > sum(1 for p in st["players"] if p["id"] != st["buzzer"])
        else:                                         # the leader closed the vote early: the majority of the votes there are
            right = yes * 2 > n
        p = next(p for p in st["players"] if p["id"] == st["buzzer"])
        p["points"] += 1 if right else -1
        st["verdict"] = {"right": right, "yes": yes, "of": n}
        st["phase"] = "result"
        if st["rules"].get("speaker_sound", True):
            threading.Thread(target=self._ding, args=(st["rules"]["player"], right), daemon=True).start()

    def _ding(self, player: str, right: bool) -> None:
        """«Ping» for right, «brrr» for wrong – as an announcement over the playlist (it is not changed)."""
        ha, url = self.ha(), self.sound_url("right" if right else "wrong")
        if not ha or not url or not hasattr(ha, "announce"):
            return
        try:
            ha.announce(player, url)
        except Exception as e:  # noqa: BLE001 - a speaker without announcements: the app plays the sound anyway
            log.info("no sound on %s: %s", player, e)

    def _solution(self, st: dict) -> dict:
        ha = self.ha()
        try:
            info = ha.media_info(st["rules"]["player"]) if ha and ha.connected else {}
        except Exception:  # noqa: BLE001
            info = {}
        return {"title": info.get("title", ""), "artist": info.get("artist", ""), "album": info.get("album", ""),
                "picture": info.get("picture", ""), "song": st["song"]}

    def _finished(self, st: dict) -> bool:
        return any(p["points"] >= st["rules"]["target"] for p in st["players"]) or st["song"] >= st["rules"]["max_songs"]

    def _finish(self, st: dict) -> None:
        st["phase"] = "done"
        st["finished"] = time.time()

    def cover(self) -> tuple[bytes, str] | None:
        row = self._row() or self.db.q1("SELECT * FROM song_game ORDER BY id DESC LIMIT 1")
        if not row:
            return None
        sol = json.loads(row["state"]).get("solution") or {}
        ha = self.ha()
        return ha.media_cover(sol.get("picture", "")) if ha and ha.connected and sol.get("picture") else None

    # ---------- what a device sees
    def state(self, viewer: int) -> dict | None:
        row = self._row() or self.db.q1("""SELECT * FROM song_game WHERE status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                           ORDER BY id DESC LIMIT 1""")
        if not row:
            return None
        st = json.loads(row["state"])
        me = str(viewer)
        if row["status"] == "done" and not any(p["id"] == me for p in st["players"]):
            return None
        sol = st.get("solution") if st["phase"] in ("reveal", "result", "done") else None
        players = sorted(({**p, "id": int(p["id"]), "voted": p["id"] in (st.get("votes") or {})} for p in st["players"]),
                         key=lambda p: -p["points"])
        return {"game": row["id"], "status": row["status"], "phase": st["phase"], "host": row["host_id"], "rules": st["rules"],
                "song": st.get("song", 0), "paused": bool(st.get("paused")), "players": players,
                "joined": any(p["id"] == me for p in st["players"]),
                "buzzer": int(st["buzzer"]) if st.get("buzzer") else None, "my_vote": (st.get("votes") or {}).get(me),
                "solution": {k: v for k, v in (sol or {}).items() if k != "picture"} | {"cover": bool((sol or {}).get("picture"))} if sol else None,
                "skipped": bool(st.get("skipped")), "verdict": st.get("verdict"), "volume": st.get("volume"),
                "reveal_in_ms": max(0, int(((st.get("buzz_at") or 0) + st["rules"].get("reveal_delay", 5) - time.time()) * 1000))
                if st["phase"] == "buzzed" else 0}

    def volume(self, step: int) -> None:
        """The game leader turns the speaker up or down by 5 %."""
        with self.lock:
            row = self._need()
            st = json.loads(row["state"])
            cur = st.get("volume")
            if cur is None:
                ha = self.ha()
                info = ha.media_info(st["rules"]["player"]) if ha and ha.connected else {}
                cur = round(float(info.get("volume") or 0.3) * 100)
            new = max(0, min(100, int(cur) + (5 if step > 0 else -5)))
            self._media(st, f"volume:{new / 100}")
            st["volume"] = new
            self._save(row, st)

    def summary(self, pid: int) -> dict | None:
        row = self._row()
        if not row:
            return None
        st = json.loads(row["state"])
        return {"status": row["status"], "joined": any(p["id"] == str(pid) for p in st["players"])}
