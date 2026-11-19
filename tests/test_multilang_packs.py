"""Built-in packs in every app language: only multilingual packs by default, German-only packs under «More packs»,
language courses with the prompt in the learner's language (progress stays with the card)."""
from familyquest.packs import i18n as pack_i18n

GERMAN_ONLY = {"allgemeinwissen", "deutsch-5kl", "geo-tg", "tg-5-klasse"}
FR = {"X-FQ-Lang": "fr-FR"}


def _family(client, lang="fr-FR"):
    hl = {"X-FQ-Lang": lang}
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}, headers=hl)
    ph = {"X-FQ-Parent": r.json()["parent_token"], **hl}
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia}).json()["token"], **hl}
    return ph, mia, h


def _viewer(lang):
    class V:
        def __enter__(self):
            self.t = pack_i18n.set_viewer(lang)

        def __exit__(self, *a):
            pack_i18n.reset_viewer(self.t)
    return V()


def test_fresh_install_in_french_shows_only_multilingual_packs(client):
    ph, mia, h = _family(client)
    packs = {p["id"]: p for p in client.get("/api/parent/packs", headers=ph).json()["packs"]}
    assert {i for i, p in packs.items() if p["status"] == "available"} == GERMAN_ONLY       # «More packs»
    assert all(packs[i]["optional"] and packs[i]["content_langs"] == ["de"] for i in GERMAN_ONLY)
    assert packs["mathe-5kl"]["title"] == "Mathématiques 5e année" and packs["mathe-5kl"]["level"] == "5e année"
    assert packs["mathe-5kl"]["units"][0]["title"] == "Tables de multiplication de 6 à 9"
    assert packs["geo-tg"]["title"] == "Géographie du canton de Thurgovie"           # parents know what it is
    # the child: maths and the English unit – no German-only pack, no French course for a French child
    subjects = {s["pack"]: s for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert set(subjects) == {"mathe-5kl", "engl-5kl-unit-1"}
    assert subjects["engl-5kl-unit-1"]["title"] == "Anglais 5e année – In the classroom"
    courses = {c["id"]: c for c in client.get("/api/me/courses", headers=h).json()}
    assert not any(i.startswith("sprache-fr-") for i in courses) and not GERMAN_ONLY & set(courses)
    assert {"sprache-en-a1", "sprache-de-b1", "sprache-es-a2"} <= set(courses)
    en = courses["sprache-en-a1"]
    assert en["title"] == "Anglais A1 – Débutant" and en["src_lang"] == "fr" and en["description"].startswith("Tes premiers pas")
    # the family language is known now (prompt fallback)
    assert client.app.state.fq.db.get_setting("family_lang") == "fr"


def test_german_packs_can_be_added_with_one_click(client):
    ph, mia, h = _family(client)
    r = client.post("/api/parent/packs/install", json={"ids": sorted(GERMAN_ONLY | {"mathe-5kl"})}, headers=ph).json()
    assert set(r["done"]) == GERMAN_ONLY                          # «Add all German-language packs»; mathe is no optional pack
    packs = {p["id"]: p for p in client.get("/api/parent/packs", headers=ph).json()["packs"]}
    assert all(packs[i]["status"] == "active" for i in GERMAN_ONLY)
    assert "geo-tg" not in {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}   # added ≠ switched on
    client.post("/api/parent/packs/activate", json={"profile_id": mia, "pack_id": "geo-tg", "on": True}, headers=ph)
    assert "geo-tg" in {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert "allgemeinwissen" in {c["id"] for c in client.get("/api/me/courses", headers=h).json()}
    # back to «More packs»: switched off for everybody
    client.post("/api/parent/packs/install", json={"ids": ["geo-tg"], "on": False}, headers=ph)
    assert "geo-tg" not in {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert client.app.state.fq.packs.get("geo-tg").status == "available"
    # switching an available pack on for a child adds it as well
    client.post("/api/parent/packs/activate", json={"profile_id": mia, "pack_id": "deutsch-5kl", "on": True}, headers=ph)
    client.post("/api/parent/packs/install", json={"ids": ["deutsch-5kl"], "on": False}, headers=ph)
    client.post("/api/parent/packs/activate", json={"profile_id": mia, "pack_id": "deutsch-5kl", "on": True}, headers=ph)
    assert client.app.state.fq.packs.get("deutsch-5kl").status == "active"


def test_german_family_gets_the_german_school_packs_offered_not_installed(client):
    ph, mia, h = _family(client, "de-CH")
    packs = {p["id"]: p for p in client.get("/api/parent/packs", headers=ph).json()["packs"]}
    assert {i for i, p in packs.items() if p["status"] == "available"} == GERMAN_ONLY
    subjects = {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert subjects == {"mathe-5kl", "engl-5kl-unit-1", "franz-5kl-la-maison"}
    courses = {c["id"]: c for c in client.get("/api/me/courses", headers=h).json()}
    assert "sprache-de-a1" not in courses and courses["sprache-en-a1"]["title"] == "Englisch A1 – Einstieg"


def _prompts(fq, kid, pack, unit, seed=1):
    s = fq.learning.build(kid, "path", pack, unit, seed=seed)
    import json
    data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s["id"])["data"])
    return {p for st in data["steps"] for p in [st["public"].get("prompt")] if p}, data["steps"]


def test_prompt_language_follows_the_learner(fq, kid):
    for pid in ("sprache-en-a1", "sprache-fr-a1"):
        fq.packs.activate(kid, pid)
    with _viewer("fr-FR"):                                         # fr → en
        prompts, steps = _prompts(fq, kid, "sprache-en-a1", "greetings")
        assert prompts and prompts <= {"Salut", "Bonjour (le matin)", "Bonjour (l'après-midi)", "Bonsoir", "Bonne nuit",
                                       "Au revoir", "À plus tard", "Merci", "S'il te plaît (pour demander quelque chose)", "Pardon"}
        assert fq.packs.get("sprache-en-a1").title == "Anglais A1 – Débutant"
        fr_keys = {k for st in steps for k in st["keys"]}
    with _viewer("en"):                                            # en → fr
        prompts, _ = _prompts(fq, kid, "sprache-fr-a1", "begruessung")
        assert "Hello (good day)" in prompts or "Hi" in prompts or "thank you" in prompts
        assert not prompts & {"Guten Tag", "Hallo", "danke"}
    with _viewer("de-CH"):                                         # de → fr: the pack as written
        prompts, _ = _prompts(fq, kid, "sprache-fr-a1", "begruessung")
        assert prompts & {"Guten Tag", "Hallo", "Auf Wiedersehen", "danke", "bitte", "Bis bald", "Wie geht's?", "Es geht mir gut."}
        de_pack = fq.packs.get("sprache-en-a1")
    with _viewer("fr"):
        fr_pack = fq.packs.get("sprache-en-a1")
    # the same cards: progress is kept when the language changes
    assert [i["key"] for i in de_pack.units[0].items] == [i["key"] for i in fr_pack.units[0].items]
    assert fr_keys <= {i["key"] for i in de_pack.units[0].items}
    # the French course for a French learner falls back to English (never French → French)
    with _viewer("fr"):
        assert fq.packs.get("sprache-fr-a1").src_lang == "en"


def test_progress_survives_a_language_switch(fq, kid):
    fq.packs.activate(kid, "sprache-en-a1")
    with _viewer("fr"):
        s = fq.learning.build(kid, "path", "sprache-en-a1", "greetings", seed=3)
        import json
        data = json.loads(fq.db.q1("SELECT data FROM session WHERE id=?", s["id"])["data"])
        for i, st in enumerate(data["steps"]):
            sol = st["solution"]
            ans = {"paare": sol.get("pairs"), "karteikarte": "correct"}.get(st["kind"], sol.get("answer"))
            fq.learning.answer(s["id"], kid, i, ans)
        before = fq.learning.pack_progress(kid, fq.packs.get("sprache-en-a1"))
    with _viewer("de"):
        after = fq.learning.pack_progress(kid, fq.packs.get("sprache-en-a1"))
    assert before["units"][0]["stars"] == after["units"][0]["stars"] and before["percent"] == after["percent"] > 0


def test_existing_installation_keeps_what_children_use(fq):
    """An older installation: every built-in pack was active and switched on for the children automatically."""
    a = fq.db.x("INSERT INTO profile(name) VALUES('Anna')")
    b = fq.db.x("INSERT INTO profile(name) VALUES('Ben')")
    for pid in GERMAN_ONLY:
        fq.packs.set_status(pid, "active")
    fq.db.x("DELETE FROM setting WHERE key IN ('packs_optional_v1','packs_optional_unassign_v1','family_lang')")
    fq.packs.activate(a, "geo-tg")                     # assigned to a child
    fq.packs.activate(a, "deutsch-5kl")
    fq.packs.activate(b, "deutsch-5kl")
    fq.db.x("INSERT INTO item_state(profile_id,item_key,pack_id,unit_id,box) VALUES(?,?,?,?,1)", b, "deutsch-5kl:artikel:x", "deutsch-5kl", "artikel")
    fq.db.x("INSERT INTO attempt(profile_id,item_key,pack_id,correct) VALUES(?,?,?,1)", b, "allgemeinwissen:x:y", "allgemeinwissen")
    fq.packs.retire_optional_once()                    # the update (runs after the folder sync at start)
    st = {p: fq.packs.get(p).status for p in GERMAN_ONLY}
    assert st == {"geo-tg": "active", "deutsch-5kl": "active", "allgemeinwissen": "active", "tg-5-klasse": "available"}
    # a German-speaking family keeps everything
    fq.packs.note_family_lang("de-CH")
    assert fq.packs.activated(a) >= {"geo-tg", "deutsch-5kl"}
    # a French-speaking family: what was switched on automatically and never used goes; progress stays
    fq.db.x("DELETE FROM setting WHERE key='packs_optional_unassign_v1'")
    fq.packs.note_family_lang("fr-FR")
    assert "geo-tg" not in fq.packs.activated(a) and "deutsch-5kl" not in fq.packs.activated(a)
    assert "deutsch-5kl" in fq.packs.activated(b)      # Ben learnt with it
    assert fq.packs.get("geo-tg").status == "available" and fq.packs.get("deutsch-5kl").status == "active"
    assert fq.packs.get("allgemeinwissen").status == "active"    # somebody learnt with it
    fq.packs.note_family_lang("fr-FR")                  # once only
    fq.packs.activate(a, "geo-tg")
    fq.packs.note_family_lang("fr-FR")
    assert "geo-tg" in fq.packs.activated(a)
