"""Etappe E: Family Quest profiles are Planer persons, Planer points and coins are one balance."""
import asyncio
import json

from familyquest.planer import rewards as prew
from familyquest.planer.host import PlanerHost


async def _bridge(fq):
    mia = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name, color) VALUES('Mia', '#ff6b6b')")
    papa = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name, role, pin_hash) VALUES('Papa', 'parent', 'x')")
    await asyncio.to_thread(fq.rewards.book, mia, "coins", 40, "start", "Start")
    host = PlanerHost(fq)
    fq.planer_host = host
    await host.start(ha_expected=False)
    b = host.bridge
    p = host.planner
    await b.sync()
    persons = p.data["persons"]
    links = b.state()["links"]
    assert persons[links[str(mia)]]["name"] == "Mia" and persons[links[str(mia)]]["role"] == "kid"
    assert persons[links[str(papa)]]["role"] == "adult" and persons[links[str(mia)]]["color"] == "#ff6b6b"
    lea = links[str(mia)]
    # coins from before the link are in the Planer now
    assert prew.balance(p.data["ledger"], lea) == 40

    # a chore done in the Planer → coins in Family Quest
    wd = str(p.today().isoweekday())
    cid = await p.async_save_chore(None, {"title": "Tisch decken", "points": 10,
                                          "assign": {lea: {wd: {"every": 1, "offset": 0, "window": 1}}}})
    await p.async_rollover()
    item = next(k for k, v in p.data["items"].items() if v["chore_id"] == cid)
    await p.async_set_item(item, True)
    await b.sync()
    gained = prew.balance(p.data["ledger"], lea) - 40
    assert gained > 0
    assert fq.rewards.balance(mia, "coins") == 40 + gained
    # un-checked again → booked back
    await p.async_set_item(item, False)
    await b.sync()
    assert fq.rewards.balance(mia, "coins") == 40 == prew.balance(p.data["ledger"], lea)

    # coins earned while learning → Planer points
    await asyncio.to_thread(fq.rewards.book, mia, "coins", 15, "lesson_done", "Lektion")
    await b.sync()
    assert prew.balance(p.data["ledger"], lea) == 55 == fq.rewards.balance(mia, "coins")
    # a second sync changes nothing
    assert not await b.sync()
    assert fq.rewards.balance(mia, "coins") == 55

    # renamed profile → renamed person; person added in the Planer → new profile
    await asyncio.to_thread(fq.db.x, "UPDATE profile SET name='Mia Sofia' WHERE id=?", mia)
    await p.async_add_person("Leo")
    await b.sync()
    assert persons[lea]["name"] == "Mia Sofia"
    leo = fq.db.q1("SELECT * FROM profile WHERE name='Leo'")
    assert leo and leo["role"] == "kid" and b.state()["links"][str(leo["id"])] in persons
    # removed profile → removed person
    await asyncio.to_thread(fq.db.x, "UPDATE profile SET archived=1 WHERE id=?", leo["id"])
    await b.sync()
    assert "Leo" not in [v["name"] for v in persons.values()]
    await host.stop()


def test_bridge_profiles_and_points(fq):
    asyncio.run(_bridge(fq))


async def _import(fq, tmp_path, monkeypatch):
    from familyquest.planer import importer
    lea = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name) VALUES('Lea')")
    await asyncio.to_thread(fq.rewards.book, lea, "coins", 10, "start", "Start")
    host = PlanerHost(fq)
    fq.planer_host = host
    await host.start(ha_expected=False)
    await host.bridge.sync()
    # the Home Assistant integration's store file
    data = {"persons": {"lea": {"name": "Lea", "color": "#123456", "image": "img:/family_planer_files/avatars/lea_1.jpg"},
                        "tom": {"name": "Tom", "color": "#654321", "role": "kid"}},
            "chores": {"c1": {"title": "Hund füttern", "assign": {}}},
            "ledger": [{"id": "e1", "pid": "lea", "pts": 25, "kind": "chore", "ref": "item:x", "text": "Hund", "ts": "2026-11-01T10:00:00"},
                       {"id": "e2", "pid": "tom", "pts": 7, "kind": "bonus", "ref": "day:x", "text": "", "ts": "2026-11-01T10:00:00"}],
            "rewards": {}, "requests": {}, "items": {}, "history": {}, "settings": {}, "lists": {}}
    (tmp_path / "ha" / ".storage").mkdir(parents=True)
    (tmp_path / "ha" / "family_planer" / "avatars").mkdir(parents=True)
    (tmp_path / "ha" / "family_planer" / "avatars" / "lea_1.jpg").write_bytes(b"\xff\xd8\xff jpeg")
    (tmp_path / "ha" / ".storage" / "family_planer.01ABC").write_text(
        json.dumps({"version": 1, "key": "family_planer.01ABC", "data": data}))
    monkeypatch.setattr(importer, "HA_CONFIG", tmp_path / "ha")
    src = importer.sources()
    assert src[0]["id"] == "family_planer.01ABC" and {p["name"] for p in src[0]["persons"]} == {"Lea", "Tom"}
    await importer.run(fq, importer.read_source("family_planer.01ABC"), importer.HA_CONFIG / "family_planer")
    p = host.planner
    links = host.bridge.state()["links"]
    assert links[str(lea)] == "lea" and p.data["chores"]["c1"]["title"] == "Hund füttern"
    # points of both sides are added up
    assert fq.rewards.balance(lea, "coins") == 35 == prew.balance(p.data["ledger"], "lea")
    tom = fq.db.q1("SELECT id FROM profile WHERE name='Tom'")["id"]
    assert fq.rewards.balance(tom, "coins") == 7
    assert (fq.settings.data_dir / "family_planer" / "avatars" / "lea_1.jpg").is_file()
    await host.stop()


def test_import_existing_planer(fq, tmp_path, monkeypatch):
    asyncio.run(_import(fq, tmp_path, monkeypatch))


def test_own_chores_move_to_the_planer(client):
    import time
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()
    ph = {"X-FQ-Parent": r["parent_token"]}
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    leo = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=ph).json()["id"]
    chore = lambda **kw: client.post("/api/parent/chores", json={"points": 10, "icon": "🛏️", "kind": "duty", **kw}, headers=ph)
    assert chore(name="Bett machen", frequency="daily", profiles=[mia]).status_code == 200
    assert chore(name="Abfall", frequency="weekly", assign="rotate", rotate_every="week", profiles=[mia, leo]).status_code == 200
    assert chore(name="Keller", frequency="once", date="2030-01-01", profiles=[leo]).status_code == 200
    res = client.post("/api/planer/chores/take-over", headers=ph).json()
    assert sorted(res["moved"]) == ["Abfall", "Bett machen"] and res["kept"] == ["Keller"]
    planner = client.app.state.fq.planer_host.planner
    chores = {c["title"]: c for c in planner.data["chores"].values()}
    bed, trash = chores["🛏️ Bett machen"], chores["🛏️ Abfall"]
    assert len(bed["assign"]) == 1 and len(next(iter(bed["assign"].values()))) == 7 and bed["points"] == 10
    rules = [r["1"] for r in trash["assign"].values()]
    assert {r["every"] for r in rules} == {2} and {r["offset"] for r in rules} == {0, 1} and rules[0]["window"] == 7
    # the own plan keeps only the one-off chore
    assert [c["name"] for c in client.get("/api/parent/chores", headers=ph).json()["chores"] if c["active"]] == ["Keller"]
    # Mia sees the Planer chore on her start page and ticks it off → coins
    kid = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia}).json()["token"]}
    me = client.get("/api/me", headers=kid).json()
    bed = next(c for c in me["chores"] if c["summary"] == "Bett machen")
    assert bed["icon"] == "🛏️" and bed["points"] == 10          # points per chore, as in the own plan
    bed_uid = bed["uid"]
    assert bed_uid.startswith("fp:")
    before = me["balances"]["coins"]
    done = client.post(f"/api/me/chores/{bed_uid}/done", headers=kid).json()
    assert next(c for c in done["chores"] if c["uid"] == bed_uid)["done"]
    for _ in range(30):
        if client.get("/api/me", headers=kid).json()["balances"]["coins"] > before:
            break
        time.sleep(0.1)
    assert client.get("/api/me", headers=kid).json()["balances"]["coins"] > before
    # Leo cannot tick off Mia's chore
    leo_h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.post(f"/api/me/chores/{bed_uid}/done", headers=leo_h).status_code == 400


async def _no_double_booking(fq):
    """M5 (review 2): the bookings and the bridge state are written in one transaction, and a Planer entry is booked
    once by its ref – also when the state was lost (a crash between the two before)."""
    mia = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name) VALUES('Mia')")
    host = PlanerHost(fq)
    fq.planer_host = host
    await host.start(ha_expected=False)
    b, p = host.bridge, host.planner
    await b.sync()
    lea = b.state()["links"][str(mia)]
    wd = str(p.today().isoweekday())
    cid = await p.async_save_chore(None, {"title": "Tisch decken", "points": 10,
                                          "assign": {lea: {wd: {"every": 1, "offset": 0, "window": 1}}}})
    await p.async_rollover()
    item = next(k for k, v in p.data["items"].items() if v["chore_id"] == cid)
    await p.async_set_item(item, True)
    await b.sync()
    coins = fq.rewards.balance(mia, "coins")
    assert coins > 0
    st = b.state()
    st["seen"] = {}                                      # as if the state had not been saved after the booking
    await asyncio.to_thread(b.kv.save, "fq.planer_bridge", st)
    await b.sync()
    assert fq.rewards.balance(mia, "coins") == coins
    assert fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'fp:%' AND ref NOT LIKE 'fp:init:%'") == 1
    await host.stop()


def test_a_planer_entry_is_booked_once(fq):
    asyncio.run(_no_double_booking(fq))
