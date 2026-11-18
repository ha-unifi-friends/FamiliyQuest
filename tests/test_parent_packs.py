"""Parents see every learning pack in the app (also drafts and switched-off packs) to try them out; children only
their own active packs."""
from tests.test_api import setup_family


def _draft(client, ph):
    pack = {"id": "probe-draft", "titel": "Probe", "fach": "englisch", "sprache": "en", "pfad": True,
            "einheiten": [{"id": "a", "karten": [{"de": "Hund", "en": "dog"}, {"de": "Katze", "en": "cat"}]},
                          {"id": "b", "karten": [{"de": "Maus", "en": "mouse"}, {"de": "Kuh", "en": "cow"}]}]}
    r = client.post("/api/parent/import/json", json=pack, headers=ph)
    assert r.status_code == 200, r.text


def test_parent_sees_and_tries_all_packs_children_do_not(client):
    ph, mia, _ = setup_family(client)
    _draft(client, ph)
    client.post("/api/parent/packs/mathe-5kl/status", json={"status": "disabled"}, headers=ph)
    me = client.get("/api/me", headers=ph).json()
    st = {s["pack"]: s["status"] for s in me["subjects"]}
    assert st["probe-draft"] == "draft" and st["mathe-5kl"] == "disabled"
    assert list(st.values())[0] == "active"                       # active packs first
    fq = client.app.state.fq
    assert len(st) == fq.db.val("SELECT COUNT(*) FROM pack WHERE kind='pack'")
    d = client.get("/api/me/packs/probe-draft", headers=ph).json()
    assert all(u["unlocked"] for u in d["progress"]["units"])     # nothing is locked for parents
    s = client.post("/api/me/session", json={"mode": "path", "pack": "probe-draft", "unit": "b"}, headers=ph)
    assert s.status_code == 200, s.text
    assert client.post("/api/me/session", json={"mode": "daily"}, headers=ph).status_code == 200
    papa = me["profile"]["id"]                                    # the daily lesson only uses the active packs
    real = {p.id for p in fq.packs.for_profile(papa, try_all=False)}
    assert "probe-draft" not in real and "mathe-5kl" not in real and real
    # a child: no draft, no switched-off pack, no pack not switched on
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    kid = {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert "probe-draft" not in kid and "mathe-5kl" not in kid
    assert kid == {p.id for p in fq.packs.for_profile(mia)}
    assert client.get("/api/me/packs/probe-draft", headers=h).status_code == 404
    assert client.post("/api/me/session", json={"mode": "path", "pack": "probe-draft"}, headers=h).status_code != 200


def test_a_pack_can_override_xp_and_coins_per_finished_lesson(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    r = client.post("/api/parent/packs/mathe-5kl/rewards", json={"xp": 33, "coins": 0}, headers=ph)
    assert r.status_code == 200 and r.json()["rewards"] == {"xp": 33, "coins": 0}
    assert next(p for p in client.get("/api/parent/packs", headers=ph).json()["packs"] if p["id"] == "mathe-5kl")["rewards"] == {"xp": 33, "coins": 0}
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}

    def lesson(pack):
        s = client.post("/api/me/session", json={"mode": "path", "pack": pack}, headers=h).json()
        for i, _ in enumerate(s["steps"]):
            client.post(f"/api/me/session/{s['id']}/answer", json={"step": i, "answer": "x"}, headers=h)
        client.post(f"/api/me/session/{s['id']}/finish", headers=h)
        return {r["account"]: r["amount"] for r in fq.db.q("SELECT account, amount FROM ledger WHERE ref=? AND event='lesson_done'", s["id"])}

    assert lesson("mathe-5kl") == {"xp": 33}                       # 0 coins: no coin booking
    other = lesson("deutsch-5kl")
    assert other.get("xp") == 10 and other.get("coins") == 10      # the family rule
    client.post("/api/parent/packs/mathe-5kl/rewards", json={}, headers=ph)
    assert lesson("mathe-5kl").get("xp") == 10
    assert client.post("/api/parent/packs/nope/rewards", json={"xp": 1}, headers=ph).status_code == 404
