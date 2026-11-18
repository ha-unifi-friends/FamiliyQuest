"""Security review (1.1): quiz size limits, backup unpack limit, new XP after restoring an old backup, the parent
rule of the planner pass-throughs, secret bot timing in Werwölfe."""
import io
import json
import zipfile

import pytest

from tests.test_api import setup_family


def test_a_quiz_has_at_most_100_questions_and_300_kb_of_drawings(client):
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    q = {"q": "?", "a": ["a", "b"], "c": 0}
    assert client.post("/api/community/quizzes", json={"title": "Big", "questions": [q] * 101}, headers=h).status_code == 400
    assert client.post("/api/community/quizzes", json={"title": "Ok", "questions": [q] * 100}, headers=h).status_code == 200
    svg = "<svg xmlns='http://www.w3.org/2000/svg'>" + "<g/>" * 7000 + "</svg>"
    many = [{**q, "img": {"svg": svg}}] * 12
    assert client.post("/api/community/quizzes", json={"title": "Svg", "questions": many}, headers=h).status_code == 400


def test_backup_refuses_a_zip_bomb():
    from familyquest import backup
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"format": backup.FORMAT}))
        z.writestr("family_quest.db", b"x")
        z.writestr("media/big.bin", b"\0" * (3 * 1024 * 1024))
    old = backup.MAX_UNPACKED_BYTES
    backup.MAX_UNPACKED_BYTES = 1024 * 1024
    try:
        with pytest.raises(backup.BackupError):
            backup.inspect(buf.getvalue())
    finally:
        backup.MAX_UNPACKED_BYTES = old


def test_restoring_an_old_backup_keeps_old_xp_old(client):
    from familyquest import backup
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    fq.rewards.book(mia, "xp", 900, "bonus", "old")
    fq.db.x("DELETE FROM setting WHERE key='xp_items_from'")          # like a backup from before the XP items
    raw, _name = backup.create(fq)
    backup.restore(fq, raw)
    assert fq.rewards.new_xp(mia) == 0


def test_a_parent_profile_in_the_app_is_privileged_only_with_a_fresh_token(client):
    from familyquest.api import planer
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    papa = fq.db.val("SELECT id FROM profile WHERE role='parent'")
    tok = fq.tokens.make(papa, "kid") if hasattr(fq.tokens, "make") else None
    kid_tok = client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]
    assert not planer._parent_in_app(fq, kid_tok, "127.0.0.1")                  # a child: never
    if tok:
        assert planer._parent_in_app(fq, tok, "127.0.0.1")
        fq.db.set_setting("parent_ha_only", True)
        assert not planer._parent_in_app(fq, tok, "127.0.0.1")                  # parent area only through HA: PIN


def test_werwolf_bot_wait_is_secret_and_varies():
    from familyquest.werwolf import Table
    st = {"rules": {}, "players": [], "night": 1, "step": "wolves"}
    t = Table(st)
    w1 = t.bot_wait()
    assert 4 <= w1 <= 11 and "bot_seed" in st
    waits = set()
    for seed in range(20):
        st2 = {**st, "bot_seed": seed}
        waits.add(round(Table(st2).bot_wait(), 3))
    assert len(waits) > 3                                                      # not predictable from the night/step
