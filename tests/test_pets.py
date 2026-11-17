"""Pet care: bars that drop, feeding with coins, growth, death, pause, pets as bots."""
import json
from datetime import datetime, timedelta

import pytest

from test_api import setup_family


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 16, 10, 0, 0)

    def __call__(self):
        return self.t

    def add(self, **kw):
        self.t += timedelta(**kw)


@pytest.fixture
def clock(monkeypatch):
    from familyquest import pets
    c = Clock()
    monkeypatch.setattr(pets, "now", c)
    return c


def login(client, pid, pin=None):
    body = {"profile_id": pid, **({"pin": pin} if pin else {})}
    return {"X-FQ-Token": client.post("/api/login", json=body).json()["token"]}


def coins(client, ph, pid, amount):
    client.post("/api/parent/book", json={"profile_id": pid, "account": "coins", "amount": amount}, headers=ph)


def buy_dog(client, ph, mia):
    h = login(client, mia, "1111")
    coins(client, ph, mia, 200)
    assert client.post("/api/me/avatar/buy", json={"item": "dog"}, headers=h).status_code == 200
    client.post("/api/me/avatar", json={"avatar": {"items": {"pet": "dog"}}}, headers=h)
    pets = client.get("/api/me/pets", headers=h).json()["pets"]
    assert len(pets) == 1
    return h, pets[0]


def test_decay_feed_play_wash(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    assert dog["name"] == "Bello" and dog["stage"] == "baby" and dog["age"] == 0
    assert (dog["hunger"], dog["mood"], dog["clean"]) == (100, 100, 100)
    clock.add(hours=24)
    dog = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert (dog["hunger"], dog["mood"], dog["clean"]) == (50, 50, 67)
    clock.add(hours=8)                   # 32 h: hunger 33
    bal = client.get("/api/me", headers=h).json()["balances"]["coins"]
    r = client.post(f"/api/me/pets/{dog['id']}/feed", headers=h).json()
    assert r["pet"]["hunger"] == 73 and r["coins"] == bal - 2
    assert client.post(f"/api/me/pets/{dog['id']}/play", headers=h).json()["pet"]["mood"] == 68
    assert client.post(f"/api/me/pets/{dog['id']}/wash", headers=h).json()["pet"]["clean"] == 100
    assert client.post(f"/api/me/pets/{dog['id']}/feed", headers=h).json()["pet"]["hunger"] == 100   # max 100
    # full: no coins wasted
    assert client.post(f"/api/me/pets/{dog['id']}/feed", headers=h).status_code == 400
    assert client.post(f"/api/me/pets/{dog['id']}/dance", headers=h).status_code == 404


def test_feeding_needs_coins_and_parents_set_the_price(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    coins(client, ph, mia, -client.get("/api/me", headers=h).json()["balances"]["coins"])    # spend everything
    clock.add(hours=30)
    r = client.post(f"/api/me/pets/{dog['id']}/feed", headers=h)
    assert r.status_code == 400 and "coins" in r.json()["detail"]
    client.put("/api/parent/settings", json={"pet_food_cost": 0}, headers=ph)
    assert client.post(f"/api/me/pets/{dog['id']}/feed", headers=h).status_code == 200
    assert client.get("/api/me/pets", headers=h).json()["food_cost"] == 0


def test_stages_and_badge_on_the_avatar(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    pub = client.get("/api/me", headers=h).json()["profile"]["avatar"]
    assert pub["pet"] == {"kind": "dog", "age": 0, "stage": "baby", "alive": True}
    client.put("/api/parent/profiles/%d/pet-pause" % mia, json={"on": True}, headers=ph)    # keep it alive while we jump
    clock.add(days=7)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["stage"] == "young"
    clock.add(days=23)
    d = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert d["stage"] == "adult" and d["age"] == 30
    fam = client.get("/api/family", headers=h).json()["members"]
    assert next(m for m in fam if m["profile"]["id"] == mia)["profile"]["avatar"]["pet"]["age"] == 30
    # the avatar saved back with the pet info: the info is not stored
    assert "pet" not in client.post("/api/me/avatar", json={"avatar": {**pub, "items": {"pet": "dog"}}}, headers=h).json()["avatar"]
    assert client.get("/api/me/avatar", headers=h).json()["avatar"]["pet"]["stage"] == "adult"


def test_death_after_three_days_at_zero(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    fq = client.app.state.fq
    told = []
    fq.pets.on_zero.append(lambda prof, pet: told.append(pet["name"]))
    clock.add(hours=72)                  # all bars at 0 now
    me = client.get("/api/me", headers=h).json()
    p = me["pets"]["pets"][0]
    assert p["dying"] and p["days_left"] == 3 and set(p["low"]) == {"hunger", "mood", "clean"}
    assert told == ["Bello"]
    clock.add(days=2)
    fq.pets.tick()
    assert told == ["Bello"]             # only once
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["days_left"] == 1
    clock.add(days=1, minutes=1)
    fq.pets.tick()
    d = client.get("/api/me/pets", headers=h).json()
    assert d["pets"] == [] and d["died"][0]["name"] == "Bello"
    assert not fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='dog'", mia)
    me = client.get("/api/me", headers=h).json()
    assert "pet" not in me["profile"]["avatar"]["items"]
    assert fq.db.q1("SELECT * FROM ledger WHERE profile_id=? AND event='pet_died'", mia)
    client.post("/api/me/pets/seen", headers=h)
    assert client.get("/api/me/pets", headers=h).json()["died"] == []
    assert client.post(f"/api/me/pets/{dog['id']}/play", headers=h).status_code == 400
    # buy it again: a new baby
    assert client.post("/api/me/avatar/buy", json={"item": "dog"}, headers=h).status_code == 400   # 80 coins left
    coins(client, ph, mia, 100)
    assert client.post("/api/me/avatar/buy", json={"item": "dog"}, headers=h).status_code == 200
    new = client.get("/api/me/pets", headers=h).json()["pets"]
    assert len(new) == 1 and new[0]["id"] != dog["id"] and new[0]["age"] == 0 and new[0]["hunger"] == 100


def test_care_resets_the_death_timer(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    clock.add(days=5)                    # 2 days at zero
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["days_left"] == 1
    client.post(f"/api/me/pets/{dog['id']}/play", headers=h)
    clock.add(hours=1)
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert not p["dying"] and p["mood"] == 33
    clock.add(days=2)                    # mood back at 0 after 17 h – then 31 h at zero
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["dying"] and 1.6 < p["days_left"] < 1.8


def test_pause_stops_decay_and_death(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    clock.add(hours=12)
    r = client.put(f"/api/parent/profiles/{mia}/pet-pause", json={"on": True}, headers=ph).json()
    assert r["paused"] and r["pets"][0]["hunger"] == 75 and r["pets"][0]["paused"] == "parents"
    clock.add(days=20)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["hunger"] == 75
    ov = client.get("/api/parent/overview", headers=ph).json()
    kid = next(k for k in ov["kids"] if k["profile"]["id"] == mia)
    assert kid["pets_paused"] and kid["pets"][0]["name"] == "Bello"
    client.put(f"/api/parent/profiles/{mia}/pet-pause", json={"on": False}, headers=ph)
    clock.add(hours=12)
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["hunger"] == 50 and p["paused"] is None and p["age"] == 21


def test_planner_holidays_pause(fq, kid, clock):
    fq.db.x("INSERT INTO unlock(profile_id,item) VALUES(?, 'cat')", kid)
    pet = fq.pets.list(kid)[0]
    assert pet["name"] == "Minka"
    away = {"2026-11-17"}
    fq.pets.away = lambda pid: away
    clock.add(days=2)                    # the 17th is a holiday
    p = fq.pets.list(kid)[0]
    assert p["hunger"] == round(100 - 100 / 48 * 24)       # 14 h on the 16th + 10 h on the 18th
    away.add("2026-11-18")
    assert fq.pets.list(kid)[0]["paused"] == "away"


def test_pets_are_bots_for_their_owner(client, clock):
    ph, mia, leo = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    bots = client.get("/api/community/bots", headers=h).json()["bots"]
    pet = next(b for b in bots if b.get("pet"))
    assert pet["id"] == f"pet:{dog['id']}" and pet["emoji"] == "🐶" and pet["name"] == "Bello"
    client.put(f"/api/me/pets/{dog['id']}", json={"name": "Rex"}, headers=h)
    st = client.post("/api/community/cards/tschau/start", json={"solo": True, "bots": 2, "bot_ids": [f"pet:{dog['id']}"]}, headers=h).json()
    names = [p["name"] for p in st["players"] if p["bot"]]
    assert names[0] == "Rex" and len(names) == 2
    # Leo neither sees nor seats Mia's pet
    hl = login(client, leo)
    assert not [b for b in client.get("/api/community/bots", headers=hl).json()["bots"] if b.get("pet")]
    st = client.post("/api/community/cards/tschau/start", json={"solo": True, "bots": 1, "bot_ids": [f"pet:{dog['id']}"]}, headers=hl).json()
    assert "Rex" not in [p["name"] for p in st["players"] if p["bot"]]


def test_other_child_cannot_care_for_my_pet(client, clock):
    ph, mia, leo = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    hl = login(client, leo)
    coins(client, ph, leo, 50)
    assert client.post(f"/api/me/pets/{dog['id']}/feed", headers=hl).status_code == 403
    assert client.put(f"/api/me/pets/{dog['id']}", json={"name": "Hack"}, headers=hl).status_code == 403
    assert client.put(f"/api/me/pets/{dog['id']}", json={"name": "  "}, headers=h).status_code == 400
    assert client.get("/api/me/pets", headers=hl).json()["pets"] == []


def test_existing_pets_get_a_record_and_the_badge_owl(fq, kid, clock):
    fq.db.x("INSERT INTO unlock(profile_id,item) VALUES(?, 'parrot')", kid)
    fq.db.x("UPDATE profile SET avatar=? WHERE id=?", json.dumps({"items": {"pet": "parrot"}}), kid)
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", kid)
    assert fq.profile_public(prof)["avatar"]["pet"]["kind"] == "parrot"
    assert [p["name"] for p in fq.pets.list(kid)] == ["Coco"]
    # the owl of the badge «Busy bee» comes once
    fq.db.x("INSERT INTO badge(profile_id,badge) VALUES(?, 'ten_lessons')", kid)
    assert sorted(p["kind"] for p in fq.pets.list(kid)) == ["owl", "parrot"]
    level, badges, bought = fq.avatar_state(kid)
    assert "owl" in bought
    clock.add(days=7)                    # both die
    assert fq.pets.list(kid) == []
    level, badges, bought = fq.avatar_state(kid)
    assert "owl" not in bought and fq.pets.lost_kinds(kid) == {"owl", "parrot"}
    assert fq.pets.list(kid) == []       # the badge does not bring it back


def test_degu_is_a_pet_like_the_others(client, clock):
    ph, mia, _ = setup_family(client)
    h = login(client, mia, "1111")
    coins(client, ph, mia, 130)
    cat = client.get("/api/me/avatar", headers=h).json()
    degu = next(i for i in cat["items"] if i["id"] == "degu")
    assert degu["slot"] == "pet" and degu["rule"] == {"cost": 120} and not degu["unlocked"]
    assert client.post("/api/me/avatar/buy", json={"item": "degu"}, headers=h).status_code == 200
    r = client.post("/api/me/avatar", json={"avatar": {"items": {"pet": "degu"}}}, headers=h).json()
    assert r["avatar"]["items"] == {"pet": "degu"}
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["kind"] == "degu" and p["name"] == "Krümel" and p["stage"] == "baby"
    assert client.get("/api/me", headers=h).json()["profile"]["avatar"]["pet"]["kind"] == "degu"
    bot = next(b for b in client.get("/api/community/bots", headers=h).json()["bots"] if b.get("pet"))
    assert bot["kind"] == "degu" and bot["name"] == "Krümel"
    clock.add(days=7)
    assert client.get("/api/me/pets", headers=h).json()["pets"] == []       # not cared for: gone


# ---------------------------------------------------------------- pet shop: outfits, houses, furniture
def xp(client, ph, pid, amount):
    client.post("/api/parent/book", json={"profile_id": pid, "account": "xp", "amount": amount}, headers=ph)


def test_pet_shop_pays_with_coins_by_default(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)                 # 80 coins left
    shop = client.get("/api/me/pets/shop", headers=h).json()
    assert shop["currency"] == "coins" and shop["max_furniture"] == 6
    items = {i["id"]: i for i in shop["items"]}
    assert {i["cat"] for i in items.values()} == {"outfit", "house", "furniture"}
    assert items["dog_house"]["best"] == ["dog"] and items["bow"]["price"] == 30
    assert all(30 <= i["price"] <= 80 for i in items.values() if i["cat"] == "outfit")
    assert all(120 <= i["price"] <= 300 for i in items.values() if i["cat"] == "house")
    assert all(20 <= i["price"] <= 60 for i in items.values() if i["cat"] == "furniture")
    assert shop["pets"][0]["owned"] == [] and shop["pets"][0]["house"] is None
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bowl"}, headers=h)
    assert r.status_code == 200 and r.json()["pet"]["furniture"] == ["bowl"]
    assert r.json()["shop"]["balance"]["coins"] == 60
    # coins only: XP is refused, also too little money
    xp(client, ph, mia, 500)
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bed", "pay": "xp"}, headers=h)
    assert r.status_code == 400 and "another way" in r.json()["detail"]
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "dog_house"}, headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "Not enough coins"
    assert client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bowl"}, headers=h).status_code == 400   # has it
    assert client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "rocket"}, headers=h).status_code == 400
    assert client.get("/api/me", headers=h).json()["balances"]["coins"] == 60


def test_pet_shop_with_xp_keeps_the_level(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    client.put("/api/parent/settings", json={"pet_shop_currency": "xp"}, headers=ph)
    xp(client, ph, mia, 160)                          # level 3 (from 150 XP)
    before = client.get("/api/me", headers=h).json()["level"]
    assert before["level"] == 3
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "dog_house"}, headers=h)   # pays with XP
    assert r.status_code == 200 and r.json()["pet"]["house"] == "dog_house"
    assert r.json()["shop"]["balance"] == {"coins": 80, "xp": 40}
    me = client.get("/api/me", headers=h).json()
    assert me["level"] == before                       # spent XP do not lower the level
    assert client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bed", "pay": "coins"}, headers=h).status_code == 400
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "wheel"}, headers=h)      # 60 XP
    assert r.status_code == 400 and r.json()["detail"] == "Not enough XP"
    # the daily XP (goal, week) count only what was earned
    fq = client.app.state.fq
    assert fq.rewards.xp_today(mia) == 160 and fq.rewards.total_xp(mia) == 160


def test_pet_shop_mixed_lets_the_child_choose(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    client.put("/api/parent/settings", json={"pet_shop_currency": "mixed"}, headers=ph)
    xp(client, ph, mia, 50)
    assert client.get("/api/me/pets/shop", headers=h).json()["currency"] == "mixed"
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bow", "pay": "xp"}, headers=h).json()
    assert r["shop"]["balance"] == {"coins": 80, "xp": 20}
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "ball", "pay": "coins"}, headers=h).json()
    assert r["shop"]["balance"] == {"coins": 55, "xp": 20}
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "lamp", "pay": "xp"}, headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "Not enough XP"


def test_new_outfit_gives_mood_once(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    clock.add(hours=24)                               # mood 50
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bow"}, headers=h).json()["pet"]
    assert r["outfit"] == "bow" and r["mood"] == 70    # bought = put on: +20
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "sweater"}, headers=h).json()["pet"]
    assert r["outfit"] == "sweater" and r["mood"] == 90
    assert client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": "bow"}, headers=h).json()["pet"]["mood"] == 90
    assert client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": "sweater"}, headers=h).json()["pet"]["mood"] == 90
    r = client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": ""}, headers=h).json()["pet"]
    assert r["outfit"] is None
    assert client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": "crown"}, headers=h).status_code == 400   # not bought
    client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": "bow"}, headers=h)
    # the avatar badge shows the outfit
    assert client.get("/api/me", headers=h).json()["profile"]["avatar"]["pet"]["outfit"] == "bow"


def test_home_slows_the_mood_with_a_cap(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    coins(client, ph, mia, 1000)
    r = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "dog_house"}, headers=h).json()["pet"]
    assert r["slow"] == 25 and not r["happy_home"]
    clock.add(hours=24)
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["mood"] == round(100 - 50 * 0.75) and p["hunger"] == 50          # only the mood drops slower
    for it in ("bed", "bowl", "ball"):
        p = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": it}, headers=h).json()["pet"]
    assert p["slow"] == 40 and p["happy_home"] and p["furniture"] == ["bed", "bowl", "ball"]
    for it in ("wheel", "cushion", "lamp", "plant"):
        p = client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": it}, headers=h).json()["pet"]
    # only 6 pieces placed (the plant waits), and 25 + 6 × 5 = 55 → capped at 50 %
    assert len(p["furniture"]) == 6 and "plant" not in p["furniture"] and "plant" in p["owned"] and p["slow"] == 50
    client.post(f"/api/me/pets/{dog['id']}/play", headers=h)
    client.post(f"/api/me/pets/{dog['id']}/play", headers=h)                   # mood 100
    clock.add(hours=24)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["mood"] == 75   # 50 % slower
    # rearranging: the plant instead of the lamp, no house → only the furniture counts
    furn = ["bed", "bowl", "ball", "wheel", "cushion", "plant"]
    p = client.put(f"/api/me/pets/{dog['id']}/home", json={"house": None, "furniture": furn}, headers=h).json()["pet"]
    assert p["house"] is None and p["furniture"] == furn and p["slow"] == 30 and not p["happy_home"]
    assert client.put(f"/api/me/pets/{dog['id']}/home", json={"house": "dog_house", "furniture": furn + ["lamp"]},
                      headers=h).status_code == 400                             # 7 pieces
    assert client.put(f"/api/me/pets/{dog['id']}/home", json={"house": "castle", "furniture": []}, headers=h).status_code == 400
    clock.add(hours=10)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["mood"] == 75 - 15   # 50 / 24 × 0.7 × 10 h ≈ 14.6


def test_unit_slowdown():
    from familyquest.pets import slowdown
    it = lambda i, used=1: {"item": i, "used": used}                          # noqa: E731
    assert slowdown([]) == 0
    assert slowdown([it("castle")]) == 0.25
    assert slowdown([it("castle", 0), it("bed")]) == 0.05
    assert slowdown([it("castle")] + [it(f) for f in ("bed", "bowl", "ball", "wheel", "cushion", "lamp")]) == 0.5
    assert slowdown([it("bow")]) == 0


def test_items_are_lost_when_the_pet_dies(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    coins(client, ph, mia, 500)
    for it in ("castle", "bow", "bed"):
        client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": it}, headers=h)
    fq = client.app.state.fq
    assert fq.db.val("SELECT COUNT(*) FROM pet_item WHERE pet_id=?", dog["id"]) == 3
    clock.add(days=10)                               # even slower mood: all at 0 long enough
    fq.pets.tick()
    assert client.get("/api/me/pets", headers=h).json()["pets"] == []
    assert fq.db.val("SELECT COUNT(*) FROM pet_item WHERE pet_id=?", dog["id"]) == 0
    assert client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "lamp"}, headers=h).status_code == 400
    assert client.post("/api/me/avatar/buy", json={"item": "dog"}, headers=h).status_code == 200
    new = client.get("/api/me/pets/shop", headers=h).json()["pets"][0]
    assert new["id"] != dog["id"] and new["owned"] == [] and new["house"] is None and new["outfit"] is None


def test_other_child_cannot_shop_for_my_pet(client, clock):
    ph, mia, leo = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bow"}, headers=h)
    hl = login(client, leo)
    coins(client, ph, leo, 500)
    assert client.post(f"/api/me/pets/{dog['id']}/buy", json={"item": "bed"}, headers=hl).status_code == 403
    assert client.put(f"/api/me/pets/{dog['id']}/wear", json={"outfit": "bow"}, headers=hl).status_code == 403
    assert client.put(f"/api/me/pets/{dog['id']}/home", json={"house": None, "furniture": []}, headers=hl).status_code == 403
    assert client.get("/api/me/pets/shop", headers=hl).json()["pets"] == []
    assert client.get("/api/me", headers=hl).json()["balances"]["coins"] == 500


def bal(client, h):
    return client.get("/api/me", headers=h).json()["balances"]["coins"]


def test_pet_sitting_by_a_family_member(client, clock):
    ph, mia, leo = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    hl = login(client, leo)
    coins(client, ph, leo, 20)
    until = (clock.t.date() + timedelta(days=3)).isoformat()
    assert client.post(f"/api/me/pets/{dog['id']}/sit", json={"sitter": mia, "until": until}, headers=h).status_code == 400   # not myself
    assert client.post(f"/api/me/pets/{dog['id']}/sit", json={"sitter": leo, "until": "2020-01-01"}, headers=h).status_code == 400
    assert client.post(f"/api/me/pets/{dog['id']}/sit", json={"sitter": leo, "until": until}, headers=hl).status_code == 403  # not Leo's pet
    r = client.post(f"/api/me/pets/{dog['id']}/sit", json={"sitter": leo, "until": until}, headers=h).json()["pet"]
    assert r["sitter"]["id"] == leo and r["sit_until"] == until
    clock.add(hours=24)
    d = client.get("/api/me/pets", headers=hl).json()
    assert d["pets"] == [] and [p["id"] for p in d["sitting"]] == [dog["id"]] and d["sitting"][0]["owner"]["id"] == mia
    assert d["sitting"][0]["hunger"] == 50                              # the bars keep dropping while sitting
    mia_before = bal(client, h)
    r = client.post(f"/api/me/pets/{dog['id']}/feed", headers=hl)        # the sitter feeds – and pays the food
    assert r.status_code == 200 and r.json()["pet"]["hunger"] == 90 and r.json()["coins"] == 18
    assert bal(client, h) == mia_before
    assert client.put(f"/api/me/pets/{dog['id']}", json={"name": "Hack"}, headers=hl).status_code == 403   # only care, no renaming
    # after the last day the pet is back with its owner
    clock.add(days=3)
    assert client.get("/api/me/pets", headers=hl).json()["sitting"] == []
    assert client.post(f"/api/me/pets/{dog['id']}/play", headers=hl).status_code == 403
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["sitter"] is None
    # fetched early
    client.post(f"/api/me/pets/{dog['id']}/sit", json={"sitter": leo, "until": (clock.t.date() + timedelta(days=5)).isoformat()}, headers=h)
    client.post(f"/api/me/pets/{dog['id']}/fetch", headers=h)
    assert client.get("/api/me/pets", headers=hl).json()["sitting"] == []


def test_pet_hotel(client, clock):
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    client.put("/api/parent/settings", json={"pet_hotel_cost": 7}, headers=ph)
    coins(client, ph, mia, 100 - bal(client, h))
    assert client.get("/api/me/pets", headers=h).json()["hotel_cost"] == 7
    assert client.post(f"/api/me/pets/{dog['id']}/hotel", json={"days": 0}, headers=h).status_code == 400
    assert client.post(f"/api/me/pets/{dog['id']}/hotel", json={"days": 20}, headers=h).status_code == 400   # 140 coins: too few
    clock.add(hours=30)
    r = client.post(f"/api/me/pets/{dog['id']}/hotel", json={"days": 5}, headers=h).json()
    assert r["coins"] == 65 and r["pet"]["paused"] == "hotel" and r["pet"]["hotel_until"]
    assert client.post(f"/api/me/pets/{dog['id']}/feed", headers=h).status_code == 400   # the hotel feeds it
    clock.add(days=4)                                                    # no decay, no death in the hotel
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["paused"] == "hotel" and not p["dying"]
    clock.add(days=1, hours=12)                                          # back since 12 hours: fed, happy and clean, then dropping
    p = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert p["paused"] is None and p["hunger"] == 75 and p["clean"] == 83
    # early fetch: unused full days are paid back
    client.post(f"/api/me/pets/{dog['id']}/hotel", json={"days": 3}, headers=h)
    clock.add(hours=12)
    r = client.post(f"/api/me/pets/{dog['id']}/fetch", headers=h).json()
    assert r["coins"] == 65 - 21 + 14 and r["pet"]["hunger"] == 100 and r["pet"]["hotel_until"] is None


def test_hamster_mines_coins_while_healthy(client, clock):
    ph, mia, _ = setup_family(client)
    h = login(client, mia, "1111")
    coins(client, ph, mia, 300)
    assert client.post("/api/me/avatar/buy", json={"item": "hamster"}, headers=h).status_code == 200
    assert bal(client, h) == 0
    old = (clock.t - timedelta(days=8)).isoformat()                    # a grown hamster (babies mine from 7 days)
    client.app.state.fq.db.x("UPDATE pet SET born_at=? WHERE profile_id=?", old, mia)
    ham = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert ham["kind"] == "hamster" and ham["emoji"] == "🐹" and ham["mining"] == {"on": True, "baby": False, "per_day": 15, "total": 0}
    clock.add(hours=12)                                                  # healthy all the time: 7.5 coins → 7 booked
    ham = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert bal(client, h) == 7 and ham["mining"]["total"] == 7
    clock.add(hours=24)                                                  # hunger/mood reach 50 after 24 h – then it stops
    ham = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert bal(client, h) == 15 and not ham["mining"]["on"]
    client.put("/api/parent/settings", json={"hamster_coins_per_day": 24}, headers=ph)
    for a in ("feed", "play", "wash"):
        client.post(f"/api/me/pets/{ham['id']}/{a}", headers=h)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["mining"]["on"]


def test_double_tap_fetch_pays_back_once(client, clock, monkeypatch):
    """Two «fetch» requests at the same time: the pet hotel is paid back once (one pet change at a time)."""
    import threading
    from familyquest import pets as P
    ph, mia, _ = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    coins(client, ph, mia, 300)
    assert client.post(f"/api/me/pets/{dog['id']}/hotel", json={"days": 30}, headers=h).status_code == 200
    client.app.state.fq.db.set_setting("pet_hotel_cost", 100)                       # the price paid counts, not today's
    gate = threading.Barrier(2)
    orig = P.Pets.refresh

    def slow(self, pid):
        r = orig(self, pid)
        try:
            gate.wait(timeout=1)
        except threading.BrokenBarrierError:
            pass
        return r
    monkeypatch.setattr(P.Pets, "refresh", slow)
    ts = [threading.Thread(target=lambda: client.post(f"/api/me/pets/{dog['id']}/fetch", headers=h)) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    monkeypatch.setattr(P.Pets, "refresh", orig)
    hotel = client.app.state.fq.db.q("SELECT amount FROM ledger WHERE profile_id=? AND event='pet_hotel' ORDER BY id", mia)
    assert [r["amount"] for r in hotel] == [-300.0, 300.0]          # paid once, paid back once – at the price paid
    r = client.put("/api/parent/settings", content='{"pet_hotel_cost": Infinity}', headers={**ph, "content-type": "application/json"})
    assert r.status_code == 400 and client.get("/api/me/pets", headers=h).status_code == 200


def test_more_pets_of_a_kind_and_babies(client, clock, monkeypatch):
    from familyquest import pets as P
    ph, mia, leo = setup_family(client)
    h, dog = buy_dog(client, ph, mia)
    coins(client, ph, mia, 1000)
    assert client.post("/api/me/pets/more", json={"kind": "cat"}, headers=h).status_code == 400      # no cat yet
    r = client.post("/api/me/pets/more", json={"kind": "dog"}, headers=h)
    assert r.status_code == 200 and r.json()["pet"]["name"] == "Bello 2" and r.json()["pet"]["stage"] == "baby"
    d = client.get("/api/me/pets", headers=h).json()
    assert len(d["pets"]) == 2 and d["more"][0]["price"] == 120 and d["more"][0]["count"] == 2
    dog2 = d["pets"][1]["id"]
    # too young
    r = client.post(f"/api/me/pets/{dog['id']}/breed", json={"partner": dog2}, headers=h)
    assert r.status_code == 400 and "3 days" in r.json()["detail"]
    clock.add(days=3)
    for pid_ in (dog["id"], dog2):                                     # healthy again
        for a in ("feed", "play", "wash"):
            client.post(f"/api/me/pets/{pid_}/{a}", headers=h)
            client.post(f"/api/me/pets/{pid_}/{a}", headers=h)
    assert client.get("/api/me/pets", headers=h).json()["breeding"][str(dog["id"])]["why"] is None
    monkeypatch.setattr(P.random, "random", lambda: 0.1)               # two babies
    r = client.post(f"/api/me/pets/{dog['id']}/breed", json={"partner": dog2}, headers=h)
    assert r.status_code == 200 and len(r.json()["babies"]) == 2
    assert len(client.get("/api/me/pets", headers=h).json()["pets"]) == 4
    # the pair rests 14 days; at most 6 of one kind
    r = client.post(f"/api/me/pets/{dog['id']}/breed", json={"partner": dog2}, headers=h)
    assert r.status_code == 400
    for _ in range(2):
        assert client.post("/api/me/pets/more", json={"kind": "dog"}, headers=h).status_code == 200
    assert client.post("/api/me/pets/more", json={"kind": "dog"}, headers=h).status_code == 400
    # another child cannot breed my pets
    hl = login(client, leo)
    assert client.post(f"/api/me/pets/{dog['id']}/breed", json={"partner": dog2}, headers=hl).status_code == 403


def test_baby_hamster_mines_from_seven_days_and_last_of_kind_keeps_unlock(client, clock):
    ph, mia, _ = setup_family(client)
    h = login(client, mia, "1111")
    coins(client, ph, mia, 600)
    client.post("/api/me/avatar/buy", json={"item": "hamster"}, headers=h)
    ham = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert ham["mining"]["baby"] is True and ham["mining"]["on"] is False
    clock.add(hours=12)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["mining"]["total"] == 0
    # two hamsters: when one dies the other keeps the unlock
    client.post("/api/me/pets/more", json={"kind": "hamster"}, headers=h)
    fq = client.app.state.fq
    first = fq.db.q1("SELECT * FROM pet WHERE profile_id=? ORDER BY id LIMIT 1", mia)
    fq.pets._die(mia, first, clock.t)
    assert fq.db.q1("SELECT 1 FROM unlock WHERE profile_id=? AND item='hamster'", mia)
    assert len(client.get("/api/me/pets", headers=h).json()["pets"]) == 1


def test_dino_starts_as_an_egg_and_hatches_on_day_one(client, clock):
    ph, mia, _ = setup_family(client)
    h = login(client, mia, "1111")
    coins(client, ph, mia, 500)
    assert client.post("/api/me/avatar/buy", json={"item": "dino"}, headers=h).status_code == 200
    egg = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert egg["kind"] == "dino" and egg["stage"] == "egg"
    assert client.post(f"/api/me/pets/{egg['id']}/play", headers=h).status_code == 400          # nothing to care for yet
    clock.add(hours=10)
    assert client.get("/api/me/pets", headers=h).json()["pets"][0]["hunger"] == 100            # no decay as an egg
    clock.add(days=1)
    baby = client.get("/api/me/pets", headers=h).json()["pets"][0]
    assert baby["stage"] == "baby" and client.post(f"/api/me/pets/{egg['id']}/play", headers=h).status_code == 200
