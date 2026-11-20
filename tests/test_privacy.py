"""Privacy (familyquest/privacy.py, api/privacy.py): retention periods, the clean-up preview, purging only what is past
due, balances / XP / levels unchanged after the ledger is folded, referenced rows kept, the run log, parent-only access,
the automatic clean-up at night."""
import json
from datetime import datetime, timedelta

import pytest

from familyquest import privacy
from familyquest.rewards.engine import today
from test_api import setup_family
from websrc import parent_js


def ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture
def fam(fq):
    papa = fq.db.x("INSERT INTO profile(name, role) VALUES('Papa', 'parent')")
    mia = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    leo = fq.db.x("INSERT INTO profile(name) VALUES('Leo')")
    return fq, papa, mia, leo


def book(fq, pid, account, amount, event="manual", days=0, ref="t"):
    lid = fq.rewards.book(pid, account, amount, event, "test", ref)["id"]
    fq.db.x("UPDATE ledger SET at=? WHERE id=?", ago(days), lid)
    return lid


def kind(fq, key):
    return next(k for k in privacy.preview(fq)["kinds"] if k["key"] == key)


# ---------------------------------------------------------------- settings
def test_defaults_and_settings_round_trip(fq):
    st = privacy.settings(fq.db)
    r = st["retention"]
    assert r["security"] == {"n": 90, "unit": "days"} and r["weather"] == {"n": 3, "unit": "months"}
    assert r["games"] == {"n": 1, "unit": "years"} and r["ledger"] == {"n": 2, "unit": "years"}
    assert r["usage"]["unit"] == "months" and st["auto"] is False
    assert {k["key"] for k in privacy.preview(fq)["keep"]} >= {"profiles", "creations", "photos"}
    privacy.save_settings(fq.db, {"retention": {"weather": {"n": 10, "unit": "days"}, "games": {"unit": "forever"},
                                                "ledger": {"n": 9999, "unit": "years"}, "security": {"n": "x", "unit": "days"},
                                                "nope": {"n": 1, "unit": "days"}}, "auto": True})
    r2 = privacy.settings(fq.db)
    assert r2["retention"]["weather"] == {"n": 10, "unit": "days"}
    assert r2["retention"]["games"] == {"n": 0, "unit": "forever"}
    assert r2["retention"]["ledger"] == {"n": 20, "unit": "years"}           # capped
    assert r2["retention"]["security"] == {"n": 90, "unit": "days"}          # invalid: unchanged
    assert "nope" not in r2["retention"] and r2["auto"] is True


def test_cutoff_never_inside_the_current_week():
    now = today()
    monday = (now - timedelta(days=now.weekday())).isoformat()
    assert privacy.cutoff_of({"n": 1, "unit": "days"}, now) <= monday
    assert privacy.cutoff_of({"n": 0, "unit": "forever"}, now) is None
    assert privacy.cutoff_of({"n": 1, "unit": "months"}, privacy.date(2026, 3, 31)) == "2026-02-28"


# ---------------------------------------------------------------- preview and purge
def test_preview_counts_and_purge_only_expired(fam):
    fq, papa, mia, leo = fam
    for d in (200, 120, 100, 10, 0):
        fq.db.x("INSERT INTO login_log(kind, profile_id, ok, ip, at) VALUES('profile', ?, 0, '1.2.3.4', ?)", mia, ago(d))
    for d in (400, 100, 30):
        fq.db.x("INSERT INTO weather_log(profile_id, level, icon, rank, at) VALUES(?, 'sun', '☀️', 0, ?)", mia, ago(d))
    sec = kind(fq, "security")
    assert sec["count"] == 3 and sec["oldest"] == ago(200)[:10] and sec["newest"] == ago(100)[:10]
    assert kind(fq, "weather")["count"] == 2
    before = fq.db.val("SELECT COUNT(*) FROM login_log")
    assert before == 5                                          # the preview deleted nothing
    res = privacy.run(fq, ["security", "weather"], by={"id": papa, "name": "Papa"})
    assert res["counts"] == {"security": 3, "weather": 2}
    assert fq.db.val("SELECT COUNT(*) FROM login_log") == 2
    assert [r["at"][:10] for r in fq.db.q("SELECT at FROM weather_log")] == [ago(30)[:10]]
    assert kind(fq, "security")["count"] == 0


def test_single_entries(fam):
    fq, papa, mia, leo = fam
    ids = [fq.db.x("INSERT INTO history(profile_id, kind, data, at) VALUES(?, 'quiz', '{}', ?)", mia, ago(d)) for d in (800, 700, 600, 5)]
    e = privacy.entries(fq, "history")
    assert {x["id"] for x in e} == {f"history:{i}" for i in ids[:3]}
    assert [x["id"] for x in e][0] == f"history:{ids[2]}"           # newest first
    privacy.run(fq, ["history"], {"history": [f"history:{ids[1]}"]}, by={"id": papa, "name": "Papa"})
    assert {r["id"] for r in fq.db.q("SELECT id FROM history")} == {ids[0], ids[2], ids[3]}
    assert privacy.entries(fq, "ledger") == []                  # no single entries for bookings


def test_referenced_rows_are_kept(fam):
    fq, papa, mia, leo = fam
    old = ago(800)
    running = fq.db.x("INSERT INTO card_game(kind, status, state, created_at) VALUES('tschau', 'running', '{}', ?)", old)
    done = fq.db.x("INSERT INTO card_game(kind, status, state, created_at, finished_at) VALUES('tschau', 'done', '{}', ?, ?)", old, old)
    fq.db.x("INSERT INTO card_game(kind, status, state) VALUES('tschau', 'done', '{}')")
    open_deal = fq.db.x("INSERT INTO deal(a_id, b_id, status, terms, updated_at) VALUES(?, ?, 'running', '{}', ?)", mia, leo, old)
    ended = fq.db.x("INSERT INTO deal(a_id, b_id, status, terms, updated_at, ended_at) VALUES(?, ?, 'done', '{}', ?, ?)", mia, leo, old, old)
    fq.db.x("INSERT INTO deal_msg(deal_id, kind, at) VALUES(?, 'text', ?)", ended, old)
    fq.db.x("INSERT INTO deal_pay(ref) VALUES(?)", f"deal:{ended}:coins:a:all")
    fq.db.x("INSERT INTO deal(a_id, b_id, status, terms) VALUES(?, ?, 'open', '{}')", mia, leo)
    chore = fq.chores.save({"name": "Tisch", "points": 5, "profiles": [mia], "frequency": "daily"})
    cid = chore["id"] if isinstance(chore, dict) else chore
    day = ago(800)[:10]
    pend = fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status) VALUES(?, ?, ?, 'pending')", cid, mia, day)
    dn = fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status) VALUES(?, ?, ?, 'done')", cid, mia, ago(799)[:10])
    deal_t = fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status, deal_id) VALUES(?, ?, ?, 'open', ?)", cid, mia, ago(798)[:10], open_deal)
    fq.db.x("INSERT INTO chore_task(chore_id, profile_id, period, status) VALUES(?, ?, ?, 'open')", cid, leo, today().isoformat())
    red_p = fq.db.x("INSERT INTO redemption(profile_id, reward_id, cost, account, status, created_at) VALUES(?, 1, 5, 'coins', 'pending', ?)", mia, old)
    red_a = fq.db.x("INSERT INTO redemption(profile_id, reward_id, cost, account, status, created_at) VALUES(?, 1, 5, 'coins', 'approved', ?)", mia, old)
    fq.db.x("INSERT INTO redemption(profile_id, reward_id, cost, account, status) VALUES(?, 1, 5, 'coins', 'approved')", mia)
    quiz = fq.db.x("INSERT INTO quiz(title) VALUES('Q')")
    q1 = fq.db.x("INSERT INTO quiz_game(quiz_id, status, created_at, finished_at) VALUES(?, 'done', ?, ?)", quiz, old, old)
    q2 = fq.db.x("INSERT INTO quiz_game(quiz_id, status, created_at, finished_at) VALUES(?, 'done', ?, ?)", quiz, old, old)
    fq.db.x("INSERT INTO quiz_answer(game_id, idx, profile_id, choice, ms, points) VALUES(?, 0, ?, 1, 100, 5)", q1, mia)
    fq.db.x("INSERT INTO quiz_game(quiz_id, status) VALUES(?, 'done')", fq.db.x("INSERT INTO quiz(title) VALUES('R')"))
    privacy.run(fq, ["games", "deals", "chores", "redemptions"], by={"id": papa, "name": "Papa"})
    games = {r["id"] for r in fq.db.q("SELECT id FROM card_game")}
    assert running in games and done not in games
    deals = {r["id"] for r in fq.db.q("SELECT id FROM deal")}
    assert open_deal in deals and ended not in deals
    assert not fq.db.q("SELECT 1 FROM deal_msg WHERE deal_id=?", ended) and not fq.db.q("SELECT 1 FROM deal_pay")
    tasks = {r["id"] for r in fq.db.q("SELECT id FROM chore_task")}
    assert pend in tasks and deal_t in tasks and dn not in tasks
    reds = {r["id"] for r in fq.db.q("SELECT id FROM redemption")}
    assert red_p in reds and red_a not in reds
    qg = {r["id"] for r in fq.db.q("SELECT id FROM quiz_game")}
    assert q2 in qg and q1 not in qg                             # the last game of the quiz stays: it is «played»
    assert not fq.db.q("SELECT 1 FROM quiz_answer WHERE game_id=?", q1)


# ---------------------------------------------------------------- balances never change
def test_ledger_carry_forward_keeps_balance_xp_and_level(fam):
    fq, papa, mia, leo = fam
    for i in range(30):
        book(fq, mia, "coins", 7, "chore_done", days=900 - i, ref=f"chore:{i}")
        book(fq, mia, "xp", 25, "lesson_done", days=900 - i)
    book(fq, mia, "coins", -40, "shop", days=850)
    book(fq, mia, "xp", -60, "pet_shop", days=840)                # XP spent: lowers the balance, not the level
    book(fq, mia, "xp", -5, "manual", days=830)
    fq.db.set_setting("xp_items_from", int(fq.db.val("SELECT id FROM ledger WHERE profile_id=? ORDER BY id LIMIT 1 OFFSET 20", mia)))
    book(fq, mia, "xp", 40, "lesson_done", days=820)
    book(fq, mia, "coins", 3, "manual", days=1)
    book(fq, leo, "coins", 11, "manual", days=900)
    r = fq.rewards
    before = (r.balances(mia), r.balances(leo), r.total_xp(mia), r.new_xp(mia), r.level(mia), fq.badge_overview(mia))
    n_before = fq.db.val("SELECT COUNT(*) FROM ledger")
    assert kind(fq, "ledger")["count"] == n_before - 1
    res = privacy.run(fq, ["ledger"], by={"id": papa, "name": "Papa"})
    assert res["counts"]["ledger"] == n_before - 1
    after = (r.balances(mia), r.balances(leo), r.total_xp(mia), r.new_xp(mia), r.level(mia), fq.badge_overview(mia))
    assert after == before
    assert fq.db.val("SELECT COUNT(*) FROM ledger") < 12
    carry = fq.db.q("SELECT * FROM ledger WHERE ref LIKE 'carry:%'")
    assert carry and all(c["reason"] == "Balance brought forward" for c in carry)
    assert fq.db.val("SELECT n FROM ledger_folded WHERE profile_id=? AND event='chore_done'", mia) == 30
    # a second run later folds the carry-forward rows again – still the same numbers, nothing more to do now
    assert kind(fq, "ledger")["count"] == 0
    assert privacy.run(fq, ["ledger"])["counts"] == {}
    assert (r.balances(mia), r.total_xp(mia), r.new_xp(mia)) == before[0:1] + before[2:4]


def test_family_goal_rows_and_streak_days_stay(fam):
    fq, papa, mia, leo = fam
    fq.db.x("INSERT INTO goal(profile_id, kind, title, target, account, created_at) VALUES(NULL, 'family', 'G', 1000, 'xp', ?)", ago(1000))
    book(fq, mia, "xp", 10, "lesson_done", days=900)
    v = fq.family_goal()["value"]
    privacy.run(fq, ["ledger"])
    assert fq.family_goal()["value"] == v and fq.db.val("SELECT COUNT(*) FROM ledger WHERE ref LIKE 'carry:%'") == 0
    # learning days: totals stay, the running streak stays
    for d in range(0, 20):
        fq.db.x("INSERT OR REPLACE INTO daily(profile_id, day, xp, seconds, lessons, goal_met) VALUES(?, ?, 60, 300, 1, 1)",
                mia, (today() - timedelta(days=d)).isoformat())
    for d in range(800, 810):
        fq.db.x("INSERT INTO daily(profile_id, day, xp, seconds, lessons, goal_met) VALUES(?, ?, 30, 100, 2, 0)",
                mia, (today() - timedelta(days=d)).isoformat())
    streak, lessons = fq.rewards.streak(mia), fq.db.val("SELECT SUM(lessons) FROM daily WHERE profile_id=?", mia)
    assert kind(fq, "learning_days")["count"] == 10
    privacy.run(fq, ["learning_days"])
    assert fq.rewards.streak(mia) == streak == 20
    assert fq.db.val("SELECT SUM(lessons) FROM daily WHERE profile_id=?", mia) == lessons
    assert fq.db.val("SELECT lessons FROM daily WHERE profile_id=? AND day='0001-01-01'", mia) == 20


# ---------------------------------------------------------------- run log, snapshot, auto
def test_run_log_and_snapshot(fam):
    fq, papa, mia, leo = fam
    for i in range(5):
        fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(300))
        res = privacy.run(fq, ["security"], by={"id": papa, "name": "Papa"})
        assert res["backup"].startswith("before-cleanup-")
    files = list((fq.settings.data_dir / privacy.BACKUP_DIR).glob("*.zip"))
    assert len(files) == privacy.KEEP_BACKUPS
    runs = privacy.runs(fq.db)
    assert len(runs) == 5 and runs[0]["by_name"] == "Papa" and runs[0]["counts"] == {"security": 1} and not runs[0]["auto"]
    assert privacy.run(fq, ["security"])["id"] is None          # nothing due: no snapshot, no log entry
    assert len(privacy.runs(fq.db)) == 5


def test_failed_snapshot_deletes_nothing(fam, monkeypatch):
    fq, papa, mia, leo = fam
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(300))
    monkeypatch.setattr(privacy, "snapshot", lambda fq: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        privacy.run(fq, ["security"])
    assert fq.db.val("SELECT COUNT(*) FROM login_log") == 1 and not privacy.runs(fq.db)


def test_auto_switch(fam):
    fq, papa, mia, leo = fam
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(300))
    night = datetime.now().replace(hour=3, minute=0)
    assert privacy.maybe_auto(fq, night) is None                # off by default
    privacy.save_settings(fq.db, {"auto": True})
    assert privacy.maybe_auto(fq, night.replace(hour=14)) is None   # only at night
    res = privacy.maybe_auto(fq, night)
    assert res["counts"] == {"security": 1}
    assert privacy.runs(fq.db)[0]["auto"] is True
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(300))
    assert privacy.maybe_auto(fq, night.replace(hour=4)) is None    # once per night
    assert privacy.settings(fq.db)["auto"] is True


def test_login_log_cap_follows_the_setting(fq):
    assert privacy.login_cap_days(fq.db, 180) == 180
    privacy.save_settings(fq.db, {"retention": {"security": {"n": 2, "unit": "years"}}})
    assert privacy.login_cap_days(fq.db, 180) >= 729
    privacy.save_settings(fq.db, {"retention": {"security": {"unit": "forever"}}})
    assert privacy.login_cap_days(fq.db, 180) is None


# ---------------------------------------------------------------- API
def test_api_parent_only(client):
    ph, mia, leo = setup_family(client)
    assert client.get("/api/parent/privacy").status_code in (401, 403)
    tok = client.post("/api/login", json={"profile_id": leo}).json()["token"]
    kid = {"X-FQ-Token": tok, "X-FQ-Parent": tok}
    assert client.get("/api/parent/privacy", headers=kid).status_code in (401, 403)
    assert client.post("/api/parent/privacy/run", json={"kinds": ["security"]}, headers=kid).status_code in (401, 403)
    assert client.put("/api/parent/privacy/settings", json={"auto": True}, headers=kid).status_code in (401, 403)
    d = client.get("/api/parent/privacy", headers=ph).json()
    assert {k["key"] for k in d["kinds"]} >= {"security", "weather", "ledger", "games", "chores", "deals"}
    d = client.put("/api/parent/privacy/settings", json={"retention": {"security": {"n": 1, "unit": "days"}}, "auto": True}, headers=ph).json()
    assert d["auto"] is True and next(k for k in d["kinds"] if k["key"] == "security")["retention"] == {"n": 1, "unit": "days"}
    fq = client.app.state.fq
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(30))
    assert client.get("/api/parent/privacy/entries/security", headers=ph).json()
    assert client.get("/api/parent/privacy/entries/nope", headers=ph).status_code == 404
    assert client.post("/api/parent/privacy/run", json={"kinds": []}, headers=ph).status_code == 400
    r = client.post("/api/parent/privacy/run", json={"kinds": ["security"]}, headers=ph).json()
    assert r["counts"]["security"] >= 1 and r["runs"][0]["by_name"] == "Papa"
    json.dumps(r)


def test_ui_sections_have_info_and_translations():
    """parent-privacy.js: every box title is a key of its PARENT_INFO entries (ⓘ), and everything is translated."""
    import re
    from pathlib import Path
    web = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
    src = (web / "parent-privacy.js").read_text(encoding="utf-8")
    info = src[src.index("Object.assign(PARENT_INFO, {"):src.index("\n});\n")]
    keys = set(re.findall(r'^  \[T\("([^"]+)"\)\]:', info, re.M))
    titles = set(re.findall(r'(?:section|pageHead)\("[^"]*" \+ I18N\.tr\(T\("([^"]+)"\)\)', src))
    titles |= set(re.findall(r'pageHead\(T\("([^"]+)"\)', src))          # the page title: no emoji (like every page)
    assert titles == {"Privacy", "Retention periods", "Clean-up runs", "Past runs", "Delete all data of a child"}
    assert titles <= keys
    texts = set(re.findall(r'\bT\("((?:[^"\\]|\\.)*)"\)', src)) | {k.info for k in privacy.KINDS + privacy.KEEP} | {k.title for k in privacy.KINDS + privacy.KEEP}
    for lang in ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]:
        d = json.loads((web / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert not [t for t in texts if t not in d], lang
    assert '"privacy", "🛡️", T("Privacy")' in parent_js()
    assert "parent-privacy.js" in (web / "eltern.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- master switch and menu badge
def test_master_switch_off_blocks_runs_and_counts(fam):
    fq, papa, mia, leo = fam
    for d in (300, 200):
        fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(d))
    fq.db.x("INSERT INTO history(profile_id, kind, data, at) VALUES(?, 'quiz', '{}', ?)", mia, ago(800))
    assert privacy.settings(fq.db)["enabled"] is True                 # on by default
    privacy.save_settings(fq.db, {"enabled": False, "auto": True})
    pv = privacy.preview(fq)
    assert pv["enabled"] is False and all(k["count"] == 0 for k in pv["kinds"])
    assert privacy.badge(fq) == {"on": False, "count": 0}
    assert privacy.entries(fq, "security") == []
    with pytest.raises(privacy.PrivacyOff):
        privacy.run(fq, ["security"])
    assert privacy.maybe_auto(fq, datetime.now().replace(hour=3)) is None       # the automatic run is blocked too
    assert fq.db.val("SELECT COUNT(*) FROM login_log") == 2 and not privacy.runs(fq.db)
    privacy.save_settings(fq.db, {"retention": {"security": {"n": 10, "unit": "days"}}})   # periods stay editable
    assert privacy.settings(fq.db)["retention"]["security"]["n"] == 10
    privacy.save_settings(fq.db, {"enabled": True})
    assert kind(fq, "security")["count"] == 2


def test_badge_equals_preview_total_and_is_cached(fam, monkeypatch):
    fq, papa, mia, leo = fam
    for d in (300, 200, 150):
        fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(d))
    for d in (500, 400):
        fq.db.x("INSERT INTO weather_log(profile_id, level, icon, rank, at) VALUES(?, 'sun', '☀️', 0, ?)", mia, ago(d))
    book(fq, mia, "coins", 5, days=900)
    privacy.badge_reset(fq.db)
    total = sum(k["count"] for k in privacy.preview(fq)["kinds"])
    assert total == 6 and privacy.badge(fq) == {"on": True, "count": total}
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(250))
    assert privacy.badge(fq)["count"] == total                         # cached
    calls = []
    monkeypatch.setattr(privacy, "due", lambda *a: calls.append(1) or {"count": 0, "oldest": None, "newest": None})
    privacy.badge(fq)
    assert not calls                                                   # the cache does not count again
    monkeypatch.undo()
    privacy.save_settings(fq.db, {"auto": False})                      # a settings change resets the cache
    assert privacy.badge(fq)["count"] == total + 1
    privacy.run(fq, ["security"])                                      # a run too
    assert privacy.badge(fq)["count"] == 3


def test_api_switch_and_badge(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    fq.db.x("INSERT INTO login_log(kind, ok, at) VALUES('parent', 1, ?)", ago(300))
    privacy.badge_reset(fq.db)
    b = client.get("/api/parent/privacy/badge", headers=ph).json()
    total = sum(k["count"] for k in client.get("/api/parent/privacy", headers=ph).json()["kinds"])
    assert b["on"] and b["count"] == total >= 1
    tok = client.post("/api/login", json={"profile_id": leo}).json()["token"]
    assert client.get("/api/parent/privacy/badge", headers={"X-FQ-Token": tok}).status_code in (401, 403)
    d = client.put("/api/parent/privacy/settings", json={"enabled": False}, headers=ph).json()
    assert d["enabled"] is False
    assert client.get("/api/parent/privacy/badge", headers=ph).json() == {"on": False, "count": 0}
    r = client.post("/api/parent/privacy/run", json={"kinds": ["security"]}, headers=ph)
    assert r.status_code == 409 and "switched off" in r.json()["detail"]
