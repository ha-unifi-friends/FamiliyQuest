"""Games per game and person (parent area › Settings › Games)."""
from test_api import setup_family


def test_games_per_game_and_person(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert set(client.get("/api/me", headers=hm).json()["games_list"]) >= {"quiz", "bingo", "tschau", "ttt", "paarjagd"}
    r = client.put("/api/parent/games", json={"access": {"bingo": {"mode": "off"}, "tschau": {"mode": "some", "profiles": [mia]}}}, headers=ph)
    assert r.status_code == 200 and r.json()["access"]["tschau"]["profiles"] == [mia]
    assert client.get("/api/community/bingo", headers=hm).status_code == 403
    assert client.get("/api/community/bingo", headers=ph).status_code == 200            # parents always
    assert client.get("/api/community/cards/tschau", headers=hm).status_code == 200
    assert client.get("/api/community/cards/tschau", headers=hl).status_code == 403
    assert client.get("/api/community/cards/karussell", headers=hl).status_code == 200
    assert client.get("/api/community/council", headers=hl).status_code == 200          # the council stays open
    me = client.get("/api/me", headers=hl).json()
    assert "bingo" not in me["games_list"] and "tschau" not in me["games_list"] and me["community"]["bingo"] is None
    assert client.put("/api/parent/games", json={"access": {"chess": {"mode": "all"}}}, headers=ph).status_code == 400


def test_old_single_switch_still_works(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.put("/api/parent/games", json={"mode": "off"}, headers=ph)
    assert client.get("/api/community/quizzes", headers=hm).status_code == 403
    assert client.get("/api/me", headers=hm).json()["games_list"] == []
    client.app.state.fq.db.set_setting("games_access", None)          # only the old settings
    client.app.state.fq.db.set_setting("games", "some")
    client.app.state.fq.db.set_setting("games_profiles", [mia])
    assert client.get("/api/community/quizzes", headers=hm).status_code == 200


def test_council_topic_with_ideas_and_vote_now(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.post("/api/community/council", json={"title": "Ausflug?", "ideas": ["Zoo"], "vote_now": True}, headers=hm).status_code == 400
    tid = client.post("/api/community/council", json={"title": "Ausflug?", "description": "Am Samstag", "ideas": ["Zoo", "Badi", "Zoo", ""],
                                                     "majority": "absolute", "both_sides": True, "vote_now": True}, headers=hm).json()["id"]
    t = next(x for x in client.get("/api/community/council", headers=hm).json() if x["id"] == tid)
    assert t["status"] == "vote" and t["majority"] == "absolute" and t["both_sides"] and [p["text"] for p in t["proposals"]] == ["Zoo", "Badi"]
    t2 = client.post("/api/community/council", json={"title": "Znacht?", "ideas": ["Pizza"]}, headers=hm).json()["id"]
    t = next(x for x in client.get("/api/community/council", headers=hm).json() if x["id"] == t2)
    assert t["status"] == "collect" and t["description"] == ""


def test_new_game_after_an_update_respects_restrictions(fq):
    games = [g for g in fq.GAMES if g != "domino"]
    fq.db.set_setting("games_access", {g: {"mode": "all", "profiles": []} for g in games})
    assert fq.games_access()["domino"]["mode"] == "all"            # everything open → the new game too
    acc = {g: {"mode": "all", "profiles": []} for g in games}
    acc["poker"] = {"mode": "off", "profiles": []}
    fq.db.set_setting("games_access", acc)
    assert fq.games_access()["domino"]["mode"] == "off"            # parents restricted games → new one starts off
