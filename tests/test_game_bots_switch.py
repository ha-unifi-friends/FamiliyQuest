"""Parent area › Games: per game «active», «active without bots» or «inactive» (services.games_access, bots: false)."""
import json

from test_api import setup_family

NO_BOTS = "Playing with bots is switched off for this game"


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def no_bots(client, ph, *games):
    r = client.put("/api/parent/games", json={"access": {g: {"mode": "all", "bots": False} for g in games}}, headers=ph)
    assert r.status_code == 200, r.text
    return r.json()


def test_api_stores_and_validates_the_bots_switch(client):
    ph, mia, _ = setup_family(client)
    d = client.get("/api/parent/games", headers=ph).json()
    assert "tschau" in d["bot_games"] and "werwolf" in d["bot_games"] and "bingo" not in d["bot_games"]
    assert all(a["bots"] for a in d["access"].values())                        # bots on by default
    d = no_bots(client, ph, "tschau")
    assert d["access"]["tschau"] == {"mode": "all", "profiles": [], "bots": False, "price": 0, "rent": 0, "period": "week", "preview": 0}
    # bots stay off when only the mode changes (the entry without «bots» keeps it)
    d = client.put("/api/parent/games", json={"access": {"tschau": {"mode": "some", "profiles": [mia]}}}, headers=ph).json()
    assert d["access"]["tschau"]["bots"] is False and d["access"]["tschau"]["mode"] == "some"
    # a game without bots cannot be switched to «without bots»; «bots» must be true / false
    r = client.put("/api/parent/games", json={"access": {"bingo": {"mode": "all", "bots": False}}}, headers=ph)
    assert r.status_code == 400 and r.json()["detail"] == "This game has no bots"
    assert client.put("/api/parent/games", json={"access": {"tschau": {"mode": "all", "bots": "no"}}}, headers=ph).status_code == 400
    assert client.put("/api/parent/games", json={"access": {"tschau": {"mode": "maybe"}}}, headers=ph).status_code == 400
    hm = login(client, mia, "1111")
    me = client.get("/api/me", headers=hm).json()
    assert me["games_nobots"] == ["tschau"] and "tschau" in me["games_list"]
    assert client.get("/api/me", headers=ph).json()["games_nobots"] == []        # parents are not bound


def test_card_games_alone_against_bots_refused_family_table_works(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    no_bots(client, ph, "tschau", "domino", "poker", "wuerfel")
    for path, body in [("cards/tschau/start", {"solo": True, "bots": 2}), ("domino/start", {"solo": True}),
                       ("poker/start", {"solo": True, "bots": 2}), ("wuerfel/start", {"solo": True})]:
        r = client.post("/api/community/" + path, json=body, headers=hm)
        assert r.status_code == 403 and r.json()["detail"] == NO_BOTS, path
    # bots at a family table: refused too
    r = client.post("/api/community/cards/tschau/start", json={"bots": 2}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == NO_BOTS
    # a family table without bots – even when the saved rules still had bots
    client.app.state.fq.db.set_setting("game_rules.tschau", {"bots": 3})
    st = client.post("/api/community/cards/tschau/start", json={}, headers=hm).json()
    assert [p["bot"] for p in st["players"]] == [False]
    client.post("/api/community/cards/tschau/join", headers=hl)
    st = client.post("/api/community/cards/tschau/begin", headers=hm).json()
    assert len(st["players"]) == 2 and not any(p["bot"] for p in st["players"])
    # the other card game is not touched
    assert client.post("/api/community/cards/karussell/start", json={"solo": True, "bots": 1}, headers=hm).status_code == 200
    # parents may still play alone against bots
    assert client.post("/api/community/domino/start", json={"solo": True}, headers=ph).status_code == 200


def test_jump_alone_without_practice_bots_and_chess_against_the_bot(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    no_bots(client, ph, "jump", "schach", "pingpong")
    r = client.post("/api/community/jump/start", json={"solo": True, "bots": 2}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == NO_BOTS
    st = client.post("/api/community/jump/start", json={"solo": True}, headers=hm).json()      # alone: still fine
    assert not any(p.get("bot") for p in st["players"])
    r = client.post("/api/community/schach/start", json={"mode": "bot", "level": "easy"}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == NO_BOTS
    assert client.post("/api/community/schach/start", json={"mode": "local"}, headers=hm).status_code == 200
    r = client.post("/api/community/pong4", json={"seats": {"A2": {"bot": "easy"}, "B1": {"bot": "easy"}, "B2": {"bot": "hard"}}}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == NO_BOTS


def test_kartenlauf_and_jass_are_not_filled_with_bots(client):
    ph, mia, leo = setup_family(client)
    hm, hl = login(client, mia, "1111"), login(client, leo)
    no_bots(client, ph, "kartenlauf", "jass")
    assert client.post("/api/community/kartenlauf/start", json={"solo": True}, headers=hm).status_code == 403
    client.post("/api/community/kartenlauf/start", json={"seats": 4, "teams": False, "bot_ms": 0}, headers=hm)
    client.post("/api/community/kartenlauf/join", headers=hl)
    st = client.post("/api/community/kartenlauf/begin", headers=hm).json()
    assert len(st["players"]) == 2 and not any(p.get("bot") for p in st["players"])
    assert client.post("/api/community/jass/start", json={"solo": True}, headers=hm).status_code == 403
    client.post("/api/community/jass/start", json={"bot_ms": 0}, headers=hm)
    client.post("/api/community/jass/join", headers=hl)
    r = client.post("/api/community/jass/begin", headers=hm)
    assert r.status_code == 400 and "4 people" in r.json()["detail"]


def test_werwolf_needs_five_people_without_bots(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    ids = [mia, leo] + [client.post("/api/parent/profiles", json={"name": f"Kind{i}"}, headers=ph).json()["id"] for i in range(3)]
    heads = {mia: login(client, mia, "1111"), **{p: login(client, p) for p in ids[1:]}}
    no_bots(client, ph, "werwolf")
    st = client.post("/api/community/werwolf/start", json={"fill": 8}, headers=heads[mia]).json()
    client.post("/api/community/werwolf/join", headers=heads[leo])
    st = client.get("/api/community/werwolf", headers=heads[mia]).json()
    assert st["no_bots"] and st["min_humans"] == 5 and st["bots"] == 0
    r = client.post("/api/community/werwolf/begin", headers=heads[mia])
    assert r.status_code == 400 and "5 players" in r.json()["detail"]
    for p in ids[2:]:
        client.post("/api/community/werwolf/join", headers=heads[p])
    st = client.post("/api/community/werwolf/begin", headers=heads[mia]).json()
    assert st["phase"] == "roles"
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werwolf' AND status!='done'")
    assert len(json.loads(row["state"])["players"]) == 5 and not any(p.get("bot") for p in json.loads(row["state"])["players"])


def test_werwolf_with_a_parent_at_the_table_is_filled(client):
    ph, mia, leo = setup_family(client)
    no_bots(client, ph, "werwolf")
    hm, hl = login(client, mia, "1111"), login(client, leo)
    client.post("/api/community/werwolf/start", json={}, headers=hm)
    client.post("/api/community/werwolf/join", headers=hl)
    client.post("/api/community/werwolf/join", headers=ph)                          # a parent plays along: parents decide
    st = client.post("/api/community/werwolf/begin", headers=hm).json()
    assert st["phase"] == "roles" and sum(1 for p in st["players"] if p["bot"]) == 2


def test_inactive_blocks_the_game(client):
    ph, mia, _ = setup_family(client)
    hm = login(client, mia, "1111")
    client.put("/api/parent/games", json={"access": {"domino": {"mode": "off", "bots": False}}}, headers=ph)
    r = client.post("/api/community/domino/start", json={}, headers=hm)
    assert r.status_code == 403 and r.json()["detail"] == "This game is switched off for you"
    me = client.get("/api/me", headers=hm).json()
    assert "domino" not in me["games_list"]
    # back on (with bots): alone against bots works again
    client.put("/api/parent/games", json={"access": {"domino": {"mode": "all", "bots": True}}}, headers=ph)
    assert client.post("/api/community/domino/start", json={"solo": True}, headers=hm).status_code == 200


def test_forced_no_bots_start_does_not_become_the_remembered_default(client):
    """«active without bots» starts the table with 0 bots – the remembered rules (game_rules.<kind>) keep the old number
    of bots, so it is back once bots are switched on again."""
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    fq.db.set_setting("game_rules.tschau", {"bots": 3})
    no_bots(client, ph, "tschau", "heimwaerts")
    st = client.post("/api/community/cards/tschau/start", json={"bots": 0}, headers=hm).json()
    assert not any(p["bot"] for p in st["players"])
    assert fq.db.get_setting("game_rules.tschau")["bots"] == 3
    assert client.post("/api/community/heimwaerts/start", json={"bots": 0, "bot_ms": 0}, headers=hm).status_code == 200
    assert "bots" not in fq.db.get_setting("game_rules.heimwaerts")           # nothing remembered before: the default stays
    from familyquest.heimwaerts import DEFAULTS
    assert fq.heimwaerts.default_rules("heimwaerts")["bots"] == DEFAULTS["bots"] > 0
    # bots on again: the remembered 3 are the default
    client.put("/api/parent/games", json={"access": {"tschau": {"mode": "all", "bots": True}}}, headers=ph)
    assert client.get("/api/community/cards/tschau/rules", headers=hm).json()["bots"] == 3
