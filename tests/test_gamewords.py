"""The word lists of «Zeichnen & Raten», «Wer bin ich?» and «Verbotene Wörter» in the translation registry
(familyquest/gamewords.py): every word in every language, the views in the viewer's language, guesses in the languages
of the table, old German tables and history entries."""
import json
import random
import sys
from pathlib import Path

from familyquest import gamewords as gw
from familyquest import verboten as vw
from familyquest import whoami as wb
from familyquest import zeichnen as zr
from familyquest.whoami_data import CATEGORIES as WB_CATS
from familyquest.zeichnen_data import CATEGORIES as ZR_CATS

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "family_quest" / "app" / "web" / "i18n"
LANGS = ["de-DE", "de-CH", "fr-FR", "it-IT", "es-ES", "nl-NL", "pl-PL", "pt-BR", "sv-SE"]
DICTS = {l: json.loads((I18N / f"{l}.json").read_text(encoding="utf-8")) for l in LANGS}


def zr_words():
    return [w for c in ZR_CATS.values() for w in c["words"]]


def wb_chars():
    return [w for c in WB_CATS.values() for w in c["chars"]]


def all_cards():
    return [c for lv in vw.cards().values() for c in lv]


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def login(client, pid, pin=None, lang=None):
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}
    if lang:
        h["X-FQ-Lang"] = lang
    return h


# ---------------------------------------------------------------- the registry
def test_every_word_character_and_card_in_every_language():
    keys = {w["name"] for w in zr_words()} | {w["name"] for w in wb_chars()}
    assert len({w["name"] for w in zr_words()}) >= 250 and len({w["name"] for w in wb_chars()}) >= 300
    for c in all_cards():
        keys |= {c["word"], gw.SEP.join(c["taboo"])}
    for l, d in DICTS.items():
        missing = sorted(k for k in keys if not d.get(k))
        assert not missing, (l, missing[:10])
    for c in all_cards():
        for l, d in DICTS.items():
            taboo = d[gw.SEP.join(c["taboo"])].split(gw.SEP)
            assert len(taboo) == 5 and len({t.lower() for t in taboo}) == 5 and all(t.strip() == t and t for t in taboo), (l, c)
            assert d[c["word"]].lower() not in {t.lower() for t in taboo}, (l, c)


def test_german_keeps_the_old_words():
    # de-DE shows the old German word of the list (a few words that appear with two spellings use the standard one)
    same = [w for w in zr_words() + wb_chars() if DICTS["de-DE"][w["name"]] == w["aliases"][0]]
    assert len(same) >= 0.9 * len(zr_words() + wb_chars())
    for w in zr_words() + wb_chars():
        de = DICTS["de-DE"][w["name"]]
        assert de == w["aliases"][0] or de in w["aliases"] or w["name"] in ("Sausage", "Croissant", "Ice cream", "Fries", "Carrot",
                                                                          "Hairdresser (job)", "Bus driver", "Lollipop", "Door",
                                                                          "Football", "Balloon", "Muesli"), (w, de)
    assert DICTS["de-DE"]["Witch"] == "Hexe" and DICTS["de-DE"]["Anchor"] == "Anker" and DICTS["de-DE"]["Rabbit"] == "Hase"
    assert DICTS["de-DE"]["Plaster (for a cut)"] == "Pflaster" and DICTS["de-DE"]["Gardener"] == "Gärtner"
    assert DICTS["de-DE"]["bark · cat · pet · leash · bone"] == "bellen · Katze · Haustier · Leine · Knochen"
    assert "ß" not in "".join(DICTS["de-CH"][k] for k in ("Football", "Hot-air balloon", "Watering can"))
    assert DICTS["de-CH"]["Carrot"] == "Rüebli" and DICTS["de-CH"]["Bicycle"] == "Velo"


def test_extract_finds_the_words():
    sys.path.insert(0, str(ROOT / "tools"))
    import i18n_extract
    ks = set(i18n_extract.keys())
    for w in zr_words() + wb_chars():
        assert w["name"] in ks, w
    for c in all_cards():
        assert c["word"] in ks and gw.SEP.join(c["taboo"]) in ks, c


def test_words_translate_and_english_drops_the_note():
    w = gw.Words()
    assert w.tr("Book (to read)", "en") == "Book" and w.tr("Book (to read)", "fr-FR") == "Livre"
    assert w.tr("Carrot", "de-DE") == "Karotte" and w.tr("Carrot", "de-CH") == "Rüebli" and w.tr("Carrot", "sv-SE") == "Morot"
    assert w.tr("Unknown thing", "fr-FR") == "Unknown thing"
    assert gw.clean_lang("fr") == "fr-FR" and gw.clean_lang("de-AT") == "de-DE" and gw.clean_lang("x-baern") == "x-baern"
    assert gw.clean_lang("<script>") == "en" and gw.clean_lang(None) == "en"
    card = w.card("Dog", ["bark", "cat", "pet", "leash", "bone"], "fr-FR")
    assert card == {"word": "Chien", "taboo": ["aboyer", "chat", "animal de compagnie", "laisse", "os"]}
    assert w.card("Dog", ["bark", "cat", "pet", "leash", "bone"], "en")["taboo"] == ["bark", "cat", "pet", "leash", "bone"]
    # the forbidden words are the obvious ones of the language, not word for word: «Hase» forbids «Kaninchen», «rabbit» forbids «hare»
    assert w.card("Rabbit", ["ears", "Easter", "carrot", "hop", "hare"], "de-DE")["taboo"][-1] == "Kaninchen"
    assert w.card("Rabbit", ["ears", "Easter", "carrot", "hop", "hare"], "fr-FR")["taboo"][-1] == "lièvre"


def test_own_texts_of_the_family_count(fq):
    fq.translations.set_overrides("fr-FR", {"Elephant": "Babar"}, merge=True)
    w = gw.Words(fq.db)
    assert w.tr("Elephant", "fr-FR") == "Babar" and w.tr("Elephant", "it-IT") == "Elefante"
    lang = fq.translations.add_language("Bärndütsch", "de-CH")
    fq.translations.set_overrides(lang["code"], {"Carrot": "Rüebli!"}, merge=True)
    assert w.tr("Carrot", lang["code"]) == "Rüebli!" and w.tr("Rabbit", lang["code"]) == "Hase"
    assert "Rüebli" in w.forms("Carrot", [lang["code"]])


# ---------------------------------------------------------------- Draw & Guess
def zr_table(langs, seed=3, clock=None):
    players = [{"id": str(i), "name": f"P{i}"} for i in range(1, len(langs) + 1)]
    st = {"kind": "zeichnen", "rules": {"category": "tiere", "rounds": 1, "time": 80, "hints": True}, "players": players, "phase": "lobby"}
    t = zr.Table(st, random.Random(seed), now=clock or Clock())
    t.begin()
    for i, l in enumerate(langs, 1):
        t.set_lang(str(i), l)
    return t


def test_draw_guess_in_the_guessers_and_the_drawers_language():
    t = zr_table(["de-CH", "fr-FR", "it-IT", "sv-SE"])            # P1 draws (Swiss German)
    t.st["choices"][0] = "Rabbit"
    t.choose("1", 0)
    assert t.st["word"] == "Rabbit"
    assert t.guess("2", "lapin") == "right"                         # French guesser, French word
    assert t.guess("3", "Hase") == "right"                          # Italian guesser, the drawer's word
    assert t.guess("4", "kaninchen") == "right"                     # the German names of the list count with a German drawer
    t2 = zr_table(["fr-FR", "it-IT", "sv-SE"])                       # P1 draws in French
    t2.st["choices"][0] = "Rabbit"
    t2.choose("1", 0)
    assert t2.guess("2", "Coniglio", "it-IT") == "right"           # own language (also as it is sent with the guess)
    assert t2.guess("3", "rabbit") == "right"                       # English always
    t3 = zr_table(["fr-FR", "it-IT", "sv-SE"])
    t3.st["choices"][0] = "Rabbit"
    t3.choose("1", 0)
    assert t3.guess("3", "Hase") == "wrong"                         # nobody speaks German here
    assert t3.guess("3", "conejo") == "wrong"                       # Spanish is not at the table
    assert t3.guess("3", "Kxnxn") == "close"                        # «Kanin» (sv), two letters off: only P3 sees «close»
    assert t3.guess("3", "Kanine") == "right"                       # one typo is fine (5 letters or more)
    assert t3.guess("2", "il coniglio") == "right"                  # articles do not matter
    t4 = zr_table(["fr-FR", "fr-FR"])
    t4.st["choices"][0] = "Rabbit"
    t4.choose("1", 0)
    assert t4.guess("2", "LÂPIN") == "right"                        # accents and case do not matter


def test_draw_guess_view_in_each_language(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    fq.zeichnen.now = Clock(5000)
    hm, hl = login(client, mia, "1111", "fr-FR"), login(client, leo, lang="de-DE")
    client.post("/api/community/zeichnen/start", json={"category": "tiere", "rounds": 1, "time": 60, "hints": True}, headers=hm)
    client.post("/api/community/zeichnen/join", headers=hl)
    st = client.post("/api/community/zeichnen/begin", headers=hm).json()
    fr = set(DICTS["fr-FR"][w["name"]] for w in ZR_CATS["tiere"]["words"])
    assert set(st["choices"]) <= fr                                  # the French drawer chooses among French words
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='zeichnen' ORDER BY id DESC LIMIT 1")
    s = json.loads(row["state"])
    s["choices"][1] = "Snail"
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    st = client.post("/api/community/zeichnen/choose", json={"idx": 1}, headers=hm).json()
    assert st["word"] == "Escargot"
    vl = client.get("/api/community/zeichnen", headers=hl).json()
    assert vl["word"] is None and len(vl["mask"]) == len("Schnecke")       # the German guesser's mask
    v = client.post("/api/community/zeichnen/guess", json={"text": "escargot"}, headers=hl).json()   # the drawer's language
    assert v["result"] == "right" and v["word"] == "Schnecke"
    v = client.post("/api/community/zeichnen/end", headers=hm).json()
    assert v["log"][0]["word"] == "Escargot"
    e = next(x for x in client.get("/api/community/history", headers=hl).json() if x["kind"] == "zeichnen")
    assert e["data"]["drawn"] == []                                   # Leo did not draw
    e = next(x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "zeichnen")
    assert e["data"]["drawn"] == ["Escargot"]
    assert fq.db.q1("SELECT data FROM history WHERE kind='zeichnen' AND profile_id=?", mia)["data"].count("Snail") == 1


def test_draw_guess_old_german_table_still_works():
    t = zr_table(["fr-FR", "de-DE"])
    t.st["choices"][0] = "Schnecke"                                  # a table of before: German words in the state
    t.choose("1", 0)
    assert t.text(t.st["word"], "fr-FR") == "Escargot" and t.text(t.st["word"], "de-DE") == "Schnecke"
    assert t.mask("fr-FR") == ["_"] * 8
    assert t.guess("2", "Schnecke") == "right"
    t2 = zr_table(["fr-FR", "de-DE"])
    t2.st["choices"][0] = "Fantasiewort"                             # not in the list: shown and checked as it is
    t2.choose("1", 0)
    assert t2.text(t2.st["word"], "fr-FR") == "Fantasiewort" and t2.guess("2", "fantasiewort") == "right"


# ---------------------------------------------------------------- Who am I?
def test_whoami_any_language_at_the_table():
    players = [{"id": str(i), "name": f"P{i}"} for i in (1, 2, 3)]
    st = {"kind": "werbinich", "rules": {"category": "berufe"}, "players": players, "phase": "lobby"}
    t = wb.Table(st, random.Random(1))
    t.deal()
    for p, l in (("1", "fr-FR"), ("2", "de-CH"), ("3", "pl-PL")):
        t.set_lang(p, l)
    keys = [c["name"] for c in WB_CATS["berufe"]["chars"]]
    t.st["chars"]["1"] = keys.index("Gardener")
    assert t.guess("1", "Je suis jardinier", "fr-FR")                # own language, «je suis» does not matter
    t.st["chars"]["2"] = keys.index("Baker")
    assert t.guess("2", "ich bin Piekarz")                           # another language at the table
    t.st["chars"]["3"] = keys.index("Butcher")
    assert t.st["turn"] == "3"
    assert not t.guess("3", "Carnicero")                             # Spanish is not at the table
    assert t.st["turn"] == "3"                                        # the only one still guessing
    assert t.guess("3", "rzeźnik") and t.st["phase"] == "done"       # own language


def test_whoami_old_german_state():
    st = {"kind": "werbinich", "rules": {"category": "berufe"}, "players": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}],
          "phase": "play", "chars": {"1": 13, "2": 0}, "turn": "1", "question": None, "log": [], "done": {}, "found": [], "qn": 0,
          "last": None}
    t = wb.Table(st)
    assert t.char_of("1")["name"] == "Gardener"                     # the state keeps the index: old tables stay the same
    assert t.guess("1", "Gärtner")                                    # no language known: every language counts


def test_whoami_view_in_each_language_and_old_history(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111", "fr-FR"), login(client, leo, lang="sv-SE")
    client.post("/api/community/werbinich/start", json={"category": "berufe"}, headers=hm)
    client.post("/api/community/werbinich/join", headers=hl)
    client.post("/api/community/werbinich/begin", headers=hm)
    row = fq.db.q1("SELECT * FROM card_game WHERE kind='werbinich' ORDER BY id DESC LIMIT 1")
    s = json.loads(row["state"])
    keys = [c["name"] for c in WB_CATS["berufe"]["chars"]]
    s["chars"] = {str(mia): keys.index("Gardener"), str(leo): keys.index("Magician")}
    s["last"] = {"type": "skip", "player": str(leo), "char": "Feuerwehrmann", "t": 1}        # an old state: a German name
    fq.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(s), row["id"])
    assert client.get("/api/community/werbinich", headers=hm).json()["last"]["char"] == "Pompier"
    vm = client.get("/api/community/werbinich", headers=hm).json()
    vl = client.get("/api/community/werbinich", headers=hl).json()
    assert next(p for p in vm["players"] if p["id"] == str(leo))["char"] == "Magicien"
    assert next(p for p in vl["players"] if p["id"] == str(mia))["char"] == "Trädgårdsmästare"
    v = client.post("/api/community/werbinich/guess", json={"text": "trädgårdsmästare"}, headers=hm).json()   # Leo's language
    assert next(p for p in v["players"] if p["id"] == str(mia))["place"] == 1 and v["last"]["char"] == "Jardinier"
    v = client.post("/api/community/werbinich/guess", json={"text": "trollkarl"}, headers=hl).json()
    assert v["phase"] == "done"
    e = next(x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "werbinich")
    assert e["data"]["char"] == "Jardinier"
    assert '"char": "Gardener"' in fq.db.q1("SELECT data FROM history WHERE kind='werbinich' AND profile_id=?", mia)["data"]
    # a history entry of before the translation (German) is shown in the viewer's language
    fq.community.add_history(mia, "werbinich", {"place": 1, "players": 2, "char": "Gärtner", "found": True, "coins": 0})
    fq.community.add_history(mia, "werbinich", {"place": 1, "players": 2, "char": "Gandalf", "found": True, "coins": 0})
    h = [x for x in client.get("/api/community/history", headers=hm).json() if x["kind"] == "werbinich"]
    assert [x["data"]["char"] for x in h[:2]] == ["Gandalf", "Jardinier"]
    h = [x for x in client.get("/api/community/history", headers=login(client, mia, "1111", "it-IT")).json() if x["kind"] == "werbinich"]
    assert h[1]["data"]["char"] == "Giardiniere"


# ---------------------------------------------------------------- Forbidden Words
def test_forbidden_words_card_in_the_explainers_language(client):
    from test_api import setup_family
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm, hl = login(client, mia, "1111", "fr-FR"), login(client, leo, lang="nl-NL")
    client.post("/api/community/verboten/start", json={"level": "easy", "teams": False}, headers=hm)
    client.post("/api/community/verboten/join", headers=hl)
    client.post("/api/community/verboten/begin", headers=hm)
    v = client.post("/api/community/verboten/go", headers=hm).json()
    key = json.loads(fq.db.q1("SELECT state FROM card_game WHERE kind='verboten' ORDER BY id DESC LIMIT 1")["state"])["card"]
    c = vw.card(key)
    assert v["card"]["word"] == DICTS["fr-FR"][c["word"]]
    assert v["card"]["taboo"] == DICTS["fr-FR"][gw.SEP.join(c["taboo"])].split(gw.SEP)
    assert client.get("/api/community/verboten", headers=hl).json()["card"] is None       # alone: the guesser never sees it
    v = client.post("/api/community/verboten/mark", json={"n": v["n"], "result": "pass"}, headers=hm).json()
    assert v["turn_cards"][0]["word"] == DICTS["fr-FR"][c["word"]]
    assert vw.card_view(key, "nl-NL")["word"] == DICTS["nl-NL"][c["word"]]
    assert vw.card_view(key)["word"] == gw.english(c["word"])
