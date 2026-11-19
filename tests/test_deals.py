"""Deals (familyquest/deals.py): offers, counter-offers, the both-accepted-same-version rule, reservations, chores taken
over (coins per deal, XP to who did it, pro rata), failures, pets / avatar items / games, approval, parents trading."""
from datetime import timedelta

import pytest

from familyquest.deals import DealError
from familyquest.gamepasses import PassError
from familyquest.pets import PetError
from familyquest.rewards.engine import today
from test_api import setup_family


@pytest.fixture
def fam(fq):
    papa = fq.db.x("INSERT INTO profile(name, role) VALUES('Papa', 'parent')")
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    leo = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    P = {i: fq.db.q1("SELECT * FROM profile WHERE id=?", i) for i in (papa, mia, leo)}
    return fq, P[papa], P[mia], P[leo]


def _id(p):
    return p["id"] if isinstance(p, dict) else p


def coins(fq, p, n):
    fq.rewards.book(_id(p), "coins", n, "manual", "test", "t")


def bal(fq, p):
    return fq.rewards.balance(_id(p), "coins")


def res(fq, p):
    return fq.rewards.reserved(_id(p))


def avail(fq, p):
    return fq.rewards.available(_id(p))


def chore(fq, name, who, points=10, account="coins", confirm=True, frequency="daily"):
    return fq.chores.save({"name": name, "points": points, "account": account, "profiles": [who], "confirm": confirm,
                           "frequency": frequency})


def tasks(fq, pid):
    return [t for t in fq.chores.for_kid(pid)]


def do_and_approve(fq, pid, task_uid):
    tid = int(task_uid[3:])
    fq.chores.mark_done(pid, tid)
    return fq.chores.decide(tid, True)


# ---------------------------------------------------------------- offer, counter-offer, answer
def test_offer_counter_and_the_same_version_rule(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 100)
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 20}], [{"t": "text", "text": "Lend me your bike on Saturday"}], "ok?")
    assert d["status"] == "open" and d["version"] == 1 and not d["turn"] and d["can"]["withdraw"]
    with pytest.raises(DealError):
        D.accept(mia, d["id"], 1)                                   # waiting for Leo
    assert D.summary(leo)["turn"] == 1 and D.summary(leo)["notes"][0]["kind"] == "offer"
    lv = D.get(leo, d["id"])                                        # opening the thread: seen
    assert lv["turn"] and lv["give"][0]["t"] == "text" and lv["get"] == [{"t": "coins", "n": 20}]
    assert D.summary(leo)["notes"] == [] and D.summary(mia)["notes"] == []
    c = D.counter(leo, d["id"], [{"t": "text", "text": "Lend me your bike on Saturday"}], [{"t": "coins", "n": 30}], "30 please", version=1)
    assert c["version"] == 2 and c["status"] == "open"
    with pytest.raises(DealError):
        D.accept(mia, d["id"], 1)                                   # an old version cannot be accepted
    with pytest.raises(DealError):
        D.counter(leo, d["id"], [], [{"t": "coins", "n": 5}])       # not Leo's turn now
    m = D.accept(mia, d["id"], 2)
    assert m["status"] == "running"                                 # both accepted version 2
    kinds = [x["kind"] for x in m["messages"]]
    assert kinds[:4] == ["offer", "counter", "accept", "stand"]
    # the coins pay for the free text: reserved until both confirm
    assert res(fq, mia) == 30 and avail(fq, mia) == 70 and bal(fq, mia) == 100
    D.confirm(mia, d["id"], True)
    assert bal(fq, leo) == 0
    done = D.confirm(leo, d["id"], True)
    assert done["status"] == "done" and bal(fq, mia) == 70 and bal(fq, leo) == 30 and res(fq, mia) == 0
    with pytest.raises(DealError):
        D.confirm(leo, d["id"], True)


def test_reject_withdraw_and_validation(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 50)
    with pytest.raises(DealError):
        D.offer(mia, mia["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "x"}])       # no self-deals
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 60}], [{"t": "text", "text": "x"}])      # more than she has
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [])                                  # both sides need something
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "xp", "n": 5}], [{"t": "text", "text": "x"}])          # XP can never be traded
    with pytest.raises(DealError):
        D.offer(papa, fq.db.x("INSERT INTO profile(name, role) VALUES('Mama', 'parent')"), [{"t": "text", "text": "a"}], [{"t": "text", "text": "b"}])
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "x"}])
    assert D.reject(leo, d["id"], "no")["status"] == "rejected"
    with pytest.raises(DealError):
        D.accept(leo, d["id"], 1)
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "y"}])
    with pytest.raises(DealError):
        D.withdraw(leo, d["id"])
    assert D.withdraw(mia, d["id"])["status"] == "withdrawn"
    with pytest.raises(DealError):
        D.get(papa, d["id"])                                        # not his deal (parents use the overview)
    assert D.thread(d["id"])["status"] == "withdrawn"


def test_settings_off_per_child_and_blocks(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 1000)
    D.save_settings({"off": [leo["id"]]})
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "x"}])
    assert [p["id"] for p in D.partners(mia)] == [papa["id"]]
    D.save_settings({"off": [], "kinds": {"text": False}, "max_coins": 50})
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "x"}])       # free text switched off
    D.save_settings({"kinds": {"text": True}})
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 60}], [{"t": "text", "text": "x"}])      # max coins per deal
    D.save_settings({"on": False})
    assert not D.can_trade(mia) and not D.can_trade(papa)
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "coins", "n": 5}], [{"t": "text", "text": "x"}])


# ---------------------------------------------------------------- reservations
def test_reserved_coins_cannot_be_spent_anywhere(fam, client):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 100)
    leo_chore = chore(fq, "Abwaschen", leo["id"])
    # Mia pays 90 coins for Leo doing her … no: Leo does Mia's chore → Mia's coins wait for it (reserved)
    mia_chore = chore(fq, "Zimmer", mia["id"])
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 90}], [{"t": "chore", "chore": mia_chore, "times": 1}])
    D.accept(leo, d["id"], 1)
    assert avail(fq, mia) == 10 and bal(fq, mia) == 100
    with pytest.raises(PassError):
        fq.passes.buy(mia["id"], "jump", {"price": 50}, "Jump")
    assert not any(o["can"] for o in fq.shop.offers(mia["id"]) if o["account"] == "coins" and o["cost"] > 10)
    with pytest.raises(DealError):                                  # the same coins cannot go into a second deal
        D.offer(mia, leo["id"], [{"t": "coins", "n": 50}], [{"t": "text", "text": "x"}])
    assert fq.dashboard(mia)["coins_reserved"] == 90
    assert leo_chore


def test_reservation_blocks_the_avatar_shop_api(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 60}, headers=ph)
    r = client.post("/api/me/deals", json={"to": leo, "give": [{"t": "coins", "n": 30}], "get": [{"t": "text", "text": "Wash my bike"}]}, headers=hm)
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    assert client.get("/api/me", headers=hl).json()["deals"]["turn"] == 1
    assert client.post(f"/api/me/deals/{did}/accept", json={"version": 1}, headers=hl).json()["status"] == "running"
    assert client.post("/api/me/avatar/buy", json={"item": "cap"}, headers=hm).status_code == 400     # cap 40 > 30 available
    assert client.post("/api/me/avatar/buy", json={"item": "earrings"}, headers=hm).status_code == 200  # 30 ok
    assert avail(fq, mia) == 0
    # guests / nobody logged in cannot trade; somebody else's deal stays closed
    assert client.get("/api/me/deals").status_code == 401
    ov = client.get("/api/parent/deals", headers=ph).json()
    assert ov["deals"][0]["id"] == did and ov["deals"][0]["a"]["name"] == "Mia"
    assert client.get("/api/me/deals", headers=hl).json()["deals"][0]["id"] == did
    # the parent cancels: reservation released
    assert client.post(f"/api/parent/deals/{did}/cancel", headers=ph).json()["status"] == "cancelled"
    assert res(fq, mia) == 0
    assert client.post(f"/api/me/deals/{did}/confirm", json={"ok": True}, headers=hm).status_code == 400


# ---------------------------------------------------------------- chores
def test_chore_for_coins_coins_per_deal_xp_to_the_doer(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 50)
    dishes = chore(fq, "Abwaschen", leo["id"], points=10)
    opts = D.assets(mia, leo["id"])["other"]["chores"]
    assert opts[0]["chore"] == dishes and opts[0]["dates"][0] == today().isoformat()
    # «I do your dishes, you pay me 20 coins»
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "times": 1}], [{"t": "coins", "n": 20}])
    with pytest.raises(DealError):                                  # a chore cannot be in two open deals
        D.offer(papa, leo["id"], [{"t": "chore", "chore": dishes, "times": 1}], [{"t": "text", "text": "x"}])
    D.accept(leo, d["id"], 1)
    mt = [t for t in tasks(fq, mia["id"]) if t["summary"] == "Abwaschen"]
    assert mt and mt[0]["from"] == "Leo" and mt[0]["deal"] == d["id"]
    assert not [t for t in tasks(fq, leo["id"]) if t["summary"] == "Abwaschen"]   # not recreated for Leo
    assert res(fq, leo) == 20
    with pytest.raises(Exception):
        fq.chores.mark_done(leo["id"], int(mt[0]["uid"][3:]))       # it is Mia's now
    fq.chores.mark_done(mia["id"], int(mt[0]["uid"][3:]))
    assert bal(fq, mia) == 0                                         # waits for the parents
    do = fq.chores.decide(int(mt[0]["uid"][3:]), True)
    assert do["status"] == "done"
    assert bal(fq, mia) == 30 and bal(fq, leo) == 30                 # 10 for the chore + 20 from Leo
    assert D.get(mia, d["id"])["status"] == "done" and res(fq, leo) == 0
    fq.chores.decide(int(mt[0]["uid"][3:]), True)                     # no double booking
    D.chore_done(fq.chores._task(int(mt[0]["uid"][3:])))
    assert bal(fq, mia) == 30 and bal(fq, leo) == 30


def test_chore_reward_to_the_owner_and_xp_always_to_the_doer(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    dishes = chore(fq, "Abwaschen", leo["id"], points=10)
    learn = chore(fq, "Vokabeln", leo["id"], points=7, account="xp", confirm=False)
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "to": "owner"}, {"t": "chore", "chore": learn, "to": "owner"}],
                [{"t": "text", "text": "You tidy the shoes"}])
    D.accept(leo, d["id"], 1)
    for t in tasks(fq, mia["id"]):
        if t["deal"]:
            if t["summary"] == "Abwaschen":
                do_and_approve(fq, mia["id"], t["uid"])
            else:
                fq.chores.mark_done(mia["id"], int(t["uid"][3:]))
    assert bal(fq, leo) == 10 and bal(fq, mia) == 0                  # the coins go to Leo as agreed
    assert fq.rewards.balance(mia["id"], "xp") >= 7 and fq.rewards.balance(leo["id"], "xp") == 0   # XP to who did it


def test_pro_rata_for_several_times(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 10)
    dishes = chore(fq, "Abwaschen", leo["id"], points=0)
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "times": 3}], [{"t": "coins", "n": 10}])
    assert d["give"][0]["dates"] == [(today() + timedelta(days=i)).isoformat() for i in range(3)]
    D.accept(leo, d["id"], 1)
    ids = [r["id"] for r in fq.db.q("SELECT id FROM chore_task WHERE deal_id=? ORDER BY period", d["id"])]
    assert len(ids) == 3 and all(fq.db.val("SELECT profile_id FROM chore_task WHERE id=?", i) == mia["id"] for i in ids)
    paid = []
    for i in ids:
        fq.db.x("UPDATE chore_task SET status='pending' WHERE id=?", i)   # done on its day (the test does not wait)
        fq.chores.decide(i, True)
        paid.append(bal(fq, mia))
    assert paid == [3, 6, 10] and bal(fq, leo) == 0
    assert D.get(mia, d["id"])["status"] == "done"


def test_missed_chore_fails_the_deal_and_releases(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 40)
    dishes = chore(fq, "Abwaschen", leo["id"])
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "times": 2}], [{"t": "coins", "n": 40}])
    D.accept(leo, d["id"], 1)
    first, second = [r["id"] for r in fq.db.q("SELECT id FROM chore_task WHERE deal_id=? ORDER BY period", d["id"])]
    fq.db.x("UPDATE chore_task SET period=? WHERE id=?", (today() - timedelta(days=1)).isoformat(), first)   # its day is over
    D.sweep()
    v = D.get(mia, d["id"])
    assert v["status"] == "failed" and v["reason"] == "missed" and v["messages"][-1]["kind"] == "failed"
    assert res(fq, leo) == 0 and bal(fq, leo) == 40
    assert fq.db.val("SELECT profile_id FROM chore_task WHERE id=?", second) == leo["id"]       # back to Leo
    assert fq.db.val("SELECT profile_id FROM chore_task WHERE id=?", first) == mia["id"]        # the missed one stays
    assert fq.db.val("SELECT deal_id FROM chore_task WHERE id=?", second) is None


def test_rejected_chore_fails_the_deal(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 40)
    dishes = chore(fq, "Abwaschen", leo["id"])
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes}], [{"t": "coins", "n": 15}])
    D.accept(leo, d["id"], 1)
    tid = fq.db.val("SELECT id FROM chore_task WHERE deal_id=?", d["id"])
    fq.chores.mark_done(mia["id"], tid)
    fq.chores.decide(tid, False)
    assert D.get(leo, d["id"])["status"] == "failed" and res(fq, leo) == 0
    assert fq.db.val("SELECT profile_id FROM chore_task WHERE id=?", tid) == leo["id"]
    assert bal(fq, mia) == 0


def test_chore_swap_plus_coins(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 20)
    table = chore(fq, "Tisch decken", mia["id"], points=5)
    dishes = chore(fq, "Abwaschen", leo["id"], points=8)
    # Mia does Leo's dishes, Leo sets the table for her – and Mia adds 5 coins
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes}, {"t": "coins", "n": 5}], [{"t": "chore", "chore": table}])
    D.accept(leo, d["id"], 1)
    assert [t["summary"] for t in tasks(fq, mia["id"])] == ["Abwaschen"] and [t["summary"] for t in tasks(fq, leo["id"])] == ["Tisch decken"]
    assert res(fq, mia) == 5
    do_and_approve(fq, mia["id"], tasks(fq, mia["id"])[0]["uid"])
    assert bal(fq, mia) == 28 and D.get(mia, d["id"])["status"] == "running"
    do_and_approve(fq, leo["id"], tasks(fq, leo["id"])[0]["uid"])
    assert bal(fq, leo) == 10 and bal(fq, mia) == 23 and D.get(mia, d["id"])["status"] == "done"


# ---------------------------------------------------------------- pets, avatar items, games
def _pet(fq, pid, kind="dog"):
    fq.db.x("INSERT OR IGNORE INTO unlock(profile_id, item) VALUES(?,?)", pid, kind)
    return fq.pets.adopt(pid, kind)


def test_pet_for_coins_and_chores_locks_and_transfers(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 100)
    hamster = _pet(fq, leo["id"], "hamster")
    tidy = chore(fq, "Zimmer aufräumen", leo["id"])
    # «50 coins + 2× tidy room for your hamster»
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 50}, {"t": "chore", "chore": tidy, "times": 2}], [{"t": "pet", "id": hamster}])
    assert d["get"][0]["kind"] == "hamster"
    D.accept(leo, d["id"], 1)
    assert bal(fq, leo) == 50 and bal(fq, mia) == 50                 # coins without services on Leo's side: at once
    assert fq.deals.locked("pet", hamster)
    with pytest.raises(PetError):
        fq.pets.hotel(leo["id"], hamster, 2)                          # locked in the deal
    with pytest.raises(PetError):
        fq.pets.sit(leo["id"], hamster, papa["id"], today().isoformat())
    ids = [r["id"] for r in fq.db.q("SELECT id FROM chore_task WHERE deal_id=? ORDER BY period", d["id"])]
    for i in ids:
        fq.db.x("UPDATE chore_task SET status='pending' WHERE id=?", i)
        fq.chores.decide(i, True)
    assert fq.db.val("SELECT profile_id FROM pet WHERE id=?", hamster) == mia["id"]
    assert fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='hamster'", mia["id"])
    assert not fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='hamster'", leo["id"])
    fq.pets.sync(leo["id"])                                           # Leo does not get a new hamster
    assert not fq.db.q1("SELECT 1 FROM pet WHERE profile_id=? AND kind='hamster' AND dead_at IS NULL", leo["id"])
    assert D.get(mia, d["id"])["status"] == "done" and not fq.deals.locked("pet", hamster)


def test_pets_in_hotel_or_earned_cannot_be_traded(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 100)
    dog = _pet(fq, mia["id"], "dog")
    fq.pets.hotel(mia["id"], dog, 1)
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "pet", "id": dog}], [{"t": "text", "text": "x"}])
    fq.pets.fetch(mia["id"], dog)
    with pytest.raises(DealError):
        D.offer(leo, mia["id"], [{"t": "pet", "id": dog}], [{"t": "text", "text": "x"}])   # not Leo's
    owl = _pet(fq, mia["id"], "owl")
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "pet", "id": owl}], [{"t": "text", "text": "x"}])   # earned with a badge
    fq.db.x("UPDATE pet SET dead_at=? WHERE id=?", "2026-01-01T00:00:00", dog)
    with pytest.raises(DealError):
        D.offer(mia, leo["id"], [{"t": "pet", "id": dog}], [{"t": "text", "text": "x"}])   # dead


def test_avatar_item_and_bought_game_transfer_rented_not(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 100)
    fq.db.x("INSERT INTO unlock(profile_id, item) VALUES(?, 'cap')", mia["id"])
    fq.db.x("INSERT INTO unlock(profile_id, item, new_xp) VALUES(?, 'bg_space', 500)", mia["id"])
    fq.db.x("UPDATE profile SET avatar=? WHERE id=?", '{"items": {"hat": "cap"}}', mia["id"])
    fq.db.x("INSERT INTO game_pass(profile_id, game, bought) VALUES(?, 'jump', 1)", mia["id"])
    fq.db.x("INSERT INTO game_pass(profile_id, game, rent_until) VALUES(?, 'snack', '2099-01-01 00:00:00')", mia["id"])
    it = D.items_of(mia["id"])
    assert [a["item"] for a in it["avatar"]] == ["cap"] and [g["game"] for g in it["games"]] == ["jump"]
    for bad in ({"t": "avatar", "item": "bg_space"}, {"t": "game", "game": "snack"}, {"t": "avatar", "item": "crown"}):
        with pytest.raises(DealError):
            D.offer(mia, leo["id"], [bad], [{"t": "coins", "n": 5}])
    d = D.offer(mia, leo["id"], [{"t": "avatar", "item": "cap"}, {"t": "game", "game": "jump"}], [{"t": "coins", "n": 60}])
    with pytest.raises(DealError):                                     # items in a deal are locked for other deals
        D.offer(mia, papa["id"], [{"t": "avatar", "item": "cap"}], [{"t": "text", "text": "x"}])
    assert D.accept(leo, d["id"], 1)["status"] == "done"
    assert fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='cap'", leo["id"])
    assert not fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='cap'", mia["id"])
    assert '"hat"' not in fq.db.val("SELECT avatar FROM profile WHERE id=?", mia["id"])
    assert fq.passes.status(leo["id"], "jump")["bought"] and not fq.passes.status(mia["id"], "jump")["bought"]
    assert bal(fq, mia) == 60 and bal(fq, leo) == 40
    assert fq.db.val("SELECT COUNT(*) FROM deal_pay WHERE ref LIKE ?", f"deal:{d['id']}:%") == 3


# ---------------------------------------------------------------- approval
def test_approval_threshold_and_pets(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 300)
    D.save_settings({"approval": True, "threshold": 100})
    small = D.offer(mia, leo["id"], [{"t": "coins", "n": 40}], [{"t": "text", "text": "a"}])
    assert D.accept(leo, small["id"], 1)["status"] == "running"
    big = D.offer(mia, leo["id"], [{"t": "coins", "n": 120}], [{"t": "text", "text": "b"}])
    v = D.accept(leo, big["id"], 1)
    assert v["status"] == "approval" and res(fq, mia) == 160
    assert D.summary(papa)["approval"] == 1
    assert D.approve(papa, big["id"], False)["status"] == "declined" and res(fq, mia) == 40
    big = D.offer(mia, leo["id"], [{"t": "coins", "n": 120}], [{"t": "text", "text": "c"}])
    D.accept(leo, big["id"], 1)
    assert D.approve(papa, big["id"], True)["status"] == "running"
    with pytest.raises(DealError):
        D.approve(papa, big["id"], True)
    D.save_settings({"approval": False, "approval_pets": True})
    dog = _pet(fq, leo["id"], "dog")
    p = D.offer(mia, leo["id"], [{"t": "coins", "n": 10}], [{"t": "pet", "id": dog}])
    assert D.accept(leo, p["id"], 1)["status"] == "approval"


# ---------------------------------------------------------------- parents trade
def test_parent_offer_new_task_with_counter_paid_by_parents(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    D.save_settings({"approval": True, "threshold": 10})               # a deal with a parent never needs approval
    # «I pay you 30 coins if you mow the lawn today»
    d = D.offer(papa, leo["id"], [{"t": "coins", "n": 30}], [{"t": "newchore", "name": "Rasen mähen", "icon": "🌱"}])
    assert d["get"][0]["t"] == "newchore" and d["get"][0]["date"] == today().isoformat()
    c = D.counter(leo, d["id"], [{"t": "newchore", "name": "Rasen mähen", "icon": "🌱"}], [{"t": "coins", "n": 40}])
    assert c["version"] == 2
    v = D.accept(papa, d["id"], 2)
    assert v["status"] == "running"
    t = [x for x in tasks(fq, leo["id"]) if x["summary"] == "Rasen mähen"][0]
    assert t["from"] == "Papa"
    do_and_approve(fq, leo["id"], t["uid"])
    assert bal(fq, leo) == 40 and bal(fq, papa) == 0                   # paid by the parents
    assert D.get(leo, d["id"])["status"] == "done"


def test_child_offers_parent_and_parent_counters(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 50)
    d = D.offer(mia, papa["id"], [{"t": "coins", "n": 10}], [{"t": "text", "text": "Pizza on Friday"}])
    assert D.summary(papa)["turn"] == 1
    c = D.counter(papa, d["id"], [{"t": "text", "text": "Pizza on Friday"}], [{"t": "coins", "n": 20}, {"t": "newchore", "name": "Tisch decken"}])
    assert c["version"] == 2
    with pytest.raises(DealError):                                     # a new task goes from the child to the parent only
        D.counter(mia, d["id"], [{"t": "text", "text": "y"}], [{"t": "newchore", "name": "x"}], version=2)
    mv = D.accept(mia, d["id"], 2)
    assert mv["status"] == "running" and res(fq, mia) == 20
    task = [x for x in tasks(fq, mia["id"]) if x["summary"] == "Tisch decken"][0]
    do_and_approve(fq, mia["id"], task["uid"])
    D.confirm(mia, d["id"], True)
    D.confirm(papa, d["id"], True)
    assert D.get(mia, d["id"])["status"] == "done"
    assert bal(fq, mia) == 30 and bal(fq, papa) == 0                   # to the parents: taken from the child only


def test_parent_rejects_child_offer_and_parent_in_the_app(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 20}, headers=ph)
    papa = 1
    r = client.post("/api/me/deals", json={"to": papa, "give": [{"t": "coins", "n": 10}], "get": [{"t": "text", "text": "Later to bed"}]}, headers=hm)
    did = r.json()["id"]
    lst = client.get("/api/me/deals", headers=ph).json()                 # the parent token works in the app API too
    assert lst["deals"][0]["turn"] and lst["on"]
    a = client.get(f"/api/me/deals/assets/{mia}", headers=ph).json()
    assert a["me"]["coins"] is None and a["new_task"]
    assert client.post(f"/api/me/deals/{did}/reject", json={"text": "no"}, headers=ph).json()["status"] == "rejected"
    # a parent offers from the parent area
    r = client.post("/api/me/deals", json={"to": leo, "give": [{"t": "coins", "n": 5}], "get": [{"t": "newchore", "name": "Altpapier"}]}, headers=ph)
    assert r.status_code == 200 and r.json()["me"]["role"] == "parent"


# ---------------------------------------------------------------- free text dispute
def test_free_text_dispute_parent_settles_or_council(fam):
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, mia, 50)
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 10}], [{"t": "text", "text": "Homework help"}])
    D.accept(leo, d["id"], 1)
    D.confirm(leo, d["id"], True)
    v = D.confirm(mia, d["id"], False)
    assert v["progress"]["dispute"] and v["can"]["council"]
    assert D.settle(papa, d["id"], True)["status"] == "done" and bal(fq, leo) == 10
    d = D.offer(mia, leo["id"], [{"t": "coins", "n": 10}], [{"t": "text", "text": "Bike"}])
    D.accept(leo, d["id"], 1)
    D.confirm(mia, d["id"], False)
    v = D.to_council(leo, d["id"], "de-CH")
    tid = v["progress"]["council"]
    topic = fq.db.q1("SELECT * FROM council_topic WHERE id=?", tid)
    assert topic["status"] == "vote"
    no = fq.db.q1("SELECT id FROM council_proposal WHERE topic_id=? AND text LIKE '✗%'", tid)["id"]
    fq.community.vote(papa, tid, no)
    fq.community.close(papa, tid)
    D.sweep()
    assert D.get(mia, d["id"])["status"] == "failed" and res(fq, mia) == 0 and bal(fq, mia) == 40


# ---------------------------------------------------------------- review fixes (lock order, failed deals)
def test_lock_order_chore_approval_vs_sweep_no_deadlock(fam):
    """A parent approves a chore of a deal (chores → deals) while the sweep runs (deals.lock → db): one lock order."""
    import threading
    import time
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 50)
    dishes = chore(fq, "Abwaschen", leo["id"], points=10)
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "times": 1}], [{"t": "coins", "n": 20}])
    D.accept(leo, d["id"], 1)
    tid = fq.db.val("SELECT id FROM chore_task WHERE deal_id=?", d["id"])
    fq.chores.mark_done(mia["id"], tid)
    in_tx = threading.Event()
    orig = D.chore_done

    def slow(t):                                       # B: inside chores._complete's transaction
        in_tx.set()
        time.sleep(0.4)
        return orig(t)
    D.chore_done = slow

    def a():                                           # A: like sweep(): deals.lock, then a transaction
        in_tx.wait(3)
        with D.lock:
            time.sleep(0.1)
            with fq.db.tx():
                pass
    ta = threading.Thread(target=a, daemon=True)
    tb = threading.Thread(target=lambda: fq.chores.decide(tid, True), daemon=True)
    ta.start()
    tb.start()
    ta.join(5)
    tb.join(5)
    assert not ta.is_alive() and not tb.is_alive(), "deadlock: chores._complete and the deal lock"
    assert bal(fq, mia) == 30 and D.get(mia, d["id"])["status"] == "done"


def test_failed_deal_pending_chore_pays_the_doer(fam):
    """A deal fails while a chore of it waits for the parents: it leaves the deal, its coins go to who did it."""
    fq, papa, mia, leo = fam
    D = fq.deals
    dishes = chore(fq, "Abwaschen", leo["id"], points=10)
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "to": "owner"}], [{"t": "text", "text": "Shoes"}])
    D.accept(leo, d["id"], 1)
    tid = fq.db.val("SELECT id FROM chore_task WHERE deal_id=?", d["id"])
    fq.chores.mark_done(mia["id"], tid)
    D.cancel(papa, d["id"])
    assert fq.db.val("SELECT deal_id FROM chore_task WHERE id=?", tid) is None
    t = fq.chores._task(tid)
    t["deal_id"] = d["id"]                              # even a stale task row: a deal that is over pays nobody else
    assert D.reward_to(t) == mia["id"]
    fq.chores.decide(tid, True)
    assert bal(fq, mia) == 10 and bal(fq, leo) == 0


def test_failed_start_holds_nothing_of_the_other_side(fam, monkeypatch):
    """Side a's item is gone when the deal starts: the deal fails – and side b's coins are not reserved afterwards."""
    from familyquest import deals as deals_mod
    fq, papa, mia, leo = fam
    D = fq.deals
    coins(fq, leo, 50)
    dishes = chore(fq, "Abwaschen", leo["id"])
    fq.db.x("INSERT INTO game_pass(profile_id, game, bought) VALUES(?, 'jump', 1)", mia["id"])
    d = D.offer(mia, leo["id"], [{"t": "chore", "chore": dishes, "times": 1}, {"t": "game", "game": "jump"}],
                [{"t": "coins", "n": 20}])

    def gone(*a, **kw):
        raise deals_mod._Gone()
    monkeypatch.setattr(D, "_item_move", gone)
    D.accept(leo, d["id"], 1)
    assert D.get(leo, d["id"])["status"] == "failed"
    assert res(fq, leo) == 0 and avail(fq, leo) == 50
    assert not fq.db.q("SELECT 1 FROM deal_hold WHERE deal_id=? AND active=1", d["id"])
