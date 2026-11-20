"""Guests choose their avatar (guest page: quick picks, «Customize») and change it during the visit (PUT /api/guest/avatar);
every game lobby shows the «Invite guests» button (shared/ui.js inviteBtn)."""
import pathlib
import re

from test_api import setup_family

WEB = pathlib.Path(__file__).resolve().parents[1] / "family_quest" / "app" / "web"
GIRL = {"skin": "#8d5524", "hair": "ponytail", "hairColor": "#111111", "eyes": "happy", "mouth": "smile",
        "outfit": "dress", "outfitColor": "#f783ac", "items": {"hairclip": "clip_bow"}}


def _tschau(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/community/cards/tschau/start", json={}, headers=hm)
    code = client.post("/api/community/guests", json={"game": "tschau"}, headers=hm).json()["invite"]["code"]
    return ph, hm, code


def _seat(client, h, name):
    st = client.get("/api/community/cards/tschau", headers=h).json()
    return next(p for p in st["players"] if p["name"] == name)


def test_guest_joins_with_own_avatar(client):
    _, hm, code = _tschau(client)
    info = client.get(f"/api/community/guest/info?code={code}").json()
    cat = info["avatar_catalog"]
    assert "dress" in cat["parts"]["outfit"] and {i["id"] for i in cat["items"]} >= {"glasses", "clip_bow"}
    assert not {"cap", "crown", "santa", "cat"} & {i["id"] for i in cat["items"]}         # no shop, level, season items, pets
    r = client.post("/api/community/guest/join", json={"code": code, "name": "Lena", "avatar": GIRL})
    assert r.status_code == 200
    assert r.json()["profile"]["avatar"] == GIRL
    assert _seat(client, hm, "Lena")["avatar"] == GIRL                                   # the seat at the table


def test_guest_avatar_is_sanitised(client):
    _, _, code = _tschau(client)
    bad = {"skin": "red; </svg><script>", "hair": "mohawk", "outfit": "dress", "items": {"hat": "nope", "eyewear": "glasses"}, "evil": 1}
    r = client.post("/api/community/guest/join", json={"code": code, "name": "Max", "avatar": bad})
    assert r.status_code == 200
    a = r.json()["profile"]["avatar"]
    assert a["skin"] == "#f1c27d" and a["hair"] == "short" and a["outfit"] == "dress"     # unknown values: the defaults
    assert a["items"] == {"eyewear": "glasses"} and "evil" not in a
    for junk in ("x", [1, 2], {"items": ["cap"]}):
        assert client.post("/api/community/guest/join", json={"code": code, "name": "Tom", "avatar": junk}).status_code == 400


def test_guest_cannot_take_shop_items(client):
    _, _, code = _tschau(client)
    for item in ({"hat": "cap"}, {"hat": "crown"}, {"pet": "cat"}, {"hat": "royal"}):
        r = client.post("/api/community/guest/join", json={"code": code, "name": "Tom", "avatar": {**GIRL, "items": item}})
        assert r.status_code in (200, 400)
        if r.status_code == 200:                         # not an item at all (royal): dropped
            assert r.json()["profile"]["avatar"]["items"] == {}
        else:
            assert "free" in r.json()["detail"]
    r = client.post("/api/community/guest/join", json={"code": code, "name": "Tom", "avatar": {**GIRL, "items": {"hat": "cap"}}})
    assert r.status_code == 400


def test_random_avatar_without_a_choice(client):
    _, _, code = _tschau(client)
    a = client.post("/api/community/guest/join", json={"code": code, "name": "Gotti"}).json()["profile"]["avatar"]
    assert a["hair"] in ("short", "long", "curly", "bun", "ponytail") and a["skin"] in ("#ffe0bd", "#f1c27d", "#e0ac69", "#c68642")
    assert a["items"] == {}


def test_put_guest_avatar_only_with_a_guest_token(client):
    ph, hm, code = _tschau(client)
    g = {"X-FQ-Token": client.post("/api/community/guest/join", json={"code": code, "name": "Oma"}).json()["token"]}
    assert client.put("/api/guest/avatar", json={"avatar": GIRL}).status_code == 403            # no token
    assert client.put("/api/guest/avatar", json={"avatar": GIRL}, headers=hm).status_code == 403  # a child
    assert client.put("/api/guest/avatar", json={"avatar": GIRL}, headers=ph).status_code == 403  # a parent
    assert client.put("/api/guest/avatar", json={"avatar": {**GIRL, "items": {"hat": "cap"}}}, headers=g).status_code == 400
    r = client.put("/api/guest/avatar", json={"avatar": GIRL}, headers=g)
    assert r.status_code == 200 and r.json()["avatar"] == GIRL
    assert _seat(client, hm, "Oma")["avatar"] == GIRL                                    # the seat shows it at once
    assert _seat(client, g, "Oma")["avatar"] == GIRL
    mia = _seat(client, hm, "Mia")["avatar"]
    assert mia != GIRL                                                                    # nobody else changed


def test_put_guest_avatar_updates_poker_seat(client):
    _, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/community/poker/start", json={}, headers=hm)
    code = client.post("/api/community/guests", json={"game": "poker"}, headers=hm).json()["invite"]["code"]
    g = {"X-FQ-Token": client.post("/api/community/guest/join", json={"code": code, "name": "Opa"}).json()["token"]}
    assert client.put("/api/guest/avatar", json={"avatar": GIRL}, headers=g).status_code == 200
    st = client.get("/api/community/poker", headers=hm).json()
    assert next(p for p in st["players"] if p["name"] == "Opa")["avatar"] == GIRL


def _call_end(src: str, start: int) -> int:
    """The end of the call h( … ) that opens at `start` (string literals skipped)."""
    depth, i, q = 0, start, None
    while i < len(src):
        c = src[i]
        if q:
            if c == "\\":
                i += 1
            elif c == q:
                q = None
        elif c in "\"'`":
            q = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise AssertionError("unbalanced")


def test_every_lobby_shows_the_invite_button():
    """Every lobby box («Waiting for the start …») holds inviteBtn() with the same value the game passes to gameMenu
    for the ☰ entry, and every game whose ☰ offers guests has such a lobby button."""
    assert "function inviteBtn(invite)" in (WEB / "shared" / "ui.js").read_text()
    assert ".lobby-invite" in (WEB / "shared" / "base.css").read_text()
    boxes = 0
    for f in sorted(WEB.glob("*.js")):
        src = f.read_text()
        calls = [src[m.start():_call_end(src, m.start() + 8) + 1] for m in re.finditer(r"gameMenu\(\{", src)]
        menus = [m.group(1) or "" for c in calls for m in [re.search(r"\binvite\b(: [^,]*)?", c)] if m]
        waits = [m.start() for m in re.finditer(r'T\("Waiting for the start …"\)', src)]
        if menus:                                   # ☰ «Invite guests» and the button: one value
            assert all(m in ("", ": invite()") for m in menus), (f.name, menus)
            assert "inviteBtn(invite" in src, f.name
        for w in waits:
            box = src.rfind('h("section.card', 0, w)
            assert box >= 0, f.name
            assert "inviteBtn(invite" in src[box:_call_end(src, box + 1) + 1], f"{f.name}: lobby box without inviteBtn"
            boxes += 1
    joins = [f.name for f in WEB.glob("*.js") if "joins on their own device" in f.read_text()]
    assert all("inviteBtn(invite" in (WEB / n).read_text() for n in joins), joins
    assert boxes >= 25
    assert "inviteBtn(invite())" in (WEB / "schach.js").read_text()          # chess: below «Waiting for an opponent …»
