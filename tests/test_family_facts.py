"""«Family Quest Facts»: the special family quiz whose questions come from the family's own data (familyquest/facts.py)."""
import json
from datetime import datetime, timedelta

import pytest

from familyquest import facts
from familyquest.community import CommunityError


def family(fq, kids=("Mia", "Leo")):
    ids = {"Papa": fq.db.x("INSERT INTO profile(name, role) VALUES('Papa','parent')")}
    for k in kids:
        ids[k] = fq.db.x("INSERT INTO profile(name, role) VALUES(?, 'kid')", k)
    return ids


def now(days=0, hours=0):
    return (datetime.now() - timedelta(days=days, hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def chore(fq, pid, n, at=None):
    for _ in range(n):
        lid = fq.db.x("INSERT INTO ledger(profile_id, account, amount, event, reason, ref) VALUES(?, 'coins', 10, 'chore_done', 'Tisch', ?)",
                      pid, f"chore:{fq.db.val('SELECT COUNT(*) FROM ledger') + 1}")
        if at:
            fq.db.x("UPDATE ledger SET at=? WHERE id=?", at, lid)


def game(fq, kind, results: dict, at=None, extra=None):
    """One finished game: {pid: place}."""
    at = at or now()
    for pid, place in results.items():
        fq.db.x("INSERT INTO history(profile_id, kind, data, at) VALUES(?,?,?,?)", pid, kind,
                json.dumps({"place": place, "players": len(results), **(extra or {}).get(pid, {})}), at)


def gens(fq):
    out = {}
    for c in facts.Facts(fq).candidates():
        out.setdefault(c["gen"], []).append(c)
    return out


def one(fq, gen):
    g = gens(fq)
    assert gen in g, sorted(g)
    return g[gen][0]


def text(t):
    return facts.tr(t, {})


def test_chores_who_and_how_many(fq):
    ids = family(fq)
    chore(fq, ids["Mia"], 3)
    chore(fq, ids["Leo"], 1)
    q = one(fq, "chores_week")
    assert text(q["right"]) == "Mia" and [text(w) for w in q["wrong"]] == ["Leo"]          # only the kids, not Papa
    assert one(fq, "chores_today")["right"] == "Mia"
    assert one(fq, "chores_week_total")["right"] == "4"
    assert "chores_last_week" not in gens(fq)                                                # nothing happened last week


def test_chores_last_week_and_ties(fq):
    ids = family(fq)
    mon = datetime.now().date() - timedelta(days=datetime.now().weekday())
    last = (mon - timedelta(days=3)).isoformat() + " 10:00:00"
    chore(fq, ids["Leo"], 2, at=last)
    chore(fq, ids["Mia"], 1, at=last)
    chore(fq, ids["Mia"], 2)
    chore(fq, ids["Leo"], 2)                                 # a tie this week: no question
    g = gens(fq)
    assert g["chores_last_week"][0]["right"] == "Leo"
    assert "chores_week" not in g and "chores_today" not in g


def test_one_kid_no_who_of_the_kids(fq):
    ids = family(fq, kids=("Mia",))
    chore(fq, ids["Mia"], 4)
    g = gens(fq)
    assert not {"chores_today", "chores_week", "chores_last_week", "chores_champion"} & set(g)    # «who of the kids»: needs 2 kids
    assert g["chores_week_total"][0]["right"] == "4"                                                # numbers still work


def test_games_counted_per_table_popular_and_wins(fq):
    ids = family(fq)
    m, l, p = ids["Mia"], ids["Leo"], ids["Papa"]
    game(fq, "wuerfel", {m: 1, l: 2}, at=now(hours=1), extra={m: {"points": 210}, l: {"points": 150}})
    game(fq, "wuerfel", {m: 1, p: 2}, at=now(hours=2), extra={m: {"points": 180}, p: {"points": 230}})
    game(fq, "wuerfel", {l: 1, m: 2}, at=now(hours=3))
    game(fq, "jass", {p: 1, l: 2}, at=now(hours=4))
    game(fq, "cards", {m: 1, l: 2}, at=now(days=20), extra={m: {"game": "Tschau Sepp"}, l: {"game": "Tschau Sepp"}})
    g = gens(fq)
    assert g["games_7days"][0]["right"] == "4"
    assert g["games_total"][0]["answer"] == 5 and g["games_total"][0]["min"] == 0 and g["games_total"][0]["max"] >= 10
    assert g["popular_all"][0]["right"] == ("Five Dice",) and ("Five Dice",) not in g["popular_all"][0]["wrong"]
    assert g["wins_all"][0]["right"] == "Mia"                 # 3 wins (Tschau Sepp too) against 1 + 1
    assert g["dice_record"][0]["right"] == "230" and g["dice_record_who"][0]["right"] == "Papa"
    assert text(one(fq, "last_winner")["q"]) == "Who won the last family game (Five Dice)?"


def test_guests_are_one_answer(fq):
    ids = family(fq)
    g1 = fq.db.x("INSERT INTO profile(name, role, archived) VALUES('Oma','guest',2)")
    g2 = fq.db.x("INSERT INTO profile(name, role, archived) VALUES('Opa','guest',2)")
    game(fq, "zeichnen", {g1: 1, ids["Mia"]: 2}, at=now(hours=1))
    game(fq, "zeichnen", {g2: 1, ids["Leo"]: 2}, at=now(hours=2))
    game(fq, "zeichnen", {ids["Mia"]: 1, g1: 2}, at=now(hours=3))
    q = one(fq, "wins_all")
    assert q["right"] == ("A guest",) and "Oma" not in q["wrong"] and "Opa" not in q["wrong"]
    q = one(fq, "played_most")                                # guests 3 entries, Mia 2
    assert q["right"] == ("A guest",)


def test_records_from_the_games(fq):
    ids = family(fq)
    fq.db.set_setting("jump_best", {str(ids["Leo"]): 412, str(ids["Mia"]): 300})
    fq.db.set_setting("klatsch_best", {str(ids["Mia"]): 96})
    g = gens(fq)
    assert g["record_jump"][0]["right"] == "412" and g["record_who_jump"][0]["right"] == "Leo"
    assert g["record_klatsch"][0]["right"] == "96%" and all(int(w[:-1]) <= 100 for w in g["record_klatsch"][0]["wrong"])
    assert text(g["record_who_jump"][0]["q"]) == "Who holds the record in Jump?"


def test_shop_queen_items_and_reward(fq):
    ids = family(fq)
    for _ in range(3):
        fq.rewards.book(ids["Mia"], "coins", -50, "avatar", "Hut", "")
    fq.rewards.book(ids["Leo"], "coins", -100, "redeem", "Ice cream", "redemption:1")
    fq.rewards.book(ids["Leo"], "coins", 100, "refund", "Ice cream", "redemption:1")      # rejected: does not count
    fq.rewards.book(ids["Leo"], "coins", -80, "redeem", "Ice cream", "redemption:2")
    rid = fq.db.val("SELECT id FROM reward WHERE name='Ice cream'")
    fq.db.x("INSERT INTO redemption(profile_id, reward_id, cost, account, status) VALUES(?,?,80,'coins','approved')", ids["Leo"], rid)
    fq.db.x("INSERT INTO redemption(profile_id, reward_id, cost, account, status) VALUES(?,?,80,'coins','approved')", ids["Mia"], rid)
    g = gens(fq)
    assert g["shopping_queen"][0]["right"] == "Mia"
    assert g["shop_items"][0]["right"] == "4"
    assert g["shop_coins"][0]["answer"] == 230
    assert g["reward_top"][0]["right"] == ("Ice cream",)


def test_pets(fq):
    ids = family(fq)
    t = datetime.now()
    def pet(pid, kind, name, days, dead=False):
        born = (t - timedelta(days=days)).isoformat()
        fq.db.x("INSERT INTO pet(profile_id, kind, name, born_at, updated_at, dead_at) VALUES(?,?,?,?,?,?)",
                pid, kind, name, born, t.isoformat(), t.isoformat() if dead else None)
    pet(ids["Mia"], "cat", "Minka", 10)
    pet(ids["Mia"], "cat", "Mauz", 2)
    pet(ids["Leo"], "dog", "Bello", 5)
    pet(ids["Leo"], "dog", "Rex", 30, dead=True)
    pet(ids["Leo"], "degu", "Krümel", 30, dead=True)
    g = gens(fq)
    assert g["pets_total"][0]["right"] == "3"
    assert g["pets_most"][0]["right"] == "Mia"
    assert g["pets_lost"][0]["right"] == "Leo"
    assert g["pet_oldest"][0]["right"].endswith("Minka (Mia)")
    assert g["pet_kind"][0]["right"] == ("Cat",)


def test_xp_only_with_the_family_view_everything(fq):
    ids = family(fq)
    fq.rewards.book(ids["Mia"], "xp", 120, "lesson_done", "", "")
    fq.rewards.book(ids["Leo"], "xp", 40, "lesson_done", "", "")
    g = gens(fq)
    assert g["xp_most"][0]["right"] == "Mia" and g["xp_total"][0]["answer"] == 160 and g["xp_week"][0]["right"] == "Mia"
    assert g["level_of"][0]["right"].isdigit()
    fq.db.set_setting("family_visibility", "percent")
    g = gens(fq)
    assert not {"xp_most", "xp_total", "xp_week", "level_of", "coins_rich"} & set(g)


def test_choose_count_variety_and_focus():
    cands = [{"gen": f"w{i}", "scope": "week", "q": "?", "right": "a", "wrong": ["b"]} for i in range(8)]
    cands += [{"gen": f"a{i}", "scope": "all", "q": "?", "right": "a", "wrong": ["b"]} for i in range(8)]
    cands += [{"gen": "w0", "scope": "week", "q": "!", "right": "a", "wrong": ["b"]}]
    for _ in range(20):
        p = facts.choose(cands, 10, "mixed")
        assert len(p) == 10 and len({x["gen"] for x in p}) == 10                 # one question per kind
    p = facts.choose(cands, 8, "week")
    assert all(x["scope"] == "week" for x in p)
    p = facts.choose(cands, 12, "all")
    assert sum(x["scope"] == "all" for x in p) == 8 and len(p) == 12          # filled up with the other scope
    assert len(facts.choose(cands, 50)) == 16


def test_numbers_and_estimates():
    for n in (0, 1, 3, 17, 250):
        w = facts.near_numbers(n)
        assert len(w) == 3 and n not in w and min(w) >= 0 and len(set(w)) == 3
    assert facts.nice_max(3) == 10 and facts.nice_max(34) == 100 and facts.nice_max(1220) == 5000


def seed_for_api(fq, ids):
    chore(fq, ids["Mia"], 3)
    chore(fq, ids["Leo"], 1)
    game(fq, "wuerfel", {ids["Mia"]: 1, ids["Leo"]: 2}, at=now(hours=1))
    game(fq, "wuerfel", {ids["Mia"]: 1, ids["Leo"]: 2}, at=now(hours=2))
    game(fq, "jass", {ids["Leo"]: 1, ids["Mia"]: 2}, at=now(hours=3))
    fq.db.set_setting("jump_best", {str(ids["Leo"]): 412})


def test_start_via_api_multilingual_and_permissions(client):
    from tests.test_api import setup_family
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.get("/api/community/quizzes/facts", headers=hm).json()["enabled"] is True
    # an empty family: nothing to ask yet
    r = client.post("/api/community/quiz/facts/start", json={"count": 10}, headers=hm)
    assert r.status_code == 400 and "Not enough" in r.json()["detail"]
    seed_for_api(fq, {"Mia": mia, "Leo": leo})
    r = client.post("/api/community/quiz/facts/start", json={"count": 5, "focus": "week", "lang": "de-CH"}, headers=hm)
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["title"] == "Family Quest Facts" and st["total"] == 5 and st["host"] == mia
    assert st["langs"]["base"] == "de" and set(st["langs"]["more"]) == {"en", "fr", "it", "es", "nl", "pl", "pt", "sv"}
    g = fq.community._game()
    assert len(g["questions"]) == 5 and all(set(q["tr"]) == set(st["langs"]["more"]) for q in g["questions"])
    # not in the list of quizzes; a second quiz cannot start meanwhile
    assert all(q["title"] != "Family Quest Facts" for q in client.get("/api/community/quizzes", headers=hm).json())
    assert client.post("/api/community/quiz/facts/start", json={}, headers=hl).status_code == 400
    # only the starter (or a parent) leads; everybody plays it like any quiz
    assert client.post("/api/community/quiz/next", headers=hl).status_code == 403
    client.post("/api/community/quiz/join", headers=hl)
    st = client.post("/api/community/quiz/next", headers=hm).json()
    q = g["questions"][0]
    if (q.get("kind") or "choice") == "choice":
        assert client.post("/api/community/quiz/answer", json={"idx": 0, "choice": q["c"]}, headers=hl).status_code == 200
        assert fq.db.val("SELECT points FROM quiz_answer WHERE profile_id=?", leo) > 0
    client.post("/api/community/quiz/abort", headers=hm)
    # the parents switch it off
    client.put("/api/parent/settings", json={"quiz_facts": False}, headers=ph)
    assert client.get("/api/community/quizzes/facts", headers=hm).json()["enabled"] is False
    assert client.post("/api/community/quiz/facts/start", json={}, headers=hm).status_code == 403


def test_texts_in_swiss_and_standard_german(fq):
    ids = family(fq)
    chore(fq, ids["Mia"], 3)
    chore(fq, ids["Leo"], 1)
    item = one(fq, "chores_week")
    base, dicts = facts.dictionaries(fq, "de-CH")
    assert base == "de" and "Ämtli" in facts.to_quiz(item, base, dicts)["q"]
    base, dicts = facts.dictionaries(fq, "de-DE")
    assert "Aufgaben" in facts.to_quiz(item, base, dicts)["q"]
    base, dicts = facts.dictionaries(fq, "fr-FR")
    q = facts.to_quiz(item, base, dicts)
    assert base == "fr" and "tâches" in q["q"] and "Aufgaben" in q["tr"]["de"]["q"] and q["tr"]["en"]["q"].startswith("Who of the kids")
    item = one(fq, "chores_week_total")
    assert facts.to_quiz(item, "de", facts.dictionaries(fq, "de-CH")[1])["a"]


def test_every_template_is_translated():
    import re
    from pathlib import Path
    src = Path(facts.__file__).read_text(encoding="utf-8")
    keys = set(re.findall(r'_t\("((?:[^"\\]|\\.)*)"\)', src))
    web = Path(facts.__file__).parent.parent / "web" / "i18n"
    for lang in ("de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"):
        d = json.loads((web / f"{lang}.json").read_text(encoding="utf-8"))
        assert not [k for k in keys if k not in d], lang


def test_build_fails_softly_without_data(fq):
    family(fq)
    with pytest.raises(CommunityError):
        facts.build(fq, 10)
