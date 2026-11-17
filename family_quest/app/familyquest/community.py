"""Etappe H – community: family quiz (live, like a quiz show), family council (proposals and a vote), personal history.

Family quiz
  Everybody can make quizzes (or copy one of the templates in quiz_templates.py). One game at a time: whoever starts
  it leads it (a parent may always lead too); everybody joins on their own device and the host shows question after
  question. At the start the questions can be limited to a number and are shuffled, the answers too. A question ends when its time is up or everybody answered (checked
  lazily whenever someone asks for the state – the devices poll about once a second). Points: a right answer gives
  1000 at once and down to 500 at the end of the time. The end writes everybody's place into their history and
  emits the reward events quiz_played and quiz_won.
Family council
  Anybody opens a topic and everybody adds proposals. The one who opened it (or a parent) starts the vote: one secret
  vote per person, it can be changed until the vote is closed. Closing writes the result into the history of
  everybody who took part.
History
  Entries carry data, not text – the app shows them in the viewer's language.
"""
from __future__ import annotations

import json
import re
import random
import threading
import time

from .db import Database
from .rewards.engine import Rewards

MAX_PROPOSALS = 5           # per person and topic
GRACE = 0.6                 # seconds after the time is up in which an answer still counts (network)


FAMILY_RESULT = "__family__"   # add_history(…, FAMILY_RESULT, {"people", "winners"}) from the games: the «No. 1» hat

class CommunityError(ValueError):
    pass


class Community:
    def __init__(self, db: Database, rewards: Rewards):
        self.db = db
        self.rewards = rewards
        self.lock = threading.RLock()     # quiz game: join / leave / start read and write the players list

    # ================================================================ quizzes (definitions)
    @staticmethod
    def clean_questions(questions, more: list[str] | None = None) -> list[dict]:
        """`more`: the further languages of a multilingual quiz – each question keeps its texts in them ("tr")."""
        out = []
        for q in questions or []:
            kind = (q or {}).get("kind") or "choice"
            if kind in ("estimate", "pin"):
                item = clean_special(q)
                tr = clean_tr(q.get("tr"), more, kind)
                if tr:
                    item["tr"] = tr
                out.append(item)
                continue
            text = str((q or {}).get("q", "")).strip()
            keep = [j for j, a in enumerate(q.get("a") or []) if str(a).strip()]     # the answers that are not empty
            answers = [str((q.get("a") or [])[j]).strip()[:120] for j in keep]
            if not text and not answers:
                continue
            if not text or not 2 <= len(answers) <= 4:
                raise CommunityError("Every question needs a text and 2 to 4 answers")
            c = q.get("c", 0)
            if not isinstance(c, int) or not 0 <= c < len(answers):
                raise CommunityError("Mark the right answer of every question")
            t = q.get("t", 20)
            t = max(5, min(120, int(t))) if isinstance(t, (int, float)) else 20
            item = {"q": text[:300], "a": answers, "c": c, "t": t}
            tr = clean_tr(q.get("tr"), more, "choice", keep, answers)
            if tr:
                item["tr"] = tr
            img = clean_image(q.get("img"))
            if img:
                item["img"] = img
            out.append(item)
        if not out:
            raise CommunityError("Add at least one question")
        if len(out) > MAX_QUESTIONS:
            raise CommunityError("A quiz can have at most 100 questions")
        if sum(len((q.get("img") or {}).get("svg") or "") for q in out) > MAX_QUIZ_SVG:
            raise CommunityError("The drawings of this quiz are too big together (max. 300 KB)")
        return out

    def quizzes(self) -> list[dict]:
        rows = self.db.q("""SELECT q.*, p.name AS author FROM quiz q LEFT JOIN profile p ON p.id=q.created_by
                            WHERE q.archived=0 ORDER BY q.id DESC""")
        for r in rows:
            r["questions"] = json.loads(r["questions"])
            r["langs"] = json.loads(r["langs"]) if r.get("langs") else None
            r["games"] = int(self.db.val("SELECT COUNT(*) FROM quiz_game WHERE quiz_id=? AND status='done'", r["id"], default=0))
            last = self.db.q1("SELECT id, finished_at FROM quiz_game WHERE quiz_id=? AND status='done' ORDER BY id DESC LIMIT 1", r["id"])
            r["last_played"] = last["finished_at"] if last else None
            win = self.db.q1("""SELECT p.name, SUM(a.points) AS pts FROM quiz_answer a JOIN profile p ON p.id=a.profile_id
                                WHERE a.game_id=? GROUP BY a.profile_id ORDER BY pts DESC LIMIT 1""", last["id"]) if last else None
            r["last_winner"] = {"name": win["name"], "points": int(win["pts"] or 0)} if win and win["pts"] else None
        return rows

    def _own(self, prof: dict, quiz_id: int) -> dict:
        q = self.db.q1("SELECT * FROM quiz WHERE id=? AND archived=0", quiz_id)
        if not q:
            raise CommunityError("Unknown quiz")
        if prof["role"] != "parent" and q["created_by"] != prof["id"]:
            raise CommunityError("Only who made the quiz (or a parent) can change it")
        return q

    def save_quiz(self, data: dict, prof: dict, quiz_id: int | None = None) -> int:
        title = str(data.get("title", "")).strip()[:80]
        if not title:
            raise CommunityError("The quiz needs a title")
        langs = clean_langs(data.get("langs"))
        qs = json.dumps(self.clean_questions(data.get("questions"), langs["more"] if langs else None), ensure_ascii=False)
        lj = json.dumps(langs, ensure_ascii=False) if langs else None
        if quiz_id:
            self._own(prof, quiz_id)
            self.db.x("UPDATE quiz SET title=?, questions=?, langs=? WHERE id=?", title, qs, lj, quiz_id)
            return quiz_id
        return self.db.x("INSERT INTO quiz(title, questions, created_by, langs) VALUES(?,?,?,?)", title, qs, prof["id"], lj)

    def import_quizzes(self, prof: dict, text: str) -> list[int]:
        """Quizzes from a file in the Family Quest quiz format (ai_format.py, self-describing JSON) – also JSON as AIs write it."""
        from .jsonish import loads
        try:
            data = loads(text)
        except ValueError:
            raise CommunityError("The file is not a quiz in the Family Quest format (JSON)") from None
        from .ai_format import strip_meta
        data = strip_meta(data)
        items = data if isinstance(data, list) else data.get("quizzes") if isinstance(data, dict) and isinstance(data.get("quizzes"), list) else [data]
        if not items or not all(isinstance(x, dict) for x in items):
            raise CommunityError("The file is not a quiz in the Family Quest format (JSON)")
        ids = []
        for i, quiz in enumerate(items[:20]):
            questions = [quiz_question(q) for q in quiz.get("questions") or [] if isinstance(q, dict)]
            if not questions:
                raise CommunityError("The quiz has no questions")
            try:
                ids.append(self.save_quiz({"title": quiz.get("title") or f"Quiz {i + 1}", "questions": questions,
                                           "langs": import_langs(quiz)}, prof))
            except CommunityError as e:
                raise CommunityError(f"{quiz.get('title') or 'Quiz'}: {e}") from None
        return ids

    def export_quizzes(self, quiz_id: int | None = None) -> dict:
        """One quiz or all of them as self-describing JSON (ai_format) – an AI can change it, the app imports it again."""
        from .ai_format import export_quiz, quiz_document
        rows = self.db.q("SELECT * FROM quiz WHERE archived=0" + (" AND id=?" if quiz_id else "") + " ORDER BY id", *([quiz_id] if quiz_id else []))
        if quiz_id and not rows:
            raise CommunityError("Unknown quiz")
        return quiz_document([export_quiz(r["title"], json.loads(r["questions"]), json.loads(r["langs"]) if r.get("langs") else None)
                              for r in rows])

    def delete_quiz(self, prof: dict, quiz_id: int) -> None:
        self._own(prof, quiz_id)
        self.db.x("UPDATE quiz SET archived=1 WHERE id=?", quiz_id)

    def from_template(self, prof: dict, template_id: str) -> int:
        from .quiz_templates import TEMPLATES
        t = TEMPLATES.get(template_id)
        if not t:
            raise CommunityError("Unknown template")
        trs = template_translations(template_id)
        langs = {"base": "de", "more": list(trs), "title": {k: v["title"] for k, v in trs.items()}} if trs else None
        return self.save_quiz({"title": t["title"], "questions": template_questions(t, trs), "langs": langs}, prof)

    # ================================================================ quiz game
    def _load(self, g: dict) -> dict:
        g["players"] = json.loads(g["players"])
        g["quiz"] = self.db.q1("SELECT * FROM quiz WHERE id=?", g["quiz_id"])
        g["questions"] = json.loads(g["questions"] or "[]")
        return g

    def _game(self) -> dict | None:
        g = self.db.q1("SELECT * FROM quiz_game WHERE status!='done' ORDER BY id DESC LIMIT 1")
        return self._load(g) if g else None

    def start(self, quiz_id: int, host: int, count: int | None = None, shuffle: bool = True) -> int:
        with self.lock:
            return self._start(quiz_id, host, count, shuffle)

    def _start(self, quiz_id: int, host: int, count: int | None = None, shuffle: bool = True) -> int:
        if self._game():
            raise CommunityError("A family quiz is already running")
        q = self.db.q1("SELECT * FROM quiz WHERE id=? AND archived=0", quiz_id)
        if not q:
            raise CommunityError("Unknown quiz")
        qs = json.loads(q["questions"])
        if shuffle:
            random.shuffle(qs)
            qs = [shuffle_answers(x) if (x.get("kind") or "choice") == "choice" else x for x in qs]
        if count:
            qs = qs[:max(1, int(count))]
        return self.db.x("INSERT INTO quiz_game(quiz_id, host_id, players, questions) VALUES(?,?,?,?)",
                         quiz_id, host, json.dumps([host]), json.dumps(qs, ensure_ascii=False))

    def may_lead(self, prof: dict) -> bool:
        g = self._game()
        return bool(g) and (prof["role"] == "parent" or g["host_id"] == prof["id"])

    def join(self, pid: int) -> None:
        with self.lock:                   # two children joining at the same moment: both stay in the list
            g = self._game()
            if not g:
                raise CommunityError("No family quiz is running")
            if pid not in g["players"]:
                g["players"].append(pid)
                self.db.x("UPDATE quiz_game SET players=? WHERE id=?", json.dumps(g["players"]), g["id"])

    def leave(self, pid: int) -> None:
        with self.lock:
            g = self._game()
            if g and pid in g["players"] and pid != g["host_id"]:
                g["players"].remove(pid)
                self.db.x("UPDATE quiz_game SET players=? WHERE id=?", json.dumps(g["players"]), g["id"])

    def _tick(self, g: dict) -> dict:
        """Lazy state change: a question ends when its time is up or everybody answered."""
        if g["status"] == "question":
            q = g["questions"][g["idx"]]
            n = int(self.db.val("SELECT COUNT(*) FROM quiz_answer WHERE game_id=? AND idx=?", g["id"], g["idx"], default=0))
            if time.time() - (g["q_started"] or 0) > q["t"] + GRACE or (g["players"] and n >= len(g["players"])):
                if self.db.x("UPDATE quiz_game SET status='reveal' WHERE id=? AND status='question' AND idx=?", g["id"], g["idx"]):
                    self._score_closest(g, g["idx"])
                g["status"] = "reveal"
        return g

    def next(self) -> None:
        """Host: from the lobby or a revealed question to the next question (or to the end)."""
        g = self._game()
        if not g:
            raise CommunityError("No family quiz is running")
        g = self._tick(g)
        if g["status"] == "question":
            self.reveal()
            return
        if g["idx"] + 1 >= len(g["questions"]):
            self.finish()
            return
        self.db.x("UPDATE quiz_game SET status='question', idx=?, q_started=? WHERE id=?", g["idx"] + 1, time.time(), g["id"])

    def reveal(self) -> None:
        g = self._game()
        if g and g["status"] == "question":
            if self.db.x("UPDATE quiz_game SET status='reveal' WHERE id=? AND status='question'", g["id"]):
                self._score_closest(g, g["idx"])

    def _score_closest(self, g: dict, idx: int) -> None:
        """Estimation and map questions: the closest answer 1000 points, the second 500, the third 250."""
        q = g["questions"][idx]
        if q.get("kind") not in ("estimate", "pin"):
            return
        rows = self.db.q("SELECT profile_id, value, lat, lon FROM quiz_answer WHERE game_id=? AND idx=?", g["id"], idx)
        errs = {r["profile_id"]: miss(q, r) for r in rows}
        ranks = sorted(set(e for e in errs.values() if e is not None))
        for pid, e in errs.items():
            place = ranks.index(e) if e is not None else 99
            pts = {0: 1000, 1: 500, 2: 250}.get(place, 0)
            self.db.x("UPDATE quiz_answer SET points=? WHERE game_id=? AND idx=? AND profile_id=?", pts, g["id"], idx, pid)

    def answer(self, pid: int, idx: int, choice: int | None = None, value: float | None = None,
               lat: float | None = None, lon: float | None = None) -> dict:
        g = self._game()
        if not g:
            raise CommunityError("No family quiz is running")
        g = self._tick(g)
        if g["status"] != "question" or idx != g["idx"]:
            raise CommunityError("This question is over")
        if pid not in g["players"]:
            raise CommunityError("Join the quiz first")
        q = g["questions"][idx]
        ms = max(0, int((time.time() - g["q_started"]) * 1000))
        kind = q.get("kind") or "choice"
        if kind == "estimate":
            if value is None:
                raise CommunityError("Type a number")
            ok = self.db.x("INSERT OR IGNORE INTO quiz_answer(game_id, idx, profile_id, choice, ms, points, value) VALUES(?,?,?,-1,?,0,?)",
                           g["id"], idx, pid, ms, float(value))
        elif kind == "pin":
            if lat is None or lon is None:
                raise CommunityError("Set your pin on the map")
            ok = self.db.x("INSERT OR IGNORE INTO quiz_answer(game_id, idx, profile_id, choice, ms, points, lat, lon) VALUES(?,?,?,-1,?,0,?,?)",
                           g["id"], idx, pid, ms, float(lat), float(lon))
        else:
            if choice is None or not 0 <= choice < len(q["a"]):
                raise CommunityError("Unknown answer")
            points = round(1000 - 500 * min(1.0, ms / (q["t"] * 1000))) if choice == q["c"] else 0
            ok = self.db.x("INSERT OR IGNORE INTO quiz_answer(game_id, idx, profile_id, choice, ms, points) VALUES(?,?,?,?,?,?)",
                           g["id"], idx, pid, choice, ms, points)
        if not ok:
            raise CommunityError("You have already answered")
        self._tick(self._game())
        return {"ok": True}

    def _scores(self, g: dict) -> list[dict]:
        pts = {r["profile_id"]: r for r in self.db.q(
            "SELECT profile_id, SUM(points) AS points, SUM(points>0) AS right FROM quiz_answer WHERE game_id=? GROUP BY profile_id", g["id"])}
        out = []
        for pid in g["players"]:
            p = self.db.q1("SELECT id, name, avatar, color FROM profile WHERE id=?", pid)
            if not p:
                continue
            r = pts.get(pid) or {}
            out.append({"id": pid, "name": p["name"], "color": p["color"], "avatar": json.loads(p["avatar"] or "{}"),
                        "points": int(r.get("points") or 0), "right": int(r.get("right") or 0)})
        out.sort(key=lambda x: (-x["points"], x["name"]))
        place, last = 0, None
        for i, x in enumerate(out):
            if x["points"] != last:
                place, last = i + 1, x["points"]
            x["place"] = place
        return out

    def finish(self) -> list[dict]:
        g = self._game()
        if not g:
            raise CommunityError("No family quiz is running")
        if not self.db.x("UPDATE quiz_game SET status='done', finished_at=datetime('now','localtime') WHERE id=? AND status!='done'", g["id"]):
            return []
        scores = self._scores(g)
        played = int(self.db.val("SELECT COUNT(DISTINCT profile_id) FROM quiz_answer WHERE game_id=?", g["id"], default=0))
        if not played:
            return scores                            # stopped before anybody answered: nothing to remember
        self.family_result([x["id"] for x in scores], [x["id"] for x in scores if x["place"] == 1 and x["points"] > 0])
        for x in scores:
            won = x["place"] == 1 and x["points"] > 0
            self.add_history(x["id"], "quiz", {"quiz": g["quiz"]["title"], "place": x["place"], "of": len(scores),
                                              "points": x["points"], "right": x["right"], "total": len(g["questions"]),
                                              "won": won, "game": g["id"]})
            self.rewards.emit(x["id"], "quiz_played", ref=f"quiz:{g['id']}")
            if won:
                self.rewards.emit(x["id"], "quiz_won", ref=f"quiz:{g['id']}")
        return scores

    def abort(self) -> None:
        g = self._game()
        if g:
            self.db.x("UPDATE quiz_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", g["id"])

    def state(self, viewer: int) -> dict | None:
        """What a device shows: lobby, the current question (without the right answer), the reveal or the end."""
        g = self._game()
        if not g:
            last = self.db.q1("""SELECT * FROM quiz_game WHERE status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                                 ORDER BY id DESC LIMIT 1""")
            if not last or viewer not in json.loads(last["players"]):
                return None
            g = self._load(last)
        else:
            g = self._tick(g)
        langs = json.loads(g["quiz"]["langs"]) if g["quiz"] and g["quiz"].get("langs") else None
        out = {"game": g["id"], "title": g["quiz"]["title"] if g["quiz"] else "", "langs": langs, "status": g["status"], "idx": g["idx"],
               "total": len(g["questions"]), "host": g["host_id"], "joined": viewer in g["players"],
               "players": self._scores(g)}
        if g["status"] in ("question", "reveal") and 0 <= g["idx"] < len(g["questions"]):
            q = g["questions"][g["idx"]]
            answers = self.db.q("""SELECT a.profile_id, a.choice, a.points, a.value, a.lat, a.lon, p.name FROM quiz_answer a
                                   LEFT JOIN profile p ON p.id=a.profile_id WHERE a.game_id=? AND a.idx=?""", g["id"], g["idx"])
            mine = next((a for a in answers if a["profile_id"] == viewer), None)
            kind = q.get("kind") or "choice"
            out["question"] = {"q": q["q"], "a": q.get("a", []), "t": q["t"], "img": q.get("img"), "kind": kind,
                               **({k: q[k] for k in ("min", "max", "unit", "step")} if kind == "estimate" else {}),
                               **({"map": q["map"]} if kind == "pin" else {}),
                               **({"tr": {k: {f: v[f] for f in ("q", "a", "unit") if f in v} for k, v in q["tr"].items()}} if q.get("tr") else {}),
                               "remaining_ms": max(0, int((q["t"] - (time.time() - (g["q_started"] or 0))) * 1000))
                               if g["status"] == "question" else 0}
            out["answered"] = [a["profile_id"] for a in answers]
            out["my_choice"] = mine["choice"] if mine else None
            if kind != "choice" and mine:
                out["my_choice"] = 0                      # answered (the value itself stays secret until the reveal)
            if g["status"] == "reveal":
                out["my_points"] = mine["points"] if mine else 0
                if kind == "choice":
                    out["correct"] = q["c"]
                    out["counts"] = [sum(1 for a in answers if a["choice"] == i) for i in range(len(q["a"]))]
                else:
                    out["solution"] = {"value": q.get("answer"), "lat": q.get("lat"), "lon": q.get("lon"), "label": q.get("label", ""),
                                       "unit": q.get("unit", ""),
                                       "tr": {k: {f: v[f] for f in ("label", "unit") if f in v} for k, v in (q.get("tr") or {}).items()}}
                    out["guesses"] = sorted(({"id": a["profile_id"], "name": a["name"], "value": a["value"], "lat": a["lat"], "lon": a["lon"],
                                              "miss": miss(q, a), "points": a["points"]} for a in answers),
                                            key=lambda x: (x["miss"] is None, x["miss"] or 0))
        return out

    # ================================================================ family council
    def topics(self, viewer: int) -> list[dict]:
        rows = self.db.q("""SELECT t.*, p.name AS author FROM council_topic t LEFT JOIN profile p ON p.id=t.created_by
                            WHERE t.status!='closed' OR t.closed_at >= datetime('now','localtime','-30 days')
                            ORDER BY t.status='closed', t.id DESC""")
        for t in rows:
            t["result"] = json.loads(t["result"]) if t["result"] else None
            t["proposals"] = self.db.q("""SELECT c.id, c.text, c.profile_id, p.name AS author FROM council_proposal c
                                          LEFT JOIN profile p ON p.id=c.profile_id WHERE c.topic_id=? ORDER BY c.id""", t["id"])
            votes = self.db.q("SELECT profile_id, proposal_id FROM council_vote WHERE topic_id=?", t["id"])
            t["voters"] = [r["name"] for r in self.db.q(
                f"SELECT name FROM profile WHERE id IN ({','.join('?' * len(votes)) or 'NULL'}) ORDER BY name",
                *[v["profile_id"] for v in votes])]
            t["my_vote"] = next((v["proposal_id"] for v in votes if v["profile_id"] == viewer), None)
            if t["status"] == "closed":                       # counts only after the vote – it is secret until then
                for c in t["proposals"]:
                    c["votes"] = sum(1 for v in votes if v["proposal_id"] == c["id"])
        return rows

    def _topic(self, topic_id: int) -> dict:
        t = self.db.q1("SELECT * FROM council_topic WHERE id=?", topic_id)
        if not t:
            raise CommunityError("Unknown topic")
        return t

    @staticmethod
    def _may_manage(t: dict, prof: dict) -> bool:
        return prof["role"] == "parent" or t["created_by"] == prof["id"]

    def open_topic(self, prof: dict, title: str, description: str = "", ideas: list[str] | None = None,
                   majority: str = "relative", both_sides: bool = False, vote_now: bool = False) -> int:
        """A new topic – with first ideas and the rule of the vote; `vote_now` starts the vote right away."""
        title = str(title or "").strip()[:100]
        if not title:
            raise CommunityError("What is the question?")
        if majority not in self.MAJORITIES:
            raise CommunityError("Unknown majority")
        ideas = [x for x in dict.fromkeys(str(i or "").strip()[:120] for i in (ideas or [])) if x][:12]
        if vote_now and len(ideas) < 2:
            raise CommunityError("A vote needs at least two proposals")
        tid = self.db.x("INSERT INTO council_topic(title, description, created_by, majority, both_sides) VALUES(?,?,?,?,?)",
                        title, str(description or "").strip()[:500], prof["id"], majority, int(bool(both_sides)))
        for text in ideas:                        # the first ideas of who opens the topic (not counted against the limit)
            self.db.x("INSERT INTO council_proposal(topic_id, profile_id, text) VALUES(?,?,?)", tid, prof["id"], text)
        if vote_now:
            self.start_vote(prof, tid, majority, both_sides)
        return tid

    def propose(self, prof: dict, topic_id: int, text: str) -> int:
        t = self._topic(topic_id)
        if t["status"] != "collect":
            raise CommunityError("Proposals are closed – the vote has started")
        text = str(text or "").strip()[:120]
        if not text:
            raise CommunityError("Write your proposal")
        n = int(self.db.val("SELECT COUNT(*) FROM council_proposal WHERE topic_id=? AND profile_id=?", topic_id, prof["id"], default=0))
        if n >= MAX_PROPOSALS:
            raise CommunityError("You have made enough proposals for this topic")
        return self.db.x("INSERT INTO council_proposal(topic_id, profile_id, text) VALUES(?,?,?)", topic_id, prof["id"], text)

    def remove_proposal(self, prof: dict, proposal_id: int) -> None:
        c = self.db.q1("SELECT c.*, t.status, t.created_by FROM council_proposal c JOIN council_topic t ON t.id=c.topic_id WHERE c.id=?", proposal_id)
        if not c:
            raise CommunityError("Unknown proposal")
        if c["status"] != "collect":
            raise CommunityError("Proposals are closed – the vote has started")
        if c["profile_id"] != prof["id"] and prof["role"] != "parent":
            raise CommunityError("Only your own proposals")
        self.db.x("DELETE FROM council_proposal WHERE id=?", proposal_id)

    MAJORITIES = ("relative", "absolute", "unanimous")

    def start_vote(self, prof: dict, topic_id: int, majority: str = "relative", both_sides: bool = False) -> None:
        t = self._topic(topic_id)
        if not self._may_manage(t, prof):
            raise CommunityError("Only who opened the topic or a parent can start the vote")
        if t["status"] != "collect":
            raise CommunityError("The vote has already started")
        if int(self.db.val("SELECT COUNT(*) FROM council_proposal WHERE topic_id=?", topic_id, default=0)) < 2:
            raise CommunityError("A vote needs at least two proposals")
        if majority not in self.MAJORITIES:
            raise CommunityError("Unknown majority")
        self.db.x("UPDATE council_topic SET status='vote', majority=?, both_sides=? WHERE id=?", majority, int(bool(both_sides)), topic_id)

    def revote(self, prof: dict, topic_id: int, runoff: bool = False) -> None:
        """No decision: vote once more – all proposals again, or a run-off between the two strongest."""
        t = self._topic(topic_id)
        if not self._may_manage(t, prof):
            raise CommunityError("Only who opened the topic or a parent can start the vote")
        res = json.loads(t["result"]) if t["result"] else {}
        if t["status"] != "closed" or res.get("decided", True):
            raise CommunityError("This topic is decided")
        if runoff:
            keep = [x["id"] for x in sorted(res.get("counts", []), key=lambda x: -x["votes"])[:2]]
            if len(keep) == 2:
                self.db.x(f"DELETE FROM council_proposal WHERE topic_id=? AND id NOT IN ({','.join('?' * len(keep))})", topic_id, *keep)
        self.db.x("DELETE FROM council_vote WHERE topic_id=?", topic_id)
        self.db.x("UPDATE council_topic SET status='vote', result=NULL, closed_at=NULL WHERE id=?", topic_id)

    def vote(self, prof: dict, topic_id: int, proposal_id: int) -> None:
        t = self._topic(topic_id)
        if t["status"] != "vote":
            raise CommunityError("There is no vote on this topic right now")
        if not self.db.q1("SELECT 1 FROM council_proposal WHERE id=? AND topic_id=?", proposal_id, topic_id):
            raise CommunityError("Unknown proposal")
        self.db.x("""INSERT INTO council_vote(topic_id, profile_id, proposal_id) VALUES(?,?,?)
                     ON CONFLICT(topic_id, profile_id) DO UPDATE SET proposal_id=excluded.proposal_id""", topic_id, prof["id"], proposal_id)

    def close(self, prof: dict, topic_id: int) -> dict:
        t = self._topic(topic_id)
        if not self._may_manage(t, prof):
            raise CommunityError("Only who opened the topic or a parent can close the vote")
        if t["status"] != "vote":
            raise CommunityError("There is no vote on this topic right now")
        proposals = self.db.q("SELECT id, text, profile_id FROM council_proposal WHERE topic_id=?", topic_id)
        votes = self.db.q("SELECT profile_id, proposal_id FROM council_vote WHERE topic_id=?", topic_id)
        counts = {c["id"]: sum(1 for v in votes if v["proposal_id"] == c["id"]) for c in proposals}
        best = max(counts.values()) if counts else 0
        winners = [c for c in proposals if best and counts[c["id"]] == best]
        majority = t["majority"] if "majority" in t.keys() else "relative"
        n = len(votes)
        # relative: most votes; absolute: more than half of the votes; unanimous: every vote for the same proposal
        decided = bool(best) and (majority == "relative" or (majority == "absolute" and best * 2 > n)
                                  or (majority == "unanimous" and best == n))
        # both sides: the winner needs at least one parent's and one child's vote
        both = bool(t["both_sides"]) if "both_sides" in t.keys() else False
        sides_ok = True
        if decided and both:
            roles = {r["id"]: r["role"] for r in self.db.q(
                f"SELECT id, role FROM profile WHERE id IN ({','.join('?' * len(votes)) or 'NULL'})", *[v["profile_id"] for v in votes])}
            def sides(pid):
                return {roles.get(v["profile_id"]) for v in votes if v["proposal_id"] == pid}
            winners = [c for c in winners if {"parent", "kid"} <= sides(c["id"])]
            sides_ok = decided = bool(winners)
        if not decided:
            winners = []
        result = {"winners": [c["text"] for c in winners], "votes": best, "voters": n, "tie": len(winners) > 1,
                  "majority": majority, "both_sides": both, "sides_ok": sides_ok, "decided": decided,
                  "counts": [{"id": c["id"], "votes": counts[c["id"]]} for c in proposals]}
        if not self.db.x("UPDATE council_topic SET status='closed', closed_at=datetime('now','localtime'), result=? WHERE id=? AND status='vote'",
                         json.dumps(result, ensure_ascii=False), topic_id):
            return result
        people = {c["profile_id"] for c in proposals} | {v["profile_id"] for v in votes}
        for pid in people:
            if pid is None:
                continue
            mine = any(c["profile_id"] == pid for c in winners)
            self.add_history(pid, "council", {"topic": t["title"], "winners": result["winners"], "tie": result["tie"], "decided": decided,
                                              "votes": best, "voters": len(votes), "mine_won": mine, "topic_id": topic_id})
        return result

    def delete_topic(self, prof: dict, topic_id: int) -> None:
        t = self._topic(topic_id)
        if prof["role"] != "parent" and not (t["created_by"] == prof["id"] and t["status"] == "collect"):
            raise CommunityError("Only a parent can remove this topic")
        with self.db.tx():
            self.db.x("DELETE FROM council_vote WHERE topic_id=?", topic_id)
            self.db.x("DELETE FROM council_proposal WHERE topic_id=?", topic_id)
            self.db.x("DELETE FROM council_topic WHERE id=?", topic_id)

    # ================================================================ history
    def add_history(self, pid: int, kind: str, data: dict) -> None:
        if kind == FAMILY_RESULT:                       # not a history entry: who wears the «No. 1» hat (games call it so)
            return self.family_result(data.get("people") or [], data.get("winners") or [])
        self.db.x("INSERT INTO history(profile_id, kind, data) VALUES(?,?,?)", pid, kind, json.dumps(data, ensure_ascii=False))

    def family_result(self, people: list, winners: list) -> None:
        """The end of a family game (at least two people of the family): the winners wear the «No. 1» hat until the
        next family game they play in; everybody else of the family at the table takes it off. Guests and bots do not count."""
        ids = {int(p) for p in people if str(p).isdigit()}
        rows = [r for r in self.db.q("SELECT id, role, settings FROM profile WHERE archived=0") if r["id"] in ids and r["role"] in ("kid", "parent")]
        if len(rows) < 2:
            return
        win = {int(w) for w in winners if str(w).isdigit()} & {r["id"] for r in rows}
        if not win:                                     # nobody of the family won (a guest, a bot, or no points): no change
            return
        for r in rows:
            st = json.loads(r["settings"] or "{}")
            if bool(st.get("champion")) != (r["id"] in win):
                if r["id"] in win:
                    st["champion"] = True
                else:
                    st.pop("champion", None)
                self.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), r["id"])

    def history(self, pid: int, limit: int = 50) -> list[dict]:
        rows = self.db.q("SELECT id, kind, data, at FROM history WHERE profile_id=? ORDER BY id DESC LIMIT ?", pid, limit)
        for r in rows:
            r["data"] = json.loads(r["data"])
        return rows

    # ================================================================ polls
    def _close_due(self) -> None:
        self.db.x("""UPDATE poll SET status='closed', closed_at=datetime('now','localtime')
                     WHERE status='open' AND closes_at IS NOT NULL AND closes_at <= strftime('%Y-%m-%dT%H:%M','now','localtime')""")

    def polls(self, viewer: int) -> list[dict]:
        """Open polls and those closed in the last 30 days. Results after one's own vote (or when closed)."""
        self._close_due()
        rows = self.db.q("""SELECT p.*, pr.name AS author FROM poll p LEFT JOIN profile pr ON pr.id=p.created_by
                            WHERE p.status='open' OR p.closed_at >= datetime('now','localtime','-30 days')
                            ORDER BY p.status='closed', p.id DESC""")
        for p in rows:
            votes = self.db.q("""SELECT v.profile_id, v.option_id, pr.name FROM poll_vote v LEFT JOIN profile pr ON pr.id=v.profile_id
                                 WHERE v.poll_id=?""", p["id"])
            mine = [v["option_id"] for v in votes if v["profile_id"] == viewer]
            see = bool(mine) or p["status"] == "closed"
            p["multi"], p["anonymous"] = bool(p["multi"]), bool(p["anonymous"])
            p["my_votes"] = mine
            p["voters"] = len({v["profile_id"] for v in votes})
            p["options"] = []
            for o in self.db.q("SELECT id, text FROM poll_option WHERE poll_id=? ORDER BY id", p["id"]):
                opt = {"id": o["id"], "text": o["text"]}
                if see:
                    opt["votes"] = sum(1 for v in votes if v["option_id"] == o["id"])
                    if not p["anonymous"]:
                        opt["names"] = sorted(v["name"] or "?" for v in votes if v["option_id"] == o["id"])
                p["options"].append(opt)
        return rows

    def open_poll(self, prof: dict, question: str, options: list[str], multi: bool = False, anonymous: bool = False,
                  closes_at: str | None = None) -> int:
        question = str(question or "").strip()[:200]
        opts = [o for o in (str(x or "").strip()[:120] for x in options or []) if o]
        opts = list(dict.fromkeys(opts))
        if not question:
            raise CommunityError("What is the question?")
        if not 2 <= len(opts) <= 12:
            raise CommunityError("A poll needs 2 to 12 answers")
        if closes_at:
            closes_at = str(closes_at)[:16]
            if len(closes_at) == 10:
                closes_at += "T23:59"
        pid = self.db.x("INSERT INTO poll(question, created_by, multi, anonymous, closes_at) VALUES(?,?,?,?,?)",
                        question, prof["id"], int(bool(multi)), int(bool(anonymous)), closes_at or None)
        for o in opts:
            self.db.x("INSERT INTO poll_option(poll_id, text) VALUES(?,?)", pid, o)
        return pid

    def poll_vote(self, prof: dict, poll_id: int, option_ids: list[int]) -> None:
        self._close_due()
        p = self.db.q1("SELECT * FROM poll WHERE id=?", poll_id)
        if not p or p["status"] != "open":
            raise CommunityError("This poll is closed")
        valid = {r["id"] for r in self.db.q("SELECT id FROM poll_option WHERE poll_id=?", poll_id)}
        ids = [int(i) for i in dict.fromkeys(option_ids or []) if int(i) in valid]
        if not ids:
            raise CommunityError("Choose an answer")
        if not p["multi"]:
            ids = ids[:1]
        self.db.x("DELETE FROM poll_vote WHERE poll_id=? AND profile_id=?", poll_id, prof["id"])
        for i in ids:
            self.db.x("INSERT INTO poll_vote(poll_id, profile_id, option_id) VALUES(?,?,?)", poll_id, prof["id"], i)

    def close_poll(self, prof: dict, poll_id: int) -> None:
        p = self.db.q1("SELECT * FROM poll WHERE id=?", poll_id)
        if not p:
            raise CommunityError("Unknown poll")
        if prof["role"] != "parent" and p["created_by"] != prof["id"]:
            raise CommunityError("Only who asked or a parent can close the poll")
        self.db.x("UPDATE poll SET status='closed', closed_at=datetime('now','localtime') WHERE id=? AND status='open'", poll_id)

    def delete_poll(self, prof: dict, poll_id: int) -> None:
        p = self.db.q1("SELECT * FROM poll WHERE id=?", poll_id)
        if not p:
            return
        if prof["role"] != "parent" and p["created_by"] != prof["id"]:
            raise CommunityError("Only who asked or a parent can remove the poll")
        for t in ("poll_vote", "poll_option"):
            self.db.x(f"DELETE FROM {t} WHERE poll_id=?", poll_id)
        self.db.x("DELETE FROM poll WHERE id=?", poll_id)

    def summary(self, pid: int) -> dict:
        """For the start page: a quiz to join, votes waiting for this person."""
        g = self._game()
        open_votes = int(self.db.val("""SELECT COUNT(*) FROM council_topic t WHERE t.status='vote'
                                         AND NOT EXISTS(SELECT 1 FROM council_vote v WHERE v.topic_id=t.id AND v.profile_id=?)""", pid, default=0))
        collecting = int(self.db.val("SELECT COUNT(*) FROM council_topic WHERE status='collect'", default=0))
        return {"quiz": ({"status": g["status"], "title": g["quiz"]["title"] if g["quiz"] else "", "joined": pid in g["players"],
                          "langs": json.loads(g["quiz"]["langs"]) if g["quiz"] and g["quiz"].get("langs") else None}
                         if g else None),
                "votes_open": open_votes, "topics_collecting": collecting,
                "polls_open": int(self.db.val("""SELECT COUNT(*) FROM poll p WHERE p.status='open'
                                                  AND (p.closes_at IS NULL OR p.closes_at > strftime('%Y-%m-%dT%H:%M','now','localtime'))
                                                  AND NOT EXISTS(SELECT 1 FROM poll_vote v WHERE v.poll_id=p.id AND v.profile_id=?)""", pid, default=0))}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def miss(q: dict, a) -> float | None:
    """How far an answer is off: the difference (estimate) or the distance in km (pin)."""
    if q.get("kind") == "estimate":
        return None if a["value"] is None else round(abs(float(a["value"]) - float(q["answer"])), 3)
    if q.get("kind") == "pin":
        return None if a["lat"] is None else round(haversine_km(a["lat"], a["lon"], q["lat"], q["lon"]), 1)
    return None


def quiz_question(q: dict) -> dict:
    """A question of the import format (type / question / answers / correct / seconds …) – into the inner format
    (kind / q / a / c / t). Questions already in the inner format pass unchanged."""
    if "q" in q and "question" not in q:
        return q
    kind = {"choice": "choice", "multiple": "choice", "estimate": "estimate", "number": "estimate",
            "map": "pin", "pin": "pin"}.get(str(q.get("type") or q.get("kind") or "choice").lower(), "choice")
    out = {"kind": kind, "q": q.get("question") or q.get("q") or ""}
    if "seconds" in q or "t" in q:
        out["t"] = q.get("seconds", q.get("t"))
    pic = q.get("image") or q.get("img")
    if isinstance(pic, dict):
        t = str(pic.get("type") or "").lower()
        if t.startswith("canton") or pic.get("canton"):
            out["img"] = {"geo": "canton", "id": str(pic.get("canton") or pic.get("id") or "").upper(),
                          "mode": {"canton_map": "map", "canton_arms": "arms"}.get(t, pic.get("mode") or "outline")}
        else:
            out["img"] = {k: pic[k] for k in ("flag", "emoji", "svg") if pic.get(k)}
    if kind == "choice":
        out["a"] = q.get("answers") or q.get("a") or []
        c = q.get("correct", q.get("c", 0))
        if isinstance(c, str) and c in out["a"]:
            c = out["a"].index(c)                      # the right answer given as text
        out["c"] = c
        out.pop("kind")
    elif kind == "estimate":
        out.update({k: q.get(k) for k in ("answer", "min", "max", "unit", "step") if q.get(k) is not None})
    else:
        out.update({k: q.get(k) for k in ("lat", "lon", "map", "label") if q.get(k) is not None})
    trs = q.get("translations")
    if isinstance(trs, dict):                          # {"fr": {"question", "answers", "unit", "label"}}
        out["tr"] = {str(lang).lower()[:2]: {k2: v[k1] for k1, k2 in (("question", "q"), ("answers", "a"), ("unit", "unit"), ("label", "label"))
                                             if v.get(k1) not in (None, "", [])}
                     for lang, v in trs.items() if isinstance(v, dict)}
    return out


def import_langs(quiz: dict) -> dict | None:
    """The languages of an imported quiz: "language" (the base), "languages" (the further ones) and
    "translations": {"fr": {"title"}} – or the languages the questions are translated into."""
    trs = quiz.get("translations") if isinstance(quiz.get("translations"), dict) else {}
    more = list(quiz.get("languages") or [])
    for q in quiz.get("questions") or []:
        if isinstance(q, dict) and isinstance(q.get("translations"), dict):
            more += [k for k in q["translations"] if k not in more]
    more += [k for k in trs if k not in more]
    if not more:
        return None
    return clean_langs({"base": quiz.get("language") or "de", "more": more,
                        "title": {k: (v or {}).get("title") for k, v in trs.items() if isinstance(v, dict)}})


def clean_special(q: dict) -> dict:
    """An estimation question {kind, q, answer, min, max, unit} or a map question {kind, q, lat, lon, map, label}."""
    text = str(q.get("q", "")).strip()[:300]
    if not text:
        raise CommunityError("Every question needs a text")
    t = q.get("t", 30)
    t = max(5, min(120, int(t))) if isinstance(t, (int, float)) else 30
    try:
        if q["kind"] == "estimate":
            lo, hi, ans = float(q["min"]), float(q["max"]), float(q["answer"])
            if not lo < hi or not lo <= ans <= hi:
                raise CommunityError("The answer must lie between minimum and maximum")
            step = float(q.get("step") or (1 if hi - lo >= 20 else 0.1))
            return {"kind": "estimate", "q": text, "answer": ans, "min": lo, "max": hi, "step": step,
                    "unit": str(q.get("unit") or "")[:20], "t": t}
        if q.get("lat") is None or q.get("lon") is None:
            raise CommunityError("Set the place on the map")
        lat, lon = float(q["lat"]), float(q["lon"])
        m = q.get("map") if q.get("map") in ("ch", "europe") else "europe"
        return {"kind": "pin", "q": text, "lat": lat, "lon": lon, "map": m, "label": str(q.get("label") or "")[:60], "t": t}
    except (KeyError, TypeError, ValueError):
        raise CommunityError("Type a number") from None


SVG_MAX = 30_000
MAX_QUESTIONS = 100                 # per quiz – keeps the list of quizzes small for every device
MAX_QUIZ_SVG = 300_000              # all own drawings of one quiz together


def clean_image(img) -> dict | None:
    """A picture of a question:
    - a canton as outline, marked on the map (web/geo/ch.json) or its coat of arms (arms.json): {geo, id, mode}
    - a country flag, big: {flag: "CH"} (web/flags/<code>.svg)
    - a big emoji: {emoji: "🦁"}
    - an own drawing: {svg: "<svg …>"} – shown as an image (<img>), so nothing in it can run."""
    from .quiz_templates import CANTON_NAMES
    from .settings import WEB_DIR
    if not isinstance(img, dict):
        return None
    if img.get("geo") == "canton" and img.get("id") in CANTON_NAMES:
        return {"geo": "canton", "id": img["id"], "mode": img.get("mode") if img.get("mode") in ("map", "arms") else "outline"}
    flag = str(img.get("flag") or "").upper()
    if flag:
        return {"flag": flag} if re.fullmatch(r"[A-Z]{2}", flag) and (WEB_DIR / "flags" / f"{flag}.svg").is_file() else None
    emoji = str(img.get("emoji") or "").strip()
    if emoji:
        return {"emoji": emoji[:16]}
    svg = str(img.get("svg") or "").strip()
    if svg:
        if len(svg) > SVG_MAX or not re.match(r"^(<\?xml[^>]*>\s*)?<svg[\s>]", svg, re.I):
            raise CommunityError("A picture must be an SVG drawing (<svg …>) of at most 30 KB")
        return {"svg": svg}
    return None


def shuffle_answers(q: dict) -> dict:
    order = list(range(len(q["a"])))
    random.shuffle(order)
    out = {**q, "a": [q["a"][i] for i in order], "c": order.index(q["c"])}
    if q.get("tr"):                                  # the translations of the answers in the same new order
        out["tr"] = {k: {**v, **({"a": [v["a"][i] for i in order]} if len(v.get("a") or []) == len(order) else {})}
                     for k, v in q["tr"].items()}
    return out


# ---------------------------------------------------------------- multilingual quizzes
QUIZ_LANGS = ("de", "fr", "it", "en", "es", "nl", "pl", "pt", "sv", "rm")


def clean_langs(v) -> dict | None:
    """{"base": "de", "more": ["fr", …], "title": {"fr": "…"}} – None: a quiz in one language."""
    if not isinstance(v, dict):
        return None
    base = str(v.get("base") or "").lower()[:2]
    if base not in QUIZ_LANGS:
        return None
    more = []
    for x in v.get("more") or []:
        x = str(x).lower()[:2]
        if x in QUIZ_LANGS and x != base and x not in more:
            more.append(x)
    if not more:
        return None
    titles = v.get("title") if isinstance(v.get("title"), dict) else {}
    return {"base": base, "more": more[:9],
            "title": {k: str(titles[k]).strip()[:80] for k in more if str(titles.get(k) or "").strip()}}


def clean_tr(tr, more: list[str] | None, kind: str, keep: list[int] | None = None, answers: list[str] | None = None) -> dict:
    """The texts of a question in the further languages; an empty text falls back to the base language."""
    if not more or not isinstance(tr, dict):
        return {}
    out = {}
    for lang in more:
        v = tr.get(lang)
        if not isinstance(v, dict):
            continue
        item = {}
        if str(v.get("q") or "").strip():
            item["q"] = str(v["q"]).strip()[:300]
        if kind == "choice" and isinstance(v.get("a"), list):
            src = v["a"]
            a = [str(src[j]).strip()[:120] if j < len(src) and str(src[j] or "").strip() else answers[n] for n, j in enumerate(keep or [])]
            if any(x != answers[n] for n, x in enumerate(a)):
                item["a"] = a
        if kind == "estimate" and str(v.get("unit") or "").strip():
            item["unit"] = str(v["unit"]).strip()[:20]
        if kind == "pin" and str(v.get("label") or "").strip():
            item["label"] = str(v["label"]).strip()[:60]
        if item:
            out[lang] = item
    return out


_TEMPLATE_TR: dict[str, dict] | None = None


def template_translations(template_id: str) -> dict:
    """{lang: {"title", "items"}} of a quiz template – from familyquest/quiz_templates_tr/<lang>.json
    (made with tools/quiz_templates_tr.py); a language whose items do not fit the template is left out."""
    global _TEMPLATE_TR
    if _TEMPLATE_TR is None:
        from pathlib import Path
        _TEMPLATE_TR = {}
        for f in sorted((Path(__file__).parent / "quiz_templates_tr").glob("*.json")):
            if f.stem in QUIZ_LANGS and f.stem != "de":
                try:
                    _TEMPLATE_TR[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    pass
    from .quiz_templates import TEMPLATES
    n = len(TEMPLATES.get(template_id, {}).get("questions") or [])
    return {lang: d[template_id] for lang, d in _TEMPLATE_TR.items()
            if isinstance(d.get(template_id), dict) and len(d[template_id].get("items") or []) == n}


def template_questions(t: dict, trs: dict | None = None) -> list[dict]:
    """Template questions are (question, right answer, wrong answers …) – into the quiz format, answers shuffled;
    `trs` (template_translations) gives every question its texts in the other languages."""
    out = []
    for i, item in enumerate(t["questions"]):
        tr = {}
        for lang, d in (trs or {}).items():
            x = d["items"][i]
            tr[lang] = {k: v for k, v in x.items() if k in ("q", "a", "unit", "label") and v}
        if isinstance(item, dict):                       # estimation and map questions
            out.append({**item, "t": item.get("t", t.get("t", 30)), **({"tr": tr} if tr else {})})
            continue
        img = item[-1] if isinstance(item[-1], dict) else None
        q, right, *wrong = item[:-1] if img else item
        a = [right, *wrong][:4]
        for v in tr.values():
            if len(v.get("a") or []) != len(a):
                v.pop("a", None)
        out.append(shuffle_answers({"q": q, "a": a, "c": 0, "t": t.get("t", 20), **({"img": img} if img else {}),
                                    **({"tr": tr} if tr else {})}))
    return out
