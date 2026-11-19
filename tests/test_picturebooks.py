"""Picture books and book types on the shelf (picturebooks.py, stories.py, svgsafe.py): types (the game type: test_adventuregame.py),
writing and checking, page-turn progress and ratings, SVG cleaning, file format and AI answers, privacy for every type,
the sample book in every language (shown, hidden by parents, never changed)."""
import json

from familyquest import picturebooks as PB
from familyquest import stories as S
from familyquest.svgsafe import SVG_MAX, SvgError, clean_svg, safe_svg
from test_stories import BOOK, _logins, coins

SVG = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'><rect width='400' height='300' fill='#a5d8ff'/>" \
      "<circle cx='200' cy='150' r='60' fill='#123abc'/></svg>"


def pb_data(n=3, layout="top"):
    return {"cover": {"pic": {"k": "svg", "v": SVG}},
            "pages": [{"id": i, "layout": layout, "text": f"Page {i}", "pic": {"k": "lib", "v": "forest"}} for i in range(1, n + 1)]}


def _pbook(client, h, data=None, title="The bear", visibility="family"):
    sid = client.post("/api/stories", json={"title": title, "lang": "en", "visibility": visibility, "type": "picture"}, headers=h).json()["id"]
    r = client.put(f"/api/stories/{sid}", json={"data": data or pb_data()}, headers=h)
    assert r.status_code == 200, r.text
    return sid, r.json()


def shelf(client, h, lang="en"):
    return client.get(f"/api/stories?lang={lang}", headers=h).json()


# ---------------------------------------------------------------- SVG cleaning
def test_svg_clean_keeps_drawing():
    out = clean_svg(SVG)
    assert out.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">') and "<circle" in out
    assert clean_svg(out) == out                                            # stable
    grad = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><defs><linearGradient id='g'><stop offset='0' stop-color='red'/>"
            "</linearGradient></defs><rect width='10' height='10' fill='url(#g)'/><text x='1' y='5'>Hi &amp; bye</text></svg>")
    c = clean_svg(grad)
    assert 'fill="url(#g)"' in c and "<stop" in c and "Hi &amp; bye" in c
    assert clean_svg("<?xml version='1.0'?><svg width='40' height='20'><rect width='4' height='4'/></svg>").startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">')


def test_svg_clean_removes_everything_active():
    evil = ("<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' viewBox='0 0 10 10' onload='alert(1)' "
            "style='background:url(http://x)'><script>alert(1)</script><foreignObject><div xmlns='http://www.w3.org/1999/xhtml'>"
            "<img src='x' onerror='alert(2)'/></div></foreignObject><image href='http://evil/x.png'/><use xlink:href='#a'/>"
            "<a href='javascript:alert(3)'><rect width='5' height='5'/></a><style>*{fill:red}</style>"
            "<rect width='3' height='3' onclick='alert(4)' fill='url(http://evil/p)' class='x' style='fill:red' xlink:href='http://evil'/>"
            "<circle r='2' fill='javascript:alert(5)' stroke='blue'/><animate attributeName='x' to='5'/><set attributeName='onclick' to='x'/>"
            "<g transform='rotate(4)'><path d='M0 0L5 5'/></g></svg>")
    c = clean_svg(evil)
    low = c.lower().replace('xmlns="http://www.w3.org/2000/svg"', "")
    for bad in ("script", "alert", "onload", "onclick", "onerror", "foreignobject", "<image", "<use", "href", "style", "http:",
                "javascript", "<a", "animate", "<set", "class"):
        assert bad not in low, bad
    assert '<rect width="3" height="3"/>' in c and '<circle r="2" stroke="blue"/>' in c and "<path" in c and "rotate(4)" in c


def test_svg_clean_refuses():
    bomb = ("<?xml version='1.0'?><!DOCTYPE lolz [<!ENTITY lol 'lol'><!ENTITY lol2 '&lol;&lol;&lol;'>]>"
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'><text>&lol2;</text></svg>")
    ext = "<!DOCTYPE svg [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><svg viewBox='0 0 1 1'><text>&x;</text></svg>"
    for bad in (bomb, ext, "<html><body>hi</body></html>", "not xml", "<svg><rect/></svg>", None, 42,
                "<svg viewBox='0 0 1 1'>" + "<rect width='1' height='1'/>" * 3000 + "</svg>",
                "<svg xmlns='http://www.w3.org/1999/xhtml' viewBox='0 0 1 1'/>"):
        assert safe_svg(bad) is None, bad
    big = "<svg viewBox='0 0 1 1'>" + "".join(f"<circle cx='{i}' cy='{i}' r='{i}' fill='#123456'/>" for i in range(1500)) + "</svg>"
    try:
        clean_svg(big)
        raise AssertionError("too large passed")
    except SvgError as e:
        assert str(e) in ("too large", "too many parts")
    assert len(clean_svg(SVG)) < SVG_MAX


def test_svg_check_endpoint(client):
    ph, hm, hl, mia, leo = _logins(client)
    r = client.post("/api/stories/svg", json={"svg": SVG.replace("<circle", "<script>x</script><circle onload='y'")}, headers=hm)
    assert r.status_code == 200 and "script" not in r.json()["svg"] and "onload" not in r.json()["svg"]
    assert client.post("/api/stories/svg", json={"svg": "<b>no</b>"}, headers=hm).status_code == 400
    assert client.post("/api/stories/svg", json={"svg": SVG}).status_code == 401


# ---------------------------------------------------------------- the shelf: book types
def test_types_on_the_shelf(client):
    ph, hm, hl, mia, leo = _logins(client)
    psid, _ = _pbook(client, hm)
    client.post(f"/api/stories/{psid}/publish", headers=hm)
    asid = client.post("/api/stories", json={"title": "Lion", "lang": "en", "visibility": "family"}, headers=hm).json()["id"]
    client.put(f"/api/stories/{asid}", json={"data": BOOK}, headers=hm)
    client.post(f"/api/stories/{asid}/publish", headers=hm)
    sh = shelf(client, hl)
    assert sh["types"] == ["picture", "adventure", "game"] and sh["creatable"] == ["picture", "adventure", "game"]
    types = {b["id"]: b["type"] for b in sh["books"]}
    assert types == {psid: "picture", asid: "adventure"}
    pb = next(b for b in sh["books"] if b["id"] == psid)
    assert pb["pages"] == 3 and pb["at"] == 0 and not pb["reading"] and pb["cover"]["k"] == "svg"
    # 🗝️ adventure games (tests/test_adventuregame.py) can be made too
    r = client.post("/api/stories", json={"title": "Escape", "type": "game"}, headers=hm)
    assert r.status_code == 200 and client.get(f"/api/stories/{r.json()['id']}", headers=hm).json()["type"] == "game"
    assert client.post("/api/stories", json={"title": "X", "type": "comic"}, headers=hm).status_code == 400
    # an old book without a type is an adventure book (the default of the migration)
    assert client.app.state.fq.db.val("SELECT type FROM story WHERE id=?", asid) == "adventure"


# ---------------------------------------------------------------- writing and checking
def test_picture_book_crud_and_checker(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid = client.post("/api/stories", json={"title": "Bear", "type": "picture", "lang": "fr-FR"}, headers=hm).json()["id"]
    ed = client.get(f"/api/stories/{sid}", headers=hm).json()
    assert ed["type"] == "picture" and ed["emoji"] == "📕" and ed["lang"] == "fr-FR" and ed["visibility"] == "family"
    assert ed["data"]["pages"] == [{"id": 1, "layout": "top", "text": "", "pic": None}]
    assert {i["code"] for i in ed["issues"]} == {"no_text", "no_pic"}
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).status_code == 400
    data = {"cover": {"pic": {"k": "emoji", "v": "🐻"}}, "pages": [
        {"id": 1, "layout": "top", "text": "x" * 2000, "pic": {"k": "lib", "v": "forest"}},
        {"id": 2, "layout": "full", "text": "", "pic": {"k": "svg", "v": SVG.replace("<rect", "<script>1</script><rect")}},
        {"id": 3, "layout": "text", "text": "Only text", "pic": {"k": "lib", "v": "forest"}},        # text only: no picture
        {"id": 4, "layout": "weird", "text": "y", "pic": {"k": "lib", "v": "../../etc/passwd"}},
        {"id": 4, "layout": "top", "text": "duplicate id"}, {"id": "x"}]}
    r = client.put(f"/api/stories/{sid}", json={"data": data}, headers=hm).json()
    p = r["data"]["pages"]
    assert [x["id"] for x in p] == [1, 2, 3, 4] and len(p[0]["text"]) == PB.TEXT
    assert p[1]["pic"]["k"] == "svg" and "script" not in p[1]["pic"]["v"]
    assert p[2]["pic"] is None and p[3]["layout"] == "top" and p[3]["pic"] is None
    assert [i["code"] for i in r["issues"]] == ["no_pic"] and r["issues"][0]["args"] == ["4"]
    data["pages"][3]["pic"] = {"k": "emoji", "v": "🦊"}
    r = client.put(f"/api/stories/{sid}", json={"data": data}, headers=hm).json()
    assert r["issues"] == []
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    # limits: pages, a broken SVG is dropped
    many = {"pages": [{"id": i, "layout": "text", "text": "x"} for i in range(1, PB.MAX_PAGES + 2)]}
    assert client.put(f"/api/stories/{sid}", json={"data": many}, headers=hm).status_code == 400
    bad = {"pages": [{"id": 1, "layout": "top", "text": "x", "pic": {"k": "svg", "v": "<svg><foreignObject/></svg>"}}]}
    assert client.put(f"/api/stories/{sid}", json={"data": bad}, headers=hm).json()["data"]["pages"][0]["pic"] is None
    # a picture book is not an adventure book: no choices
    assert client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hm).status_code == 400
    assert client.delete(f"/api/stories/{sid}", headers=hl).status_code == 400
    assert client.delete(f"/api/stories/{sid}", headers=hm).status_code == 200


def test_picture_book_reading_progress_rating_rewards(client):
    fq = client.app.state.fq
    ph, hm, hl, mia, leo = _logins(client)
    client.put("/api/stories/settings", json={"read_coins": 4}, headers=ph)
    sid, _ = _pbook(client, hm, pb_data(3))
    c0 = coins(fq, mia)
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    assert coins(fq, mia) == c0 + 20                                                   # writing reward, as for every type
    r = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert r["type"] == "picture" and r["at"] == 0 and len(r["pages"]) == 3 and r["author"] == "Mia" and r["cover"]["k"] == "svg"
    assert set(r["pages"][0]) == {"id", "layout", "text", "pic"}
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hl).status_code == 400   # not read yet
    t = client.post(f"/api/stories/{sid}/read/page", json={"page": 2}, headers=hl).json()
    assert t["at"] == 2 and t["finished"] == 0
    b = next(b for b in shelf(client, hl)["books"] if b["id"] == sid)
    assert b["at"] == 2 and b["reading"]
    assert client.post(f"/api/stories/{sid}/read/page", json={"page": 4}, headers=hl).status_code == 400
    assert client.post(f"/api/stories/{sid}/read/page", json={"page": -1}, headers=hl).status_code == 400
    t = client.post(f"/api/stories/{sid}/read/page", json={"page": 3}, headers=hl).json()
    assert t["finished"] == 1 and t["new_finish"] and t["may_rate"]
    assert coins(fq, mia) == c0 + 24
    client.post(f"/api/stories/{sid}/read/page", json={"page": 3}, headers=hl)               # staying there is not a second end
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["finished"] == 1
    r = client.post(f"/api/stories/{sid}/read/restart", headers=hl).json()
    assert r["at"] == 0
    client.post(f"/api/stories/{sid}/read/page", json={"page": 3}, headers=hl)
    assert coins(fq, mia) == c0 + 24                                                   # reading reward once per reader
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 4}, headers=hl).status_code == 200
    b = next(b for b in shelf(client, hl)["books"] if b["id"] == sid)
    assert b["finished"] == 2 and b["rating"] == 4 and not b["reading"]
    # the author reads her own book: no reward, no rating
    client.post(f"/api/stories/{sid}/read/page", json={"page": 3}, headers=hm)
    assert coins(fq, mia) == c0 + 24
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hm).status_code == 400
    # a shorter new version: the progress is clamped
    client.put(f"/api/stories/{sid}", json={"data": pb_data(1)}, headers=hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    assert client.get(f"/api/stories/{sid}/read", headers=hl).json()["at"] == 1


def test_picture_book_approval(client):
    ph, hm, hl, mia, leo = _logins(client)
    client.put("/api/stories/settings", json={"approval": True}, headers=ph)
    sid, _ = _pbook(client, hm)
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "pending"
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    sh = shelf(client, ph)
    assert sh["pending"] == 1 and next(b for b in sh["books"] if b["id"] == sid)["type"] == "picture"
    assert client.post(f"/api/stories/{sid}/approve", headers=ph).status_code == 200
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 200


# ---------------------------------------------------------------- privacy: the same rules for every type
def test_private_books_of_every_type(client):
    ph, hm, hl, mia, leo = _logins(client)
    papa_app = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}
    psid, _ = _pbook(client, hm, title="Secret pictures", visibility="me")
    asid = client.post("/api/stories", json={"title": "Secret adventure", "lang": "en", "visibility": "me"}, headers=hm).json()["id"]
    client.put(f"/api/stories/{asid}", json={"data": BOOK}, headers=hm)
    for sid in (psid, asid):
        assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    assert client.get(f"/api/stories/{psid}/read", headers=hm).status_code == 200
    for h in (hl, ph, papa_app):
        for sid in (psid, asid):
            assert client.get(f"/api/stories/{sid}/read", headers=h).status_code == 400
            assert client.get(f"/api/stories/{sid}", headers=h).status_code == 400
            assert client.get(f"/api/stories/{sid}/export", headers=h).status_code == 400
            assert client.put(f"/api/stories/{sid}", json={"title": "x"}, headers=h).status_code == 400
            assert client.delete(f"/api/stories/{sid}", headers=h).status_code == 400
        assert client.post(f"/api/stories/{psid}/read/page", json={"page": 1}, headers=h).status_code == 400
        dump = json.dumps(shelf(client, h), ensure_ascii=False)
        assert "Secret" not in dump and "Page 1" not in dump and "#123abc" not in dump and "forest" not in dump
    pv = shelf(client, ph)["private"]
    assert sorted(p["type"] for p in pv) == ["adventure", "picture"]
    assert all(set(p) == {"id", "private", "visibility", "type", "author", "pages", "created_at", "updated_at"} for p in pv)
    assert shelf(client, papa_app)["private"] == [] and shelf(client, hl)["private"] == []


# ---------------------------------------------------------------- file format, template for an AI, import
def test_picture_ai_template(client):
    r = client.get("/api/stories/ai-template?type=picture")
    assert r.status_code == 200 and "picturebook" in r.headers["content-disposition"]
    doc = r.json()
    assert doc["_format"] == PB.FORMAT and doc["_ai_instructions"] and doc["_svg_rules"] and set(doc["_library"]) == set(S.BACKGROUNDS)
    assert any("viewBox" in x for x in doc["_svg_rules"]) and any("script" in x for x in doc["_svg_rules"])
    [b] = S.import_books(r.text)
    assert b["type"] == "picture" and len(b["data"]["pages"]) == 12 and PB.check(b["data"], b["title"]) == []
    assert all(p["pic"]["k"] == "svg" for p in b["data"]["pages"])
    assert client.get("/api/stories/ai-template").json()["_format"] == S.STORY_FORMAT          # adventure books as before


def test_picture_export_import_round_trip(client):
    ph, hm, hl, mia, leo = _logins(client)
    data = pb_data(3)
    data["pages"][1] = {"id": 2, "layout": "full", "text": "Big", "pic": {"k": "svg", "v": SVG}}
    data["pages"][2] = {"id": 3, "layout": "text", "text": "The end", "pic": None}
    sid, ed = _pbook(client, hm, data, title="Round trip")
    r = client.get(f"/api/stories/{sid}/export", headers=hm)
    assert r.status_code == 200
    doc = r.json()
    assert doc["_format"] == PB.FORMAT and doc["books"][0]["type"] == "picture_book"
    assert [p["layout"] for p in doc["books"][0]["pages"]] == ["picture_top", "full_picture", "text_only"]
    assert client.get(f"/api/stories/{sid}/export", headers=hl).status_code == 400
    ids = client.post("/api/stories/import", json={"text": r.text}, headers=hl).json()["ids"]
    new = client.get(f"/api/stories/{ids[0]}", headers=hl).json()
    assert new["type"] == "picture" and new["visibility"] == "me" and new["mine"] and new["title"] == "Round trip"
    assert new["data"] == ed["data"] and new["issues"] == []


def test_picture_import_ai_answer(client):
    ph, hm, hl, mia, leo = _logins(client)
    book = {"type": "picture_book", "title": "Der Igel", "emoji": "🦔", "language": "de-CH", "author_id": 1, "visibility": "family",
            "cover": {"picture": {"emoji": "🦔"}},
            "pages": [{"layout": "picture_top", "text": "Es isch emal en Igel.", "picture": {"svg": SVG}},
                      {"layout": "full_picture", "text": "Er schlaft.", "picture": {"library": "forest"}},
                      {"layout": "text_only", "text": "Ende."},
                      {"text": "Ohne Layout", "picture": "<svg viewBox='0 0 4 3' onload='alert(1)'><rect width='4' height='3'/><script>x</script></svg>"},
                      {"layout": "picture_top", "text": "Böses Bild", "picture": {"svg": "<svg><foreignObject/></svg>"}},
                      "Nur en Satz."]}
    answer = "Gärn! Da isch dis Buech:\n\n```json\n" + json.dumps({"books": [book]}, ensure_ascii=False) + "\n```\nViel Spass!"
    ids = client.post("/api/stories/import", json={"text": answer}, headers=hm).json()["ids"]
    ed = client.get(f"/api/stories/{ids[0]}", headers=hm).json()
    assert ed["type"] == "picture" and ed["author_id"] == mia and ed["visibility"] == "me" and ed["lang"] == "de-CH"
    p = ed["data"]["pages"]
    assert [x["layout"] for x in p] == ["top", "full", "text", "top", "top", "text"]
    assert p[0]["pic"]["k"] == "svg" and p[1]["pic"] == {"k": "lib", "v": "forest"}
    assert "onload" not in p[3]["pic"]["v"] and "script" not in p[3]["pic"]["v"]
    assert p[4]["pic"] is None and p[5]["text"] == "Nur en Satz."
    assert ed["data"]["cover"]["pic"] == {"k": "emoji", "v": "🦔"}
    assert [i["code"] for i in ed["issues"]] == ["no_pic"]                                 # the bad picture is gone
    # a file with an adventure book and a picture book
    both = {"books": [S.export_book("Lion", "🦁", "en", S.clean(BOOK)), book]}
    ids = client.post("/api/stories/import", json={"text": json.dumps(both)}, headers=hm).json()["ids"]
    assert [client.get(f"/api/stories/{i}", headers=hm).json()["type"] for i in ids] == ["adventure", "picture"]
    for bad in ('{"type": "picture_book", "pages": []}', json.dumps({"type": "picture_book", "pages": ["x"] * (PB.MAX_PAGES + 1)})):
        assert client.post("/api/stories/import", json={"text": bad}, headers=hm).status_code == 400


# ---------------------------------------------------------------- the sample book
def test_sample_book_in_every_language():
    texts = PB.sample_file()["dwarf"]["texts"]
    assert set(texts) == set(S.LANGS)
    titles = set()
    for lang in S.LANGS:
        s = PB.sample("dwarf", lang)
        assert s["lang"] == lang and len(s["data"]["pages"]) == 12
        assert PB.check(PB.clean(s["data"]), s["title"]) == []
        assert PB.clean(s["data"]) == s["data"]                                # the cleaner keeps every picture as it is
        titles.add(s["title"])
    assert len(titles) == len(S.LANGS)
    assert PB.sample("dwarf", "fr")["lang"] == "fr-FR" and PB.sample("dwarf", "xx")["lang"] == "en"
    assert "Finke" in " ".join(texts["de-CH"]["pages"]) and "Pantoffeln" in " ".join(texts["de-DE"]["pages"])
    pics = [PB.sample_file()["dwarf"]["cover"], *PB.sample_file()["dwarf"]["pics"]]
    assert len(set(pics)) == 13 and all(clean_svg(x) == x and len(x) < 10000 for x in pics)


def test_sample_book_on_the_shelf(client):
    ph, hm, hl, mia, leo = _logins(client)
    papa_app = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}
    sh = shelf(client, hm, "de-CH")
    assert sh["books"] == [] and len(sh["samples"]) == 1
    s = sh["samples"][0]
    assert s["type"] == "picture" and s["sample"] == "dwarf" and s["author"]["name"] == "Family Quest" and not s["edit"]
    assert s["title"] == "De Klonk, de fuulscht Zwärg vom ganze Bärg" and s["lang"] == "de-CH" and s["pages"] == 12
    assert shelf(client, papa_app, "fr-FR")["samples"][0]["title"].startswith("Klonk, le nain")
    sid = s["id"]
    r = client.get(f"/api/stories/{sid}/read?lang=it-IT", headers=hl).json()
    assert r["lang"] == "it-IT" and r["author"] == "Family Quest" and r["pages"][0]["text"].startswith("Io sono Klonk")
    client.post(f"/api/stories/{sid}/read/page", json={"page": 12}, headers=hl)
    assert client.post(f"/api/stories/{sid}/rate", json={"stars": 5}, headers=hl).status_code == 200
    # nobody changes it – children cannot remove it, parents take it off the shelf (and put it back)
    for h in (hm, ph):
        assert client.get(f"/api/stories/{sid}", headers=h).status_code == 400
        assert client.put(f"/api/stories/{sid}", json={"title": "x"}, headers=h).status_code == 400
        assert client.post(f"/api/stories/{sid}/unpublish", headers=h).status_code == 400
    assert client.delete(f"/api/stories/{sid}", headers=hm).status_code == 400
    assert client.put("/api/stories/samples/dwarf", json={"hidden": True}, headers=hm).status_code == 400
    assert client.delete(f"/api/stories/{sid}", headers=ph).status_code == 200            # = hidden
    assert shelf(client, hm)["samples"] == [] and shelf(client, papa_app)["samples"] == []
    assert client.get(f"/api/stories/{sid}/read", headers=hl).status_code == 400
    po = shelf(client, ph)["samples"]
    assert len(po) == 1 and po[0]["hidden"]                                                # the parent area still lists it
    assert client.get("/api/stories/settings", headers=ph).json()["samples_off"] == ["dwarf"]
    assert client.put("/api/stories/samples/dwarf", json={"hidden": False}, headers=ph).status_code == 200
    s = shelf(client, hl)["samples"][0]
    assert s["id"] == sid and s["finished"] == 1 and s["rating"] == 5                     # progress and ⭐ stayed
    assert client.put("/api/stories/samples/nope", json={"hidden": True}, headers=ph).status_code == 400
    # not counted as a book of the family
    assert client.app.state.fq.stories._count() == 0
