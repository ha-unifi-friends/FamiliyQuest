import json
from datetime import date

import pytest

from familyquest.learning.leitner import next_state, stars


@pytest.fixture
def kid(fq, kid):
    """Mia also learns with the German-only packs (optional: Parent area › Learning packs › More packs)."""
    for pid in ("deutsch-5kl", "geo-tg", "tg-5-klasse"):
        fq.packs.activate(kid, pid)
    return kid


def _solve(fq, sid):
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", sid)["data"])
    answers = []
    for st in data["steps"]:
        sol = st["solution"]
        answers.append({"paare": sol.get("pairs"), "zuordnen": sol.get("map"), "karteikarte": "correct"}.get(st["kind"], sol.get("answer")))
    return answers


def test_leitner():
    d = date(2026, 11, 15)
    assert next_state(0, "correct", d) == (1, "2026-11-16")
    assert next_state(4, "correct", d) == (5, "2026-12-01")
    assert next_state(5, "correct", d)[0] == 5
    assert next_state(4, "wrong", d) == (1, "2026-11-15")
    assert next_state(3, "almost", d) == (3, "2026-11-16")
    assert stars([]) == 0 and stars([5, 5]) == 5 and stars([0, 2, 4]) == 2


def test_packs_loaded(fq):
    ids = {p.id for p in fq.packs.all()}
    assert {"mathe-5kl", "franz-5kl-la-maison", "deutsch-5kl", "geo-tg", "tg-5-klasse"} <= ids


def test_lesson_flow_and_rewards(fq, kid):
    s = fq.learning.build(kid, "path", "franz-5kl-la-maison", "zimmer", seed=1)
    assert all("solution" not in st and "answer" not in st for st in s["steps"])
    for i, a in enumerate(_solve(fq, s["id"])):
        r = fq.learning.answer(s["id"], kid, i, a, 1200)
        assert r["correct"]
    res = fq.learning.finish(s["id"], kid)
    assert res["right"] == res["total"] and res["completed"]
    assert res["gained"]["xp"] >= 10 + res["total"]
    assert res["gained"]["coins"] == 10 + 5               # lesson finished + perfect lesson (no mistake)
    assert any(b["id"] == "first_lesson" for b in res["badges"])
    # finishing twice does not book twice
    again = fq.learning.finish(s["id"], kid)
    assert again == res
    assert fq.rewards.balance(kid, "coins") == 15                 # booked only once (10 + 5 perfect)


def test_wrong_answers_come_back(fq, kid):
    s = fq.learning.build(kid, "path", "deutsch-5kl", "artikel", seed=3)
    for i, st in enumerate(s["steps"]):
        fq.learning.answer(s["id"], kid, i, "xyz", 500)
    fq.learning.finish(s["id"], kid)
    rows = fq.db.q("SELECT * FROM item_state WHERE profile_id=?", kid)
    assert rows and all(r["box"] == 1 and r["due"] == date.today().isoformat() for r in rows)
    s2 = fq.learning.build(kid, "path", "deutsch-5kl", "artikel", seed=4)
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s2["id"])["data"])
    wrong = {r["item_key"] for r in rows}
    first = {k for st in data["steps"][: len(wrong)] for k in st["keys"]}
    assert first & wrong


def test_generator_lesson_and_daily(fq, kid):
    s = fq.learning.build(kid, "path", "mathe-5kl", "einmaleins", seed=2)
    assert all(st["kind"] == "rechnen" for st in s["steps"])
    d = fq.learning.build(kid, "daily", seed=5)
    assert len(d["steps"]) >= 5


def test_drag_and_drop_unit(fq, kid):
    s = fq.learning.build(kid, "path", "deutsch-5kl", "wortarten", seed=1)
    assert s["steps"][0]["kind"] == "zuordnen"
    st = s["steps"][0]
    assert st["targets"] and st["chips"]
    answers = _solve(fq, s["id"])
    r = fq.learning.answer(s["id"], kid, 0, answers[0], 3000)
    assert r["correct"] and r["score"][0] == r["score"][1]
    # one wrong drop
    s = fq.learning.build(kid, "path", "deutsch-5kl", "wortarten", seed=9)
    a = dict(_solve(fq, s["id"])[0])
    k = next(iter(a))
    a[k] = "nope"
    r = fq.learning.answer(s["id"], kid, 0, a, 3000)
    assert not r["correct"] and r["score"][0] == r["score"][1] - 1


def test_units_open_by_default(fq, kid):
    s = fq.learning.build(kid, "path", "geo-tg", "gewaesser", seed=1)      # straight to station 2
    assert s["steps"]
    prog = fq.learning.pack_progress(kid, fq.packs.get("geo-tg"))
    assert all(u["unlocked"] for u in prog["units"])


def test_units_unlock_in_order_when_wanted(fq, kid):
    import pytest
    from familyquest.learning.lesson import LearnError
    from familyquest.packs.loader import pack_dict, parse_doc
    data = fq.packs.raw("franz-5kl-la-maison")
    data["pfad"] = True
    fq.packs.upsert(parse_doc(data), "edited", force=True)
    with pytest.raises(LearnError):
        fq.learning.build(kid, "path", "franz-5kl-la-maison", "famille")
    prog = fq.learning.pack_progress(kid, fq.packs.get("franz-5kl-la-maison"))
    assert prog["units"][0]["unlocked"] and not prog["units"][1]["unlocked"]


def test_daily_goal_and_streak(fq, kid):
    fq.rewards.book(kid, "xp", 60, "test")
    out = fq.rewards.emit(kid, "answer_correct")
    assert any(b.get("event") == "daily_goal" for b in out)
    assert fq.rewards.streak(kid) == 1
    assert fq.rewards.emit(kid, "answer_correct")  # goal not booked twice
    assert sum(1 for r in fq.db.q("SELECT * FROM ledger WHERE profile_id=? AND event='daily_goal'", kid)) == 1


def test_daily_limit(fq, kid):
    for _ in range(8):
        fq.rewards.emit(kid, "lesson_done")
    booked = fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account='coins' AND event='lesson_done'", kid)
    assert booked == 50                                # daily limit of the default rule


def test_badge_awarded_once(fq, kid):
    first = fq.rewards.award(kid, "quiz_ace")
    again = fq.rewards.award(kid, "quiz_ace")
    assert first and again == []
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE profile_id=? AND event='badge'", kid) == 1


def test_card_box(fq, kid):
    pack = fq.packs.get("franz-5kl-la-maison")
    prog = fq.learning.pack_progress(kid, pack)
    total = sum(u["count"] for u in prog["units"])
    assert prog["boxes"] == [total, 0, 0, 0, 0, 0]
    s = fq.learning.build(kid, "cards", "franz-5kl-la-maison", seed=1)       # whole pack: card box
    assert s["steps"] and all(st["kind"] == "karteikarte" for st in s["steps"])
    for i, _ in enumerate(s["steps"]):
        fq.learning.answer(s["id"], kid, i, "correct" if i % 2 else "wrong")
    fq.learning.finish(s["id"], kid)
    prog = fq.learning.pack_progress(kid, pack)
    assert prog["boxes"][1] > 0 and prog["boxes"][0] < total and sum(prog["boxes"]) == total
    # due (wrong) cards come first in the next card-box session
    due = {r["item_key"] for r in fq.db.q("SELECT item_key FROM item_state WHERE profile_id=? AND due<=date('now','localtime')", kid)}
    s2 = fq.learning.build(kid, "cards", "franz-5kl-la-maison", seed=2)
    import json
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s2["id"])["data"])
    assert {st["keys"][0] for st in data["steps"][: len(due)]} == due
    # one unit only
    s3 = fq.learning.build(kid, "cards", "franz-5kl-la-maison", "moebel", seed=3)
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s3["id"])["data"])
    assert {st["unit"] for st in data["steps"]} == {"moebel"}


def test_badge_overview(fq, kid):
    s = fq.learning.build(kid, "path", "mathe-5kl", "einmaleins", seed=1)
    import json
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s["id"])["data"])
    for i, st in enumerate(data["steps"]):
        fq.learning.answer(s["id"], kid, i, st["solution"]["answer"])
    fq.learning.finish(s["id"], kid)
    badges = {b["id"]: b for b in fq.badge_overview(kid)}
    assert badges["first_lesson"]["earned"] and badges["first_lesson"]["value"] == 1
    tl = badges["ten_lessons"]
    assert not tl["earned"] and tl["value"] == 1 and tl["target"] == 10 and tl["how"] == "Finish 10 lessons"
    assert badges["french_star"]["unlocks"] == ["Beret"]
    assert badges["times_tables_pro"]["value"] >= 1
    assert list(badges)[0] == "first_lesson"                      # earned ones first


def test_answer_language_is_shown(fq, kid):
    s = fq.learning.build(kid, "cards", "engl-5kl-unit-1", seed=1)
    assert all(st["answer_lang"] == "en" for st in s["steps"])
    s = fq.learning.build(kid, "path", "deutsch-5kl", "artikel", seed=1)
    assert all(not st.get("answer_lang") for st in s["steps"])          # no language pack → no hint
