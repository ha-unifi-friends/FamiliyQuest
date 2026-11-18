"""Own vector drawings (web/svgpaint.js) in every book type: svgsafe.py keeps what the drawing editor writes and removes
everything active, the size limits per use (scenes 60 KB, things 20 KB), saving and loading the drawings in 📖 adventure
books, 📕 picture books and 🗝️ adventure games, privacy of the drawings of private books, export → import with the
drawings, the AI templates (rules and an inline example per type) and that older painted PNG drawings still work."""
import io
import json
import re
import zipfile

import pytest

from familyquest import adventuregame as A
from familyquest import picturebooks as PB
from familyquest import stories as S
from familyquest.svgsafe import ART_MAX, BG_MAX, LIMITS, SvgError, clean_svg, safe_svg
from test_adventuregame import game
from test_stories import BOOK, _logins

# what the drawing editor writes (a scene, 800×600): background preset, shapes with translate / rotate / scale, a stamp
# (a group of paths), a polygon, a pen stroke, a line and a word of text
SCENE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" id="fq-draw"><defs><linearGradient id="fq-g" x1="0" y1="0" '
         'x2="0" y2="1"><stop offset="0" stop-color="#212529"/><stop offset="1" stop-color="#5c5f66"/></linearGradient></defs>'
         '<rect id="fq-bg-cave" width="800" height="600" fill="url(#fq-g)"/><rect x="-360" y="-108" width="720" height="216" fill="#868e96" '
         'stroke="#1f2433" stroke-width="5" stroke-linejoin="round" transform="translate(400 480)"/><polygon points="0,-126 96,126 -96,126" '
         'fill="#8d5524" stroke="#1f2433" stroke-width="5" stroke-linejoin="round" transform="translate(144 246) rotate(-12)"/>'
         '<g fill="#a0522d" stroke="#1f2433" stroke-width="3.1" stroke-linejoin="round" transform="translate(600 270) scale(1.6)">'
         '<path d="M-30 50V-20A30 30 0 0 1 30-20V50Z"/><path d="M8 12A6 6 0 1 0 20 12A6 6 0 1 0 8 12Z" fill="#fcc419"/></g>'
         '<path d="M64 0Q62 16 59 23Q55 30 50 36L64 1" fill="none" stroke="#fcc419" stroke-width="20" stroke-linecap="round" '
         'stroke-linejoin="round" transform="translate(360 150)"/><line x1="-50" y1="0" x2="50" y2="0" stroke="#e03131" stroke-width="10" '
         'stroke-linecap="round" stroke-linejoin="round" transform="translate(100 100) rotate(45) scale(1.2 0.8)"/>'
         '<ellipse rx="35" ry="20" fill="#fcc419" opacity="0.5" transform="translate(65 65)"/>'
         '<text x="0" y="0" font-size="48" font-family="sans-serif" font-weight="bold" text-anchor="middle" dominant-baseline="central" '
         'fill="#2f9e44" transform="translate(500 80)">Hallo &amp; tschüss</text></svg>')
# a thing (200×200, see-through)
THING = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" id="fq-draw"><ellipse rx="35" ry="35" fill="#fcc419" stroke="#1f2433" '
         'stroke-width="2.5" stroke-linejoin="round" transform="translate(65 65)"/><rect x="-43" y="-12" width="86" height="24" fill="#fcc419" '
         'stroke="#1f2433" stroke-width="2.5" stroke-linejoin="round" transform="translate(127 92) rotate(62)"/></svg>')


def big(n_paths: int, vb="0 0 800 600") -> str:
    """An own drawing with many pen strokes (about 120 characters each)."""
    d = "M0 0" + "".join(f"Q{i} {i + 1} {i + 2} {i + 3}" for i in range(8))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" id="fq-draw">' +
            "".join(f'<path d="{d}" fill="none" stroke="#123456" stroke-width="4" transform="translate({i} {i})"/>' for i in range(n_paths)) + "</svg>")


# ---------------------------------------------------------------- svgsafe: the editor's output
def test_editor_output_survives_cleaning_unchanged():
    assert clean_svg(SCENE) == SCENE                         # the shape model (ids, transforms, groups, text) stays as it is
    assert clean_svg(THING, ART_MAX) == THING
    assert LIMITS == {"bg": 60_000, "art": 20_000}


@pytest.mark.parametrize("evil", [
    ('<path d="M0 0L5 5"', '<path onload="alert(1)" d="M0 0L5 5"'),
    ('<g fill="#a0522d"', '<g onclick="alert(1)" style="fill:url(http://x)" fill="#a0522d"'),
    ('</defs>', '</defs><script>alert(1)</script><foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>'),
    ('</defs>', '</defs><image href="http://evil/x.png" width="10" height="10"/><use href="#fq-g"/><a href="javascript:alert(1)"><rect width="1" height="1"/></a>'),
    ('fill="#868e96"', 'fill="url(http://evil/p)"'),
    ('fill="#8d5524"', 'fill="javascript:alert(1)"'),
    ('transform="translate(400 480)"', 'transform="translate(400 480)" xlink:href="data:text/html,x" class="x"'),
    ('</svg>', '<animate attributeName="d" to="M0 0"/><set attributeName="onclick" to="alert(1)"/><style>*{fill:red}</style></svg>'),
    ('<text ', '<text onmouseover="alert(1)" '),
])
def test_malicious_variants_of_editor_output(evil):
    raw = SCENE.replace(*evil).replace("<svg ", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ', 1)
    out = clean_svg(raw)
    low = out.lower().replace('xmlns="http://www.w3.org/2000/svg"', "")
    for bad in ("script", "alert", "onload", "onclick", "onmouseover", "foreignobject", "<image", "<use", "href", "style", "http:",
                "javascript", "<a ", "animate", "<set", "class", "data:"):
        assert bad not in low, (bad, out)
    assert out.count("<path") >= 3 and 'id="fq-draw"' in out and "Hallo &amp; tschüss" in out


def test_entities_and_doctype_are_refused():
    assert safe_svg('<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + SCENE.replace("Hallo", "&x;")) is None
    assert safe_svg(SCENE.replace("<svg ", "<svgx ").replace("</svg>", "</svgx>")) is None


def test_size_limits_per_use():
    scene, thing = big(380), big(140, "0 0 200 200")
    assert 20_000 < len(thing) < 25_000 and 40_000 < len(scene) < 60_000
    assert clean_svg(scene) and safe_svg(thing, ART_MAX) is None and safe_svg(thing, BG_MAX)
    with pytest.raises(SvgError):
        clean_svg(big(600))                                    # > 60 KB
    with pytest.raises(SvgError):
        clean_svg("<svg viewBox='0 0 1 1'>" + "<g/>" * 3000 + "</svg>")


def test_check_endpoint_takes_the_use(client):
    ph, hm, hl, mia, leo = _logins(client)
    thing = big(140, "0 0 200 200")
    r = client.post("/api/stories/svg", json={"svg": thing, "use": "art"}, headers=hm)
    assert r.status_code == 400 and r.json()["detail"] == "The drawing is too large (max. 20 KB)"
    assert client.post("/api/stories/svg", json={"svg": thing, "use": "bg"}, headers=hm).status_code == 200
    r = client.post("/api/stories/svg", json={"svg": big(600)}, headers=hm)
    assert r.status_code == 400 and r.json()["detail"] == "The drawing is too large (max. 60 KB)"
    r = client.post("/api/stories/svg", json={"svg": THING.replace("<ellipse", "<ellipse onclick='x()'"), "use": "art"}, headers=hm)
    assert r.status_code == 200 and r.json()["svg"] == THING


# ---------------------------------------------------------------- saving and loading in every book type
def _new(client, h, kind, data, title="Drawn", visibility="family"):
    sid = client.post("/api/stories", json={"title": title, "type": kind, "lang": "en", "visibility": visibility}, headers=h).json()["id"]
    r = client.put(f"/api/stories/{sid}", json={"data": data}, headers=h)
    assert r.status_code == 200, r.text
    return sid, r.json()["data"]


def adventure_with_drawings():
    data = json.loads(json.dumps(BOOK))
    data["pages"][0]["pic"] = {"k": "svg", "v": THING}
    data["pages"][0]["bg"] = {"k": "svg", "v": SCENE}
    data["pages"][1]["bg"] = "jungle"
    return data


def picture_with_drawings():
    return {"cover": {"pic": {"k": "svg", "v": SCENE}},
            "pages": [{"id": 1, "layout": "top", "text": "A cave.", "pic": {"k": "svg", "v": SCENE}},
                      {"id": 2, "layout": "full", "text": "A key.", "pic": {"k": "emoji", "v": "🗝️"}}]}


def game_with_drawings():
    g = game()
    g["rooms"][0]["bg"] = {"k": "svg", "v": SCENE}
    g["rooms"][0]["variants"][0]["bg"] = {"k": "svg", "v": SCENE.replace("#212529", "#000000")}
    g["rooms"][0]["spots"][0]["art"] = {"k": "svg", "v": THING}
    g["items"][0]["icon"] = {"k": "svg", "v": THING}
    return g


def test_adventure_book_keeps_drawings(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, data = _new(client, hm, "adventure", adventure_with_drawings())
    p1, p2 = data["pages"][0], data["pages"][1]
    assert p1["pic"] == {"k": "svg", "v": THING} and p1["bg"] == {"k": "svg", "v": SCENE} and p2["bg"] == "jungle"
    assert client.get(f"/api/stories/{sid}", headers=hm).json()["data"]["pages"][0]["bg"]["v"] == SCENE
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    page = client.get(f"/api/stories/{sid}/read", headers=hl).json()["page"]
    assert page["pic"]["v"] == THING and page["bg"]["v"] == SCENE
    b = next(x for x in client.get("/api/stories", headers=hl).json()["books"] if x["id"] == sid)
    assert b["cover"] == {"k": "svg", "v": THING} and b["cover_bg"]["v"] == SCENE
    # a thing that is too big for a page picture, an unusable background: dropped, the rest stays
    bad = adventure_with_drawings()
    bad["pages"][0]["pic"] = {"k": "svg", "v": big(140, "0 0 200 200")}
    bad["pages"][0]["bg"] = {"k": "svg", "v": "<svg><script>alert(1)</script></svg>"}
    bad["pages"][1]["bg"] = {"k": "lib", "v": "forest"}
    p = client.put(f"/api/stories/{sid}", json={"data": bad}, headers=hm).json()["data"]["pages"]
    assert p[0]["pic"] is None and p[0]["bg"] is None and p[1]["bg"] == "forest"


def test_picture_book_keeps_drawings(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, data = _new(client, hm, "picture", picture_with_drawings())
    assert data["cover"]["pic"]["v"] == SCENE and data["pages"][0]["pic"]["v"] == SCENE
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    v = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert v["cover"]["v"] == SCENE and v["pages"][0]["pic"]["v"] == SCENE


def test_game_keeps_drawings_and_plays_them(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, data = _new(client, hm, "game", game_with_drawings())
    r = data["rooms"][0]
    assert r["bg"]["v"] == SCENE and r["variants"][0]["bg"]["v"].startswith('<svg') and r["spots"][0]["art"]["v"] == THING
    assert data["items"][0]["icon"]["v"] == THING
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    v = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert v["room"]["bg"]["v"] == SCENE and next(s for s in v["spots"] if s["id"] == 11)["art"]["v"] == THING
    v = client.post(f"/api/stories/{sid}/read/act", json={"verb": "take", "spot": 11}, headers=hl).json()
    assert v["inv"][0]["icon"] == {"k": "svg", "v": THING}
    cover = next(x for x in client.get("/api/stories", headers=hl).json()["books"] if x["id"] == sid)["cover"]
    assert cover == {"k": "svg", "v": SCENE}                                    # the shelf: the drawn start room
    # a room background may be a scene (60 KB), a hotspot picture only a thing (20 KB)
    g = game_with_drawings()
    g["rooms"][0]["spots"][0]["art"] = {"k": "svg", "v": big(140, "0 0 200 200")}
    g["rooms"][1]["bg"] = {"k": "svg", "v": big(380)}
    d = client.put(f"/api/stories/{sid}", json={"data": g}, headers=hm).json()["data"]
    assert d["rooms"][0]["spots"][0]["art"] is None and d["rooms"][1]["bg"]["k"] == "svg"


def test_book_size_limit_with_drawings(client):
    ph, hm, hl, mia, leo = _logins(client)
    g = game_with_drawings()
    scene = big(380)
    for i in range(3, 40):
        g["rooms"].append({"id": i, "name": f"R{i}", "text": "x", "bg": {"k": "svg", "v": scene}, "variants": [], "spots": []})
    sid = client.post("/api/stories", json={"title": "Huge", "type": "game"}, headers=hm).json()["id"]
    r = client.put(f"/api/stories/{sid}", json={"data": g}, headers=hm)
    assert r.status_code == 400 and "too big" in r.json()["detail"]
    assert len(json.dumps(g)) > A.MAX_BYTES


# ---------------------------------------------------------------- privacy: drawings of a private book reach nobody else
@pytest.mark.parametrize("kind,make", [("adventure", adventure_with_drawings), ("picture", picture_with_drawings), ("game", game_with_drawings)])
def test_private_drawings_reach_nobody_else(client, kind, make):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _new(client, hm, kind, make(), title="Secret", visibility="me")
    assert client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    hp = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}   # the parent in the app
    marker = "fq-draw"
    for h in (hl, ph, hp):
        for path in (f"/api/stories/{sid}", f"/api/stories/{sid}/read", f"/api/stories/{sid}/export"):
            r = client.get(path, headers=h)
            assert r.status_code in (400, 403, 404) and marker not in r.text, (path, r.status_code)
        assert client.post(f"/api/stories/{sid}/try", json={}, headers=h).status_code in (400, 403, 404)
        r = client.get("/api/stories", headers=h)
        assert r.status_code == 200 and marker not in r.text and "Secret" not in r.text
    # the parent area only sees that a private book exists
    assert any(p["id"] == sid for p in client.get("/api/stories", headers=ph).json()["private"])
    # the author has everything
    assert marker in client.get(f"/api/stories/{sid}", headers=hm).text and marker in client.get(f"/api/stories/{sid}/export", headers=hm).text


def test_drawings_are_in_the_backup(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _new(client, hm, "game", game_with_drawings(), visibility="me")
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/parent/backup", headers=ph).content))
    assert b"fq-draw" in z.read("family_quest.db")                  # inside the book data – no separate files


# ---------------------------------------------------------------- the file format: export → import with the drawings
@pytest.mark.parametrize("kind,make", [("adventure", adventure_with_drawings), ("picture", picture_with_drawings), ("game", game_with_drawings)])
def test_export_import_round_trip_keeps_drawings(client, kind, make):
    ph, hm, hl, mia, leo = _logins(client)
    sid, data = _new(client, hm, kind, make())
    doc = client.get(f"/api/stories/{sid}/export", headers=hm).json()
    text = json.dumps(doc, ensure_ascii=False)
    assert text.count('"svg": "<svg') >= 2 and doc["_svg_rules"] and "Own drawings (SVG)" in doc["_note"]
    nid = client.post("/api/stories/import", json={"text": text}, headers=hl).json()["ids"][0]
    again = client.get(f"/api/stories/{nid}", headers=hl).json()
    assert again["type"] == kind and again["visibility"] == "me"

    def svgs(d):
        return sorted(re.findall(r"<svg.*?</svg>", json.dumps(d, ensure_ascii=False)))
    assert svgs(again["data"]) == svgs(data) and svgs(data)


def test_import_cleans_and_caps_drawings(client):
    ph, hm, hl, mia, leo = _logins(client)
    evil = SCENE.replace("<path ", '<path onload="alert(1)" ').replace("</defs>", "</defs><script>alert(2)</script>")
    doc = {"_format": S.STORY_FORMAT, "books": [{"title": "Imp", "language": "en", "start": "a", "pages": [
        {"id": "a", "type": "scene", "text": "Go", "picture": {"svg": THING}, "background": {"svg": evil},
         "choices": [{"text": "x", "goes_to": "b"}, {"text": "y", "goes_to": "c"}]},
        {"id": "b", "type": "good_ending", "text": "Yay", "picture": {"svg": big(140, "0 0 200 200")}, "background": evil},
        {"id": "c", "type": "bad_ending", "text": "Oh", "picture": "🙈", "background": "jungle"}]}]}
    sid = client.post("/api/stories/import", json={"text": json.dumps(doc)}, headers=hm).json()["ids"][0]
    p = client.get(f"/api/stories/{sid}", headers=hm).json()["data"]["pages"]
    assert p[0]["pic"]["v"] == THING and "script" not in p[0]["bg"]["v"] and "onload" not in p[0]["bg"]["v"] and "fq-draw" in p[0]["bg"]["v"]
    assert p[1]["pic"] is None and p[1]["bg"]["k"] == "svg"           # a thing over 20 KB is left out; a scene as plain text works too
    assert p[2]["pic"] == {"k": "emoji", "v": "🙈"} and p[2]["bg"] == "jungle"
    # the whole file has a limit too
    assert client.post("/api/stories/import", json={"text": "x" * (S.IMPORT_MAX + 1)}, headers=hm).status_code in (400, 422)


@pytest.mark.parametrize("kind", ["adventure", "picture", "game"])
def test_ai_templates_explain_svg_with_an_example(client, kind):
    r = client.get(f"/api/stories/ai-template?type={kind}")
    doc = r.json()
    rules = " ".join(doc["_svg_rules"])
    assert "800 600" in rules and "60 KB" in rules and "script" in rules and "foreignObject" in rules
    if kind != "picture":
        assert "200 200" in rules and "20 KB" in rules and "transparent" in rules
    svgs = re.findall(r"<svg.*?</svg>", json.dumps(doc["books"] if "books" in doc else doc["games"], ensure_ascii=False))
    assert svgs and all(safe_svg(s.replace('\\"', '"')) for s in svgs)
    # the template itself imports with its drawings
    ids = client.post("/api/stories/import", json={"text": r.text}, headers={"X-FQ-Token": _logins(client)[2]["X-FQ-Token"]}).json()["ids"]
    assert len(ids) == 1


# ---------------------------------------------------------------- older painted PNG drawings still work
def test_old_png_drawings_still_render(client):
    ph, hm, hl, mia, leo = _logins(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
    name = client.post("/api/stories/image", files={"file": ("d.png", io.BytesIO(png), "image/png")}, headers=hm).json()["name"]
    old = {"k": "img", "v": name, "src": "draw"}
    g = game()
    g["rooms"][0]["bg"] = old
    g["rooms"][0]["spots"][0]["art"] = old
    sid, d = _new(client, hm, "game", g)
    assert d["rooms"][0]["bg"] == old and d["rooms"][0]["spots"][0]["art"] == old
    assert client.get(f"/media/_stories/{name}").status_code == 200
    data = json.loads(json.dumps(BOOK))
    data["pages"][0]["pic"] = old
    bid, d = _new(client, hm, "adventure", data)
    assert d["pages"][0]["pic"] == old
    exp = client.get(f"/api/stories/{bid}/export", headers=hm).json()
    assert "picture" not in exp["books"][0]["pages"][0]                # PNG files stay out of the file, like photos
    pb = PB.clean({"pages": [{"id": 1, "layout": "top", "text": "x", "pic": old}]})
    assert pb["pages"][0]["pic"] == old
