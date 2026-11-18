"""Parent area › Games › 🛠️ Custom games: the adventure games as a game of their own (status per child, enforced on the
server), the library without them, the photo sets of the Pair Hunt as ZIP (import / export) and the frontend structure."""
import io
import json
import zipfile
from pathlib import Path

from test_stories import BOOK, _logins

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40


def _game(client, h, publish=True):
    sid = client.post("/api/stories", json={"template": "tower", "lang": "en", "type": "game", "visibility": "family"}, headers=h).json()["id"]
    if publish:
        assert client.post(f"/api/stories/{sid}/publish", headers=h).status_code == 200
    return sid


def _off(client, ph, game="adventuregame", **a):
    acc = client.get("/api/parent/games", headers=ph).json()["access"][game]
    r = client.put("/api/parent/games", json={"access": {game: {**acc, "mode": "off", **a}}}, headers=ph)
    assert r.status_code == 200, r.text
    return r.json()["access"][game]


def test_adventure_games_are_a_game_without_bots_or_price(client):
    ph, hm, hl, mia, leo = _logins(client)
    d = client.get("/api/parent/games", headers=ph).json()
    a = d["access"]["adventuregame"]
    assert a["mode"] == "all" and a["price"] == 0 and a["rent"] == 0 and "adventuregame" not in d["bot_games"]
    assert "adventuregame" in client.get("/api/me", headers=hm).json()["games_list"]
    r = client.put("/api/parent/games", json={"access": {"adventuregame": {**a, "price": 300, "rent": 50}}}, headers=ph)
    assert r.json()["access"]["adventuregame"]["price"] == 0 and r.json()["access"]["adventuregame"]["rent"] == 0   # always free
    assert client.put("/api/parent/games", json={"access": {"adventuregame": {**a, "bots": False}}}, headers=ph).status_code == 400


def test_switched_off_kids_can_neither_play_nor_make_adventure_games(client):
    ph, hm, hl, mia, leo = _logins(client)
    gid = _game(client, hm)                        # Mia's game on the shelf, an adventure book of Leo too
    bid = client.post("/api/stories", json={"title": "Lion", "lang": "en", "visibility": "family"}, headers=hl).json()["id"]
    client.put(f"/api/stories/{bid}", json={"data": BOOK}, headers=hl)
    assert client.post(f"/api/stories/{bid}/publish", headers=hl).status_code == 200
    assert client.post(f"/api/stories/{gid}/read/act", json={"verb": "look", "spot": 11}, headers=hl).status_code == 200
    _off(client, ph, profiles=[])
    for h in (hm, hl):
        s = client.get("/api/stories", headers=h).json()
        assert "game" not in s["creatable"] and "game" not in s["types"] and all(b["type"] != "game" for b in s["books"])
        assert client.post(f"/api/stories/{gid}/read/act", json={"verb": "look", "spot": 11}, headers=h).status_code == 400
        assert client.get(f"/api/stories/{gid}/read", headers=h).status_code == 400
        r = client.post("/api/stories", json={"template": "tower", "lang": "en", "type": "game"}, headers=h)
        assert r.status_code == 400 and "switched off" in r.json()["detail"]
    assert client.get(f"/api/stories/{gid}", headers=hm).status_code == 400           # not even the own draft
    assert client.put(f"/api/stories/{gid}", json={"title": "X"}, headers=hm).status_code == 400
    doc = client.get(f"/api/stories/{gid}/export", headers=ph).text                  # parents: never bound
    assert client.post("/api/stories/import", json={"text": doc}, headers=hl).status_code == 400
    assert client.post("/api/stories/import", json={"text": doc}, headers=ph).status_code == 200
    # the library itself stays: adventure books are read as before
    assert client.get(f"/api/stories/{bid}/read", headers=hm).status_code == 200
    assert any(b["id"] == bid for b in client.get("/api/stories", headers=hm).json()["books"])
    assert any(b["id"] == gid for b in client.get("/api/stories", headers=ph).json()["books"])
    assert "adventuregame" not in client.get("/api/me", headers=hm).json()["games_list"]
    # only for Mia again
    acc = client.get("/api/parent/games", headers=ph).json()["access"]["adventuregame"]
    client.put("/api/parent/games", json={"access": {"adventuregame": {**acc, "mode": "some", "profiles": [mia]}}}, headers=ph)
    assert client.post(f"/api/stories/{gid}/read/act", json={"verb": "look", "spot": 11}, headers=hm).status_code == 200
    assert client.post(f"/api/stories/{gid}/read/act", json={"verb": "look", "spot": 11}, headers=hl).status_code == 400
    assert "game" in client.get("/api/stories", headers=hm).json()["creatable"]


def test_adventure_games_stay_open_after_the_update(fq):
    games = [g for g in fq.GAMES if g != "adventuregame"]
    acc = {g: {"mode": "all", "profiles": []} for g in games}
    acc["poker"] = {"mode": "off", "profiles": []}                # restricted: a really new game would start off
    fq.db.set_setting("games_access", acc)
    assert fq.games_access()["adventuregame"]["mode"] == "all"


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return buf.getvalue()


def test_photo_set_zip_import_and_export(client):
    ph, *_ = _logins(client)
    raw = _zip({"b.png": PNG + b"2", "a.png": PNG + b"1", "__MACOSX/._a.png": PNG, "notes.txt": b"hi", "fake.jpg": b"nope",
                "sub/c.png": PNG + b"3"})
    r = client.post("/api/parent/memory/import", files={"file": ("set.zip", raw, "application/zip")}, headers=ph)
    assert r.status_code == 200, r.text
    names = r.json()["names"]
    assert len(names) == 3 and all(n.startswith("foto-") and n.endswith(".png") for n in names)
    sets = client.put("/api/parent/memory", json={"sets": [{"name": "🐾 Pets", "photos": names}]}, headers=ph).json()["sets"]
    assert sets[0]["photos"] == names
    r = client.get(f"/api/parent/memory/sets/{sets[0]['id']}/export", headers=ph)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert z.namelist() == ["01.png", "02.png", "03.png"] and z.read("01.png") == PNG + b"1"
    # the export imports again (same photos, same names)
    assert client.post("/api/parent/memory/import", files={"file": ("x.zip", r.content)}, headers=ph).json()["names"] == names
    bad = client.post("/api/parent/memory/import", files={"file": ("x.zip", b"not a zip")}, headers=ph)
    assert bad.status_code == 400 and "ZIP" in bad.json()["detail"]
    assert client.post("/api/parent/memory/import", files={"file": ("x.zip", _zip({"a.txt": b"x"}))}, headers=ph).status_code == 400
    big = _zip({"huge.png": PNG + b"\0" * (5 * 1024 * 1024)})
    assert client.post("/api/parent/memory/import", files={"file": ("x.zip", big)}, headers=ph).status_code == 400
    assert client.get("/api/parent/memory/sets/nope/export", headers=ph).status_code == 404
    assert client.post("/api/parent/memory/import", files={"file": ("x.zip", raw)}).status_code in (401, 403)


def test_frontend_structure():
    parent, kid, stories = (WEB / "parent.js").read_text("utf-8"), (WEB / "kid.js").read_text("utf-8"), (WEB / "stories.js").read_text("utf-8")
    assert '["adventuregame", "🗝️", T("Adventure games")]' in parent
    assert 'const CUSTOM_GAMES = ["quiz", "paarjagd", "adventuregame"]' in parent and 'h("section.cg-group"' in parent
    assert "P.openGames" not in parent                                   # every game folded, nothing remembered open
    assert 'quizzesPanel(quizzes, me, showLive, { actions: cQuiz.actions, withImport: true' in parent
    assert 'storyShelf(cAdv.list, { types: ["game"], actions: cAdv.actions' in parent
    assert "runningGamesBox(), custom, none" in parent
    assert 'canPlay("adventuregame") && S.me.stories !== false ? adventureGamesCard() : null' in kid and 'view === "advgames"' in kid
    assert 'const LIBRARY_TYPES = ["picture", "adventure"]' in stories and "storyShelf(box, { types: LIBRARY_TYPES })" in stories
    names = {"de-DE": "Eigene Spiele", "de-CH": "Eigeni Spiil", "fr-FR": "Jeux personnalisés", "it-IT": "Giochi personalizzati",
             "es-ES": "Juegos personalizados", "nl-NL": "Eigen spellen", "pl-PL": "Własne gry", "pt-BR": "Jogos personalizados",
             "sv-SE": "Egna spel"}
    for lang, n in names.items():
        d = json.loads((WEB / "i18n" / f"{lang}.json").read_text("utf-8"))
        assert d["Custom games"] == n and d.get("Adventure games are switched off for you") and d.get("Import a photo set"), lang
