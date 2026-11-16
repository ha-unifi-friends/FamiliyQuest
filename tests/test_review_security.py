"""Review fixes: what children may see of Home Assistant, the PIN limit."""
import concurrent.futures

from test_api import setup_family


def test_children_see_only_planner_entities(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    st = client.app.state.fq.planer_host.hass.states
    st.set("person.papa", "home", {"friendly_name": "Papa", "latitude": 47.5, "longitude": 9.1, "user_id": "abc"})
    st.set("camera.door", "idle", {"access_token": "secret", "entity_picture": "/api/camera_proxy/camera.door?token=secret"})
    st.set("lock.front", "unlocked", {})
    st.set("todo.zuhause", "3", {"friendly_name": "Zuhause"})
    kid = {s["entity_id"]: s for s in client.get("/api/planer/ha/states", headers=hm).json()}
    assert "camera.door" not in kid and "lock.front" not in kid and "todo.zuhause" in kid
    assert "latitude" not in kid["person.papa"]["attributes"] and "user_id" not in kid["person.papa"]["attributes"]
    par = {s["entity_id"] for s in client.get("/api/planer/ha/states", headers=ph).json()}
    assert "camera.door" in par
    # a list the planner does not use: children cannot change it
    r = client.post("/api/planer/ha/service", json={"domain": "todo", "service": "remove_item", "data": {"entity_id": "todo.zuhause", "item": "x"}}, headers=hm)
    assert r.status_code == 403


def test_pin_limit_holds_against_parallel_guesses(client):
    setup_family(client)
    def guess(pin):
        return client.post("/api/parent/login", json={"pin": pin}).status_code
    with concurrent.futures.ThreadPoolExecutor(12) as ex:
        codes = list(ex.map(guess, [f"{i:04d}" for i in range(20)]))
    assert codes.count(403) <= 5 and codes.count(429) >= 15         # at most 5 guesses per minute, even in parallel


def test_shop_double_tap_buys_once(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    fq = client.app.state.fq
    rid = fq.db.x("INSERT INTO reward(name, kind, account, cost, approval, active, icon, config) VALUES('Glace','voucher','coins',30,1,1,'🍦','{}')")
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 40}, headers=ph)
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda _: fq.shop.redeem(mia, rid) if True else None, range(1)))
        res = list(ex.map(lambda _: _try(fq.shop.redeem, mia, rid), range(6)))
    assert fq.rewards.balance(mia, "coins") >= 0 and fq.db.val("SELECT COUNT(*) FROM redemption WHERE reward_id=?", rid) == 1
    red = fq.db.q1("SELECT id FROM redemption WHERE reward_id=?", rid)["id"]
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda _: fq.shop.decide(red, False), range(4)))
    assert fq.rewards.balance(mia, "coins") == 40              # refunded exactly once


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception:  # noqa: BLE001
        return None


def test_logins_end_with_archive_and_app_token_is_short(client):
    ph, mia, leo = setup_family(client)
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.get("/api/me", headers=hl).status_code == 200
    fq = client.app.state.fq
    fq.db.x("UPDATE profile SET archived=1 WHERE id=?", leo)
    assert client.get("/api/me", headers=hl).status_code == 401
    fq.db.x("UPDATE profile SET archived=0 WHERE id=?", leo)
    import itsdangerous
    tok = client.post("/api/parent/app-token", headers=ph).json()["token"]
    d = itsdangerous.URLSafeTimedSerializer(fq.settings.secret, salt="familyquest").loads(tok)
    import time as _t
    assert d["k"] == "kid" and d["x"] - _t.time() <= 12 * 3600 + 5


def test_quiz_joins_at_the_same_moment(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    kids = [fq.db.x("INSERT INTO profile(name) VALUES(?)", f"K{i}") for i in range(8)]
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    q = client.post("/api/community/quizzes/from-template", json={"template": "schweiz"}, headers=hm).json()
    client.post("/api/community/quiz/start", json={"quiz_id": q["id"]}, headers=hm)
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        list(ex.map(fq.community.join, kids))
    assert set(kids) <= set(fq.community._game()["players"])


def test_duel_new_invitation_after_a_decline(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    papa = fq.db.q1("SELECT id FROM profile WHERE role='parent'")["id"]
    fq.duels.invite(mia, leo)
    fq.duels.answer(leo, False)
    assert fq.duels.state(mia)["status"] == "declined"
    fq.duels.invite(papa, leo)                                   # Papa invites Leo next
    assert fq.duels.summary(leo)["from"] == "Papa"


def test_song_skip_while_paused_unblocks_the_buzzer(client):
    from test_songquiz import FakeSpeaker
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    fq.ha = FakeSpeaker()
    fq.songs.start(mia, {"player": "media_player.x", "reveal_delay": 0})
    fq.songs.join(leo)
    fq.songs.begin()
    fq.songs.pause(True)
    fq.songs.next()                                              # skip the paused song
    fq.songs.next()                                              # the next one plays
    assert fq.songs.buzz(leo)
    fq.songs.reveal({"id": mia, "role": "kid"})
    fq.songs.decide()                                            # nobody judged: no points
    assert all(p["points"] == 0 for p in fq.songs.state(mia)["players"])
    fq.ha = None
