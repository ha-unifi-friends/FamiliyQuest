"""Adventure books (stories.py): writing, the checker, publishing (with approval), reading with items and endings,
ratings, rewards paid once, permissions, limits and the templates in every language."""
import io
import json

import pytest

from familyquest import stories as S
from test_api import setup_family


def _logins(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    return ph, hm, hl, mia, leo


def scene(pid, text, *choices, give=None):
    return {"id": pid, "kind": "scene", "text": text, "pic": {"k": "emoji", "v": "🦁"}, "give": give,
            "choices": [{"t": t, "to": to, "need": need} for t, to, need in choices]}


def end(pid, kind="good", text="The end"):
    return {"id": pid, "kind": kind, "text": text, "pic": None}


# start → 2 (gives banana) or 3; 3 → bad 4 / good 5 (needs banana)
BOOK = {"start": 1, "pages": [
    scene(1, "Jungle", ("Take the banana", 2, None), ("Walk on", 3, None)),
    scene(2, "Banana", ("On", 3, None), ("Home", 4, None), give="🍌 Banana"),
    scene(3, "Lion", ("Run", 4, None), ("Feed it", 5, "🍌 Banana")),
    end(4, "bad", "Up a tree"), end(5, "good", "Friends")]}


def _book(client, h, data=BOOK, title="Lion", visibility="family"):
    sid = client.post("/api/stories", json={"title": title, "lang": "en", "visibility": visibility}, headers=h).json()["id"]
    r = client.put(f"/api/stories/{sid}", json={"data": data}, headers=h)
    assert r.status_code == 200, r.text
    return sid, r.json()


def codes(issues):
    return sorted(i["code"] for i in issues)


# ---------------------------------------------------------------- the checker
def test_checker_finds_problems():
    assert codes(S.check(S.clean({"pages": []}), "")) == ["empty", "title"]
    d = S.clean({"start": 1, "pages": [scene(1, "a", ("x", 2, None)), scene(2, "", ), scene(3, "c", ("y", None, None), ("", 1, None)),
                                       end(4, "bad")]})
    c = codes(S.check(d, "T"))
    assert c.count("one_choice") == 1 and "dead_end" in c and "no_text" in c and "no_target" in c and "choice_text" in c
    assert "no_good" in c and c.count("unreachable") == 2                 # pages 3 and 4
    msg = next(i for i in S.check(d, "T") if i["code"] == "dead_end")
    assert msg["msg"] == "Page {0} has no continuation" and msg["args"] == ["2"] and msg["page"] == 2
    # items: a need nobody gives, all choices gated
    d = S.clean({"start": 1, "pages": [scene(1, "a", ("x", 2, "🔑 Key"), ("y", 2, "🔑 Key")), end(2)]})
    assert "item_never" in codes(S.check(d, "T")) and "all_gated" in codes(S.check(d, "T"))
    # an ending as first page
    assert "start" in codes(S.check(S.clean({"start": 1, "pages": [end(1)]}), "T"))
    assert S.check(S.clean(BOOK), "T") == []


def test_clean_limits_and_targets():
    d = S.clean({"start": 99, "pages": [scene(1, "x" * 5000, ("a" * 500, 7, None), ("b", 1, None), ("c", 1, None), ("d", 1, None), ("e", 1, None)),
                                        {"id": 1, "kind": "scene"}, {"id": "bad"}, {"id": 2, "kind": "weird", "text": "y"}]})
    assert d["start"] == 1 and [p["id"] for p in d["pages"]] == [1, 2]
    p = d["pages"][0]
    assert len(p["text"]) == S.TEXT and len(p["choices"]) == 4 and len(p["choices"][0]["t"]) == S.CHOICE
    assert p["choices"][0]["to"] is None                                  # target 7 does not exist
    assert d["pages"][1]["kind"] == "scene"
    with pytest.raises(Exception):
        S.clean({"pages": [scene(i, "x") for i in range(1, S.MAX_PAGES + 2)]})
    assert S.clean_pic({"k": "img", "v": "../../etc/passwd"}, None) is None
    assert S.clean_pic({"k": "emoji", "v": "🦁" * 20}, None)["v"] == ("🦁" * 20)[:S.EMOJI]


def test_templates_valid_in_all_languages():
    texts = S.template_texts()
    assert set(texts) == set(S.LANGS)
    for lang in S.LANGS:
        for key in S.TEMPLATES:
            t = S.template(key, lang)
            d = S.clean(t["data"])
            assert S.check(d, t["title"]) == [], (lang, key)
            assert all(p["text"] for p in d["pages"]) and t["title"]
            if key in ("princess", "fox"):                      # interactive books: mostly linear, two branch points, happy endings
                assert sum(1 for p in d["pages"] if p.get("choices")) == 2 and 10 <= len(d["pages"]) <= 14, (lang, key)
                assert sum(1 for p in d["pages"] if S.linear(p)) >= len(d["pages"]) // 2
                assert {p["kind"] for p in d["pages"] if p["kind"] != "scene"} == {"good"} and len(S.endings(d)) >= 3
                continue
            assert any(c["need"] for p in d["pages"] for c in p.get("choices", [])), (lang, key)    # every template uses an item
            assert any(p["kind"] == "bad" for p in d["pages"])
    assert S.template("jungle", "fr")["lang"] == "fr-FR"
    assert S.template("jungle", "de-CH")["title"] != S.template("jungle", "de-DE")["title"]
    jungle = S.template("jungle", "en")["data"]["pages"]
    assert len(next(p for p in jungle if p["id"] == 3)["choices"]) == 4  # the lion: run, stand still, shout, feed it


# ---------------------------------------------------------------- writing and publishing
def test_create_edit_publish_validation(client):
    ph, hm, hl, mia, leo = _logins(client)
    assert client.post("/api/stories", json={"title": " "}, headers=hm).status_code == 400
    sid = client.post("/api/stories", json={"title": "Draft", "lang": "de-CH", "visibility": "family"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    assert ed["lang"] == "de-CH" and len(ed["data"]["pages"]) == 1 and ed["issues"]
    # an incomplete draft is saved, but cannot be published
    bad = {"start": 1, "pages": [scene(1, "Start", ("A", 2, None), ("B", None, None)), scene(2, "dead end"), end(3, "bad")]}
    r = client.put(f"/api/stories/{sid}", json={"data": bad}, headers=hm).json()
    assert {"no_target", "dead_end", "no_good", "unreachable"} <= set(codes(r["issues"]))
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).status_code == 400
    # Leo does not see a draft of Mia
    assert all(b["id"] != sid for b in client.get("/api/stories", headers=hl).json()["books"])
    r = client.put(f"/api/stories/{sid}", json={"data": BOOK, "title": "Der Löi"}, headers=hm).json()
    assert r["issues"] == [] and r["title"] == "Der Löi"
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    shelf = client.get("/api/stories", headers=hl).json()["books"]
    b = next(b for b in shelf if b["id"] == sid)
    assert b["live"] and b["endings"] == 2 and b["found"] == 0 and b["author"]["name"] == "Mia"
    # further edits stay in the working copy: readers see the published version
    client.put(f"/api/stories/{sid}", json={"data": {**BOOK, "pages": BOOK["pages"][:3]}}, headers=hm)
    assert next(b for b in client.get("/api/stories", headers=hm).json()["books"] if b["id"] == sid)["changed"]
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["endings"] == 2


def test_permissions(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _book(client, hm)
    assert client.get(f"/api/stories/{sid}", headers=hl).status_code == 400
    assert client.put(f"/api/stories/{sid}", json={"title": "Mine"}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/publish", headers=hl).status_code == 400
    assert client.delete(f"/api/stories/{sid}", headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/approve", headers=hl).status_code == 400
    # parents edit, unpublish and remove any book
    assert client.put(f"/api/stories/{sid}", json={"title": "Fixed"}, headers=ph).status_code == 200
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.post(f"/api/stories/{sid}/unpublish", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    # nobody without a family login; guests (QR invitation) neither
    assert client.get("/api/stories").status_code == 401
    client.post("/api/community/bingo/start", json={}, headers=hm)
    inv = client.post("/api/community/guests", json={"game": "bingo"}, headers=hm).json()["invite"]
    g = {"X-FQ-Token": client.post("/api/community/guest/join", json={"code": inv["code"], "name": "Oma"}).json()["token"]}
    assert client.get("/api/stories", headers=g).status_code == 401
    assert client.post("/api/stories", json={"title": "X"}, headers=g).status_code == 401
    assert client.get(f"/api/stories/{sid}/read", headers=g).status_code == 401
    # settings only with the parent PIN
    assert client.put("/api/stories/settings", json={"approval": True}, headers=hm).status_code == 401
    assert client.delete(f"/api/stories/{sid}", headers=ph).status_code == 200
    assert client.get("/api/stories", headers=hm).json()["books"] == []


def test_stories_off_for_a_child(client):
    ph, hm, hl, mia, leo = _logins(client)
    client.put("/api/stories/settings", json={"off": [leo]}, headers=ph)
    assert client.get("/api/me", headers=hl).json()["stories"] is False
    assert client.get("/api/me", headers=hm).json()["stories"] is True
    assert client.get("/api/stories", headers=hl).status_code == 400
    assert client.post("/api/stories", json={"title": "X"}, headers=hl).status_code == 400
    sid, _ = _book(client, hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400


# ---------------------------------------------------------------- reading
def test_reading_items_endings_ratings(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _book(client, hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    r = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert r["page"]["id"] == 1 and r["page"]["start"] and [c["i"] for c in r["page"]["choices"]] == [0, 1]
    # without the banana the lion page shows only «Run»
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=hl).json()
    assert r["page"]["id"] == 3 and [c["t"] for c in r["page"]["choices"]] == ["Run"]
    assert client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hl).status_code == 400   # not finished yet
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).json()
    assert r["page"]["kind"] == "bad" and r["new_ending"] and r["found"] == 1 and r["endings"] == 2
    assert client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).status_code == 400  # an ending has no choices
    # again: take the banana, feed the lion
    r = client.post(f"/api/stories/{sid}/read/restart", headers=hl).json()
    assert r["page"]["id"] == 1 and r["items"] == []
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).json()
    assert r["items"] == ["🍌 Banana"] and r["page"]["give"] == "🍌 Banana"
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).json()
    assert [c["t"] for c in r["page"]["choices"]] == ["Run", "Feed it"]
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=hl).json()
    assert r["page"]["kind"] == "good" and r["new_ending"] and r["found"] == 2 and r["may_rate"]
    # the same ending again is not new
    client.post(f"/api/stories/{sid}/read/restart", headers=hl)
    for i in (0, 0, 1):
        r = client.post(f"/api/stories/{sid}/read/choose", json={"i": i}, headers=hl).json()
    assert not r["new_ending"] and r["found"] == 2 and r["finished"] == 3
    # ratings: 1–5 stars, not for the own book
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 6}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 4}, headers=hl).status_code == 200
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hm).status_code == 400
    b = next(b for b in client.get("/api/stories", headers=hl).json()["books"] if b["id"] == sid)
    assert b["found"] == 2 and b["endings"] == 2 and b["rating"] == 4 and b["votes"] == 1 and b["my_rating"] == 4
    # Mia's own progress is her own
    assert next(b for b in client.get("/api/stories", headers=hm).json()["books"] if b["id"] == sid)["found"] == 0
    # a new version without the current page: back to the start
    client.post(f"/api/stories/{sid}/read/restart", headers=hl)
    client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl)            # Leo is on page 2
    new = {"start": 1, "pages": [scene(1, "Jungle", ("Walk on", 3, None), ("Home", 4, None)), BOOK["pages"][2], BOOK["pages"][3],
                                 {**BOOK["pages"][4]}, scene(6, "Banana tree", ("Back", 1, None), ("On", 3, None), give="🍌 Banana")]}
    new["pages"][0]["choices"].append({"t": "Tree", "to": 6, "need": None})
    client.put(f"/api/stories/{sid}", json={"data": new}, headers=hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["page"]["id"] == 1


# ---------------------------------------------------------------- approval and rewards
def coins(fq, pid):
    return fq.rewards.balance(pid, "coins")


def test_approval_flow_and_rewards_once(client):
    fq = client.app.state.fq
    ph, hm, hl, mia, leo = _logins(client)
    assert client.get("/api/stories/settings", headers=ph).json() == S.DEFAULT
    s = client.put("/api/stories/settings", json={"approval": True, "write_coins": 30, "write_xp": 5, "read_coins": 3, "read_xp": -4}, headers=ph).json()
    assert s["approval"] and s["write_coins"] == 30 and s["read_coins"] == 3 and s["read_xp"] == 0
    sid, _ = _book(client, hm)
    c0 = coins(fq, mia)
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "pending"
    assert coins(fq, mia) == c0
    assert all(b["id"] != sid for b in client.get("/api/stories", headers=hl).json()["books"])      # not visible yet
    sh = client.get("/api/stories", headers=ph).json()
    assert sh["pending"] == 1 and next(b for b in sh["books"] if b["id"] == sid)["pending"]
    assert client.post(f"/api/stories/{sid}/approve", headers=hm).status_code == 400              # a child cannot approve
    # rejected: back to a draft
    assert client.post(f"/api/stories/{sid}/reject", headers=ph).status_code == 200
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 400
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 200
    assert coins(fq, mia) == c0 + 30 and fq.rewards.balance(mia, "xp") >= 5
    assert any(b["id"] == sid for b in client.get("/api/stories", headers=hl).json()["books"])
    # publishing again (new version, approved again): no second reward
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    client.post(f"/api/stories/{sid}/approve", headers=ph)
    client.post(f"/api/stories/{sid}/unpublish", headers=hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    client.post(f"/api/stories/{sid}/approve", headers=ph)
    assert coins(fq, mia) == c0 + 30
    # reading reward: once per other reader – not for the author herself
    for h in (hm, hl, hl):
        client.post(f"/api/stories/{sid}/read/restart", headers=h)
        client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=h)
        client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=h)
    assert coins(fq, mia) == c0 + 33
    # a parent publishes without approval
    pid2, _ = _book(client, ph, title="Papa's book")
    assert client.post(f"/api/stories/{pid2}/publish", headers=ph).json()["status"] == "live"


def test_default_rewards(client):
    fq = client.app.state.fq
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _book(client, hl)
    c0 = coins(fq, leo)
    assert client.post(f"/api/stories/{sid}/publish", headers=hl).json()["status"] == "live"     # approval off by default
    assert coins(fq, leo) == c0 + 20
    client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=hm)
    client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hm)
    assert coins(fq, leo) == c0 + 20                                                         # reading reward 0 by default


# ---------------------------------------------------------------- templates, pictures, limits
def test_create_from_template(client):
    ph, hm, hl, mia, leo = _logins(client)
    t = client.get("/api/stories/templates?lang=fr-FR", headers=hm).json()
    assert [x["key"] for x in t] == ["jungle", "space", "castle", "sea", "princess", "fox"] and t[0]["title"] == "Le lion de la jungle"
    sid = client.post("/api/stories", json={"template": "castle", "lang": "de-CH"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    assert ed["title"] == "S Gspängschterschloss" and ed["lang"] == "de-CH" and ed["issues"] == []
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    assert client.post("/api/stories", json={"template": "nope"}, headers=hm).status_code == 400


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_pictures(client, settings):
    ph, hm, hl, mia, leo = _logins(client)
    r = client.post("/api/stories/image", files={"file": ("a.png", io.BytesIO(PNG), "image/png")}, headers=hm)
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    assert S.IMG_NAME.fullmatch(name) and client.get(r.json()["url"]).status_code == 200
    assert client.post("/api/stories/image", files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}, headers=hm).status_code == 400
    big = PNG + b"\x00" * S.IMAGE_MAX
    assert client.post("/api/stories/image", files={"file": ("b.png", io.BytesIO(big), "image/png")}, headers=hm).status_code == 400
    assert client.post("/api/stories/image", files={"file": ("a.png", io.BytesIO(PNG), "image/png")}).status_code == 401
    data = json.loads(json.dumps(BOOK))
    data["pages"][0]["pic"] = {"k": "img", "v": name, "src": "draw"}
    data["pages"][1]["pic"] = {"k": "img", "v": "s-0000000000000000.png", "src": "photo"}     # not uploaded: dropped
    sid, ed = _book(client, hm, data)
    assert ed["data"]["pages"][0]["pic"] == {"k": "img", "v": name, "src": "draw"} and ed["data"]["pages"][1]["pic"] is None
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["page"]["pic"]["v"] == name
    assert next(b for b in client.get("/api/stories", headers=hl).json()["books"] if b["id"] == sid)["cover"]["v"] == name


def test_limits(client, monkeypatch):
    ph, hm, hl, mia, leo = _logins(client)
    sid = client.post("/api/stories", json={"title": "Long"}, headers=hm).json()["id"]
    many = {"start": 1, "pages": [scene(i, "x") for i in range(1, S.MAX_PAGES + 2)]}
    assert client.put(f"/api/stories/{sid}", json={"data": many}, headers=hm).status_code == 400
    ok = {"start": 1, "pages": [scene(i, "x") for i in range(1, S.MAX_PAGES + 1)]}
    assert client.put(f"/api/stories/{sid}", json={"data": ok}, headers=hm).status_code == 200
    r = client.put(f"/api/stories/{sid}", json={"title": "y" * 300, "data": {"pages": [scene(1, "z" * 9000)]}}, headers=hm).json()
    assert len(r["title"]) == S.TITLE and len(r["data"]["pages"][0]["text"]) == S.TEXT
    monkeypatch.setattr(S, "MAX_PER_AUTHOR", 2)                      # one person: at most MAX_PER_AUTHOR books
    client.post("/api/stories", json={"title": "Two"}, headers=hm)
    r = client.post("/api/stories", json={"title": "Three"}, headers=hm)
    assert r.status_code == 400 and "one person" in r.json()["detail"]
    assert client.post("/api/stories", json={"title": "Leo 1"}, headers=hl).status_code == 200   # the others still can
    monkeypatch.setattr(S, "MAX_PER_AUTHOR", 60)
    monkeypatch.setattr(S, "MAX_BOOKS", 3)
    r = client.post("/api/stories", json={"title": "Leo 2"}, headers=hl)
    assert r.status_code == 400 and "bookshelf is full" in r.json()["detail"]


# ---------------------------------------------------------------- who reads it: only me · other children · whole family
def test_visibility_private_kids_family(client):
    fq = client.app.state.fq
    ph, hm, hl, mia, leo = _logins(client)
    papa_app = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}
    shelf = lambda h: client.get("/api/stories", headers=h).json()      # noqa: E731
    # a private book: only Mia – the parents neither (no title, no content, not in the app, not in the parent area)
    sid = client.post("/api/stories", json={"title": "Secret diary", "lang": "en", "visibility": "me"}, headers=hm).json()["id"]
    client.put(f"/api/stories/{sid}", json={"data": BOOK}, headers=hm)
    assert client.get(f"/api/stories/{sid}", headers=hm).json()["visibility"] == "me"
    c0 = coins(fq, mia)
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    assert coins(fq, mia) == c0                                                       # no reward while nobody else sees it
    assert client.get(f"/api/stories/{sid}/read", headers=hm).json()["page"]["id"] == 1   # the author plays it
    for h in (hl, ph, papa_app):
        assert client.get(f"/api/stories/{sid}/read", headers=h).status_code == 400
        assert client.get(f"/api/stories/{sid}", headers=h).status_code == 400
        assert client.put(f"/api/stories/{sid}", json={"title": "x"}, headers=h).status_code == 400
        assert client.post(f"/api/stories/{sid}/unpublish", headers=h).status_code == 400
        assert client.delete(f"/api/stories/{sid}", headers=h).status_code == 400   # parents cannot remove a private book
        assert client.post(f"/api/stories/{sid}/approve", headers=h).status_code == 400
        dump = json.dumps(shelf(h), ensure_ascii=False)
        assert "Secret diary" not in dump and "Jungle" not in dump and "🦁" not in dump
    assert all(b["id"] != sid for b in shelf(hl)["books"]) and shelf(hl)["private"] == []
    # the parent area only knows that it exists: author, pages, dates
    pv = shelf(ph)["private"]
    assert len(pv) == 1 and set(pv[0]) == {"id", "private", "visibility", "type", "author", "pages", "created_at", "updated_at"}
    assert pv[0]["author"]["name"] == "Mia" and pv[0]["pages"] == 5
    assert shelf(papa_app)["private"] == []
    # nobody but the author chooses who reads it
    assert client.put(f"/api/stories/{sid}", json={"visibility": "family"}, headers=ph).status_code == 400
    # «other children»: Leo reads it; parents not in the app, but in the parent area (moderation)
    client.put(f"/api/stories/{sid}", json={"visibility": "kids"}, headers=hm)
    assert coins(fq, mia) == c0 + 20                                                  # the others see it now: rewarded once
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 200
    assert all(b["id"] != sid for b in shelf(papa_app)["books"])
    assert client.get(f"/api/stories/{sid}/read", headers=papa_app).status_code == 400
    assert any(b["id"] == sid and b["visibility"] == "kids" for b in shelf(ph)["books"])
    assert client.get(f"/api/stories/{sid}/read", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}", headers=ph).status_code == 200
    # «whole family»: the parents in the app too
    client.put(f"/api/stories/{sid}", json={"visibility": "family"}, headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=papa_app).status_code == 200
    # back to private: gone for everybody else again; switching around pays no second reward
    client.put(f"/api/stories/{sid}", json={"visibility": "me"}, headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    assert client.get(f"/api/stories/{sid}/read", headers=ph).status_code == 400
    client.put(f"/api/stories/{sid}", json={"visibility": "family"}, headers=hm)
    assert coins(fq, mia) == c0 + 20
    # a parent's private book: the children see nothing either
    psid, _ = _book(client, ph, visibility="me")
    client.post(f"/api/stories/{psid}/publish", headers=ph)
    assert client.get(f"/api/stories/{psid}/read", headers=hm).status_code == 400
    assert client.get(f"/api/stories/{psid}/read", headers=ph).status_code == 200


def test_new_books_are_for_the_whole_family_approval_unchanged(client):
    ph, hm, hl, mia, leo = _logins(client)
    for kind in ("adventure", "picture"):
        sid = client.post("/api/stories", json={"title": "New " + kind, "lang": "en", "type": kind}, headers=hm).json()["id"]
        assert client.get(f"/api/stories/{sid}", headers=hm).json()["visibility"] == "family"
    # with approval on, sharing still waits for a parent
    client.put("/api/stories/settings", json={"approval": True}, headers=ph)
    sid = client.post("/api/stories", json={"title": "Lion", "lang": "en"}, headers=hm).json()["id"]
    client.put(f"/api/stories/{sid}", json={"data": BOOK}, headers=hm)
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "pending"
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 200
    from familyquest.stories import Stories
    import inspect
    assert inspect.signature(Stories.create).parameters["visibility"].default == "family"


def test_visibility_and_approval(client):
    ph, hm, hl, mia, leo = _logins(client)
    client.put("/api/stories/settings", json={"approval": True}, headers=ph)
    sid, _ = _book(client, hm, visibility="me")
    # «only me» never needs approval
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    assert client.get("/api/stories", headers=ph).json()["pending"] == 0
    # shown to the others: the published copy waits for a parent first
    r = client.put(f"/api/stories/{sid}", json={"visibility": "kids"}, headers=hm).json()
    assert r["pending"] and not r["shared"]
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    assert client.get("/api/stories", headers=ph).json()["pending"] == 1
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 200
    # a new version waits again – the readers keep the approved one meanwhile
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "pending"
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 200
    # back to «only me»: the request is gone
    client.put(f"/api/stories/{sid}", json={"visibility": "me"}, headers=hm)
    assert client.get("/api/stories", headers=ph).json()["pending"] == 0
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 400


# ---------------------------------------------------------------- backgrounds, file format, template for an AI, import
def test_backgrounds():
    from pathlib import Path
    web = Path(S.__file__).parent.parent / "web" / "img" / "stories"
    assert len(S.BACKGROUNDS) >= 20
    for key in S.BACKGROUNDS:
        f = web / f"{key}.svg"
        assert f.is_file() and f.stat().st_size < 15000 and "<script" not in f.read_text()
    d = S.clean({"pages": [{"id": 1, "kind": "scene", "bg": "jungle"}, {"id": 2, "kind": "good", "bg": "../../x"}]})
    assert d["pages"][0]["bg"] == "jungle" and d["pages"][1]["bg"] is None
    for lang in S.LANGS:                                         # the templates use them
        for key in S.TEMPLATES:
            assert all(p["bg"] in S.BACKGROUNDS for p in S.template(key, lang)["data"]["pages"])


def test_ai_template_is_valid(client):
    r = client.get("/api/stories/ai-template")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    doc = r.json()
    assert doc["_format"] == S.STORY_FORMAT and doc["_ai_instructions"] and set(doc["_backgrounds"]) == set(S.BACKGROUNDS)
    [b] = S.import_books(r.text)
    assert S.check(b["data"], b["title"]) == [] and b["lang"] == "en" and len(b["data"]["pages"]) == 13
    assert sum(1 for p in b["data"]["pages"] if p.get("choices")) == 2 and sum(1 for p in b["data"]["pages"] if S.linear(p)) == 8
    assert "next" in doc["_field_guide"]["pages[]"] and any("'next'" in x for x in doc["_ai_instructions"])


def test_export_import_round_trip(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid = client.post("/api/stories", json={"template": "castle", "lang": "fr-FR", "visibility": "family"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    r = client.get(f"/api/stories/{sid}/export", headers=hm)
    assert r.status_code == 200 and r.json()["books"][0]["language"] == "fr-FR"
    assert client.get(f"/api/stories/{sid}/export", headers=hl).status_code == 400
    ids = client.post("/api/stories/import", json={"text": r.text}, headers=hl).json()["ids"]
    new = client.get(f"/api/stories/{ids[0]}", headers=hl).json()
    assert new["visibility"] == "me" and new["mine"] and new["issues"] == [] and new["title"] == ed["title"]
    strip = lambda d: [{k: v for k, v in p.items() if k != "id"} for p in d["pages"]]     # noqa: E731
    assert len(new["data"]["pages"]) == len(ed["data"]["pages"])
    assert [p["text"] for p in new["data"]["pages"]] == [p["text"] for p in ed["data"]["pages"]]
    assert [p["bg"] for p in new["data"]["pages"]] == [p["bg"] for p in ed["data"]["pages"]]
    assert strip(new["data"]) == strip(ed["data"])                # same ids by order: the choices point to the same pages


def test_import_ai_answer_and_bad_input(client):
    ph, hm, hl, mia, leo = _logins(client)
    book = {"title": "Die Höhle", "emoji": "🦇", "language": "de-CH", "author_id": 99, "id": 7, "start": "a",
            "pages": [{"id": "a", "type": "scene", "text": "<script>alert(1)</script> Dunkel.", "picture": "🦇", "background": "cave",
                       "gives": "🔦 Lampe", "choices": [{"text": "Rein", "goes_to": "b"}, {"text": "Mit Licht", "goes_to": "c", "needs": "🔦 Lampe"},
                                                        {"text": "Nirgends", "goes_to": "zzz"}]},
                      {"id": "b", "type": "bad_ending", "text": "Zu dunkel."},
                      {"id": "c", "type": "good_ending", "text": "Schatz!", "picture": "<img src=x onerror=alert(1)>" * 3}]}
    answer = "Klar! Hier ist dein Buch:\n\n```json\n" + json.dumps({"books": [book]}, ensure_ascii=False) + "\n```\nViel Spass!"
    ids = client.post("/api/stories/import", json={"text": answer}, headers=hm).json()["ids"]
    ed = client.get(f"/api/stories/{ids[0]}", headers=hm).json()
    assert ed["author_id"] == mia and ed["visibility"] == "me" and ed["lang"] == "de-CH" and ed["title"] == "Die Höhle"
    p1 = ed["data"]["pages"][0]
    assert p1["text"].startswith("<script>") and p1["bg"] == "cave" and p1["give"] == "🔦 Lampe"     # plain text, shown as text
    assert [c["to"] for c in p1["choices"]] == [2, 3, None]                                         # a target that is not there
    assert ed["data"]["pages"][2]["pic"] is None                                                     # not an emoji
    assert {i["code"] for i in ed["issues"]} == {"no_target"}
    # a single book without the wrapper, with comments and trailing commas
    lax = '{"title": "X", // the title\n "start": 1, "pages": [{"id": 1, "type": "good_ending", "text": "Hi",},],}'
    assert client.post("/api/stories/import", json={"text": lax}, headers=hm).status_code == 200
    for bad in ("", "hello", "[1, 2, 3]", '{"books": [{"title": "x"}]}', json.dumps({"pages": [{"id": i} for i in range(S.MAX_PAGES + 5)]})):
        assert client.post("/api/stories/import", json={"text": bad}, headers=hm).status_code == 400, bad
    assert client.post("/api/stories/import", json={"text": "x" * (S.IMPORT_MAX + 1)}, headers=hm).status_code in (400, 422)
    assert client.post("/api/stories/import", json={"text": answer}).status_code == 401
