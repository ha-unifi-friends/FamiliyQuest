"""Regression tests for the code / security review of 2026-11-19 (one block per finding)."""
import sqlite3

import pytest

from familyquest import db as dbmod
from familyquest.community import CommunityError
from test_api import setup_family


def _kid_token(client, pid, pin=None):
    body = {"profile_id": pid, **({"pin": pin} if pin else {})}
    return {"X-FQ-Token": client.post("/api/login", json=body).json()["token"]}


# ---------------------------------------------------------------- 2: a deleted profile's id is never used again
def test_deleted_profile_id_is_not_reused_and_books_go(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    m = fq.db.q1("SELECT * FROM profile WHERE id=?", leo)
    diary = fq.stories.create(m, "Mein Tagebuch", visibility="me")
    shared = fq.stories.create(m, "Für alle", visibility="family")
    fq.db.x("INSERT INTO story_read(story_id, profile_id) VALUES(?,?)", shared, mia)
    # Leo took over a chore of Mia in a running deal – it goes back to her
    from test_deals import chore
    dishes = chore(fq, "Abwaschen", mia, points=10)
    mp = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    d = fq.deals.offer(m, mia, [{"t": "chore", "chore": dishes, "times": 1}], [{"t": "text", "text": "x"}])
    fq.deals.accept(mp, d["id"], 1)
    tid = fq.db.val("SELECT id FROM chore_task WHERE deal_id=?", d["id"])
    assert fq.db.val("SELECT profile_id FROM chore_task WHERE id=?", tid) == leo
    assert client.delete(f"/api/parent/profiles/{leo}?name=leo&mode=delete", headers=ph).status_code == 200
    assert not fq.db.q("SELECT 1 FROM story WHERE id IN (?,?)", diary, shared)
    assert not fq.db.q("SELECT 1 FROM story_read WHERE story_id=?", shared)
    t = fq.db.q1("SELECT * FROM chore_task WHERE id=?", tid)
    assert t["profile_id"] == mia and t["deal_id"] is None and t["from_id"] is None
    # a new profile gets a new id – nothing of Leo's (books, ledger, …) belongs to it
    r = client.post("/api/parent/profiles", json={"name": "Neu"}, headers=ph)
    new = r.json()["id"]
    assert new > leo
    fq.db.x("INSERT INTO story(title, author_id, data, visibility) VALUES('alt', ?, '{}', 'me')", new + 5)  # an orphan row
    fq.db.x("DELETE FROM profile WHERE id=?", new)
    assert fq.db.x("INSERT INTO profile(name) VALUES('Noch einer')") == new + 1


def test_reuse_probe_private_book_not_inherited(fq):
    """The reviewer's probe: a profile deleted the raw way – a new profile still never gets the old id."""
    fq.db.x("INSERT INTO profile(name, role) VALUES('Papa', 'parent')")
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    m = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    sid = fq.stories.create(m, "Mein Tagebuch", visibility="me")
    fq.db.x("DELETE FROM profile WHERE id=?", mia)
    new = fq.db.x("INSERT INTO profile(name) VALUES('Neu')")
    assert new != mia
    with pytest.raises(CommunityError):
        fq.stories.get(fq.db.q1("SELECT * FROM profile WHERE id=?", new), sid)


def test_migration_42_keeps_rows_and_starts_above_every_old_id(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path, isolation_level=None)
    con.execute("PRAGMA foreign_keys=ON")
    for i, sql in enumerate(dbmod.MIGRATIONS[:41], start=1):
        con.executescript("BEGIN;" + sql + f";PRAGMA user_version={i};COMMIT;")
    con.execute("INSERT INTO profile(id, name) VALUES(1, 'Papa'), (2, 'Mia'), (3, 'Leo')")
    con.execute("INSERT INTO deal(a_id, b_id, by_id, terms) VALUES(2, 3, 2, '{}')")
    con.execute("INSERT INTO story(title, author_id, data) VALUES('alt', 9, '{}')")     # a deleted author (id 9)
    con.execute("INSERT INTO story_read(story_id, profile_id) VALUES(1, 3)")
    con.close()
    d = dbmod.Database(path)
    assert d.val("PRAGMA user_version") == len(dbmod.MIGRATIONS) and d.val("PRAGMA foreign_keys") == 1
    assert d.val("SELECT COUNT(*) FROM profile") == 3 and d.val("SELECT COUNT(*) FROM deal") == 1   # nothing cascaded
    assert d.val("SELECT COUNT(*) FROM story_read") == 1
    assert d.x("INSERT INTO profile(name) VALUES('Neu')") == 10
    assert not d.q("PRAGMA foreign_key_check")
    d.x("DELETE FROM profile WHERE id=3")                                     # the foreign keys still cascade
    assert d.val("SELECT COUNT(*) FROM deal") == 0 and d.val("SELECT COUNT(*) FROM story_read") == 0
    assert d.q1("SELECT 1 FROM sqlite_master WHERE type='index' AND name='ledger_ref'")


# ---------------------------------------------------------------- 5: deal reservations in the shop and the Planer
def test_shop_checks_the_reservation_inside_the_transaction(fq, kid):
    from familyquest.rewards.shop import ShopError
    fq.rewards.book(kid, "coins", 100, "test")
    ice = next(o for o in fq.shop.offers(kid) if o["name"] == "Ice cream")
    other = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    did = fq.db.x("INSERT INTO deal(a_id, b_id, terms) VALUES(?,?, '{}')", kid, other)
    orig = fq.shop.offers

    def offers_then_a_deal(pid):                       # a deal reserves 50 coins right after the offers were checked
        out = orig(pid)
        fq.db.x("INSERT INTO deal_hold(deal_id, profile_id, kind, amount) VALUES(?,?, 'coins', 50)", did, kid)
        return out
    fq.shop.offers = offers_then_a_deal
    with pytest.raises(ShopError):
        fq.shop.redeem(kid, ice["id"])
    assert fq.rewards.balance(kid, "coins") == 100 and not fq.db.q("SELECT 1 FROM redemption")


def test_planer_mirrors_balance_minus_reserved(fq):
    import asyncio
    from familyquest.planer import rewards as prew
    from familyquest.planer.host import PlanerHost

    async def run():
        mia = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name) VALUES('Mia')")
        leo = await asyncio.to_thread(fq.db.x, "INSERT INTO profile(name) VALUES('Leo')")
        await asyncio.to_thread(fq.rewards.book, mia, "coins", 40, "start", "Start")
        host = PlanerHost(fq)
        fq.planer_host = host
        await host.start(ha_expected=False)
        b, p = host.bridge, host.planner
        await b.sync()
        person = b.state()["links"][str(mia)]
        assert prew.balance(p.data["ledger"], person) == 40
        did = await asyncio.to_thread(fq.db.x, "INSERT INTO deal(a_id, b_id, terms) VALUES(?,?, '{}')", mia, leo)
        hid = await asyncio.to_thread(fq.db.x, "INSERT INTO deal_hold(deal_id, profile_id, kind, amount) VALUES(?,?, 'coins', 15)", did, mia)
        await b.sync()
        assert prew.balance(p.data["ledger"], person) == 25            # 15 coins promised in a deal
        assert fq.rewards.balance(mia, "coins") == 40                  # nothing booked back into Family Quest
        await asyncio.to_thread(fq.rewards.book, mia, "coins", -15, "deal", "Deal", f"deal:{did}:coins:a:all")       # the deal pays …
        await asyncio.to_thread(fq.db.x, "UPDATE deal_hold SET paid=15, active=0 WHERE id=?", hid)                   # … the reservation ends
        await b.sync()
        assert prew.balance(p.data["ledger"], person) == 25 == fq.rewards.balance(mia, "coins")
        assert not await b.sync()
        await host.stop()
    asyncio.run(run())


# ---------------------------------------------------------------- 6: the poll time has its own setting
def test_integration_poll_does_not_write_the_token_setting(fq):
    from familyquest import integration
    integration.set_enabled(fq, True)
    before = integration.config(fq)
    orig = fq.db.set_setting
    written = []
    fq.db.set_setting = lambda k, v: (written.append(k), orig(k, v))
    integration.polled(fq)
    integration.polled(fq)                              # the same 10 minutes: not written again
    assert written == [integration.POLL_KEY]
    assert integration.config(fq) == before and integration.status(fq)["last_poll"]


# ---------------------------------------------------------------- 7: Infinity / NaN in the realtime syncs
def test_langstrecke_report_ignores_non_finite_inputs():
    from test_langstrecke import at, mine, table
    t, clock = table(humans=(("1", 0),), bots=1)
    at(t, clock, 5)
    inputs = [[5.2, "u", float("inf")], [5.2, "u", float("nan")], [float("nan"), "l", 0], [5.3, "l", 0]]
    assert t.report("1", inputs) == 1
    assert mine(t)["ev"][-1][1:] == ["l", 0]


def _raw(client, url, body, h):
    return client.post(url, content=body, headers={**h, "Content-Type": "application/json"})


def test_realtime_bodies_refuse_infinity_and_nan(client):
    from test_pong4 import _family
    ph, (mia, hm), (leo, hl), (ben, hb) = _family(client)
    client.post("/api/community/pong4", json={"seats": {"A2": {"bot": "easy"}, "B1": {"bot": "normal"}, "B2": {"bot": "hard"}}},
                headers=hm)
    client.post("/api/community/pong4/start", headers=hm)
    assert _raw(client, "/api/community/pong4/sync", '{"pad": Infinity}', hm).status_code == 422
    assert _raw(client, "/api/community/pong4/sync", '{"pad": 1e999}', hm).status_code == 422
    for url, body in (("/api/community/jump/sync", '{"t": NaN}'), ("/api/community/snack/sync", '{"spent": Infinity}'),
                      ("/api/community/langstrecke/sync", '{"inputs": [[1, "u", 1e999]]}'),
                      ("/api/community/klatsch/sync", '{"taps": [Infinity]}'),
                      ("/api/community/boards/1/sync", '{"ops": [{"op": "del", "id": 1e999}]}')):
        assert _raw(client, url, body, hl).status_code < 500, url                           # never 500
    assert _raw(client, "/api/community/quiz/answer", '{"idx": 0, "value": NaN}', hl).status_code == 422
    # the host's dict fields are free JSON: a ball or points with Infinity are ignored, the table keeps answering
    fq = client.app.state.fq
    st = fq.pong4.sync(mia, 0.5, ball={"x": float("inf"), "y": 0.5, "vx": 0, "vy": 0}, points={"A": float("inf"), "B": 1})
    assert st["pong"]["ball"] is None or all(abs(v) < 1e9 for v in st["pong"]["ball"].values())
    assert client.post("/api/community/pong4/sync", json={"pad": 0.3}, headers=hm).status_code == 200
    body = '{"event": "lesson_done", "account": "coins", "amount": Infinity}'
    assert _raw(client, "/api/parent/rules", body, ph).status_code == 422


def test_duel_pong_ignores_non_finite_numbers():
    from familyquest.duel import Duels
    d = Duels(lambda pid: f"P{pid}")
    d.invite(1, 2, "pong")
    d.answer(2, True)
    st = d.pong(1, float("nan"), ball={"x": float("inf"), "y": 0, "vx": 0, "vy": 0}, points={"X": float("inf")})
    assert st["pong"]["pads"]["X"] == 0.5 and st["pong"]["ball"] is None and st["pong"]["points"] == {"X": 0, "O": 0}


# ---------------------------------------------------------------- 9: the shelf does not read others' private books
def test_shelf_never_reads_private_books_and_parses_once(client, monkeypatch):
    from familyquest import stories as S
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    m, lp = (fq.db.q1("SELECT * FROM profile WHERE id=?", i) for i in (mia, leo))
    secret = fq.stories.create(m, "Secret diary", visibility="me")
    fq.stories.save(m, secret, data={"start": 1, "pages": [{"id": 1, "kind": "scene", "text": "my secret"}]})
    fq.stories.create(m, "For all", visibility="family")
    fq.stories.create(lp, "Leo's own", visibility="me")
    seen, parsed = [], []
    orig_meta, orig_cover = S.cover_meta, fq.stories._cover_meta
    monkeypatch.setattr(S, "cover_meta", lambda kind, data: (parsed.append(kind), orig_meta(kind, data))[1])
    monkeypatch.setattr(fq.stories, "_cover_meta", lambda kind, raw: (seen.append(raw), orig_cover(kind, raw))[1])
    papa = fq.db.q1("SELECT * FROM profile WHERE role='parent'")
    sh = fq.stories.shelf(papa, oversee=True)
    assert secret in [p["id"] for p in sh["private"]] and sh["private"][0]["pages"] >= 1
    fq.stories.shelf(lp)
    raw_secret = fq.db.val("SELECT data FROM story WHERE id=?", secret)
    assert seen and raw_secret not in seen                          # never read for the parents or Leo
    parsed.clear()
    sh = fq.stories.shelf(papa, oversee=True)
    assert len(parsed) == len(sh["samples"])                        # only the sample books (from the code), no stored text again


# ---------------------------------------------------------------- 13: buying a game during a party
def test_party_unlock_does_not_open_buying_a_switched_off_game(client):
    ph, mia, leo = setup_family(client)
    hm = _kid_token(client, mia, "1111")
    fq = client.app.state.fq
    fq.rewards.book(mia, "coins", 1000, "manual", "t")
    client.put("/api/parent/games", json={"access": {"jump": {"mode": "off", "profiles": [], "price": 300},
                                                     "wuerfel": {"mode": "all", "profiles": [], "price": 300}}}, headers=ph)
    assert client.post("/api/parent/party", json={"kids": [mia], "unlock": True, "for": "3h"}, headers=ph).status_code == 200
    assert "jump" in client.get("/api/me", headers=hm).json()["games_list"]          # the party opens it to play …
    r = client.post("/api/me/games/buy", json={"game": "jump", "kind": "buy"}, headers=hm)
    assert r.status_code == 403                                                      # … not to buy it for good
    assert client.post("/api/me/games/buy", json={"game": "wuerfel", "kind": "buy"}, headers=hm).status_code == 200


# ---------------------------------------------------------------- 15: ids and numbers from the apps → 400, never 500
def test_party_kids_and_deal_numbers_are_checked(client):
    ph, mia, leo = setup_family(client)
    hm = _kid_token(client, mia, "1111")
    for kids in (["x"], ["²"], [None], [[1]], "abc"):
        r = client.post("/api/parent/party", json={"kids": kids, "unlock": True}, headers=ph)
        assert r.status_code == 400, kids
    assert client.post("/api/parent/party", json={"kids": [str(mia)], "unlock": True}, headers=ph).status_code == 200
    client.app.state.fq.rewards.book(mia, "coins", 50, "manual", "t")
    for n in ("²", "x", None, [1]):
        body = {"to": leo, "give": [{"t": "coins", "n": n}], "get": [{"t": "text", "text": "x"}]}
        assert client.post("/api/me/deals", json=body, headers=hm).status_code == 400, n
    body = '{"to": ' + str(leo) + ', "give": [{"t": "coins", "n": 1e999}], "get": [{"t": "text", "text": "x"}]}'
    assert _raw(client, "/api/me/deals", body, hm).status_code == 400
    for give in ([{"t": "chore", "chore": "²"}], [{"t": "pet", "id": "¹"}]):
        assert client.post("/api/me/deals", json={"to": leo, "give": give, "get": []}, headers=hm).status_code == 400
    fq = client.app.state.fq
    assert fq.deals.clean({"off": ["²", "3", -1], "max_coins": float("inf")})["off"] == [-1, 3]
    fq.community.family_result(["²", str(mia), str(leo)], ["²"])                     # no error


# ---------------------------------------------------------------- 14: ledger reasons are templates the app translates
def test_ledger_reasons_are_translatable_templates(fq):
    import json
    import re
    from familyquest.settings import WEB_DIR
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    leo = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    fq.rewards.book(mia, "coins", 100, "manual", "t")
    m = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    d = fq.deals.offer(m, leo, [{"t": "coins", "n": 10}], [{"t": "text", "text": "x"}])
    lp = fq.db.q1("SELECT * FROM profile WHERE id=?", leo)
    fq.deals.accept(lp, d["id"], 1)
    fq.deals.confirm(lp, d["id"], True)
    fq.deals.confirm(m, d["id"], True)
    fq.passes.buy(mia, "jump", {"price": 20, "rent": 0, "period": "week", "preview": 0}, "Jump")
    reasons = {r["reason"] for r in fq.db.q("SELECT reason FROM ledger WHERE profile_id IN (?,?)", mia, leo)}
    assert {"Deal with Leo", "Deal with Mia", "Game bought: Jump"} <= reasons
    de = json.loads((WEB_DIR / "i18n" / "de-DE.json").read_text(encoding="utf-8"))

    def tr(s):                                         # the pattern rule of web/shared/i18n.js, enough for these
        for k, v in de.items():
            if "{0}" in k and len(k.replace("{0}", "")) >= 6:
                m = re.fullmatch(re.escape(k).replace(re.escape("{0}"), "(.+?)"), s)
                if m:
                    return v.replace("{0}", de.get(m.group(1), m.group(1)))
        return s
    assert tr("Deal with Leo") == "Deal mit Leo" and tr("Game bought: Jump") == "Spiel gekauft: Jump"
    assert tr("Pet food – Minka") == "Haustierfutter – Minka" and tr("Game rented: Jump") == "Spiel gemietet: Jump"


# ================================================================ architecture items
# ---------------------------------------------------------------- H3: booked once, the game coins helper
def test_book_once_and_the_game_payout(fq):
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    assert fq.rewards.book_once(mia, "coins", 5, "x", "r", "once:1")["id"]
    assert fq.rewards.book_once(mia, "coins", 5, "x", "r", "once:1") is None
    assert fq.rewards.balance(mia, "coins") == 5
    fq.jump._payout("jump", 77, {str(mia): 10}, lambda pid: "Jump – place 1")
    fq.jump._payout("jump", 77, {str(mia): 10}, lambda pid: "Jump – place 1")       # a second end: not again
    assert fq.rewards.balance(mia, "coins") == 15
    assert fq.db.q1("SELECT 1 FROM sqlite_master WHERE type='index' AND name='ledger_ref'")


# ---------------------------------------------------------------- H4 / M7: publish checks first, picture clean-up
def test_publish_refuses_a_version_saved_during_the_check(client, monkeypatch):
    from familyquest import stories as S
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    m = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    sid = fq.stories.create(m, "Book", visibility="me")
    from test_stories import BOOK as page
    fq.stories.save(m, sid, data=page)
    orig = S.blocking_as

    def check_while_saved(kind, data, title="x"):         # the author saves again while the checker runs
        fq.db.x("UPDATE story SET data=? WHERE id=?", '{"start": 1, "pages": []}', sid)
        return orig(kind, data, title)
    monkeypatch.setattr(S, "blocking_as", check_while_saved)
    with pytest.raises(CommunityError, match="changed meanwhile"):
        fq.stories.publish(m, sid)
    assert fq.db.val("SELECT live FROM story WHERE id=?", sid) is None
    monkeypatch.setattr(S, "blocking_as", orig)
    fq.stories.save(m, sid, data=page)
    assert fq.stories.publish(m, sid) == "live"


def test_picture_cleanup_after_autosave_at_most_hourly(fq, monkeypatch):
    import os
    import time as _time
    m = fq.db.q1("SELECT * FROM profile WHERE id=?", fq.db.x("INSERT INTO profile(name) VALUES('Mia')"))
    sid = fq.stories.create(m, "Book", visibility="me")
    folder = fq.stories.folder
    folder.mkdir(parents=True, exist_ok=True)

    def old_file(name):
        f = folder / name
        f.write_bytes(b"x")
        os.utime(f, (_time.time() - 7200, _time.time() - 7200))
        return f
    a = old_file("s-0000000000000001.png")
    fq.stories.save(m, sid, title="One")                  # the first clean-up runs
    assert not a.exists()
    b = old_file("s-0000000000000002.png")
    fq.stories.save(m, sid, title="Two")                  # within the hour: no clean-up after an autosave …
    assert b.exists()
    fq.stories.delete(m, sid)                             # … but after deleting a book
    assert not b.exists()


def test_game_check_is_cached_per_version(monkeypatch):
    from familyquest import adventuregame as A
    calls = []
    orig = A.search
    monkeypatch.setattr(A, "search", lambda data, *a, **kw: (calls.append(1), orig(data, *a, **kw))[1])
    data = A.template(A.templates("en")[0]["key"], "en")["data"]
    A._CHECKED.clear()
    first = A.check(dict(data, rooms=[]), "T")              # an empty game: issues to look at
    assert first
    first[0]["args"].append("changed by a caller")
    calls.clear()
    A.check(data, "T")
    again = A.check(dict(data, rooms=[]), "T")
    assert len(calls) == 1 and "changed by a caller" not in again[0]["args"]     # cached – and a copy for each caller
    A.check(data, "Other title")
    A.check(data, "T")
    assert len(calls) == 2


# ---------------------------------------------------------------- H5: one memo per request, emptied by every write
def test_request_memo(fq):
    from familyquest import memo
    calls = []
    t = memo.begin()
    try:
        assert memo.get("k", lambda: calls.append(1) or 1) == 1 and memo.get("k", lambda: calls.append(1) or 2) == 1
        fq.db.set_setting("games_access", {})
        assert fq.db.get_setting("games_access") == {}
        fq.db.set_setting("games_access", {"jump": {"mode": "off"}})             # a write empties the memo
        assert fq.db.get_setting("games_access") == {"jump": {"mode": "off"}}
        a = fq.games_access()
        a["jump"]["mode"] = "all"                                                 # callers get copies
        assert fq.games_access()["jump"]["mode"] == "off"
        assert memo.get("k", lambda: 3) == 3 and calls == [1]
        import contextvars
        leaked = contextvars.copy_context()                                       # e.g. a task started by the request
    finally:
        memo.end(t)
    assert memo.get("k", lambda: 4) == 4                                          # no request: no memo
    assert leaked.run(memo.get, "k", lambda: 5) == 5 and leaked.run(memo.get, "k", lambda: 6) == 6   # over: closed


def test_queries_per_request_stay_low(client):
    """/api/me and a live-game poll read the settings, the games access and the running tables once (was ≈266 / 60)."""
    ph, mia, leo = setup_family(client)
    hm, hl = _kid_token(client, mia, "1111"), _kid_token(client, leo)
    client.post("/api/community/jump/start", json={"bots": 0, "lives": 3}, headers=hm)
    client.post("/api/community/jump/join", headers=hl)
    client.post("/api/community/jump/begin", headers=hm)
    db = client.app.state.fq.db
    n = [0]
    real = db.conn

    class Counting:
        def execute(self, *a):
            n[0] += 1
            return real.execute(*a)

        def __getattr__(self, k):
            return getattr(real, k)
    db.conn = Counting()
    try:
        for url, h, most in (("/api/me", hm, 190), ("/api/community/jump", hl, 35)):
            client.get(url, headers=h)
            n[0] = 0
            assert client.get(url, headers=h).status_code == 200
            assert n[0] <= most, (url, n[0])
    finally:
        db.conn = real


# ---------------------------------------------------------------- M1 / M2: game time and coins the same everywhere
def test_game_status_party_aware_in_home_assistant_and_coins_available(client):
    from familyquest import integration
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = _kid_token(client, mia, "1111")
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", '{"game_limit": {"all": 0, "days": {}}}', mia)
    kid = lambda: next(c for c in integration.state(fq)["children"] if c["name"] == "Mia")   # noqa: E731
    assert kid()["game_used_up"] and kid()["game_left"] == 0
    client.post("/api/parent/party", json={"kids": "all", "limits": True, "for": "3h"}, headers=ph)
    assert client.get("/api/me", headers=hm).json()["time_left"]["games"] is None
    assert kid()["game_unlimited"] and not kid()["game_used_up"]               # Home Assistant: like the app
    fq.rewards.book(mia, "coins", 40, "manual", "t")
    did = fq.db.x("INSERT INTO deal(a_id, b_id, terms, status) VALUES(?,?, '{}', 'running')", mia, leo)
    fq.db.x("INSERT INTO deal_hold(deal_id, profile_id, kind, amount) VALUES(?,?, 'coins', 15)", did, mia)
    me = client.get("/api/me", headers=hm).json()
    assert me["balances"]["coins"] == 40 and me["coins_reserved"] == 15 and me["coins_available"] == 25


# ---------------------------------------------------------------- M8: wrong answers only from this channel's games
def test_facts_game_answers_only_from_this_channel(fq):
    from familyquest import facts
    assert "stempeljagd" not in facts.Facts.game_pool() and "jump" in facts.Facts.game_pool()


# ---------------------------------------------------------------- the song quiz on the guest network (sync guard find)
def test_guest_network_lets_guests_play_the_song_quiz():
    from familyquest import netfilter
    assert netfilter.is_guest_path("/api/community/song/buzz") and netfilter.is_guest_path("/api/community/song")
    assert not netfilter.is_guest_path("/api/community/song/start")
