"""Etappe H: family quiz, family council, personal history."""
import time

import pytest


def family(client):
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()
    ph = {"X-FQ-Parent": r["parent_token"]}
    papa = r["profile"]["id"] if "profile" in r else None
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    leo = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=ph).json()["id"]
    tok = lambda pid: {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid}).json()["token"]}
    return ph, tok(mia), tok(leo), mia, leo


QUIZ = {"title": "Tiere", "questions": [
    {"q": "Wie viele Beine hat eine Spinne?", "a": ["6", "8", "10"], "c": 1, "t": 10},
    {"q": "Welches Tier bellt?", "a": ["Katze", "Hund"], "c": 1, "t": 10},
]}


def test_quiz_game(client):
    ph, mia_h, leo_h, mia, leo = family(client)
    assert client.post("/api/community/quizzes", json={"title": "x", "questions": [{"q": "?", "a": ["nur eine"], "c": 0}]}, headers=ph).status_code == 400
    qid = client.post("/api/community/quizzes", json=QUIZ, headers=ph).json()["id"]
    assert client.get("/api/community/quiz", headers=mia_h).json() is None
    st = client.post("/api/community/quiz/start", json={"quiz_id": qid, "shuffle": False}, headers=ph).json()
    assert st["status"] == "lobby" and st["total"] == 2
    assert client.post("/api/community/quiz/start", json={"quiz_id": qid}, headers=ph).status_code == 400   # one game at a time
    assert client.get("/api/me", headers=mia_h).json()["community"]["quiz"]["status"] == "lobby"
    for h in (mia_h, leo_h):
        assert client.post("/api/community/quiz/join", headers=h).json()["joined"]
    assert client.post("/api/community/quiz/next", headers=mia_h).status_code == 403          # Papa leads, not Mia
    # the host (Papa) plays too: three players
    st = client.post("/api/community/quiz/next", headers=ph).json()
    assert st["status"] == "question" and st["idx"] == 0 and "correct" not in st and st["question"]["a"] == ["6", "8", "10"]
    assert client.post("/api/community/quiz/answer", json={"idx": 0, "choice": 1}, headers=mia_h).json()["my_choice"] == 1
    assert client.post("/api/community/quiz/answer", json={"idx": 0, "choice": 2}, headers=mia_h).status_code == 400  # only once
    client.post("/api/community/quiz/answer", json={"idx": 0, "choice": 0}, headers=leo_h)
    st = client.post("/api/community/quiz/answer", json={"idx": 0, "choice": 1}, headers=ph).json()
    # everybody answered → the answer is revealed at once
    assert st["status"] == "reveal" and st["correct"] == 1 and st["counts"] == [1, 2, 0] and st["my_points"] > 500
    client.post("/api/community/quiz/next", headers=ph)
    client.post("/api/community/quiz/answer", json={"idx": 1, "choice": 1}, headers=mia_h)
    time.sleep(0.05)
    client.post("/api/community/quiz/answer", json={"idx": 1, "choice": 1}, headers=leo_h)
    client.post("/api/community/quiz/next", headers=ph)                    # Papa does not answer: reveal …
    st = client.post("/api/community/quiz/next", headers=ph).json()       # … and the end
    assert st["status"] == "done"
    ranking = {p["name"]: p for p in st["players"]}
    assert ranking["Mia"]["place"] == 1 and ranking["Mia"]["right"] == 2 and ranking["Leo"]["right"] == 1
    # the history shows it, the reward events were emitted
    hist = client.get("/api/community/history", headers=mia_h).json()
    assert hist[0]["kind"] == "quiz" and hist[0]["data"]["won"] and hist[0]["data"]["place"] == 1 and hist[0]["data"]["of"] == 3
    assert client.get(f"/api/community/history?profile_id={mia}", headers=leo_h).status_code == 403
    assert client.get(f"/api/community/history?profile_id={mia}", headers=ph).json()[0]["data"]["quiz"] == "Tiere"
    fq = client.app.state.fq
    assert fq.db.val("SELECT COUNT(*) FROM quiz_game WHERE status!='done'") == 0
    # the quiz list knows it was played: how often, when, who won
    q = next(x for x in client.get("/api/community/quizzes", headers=mia_h).json() if x["id"] == qid)
    assert q["games"] == 1 and q["last_played"] and q["last_winner"]["name"] == "Mia"


def test_quiz_time_runs_out(client, monkeypatch):
    from familyquest import community
    ph, mia_h, leo_h, mia, leo = family(client)
    qid = client.post("/api/community/quizzes", json=QUIZ, headers=ph).json()["id"]
    client.post("/api/community/quiz/start", json={"quiz_id": qid, "shuffle": False}, headers=ph)
    client.post("/api/community/quiz/join", headers=mia_h)
    client.post("/api/community/quiz/next", headers=ph)
    real = time.time
    monkeypatch.setattr(community.time, "time", lambda: real() + 11)
    st = client.get("/api/community/quiz", headers=mia_h).json()
    assert st["status"] == "reveal"
    assert client.post("/api/community/quiz/answer", json={"idx": 0, "choice": 1}, headers=mia_h).status_code == 400


def test_family_council(client):
    ph, mia_h, leo_h, mia, leo = family(client)
    tid = client.post("/api/community/council", json={"title": "Was machen wir am Samstag?"}, headers=mia_h).json()["id"]
    a = client.post(f"/api/community/council/{tid}/proposals", json={"text": "Zoo"}, headers=mia_h).json()["id"]
    b = client.post(f"/api/community/council/{tid}/proposals", json={"text": "Schwimmbad"}, headers=leo_h).json()["id"]
    assert client.post(f"/api/community/council/{tid}/vote", json={"proposal_id": a}, headers=leo_h).status_code == 400  # not yet
    assert client.post(f"/api/community/council/{tid}/start-vote", headers=leo_h).status_code == 400  # only Mia or a parent
    assert client.post(f"/api/community/council/{tid}/start-vote", headers=mia_h).status_code == 200
    assert client.post(f"/api/community/council/{tid}/proposals", json={"text": "Kino"}, headers=leo_h).status_code == 400
    assert client.get("/api/me", headers=leo_h).json()["community"]["votes_open"] == 1
    client.post(f"/api/community/council/{tid}/vote", json={"proposal_id": b}, headers=leo_h)
    client.post(f"/api/community/council/{tid}/vote", json={"proposal_id": a}, headers=leo_h)     # changed his mind
    client.post(f"/api/community/council/{tid}/vote", json={"proposal_id": a}, headers=ph)
    t = next(x for x in client.get("/api/community/council", headers=mia_h).json() if x["id"] == tid)
    assert t["status"] == "vote" and "votes" not in t["proposals"][0] and t["voters"] == ["Leo", "Papa"]
    res = client.post(f"/api/community/council/{tid}/close", headers=ph).json()
    assert res["winners"] == ["Zoo"] and res["votes"] == 2 and not res["tie"]
    t = next(x for x in client.get("/api/community/council", headers=mia_h).json() if x["id"] == tid)
    assert {c["text"]: c["votes"] for c in t["proposals"]} == {"Zoo": 2, "Schwimmbad": 0}
    mine = client.get("/api/community/history", headers=mia_h).json()[0]
    assert mine["kind"] == "council" and mine["data"]["mine_won"] and mine["data"]["winners"] == ["Zoo"]
    assert not client.get("/api/community/history", headers=leo_h).json()[0]["data"]["mine_won"]
    assert client.delete(f"/api/community/council/{tid}", headers=leo_h).status_code == 400
    assert client.delete(f"/api/community/council/{tid}", headers=ph).status_code == 200


def test_children_make_quizzes_and_templates(client):
    from familyquest.quiz_templates import TEMPLATES
    ph, mia_h, leo_h, mia, leo = family(client)
    for tid, t in TEMPLATES.items():                       # every template is a valid quiz
        assert len(t["questions"]) >= 10, tid
        for q in t["questions"]:
            if isinstance(q, dict):                                 # estimation / map question
                assert q["kind"] in ("estimate", "pin"), (tid, q)
                continue
            q = q[:-1] if isinstance(q[-1], dict) else q            # a picture (e.g. a canton) may come last
            assert len(q) == 5 and len(set(q[1:])) == 4, (tid, q)   # right answer + 3 different wrong ones
    tpl = client.get("/api/community/templates", headers=mia_h).json()
    assert {"schweizer-gewaesser", "hauptstaedte-europa", "laenderflaggen"} <= {t["id"] for t in tpl}
    qid = client.post("/api/community/quizzes/from-template", json={"template": "hauptstaedte-europa"}, headers=mia_h).json()["id"]
    quiz = next(q for q in client.get("/api/community/quizzes", headers=leo_h).json() if q["id"] == qid)
    assert quiz["author"] == "Mia" and quiz["questions"][0]["q"].startswith("Was ist die Hauptstadt")
    first = quiz["questions"][0]
    assert first["a"][first["c"]] == "Bern"                 # answers shuffled, the right one still marked
    # only Mia (or a parent) changes her quiz
    assert client.put(f"/api/community/quizzes/{qid}", json={"title": "Meins", "questions": quiz["questions"]}, headers=leo_h).status_code == 400
    assert client.put(f"/api/community/quizzes/{qid}", json={"title": "Mias Quiz", "questions": quiz["questions"]}, headers=mia_h).status_code == 200
    own = client.post("/api/community/quizzes", json=QUIZ, headers=leo_h).json()["id"]
    assert client.delete(f"/api/community/quizzes/{own}", headers=mia_h).status_code == 400
    # Mia starts and leads a game with 5 of the questions
    st = client.post("/api/community/quiz/start", json={"quiz_id": qid, "count": 5}, headers=mia_h).json()
    assert st["host"] == mia and st["total"] == 5
    client.post("/api/community/quiz/join", headers=leo_h)
    assert client.post("/api/community/quiz/next", headers=leo_h).status_code == 403
    assert client.post("/api/community/quiz/next", headers=mia_h).json()["status"] == "question"
    assert client.post("/api/community/quiz/abort", headers=ph).status_code == 200            # a parent may always step in


def test_games_can_be_switched_off(client):
    ph, mia_h, leo_h, mia, leo = family(client)
    assert client.get("/api/me", headers=mia_h).json()["games"] is True
    client.put("/api/parent/games", json={"mode": "some", "profiles": [leo]}, headers=ph)
    assert client.get("/api/me", headers=mia_h).json()["games"] is False
    assert client.get("/api/community/quiz", headers=mia_h).status_code == 403
    assert client.post("/api/community/bingo/start", json={}, headers=mia_h).status_code == 403
    assert client.post("/api/community/bingo/start", json={}, headers=leo_h).status_code == 200
    client.put("/api/parent/games", json={"mode": "off"}, headers=ph)
    assert client.get("/api/community/bingo", headers=leo_h).status_code == 403
    assert client.get("/api/community/bingo", headers=ph).status_code == 200          # parents always
    assert client.get("/api/community/council", headers=mia_h).status_code == 200     # the council is not a game
    assert client.put("/api/parent/games", json={"mode": "maybe"}, headers=ph).status_code == 400


def test_council_majority_rules(fq):
    c = fq.community
    pa = {"id": fq.db.x("INSERT INTO profile(name, role) VALUES('Papa','parent')"), "role": "parent"}
    kids = [{"id": fq.db.x("INSERT INTO profile(name) VALUES(?)", n), "role": "kid"} for n in ("A", "B", "C")]
    t = c.open_topic(pa, "Samstag?")
    a = c.propose(pa, t, "Zoo"); b = c.propose(kids[0], t, "Kino"); z = c.propose(kids[1], t, "Baden")
    c.start_vote(pa, t, "absolute")
    for prof, pick in ((pa, a), (kids[0], b), (kids[1], z), (kids[2], a)):
        c.vote(prof, t, pick)
    r = c.close(pa, t)
    assert not r["decided"] and r["winners"] == [] and r["votes"] == 2 and r["voters"] == 4      # 2 of 4 is not more than half
    c.revote(pa, t, runoff=True)                                      # run-off: Zoo against one of the others
    left = [x["text"] for x in c.topics(pa["id"])[0]["proposals"]]
    assert len(left) == 2 and "Zoo" in left
    for prof in (pa, kids[0], kids[2]):
        c.vote(prof, t, a)
    assert c.close(pa, t)["winners"] == ["Zoo"]
    t2 = c.open_topic(pa, "Pizza?")
    y = c.propose(pa, t2, "Ja"); n = c.propose(pa, t2, "Nein")
    c.start_vote(pa, t2, "unanimous")
    c.vote(pa, t2, y); c.vote(kids[0], t2, n)
    assert not c.close(pa, t2)["decided"]
    import pytest
    with pytest.raises(Exception):
        c.start_vote(pa, c.open_topic(pa, "x"), "dictator")


def test_council_parents_and_children(fq):
    c = fq.community
    pa = {"id": fq.db.x("INSERT INTO profile(name, role) VALUES('Papa','parent')"), "role": "parent"}
    ma = {"id": fq.db.x("INSERT INTO profile(name, role) VALUES('Mama','parent')"), "role": "parent"}
    kid = {"id": fq.db.x("INSERT INTO profile(name) VALUES('Mia')"), "role": "kid"}
    t = c.open_topic(pa, "Ferien?")
    berg = c.propose(pa, t, "Berge"); meer = c.propose(kid, t, "Meer")
    c.start_vote(pa, t, "relative", both_sides=True)
    c.vote(pa, t, berg); c.vote(ma, t, berg); c.vote(kid, t, meer)
    r = c.close(pa, t)
    assert not r["decided"] and r["sides_ok"] is False                 # «Berge» has no child's vote
    c.revote(pa, t)
    c.vote(pa, t, berg); c.vote(ma, t, meer); c.vote(kid, t, meer)
    assert c.close(pa, t)["winners"] == ["Meer"]


def test_polls(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.post("/api/community/polls", json={"question": "Pizza?", "options": ["Ja"]}, headers=hm).status_code == 400
    pid = client.post("/api/community/polls", json={"question": "Welche Pizza?", "options": ["Margherita", "Salami", "Hawaii", "Salami"],
                                                    "multi": True}, headers=hm).json()["id"]
    p = client.get("/api/community/polls", headers=hl).json()[0]
    assert len(p["options"]) == 3 and "votes" not in p["options"][0]                  # results only after voting
    assert client.get("/api/me", headers=hl).json()["community"]["polls_open"] == 1
    opts = [o["id"] for o in p["options"]]
    client.post(f"/api/community/polls/{pid}/vote", json={"options": opts[:2]}, headers=hl)
    client.post(f"/api/community/polls/{pid}/vote", json={"options": [opts[1]]}, headers=hm)
    p = client.get("/api/community/polls", headers=hl).json()[0]
    assert [o["votes"] for o in p["options"]] == [1, 2, 0] and p["options"][1]["names"] == ["Leo", "Mia"] and p["voters"] == 2
    assert client.post(f"/api/community/polls/{pid}/close", headers=hl).status_code == 400    # only who asked / a parent
    client.post(f"/api/community/polls/{pid}/close", headers=hm)
    assert client.post(f"/api/community/polls/{pid}/vote", json={"options": [opts[0]]}, headers=hl).status_code == 400
    # anonymous and with a closing time in the past → closed at once
    a = client.post("/api/community/polls", json={"question": "Ferien?", "options": ["Berge", "Meer"], "anonymous": True,
                                                  "closes_at": "2020-01-01T10:00"}, headers=hm).json()["id"]
    p = next(x for x in client.get("/api/community/polls", headers=hm).json() if x["id"] == a)
    assert p["status"] == "closed" and "names" not in p["options"][0]


def test_canton_picture_templates(client):
    import json, pathlib
    from test_api import setup_family
    from familyquest.quiz_templates import CANTON_NAMES
    geo = json.loads((pathlib.Path(__file__).parent.parent / "family_quest/app/web/geo/ch.json").read_text())
    assert set(geo["cantons"]) == set(CANTON_NAMES) and all(c["d"].startswith("M") for c in geo["cantons"].values())
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    q = client.post("/api/community/quizzes/from-template", json={"template": "kantone-umrisse"}, headers=h).json()
    client.post("/api/community/quiz/start", json={"quiz_id": q["id"], "count": 5}, headers=h)
    client.post("/api/community/quiz/next", headers=h)
    st = client.get("/api/community/quiz", headers=h).json()
    img = st["question"]["img"]
    assert img["geo"] == "canton" and img["mode"] == "outline" and CANTON_NAMES[img["id"]] in st["question"]["a"]
    assert client.get("/geo/ch.json").status_code == 200
    arms = json.loads((pathlib.Path(__file__).parent.parent / "family_quest/app/web/geo/arms.json").read_text())
    assert set(arms["arms"]) == set(CANTON_NAMES) and "<script" not in json.dumps(arms)
    from familyquest.quiz_templates import TEMPLATES
    qs = TEMPLATES["kantone-wappen"]["questions"]
    assert len(qs) == 26 and all(q[1] not in q[2:5] and len(set(q[1:5])) == 4 for q in qs)
    qid = client.post("/api/community/quizzes/from-template", json={"template": "kantone-wappen"}, headers=h).json()["id"]
    mine = [x for x in client.get("/api/community/quizzes", headers=h).json() if x["id"] == qid][0]
    assert all(x["img"]["mode"] == "arms" for x in mine["questions"])


def test_estimation_and_map_questions(client):
    from test_api import setup_family
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    qid = client.post("/api/community/quizzes", json={"title": "Mix", "questions": [
        {"kind": "estimate", "q": "Wie hoch ist das Matterhorn?", "answer": 4478, "min": 2000, "max": 6000, "unit": "m"},
        {"kind": "pin", "q": "Wo liegt Berlin?", "lat": 52.52, "lon": 13.405, "map": "europe", "label": "Berlin"}]}, headers=hm).json()["id"]
    assert client.post("/api/community/quizzes", json={"title": "x", "questions": [
        {"kind": "estimate", "q": "?", "answer": 9, "min": 1, "max": 5}]}, headers=hm).status_code == 400
    client.post("/api/community/quiz/start", json={"quiz_id": qid, "shuffle": False}, headers=hm)
    client.post("/api/community/quiz/join", headers=hl)
    client.post("/api/community/quiz/next", headers=hm)
    st = client.get("/api/community/quiz", headers=hl).json()
    assert st["question"]["kind"] == "estimate" and st["question"]["max"] == 6000 and "answer" not in st["question"]
    client.post("/api/community/quiz/answer", json={"idx": 0, "value": 4400}, headers=hm)
    client.post("/api/community/quiz/answer", json={"idx": 0, "value": 3000}, headers=hl)
    st = client.get("/api/community/quiz", headers=hm).json()
    assert st["status"] == "reveal" and st["solution"]["value"] == 4478
    assert [(g["name"], g["points"]) for g in st["guesses"]] == [("Mia", 1000), ("Leo", 500)]
    client.post("/api/community/quiz/next", headers=hm)
    st = client.get("/api/community/quiz", headers=hm).json()
    assert st["question"]["kind"] == "pin" and st["question"]["map"] == "europe"
    client.post("/api/community/quiz/answer", json={"idx": 1, "lat": 48.86, "lon": 2.35}, headers=hm)        # Paris
    client.post("/api/community/quiz/answer", json={"idx": 1, "lat": 52.4, "lon": 13.1}, headers=hl)         # near Berlin
    st = client.get("/api/community/quiz", headers=hm).json()
    g = st["guesses"]
    assert g[0]["name"] == "Leo" and g[0]["miss"] < 30 and 850 < g[1]["miss"] < 900
    tpl = {t["id"] for t in client.get("/api/community/templates", headers=hm).json()}
    assert {"schaetzfragen", "wo-liegt-schweiz", "wo-liegt-europa"} <= tpl


def test_stopping_games_returns_a_state(client):
    from test_api import setup_family
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    q = client.post("/api/community/quizzes/from-template", json={"template": "schaetzfragen"}, headers=h).json()
    client.post("/api/community/quiz/start", json={"quiz_id": q["id"], "count": 5}, headers=h)
    r = client.post("/api/community/quiz/abort", headers=h)
    assert r.status_code == 200 and (r.json() is None or "players" in r.json())
    after = client.get("/api/community/quiz", headers=h).json()
    assert after is None or (after["status"] == "done" and isinstance(after["players"], list))
    client.post("/api/community/bingo/start", json={}, headers=h)
    r = client.post("/api/community/bingo/end", headers=h).json()
    assert r is None or "players" in r
    client.post("/api/community/cards/tschau/start", json={"solo": True, "bots": 1}, headers=h)
    r = client.post("/api/community/cards/tschau/end", headers=h).json()
    assert r is None or "players" in r
