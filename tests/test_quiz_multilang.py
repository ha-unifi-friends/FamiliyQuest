"""Multilingual quizzes: languages and translations through editor, import, export and the live game."""
import json

from tests.test_api import setup_family


def test_multilingual_quiz_template_import_export_and_game(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    tpl = client.get("/api/ai-template/quiz").text
    ids = client.post("/api/community/quizzes/import", json={"text": tpl}, headers=hm).json()["ids"]
    assert len(ids) == 2
    quizzes = {q["id"]: q for q in client.get("/api/community/quizzes", headers=hm).json()}
    single, multi = quizzes[ids[0]], quizzes[ids[1]]
    assert single["langs"] is None
    assert multi["langs"] == {"base": "en", "more": ["de", "fr"], "title": {"de": "Tiere der Alpen", "fr": "Animaux des Alpes"}}
    q0 = multi["questions"][0]
    assert q0["tr"]["fr"]["a"] == ["Marmotte", "Bouquetin", "Chamois"] and q0["tr"]["de"]["q"] == "Welches Tier pfeift bei Gefahr?"
    # export keeps everything – import again gives the same quiz
    doc = client.get(f"/api/community/quizzes/{ids[1]}/export", headers=hm).json()
    assert doc["quizzes"][0]["language"] == "en" and doc["quizzes"][0]["questions"][0]["translations"]["de"]["answers"][0] == "Murmeltier"
    again = client.post("/api/community/quizzes/import", json={"text": json.dumps(doc)}, headers=hm).json()["ids"][0]
    fq = client.app.state.fq
    assert fq.db.val("SELECT questions FROM quiz WHERE id=?", again) == fq.db.val("SELECT questions FROM quiz WHERE id=?", ids[1])
    # the game: translations come with the question, the answers shuffled in the same order
    assert client.post("/api/community/quiz/start", json={"quiz_id": ids[1]}, headers=hm).status_code == 200
    client.post("/api/community/quiz/next", headers=hm)
    st = client.get("/api/community/quiz", headers=hm).json()
    assert st["langs"]["more"] == ["de", "fr"]
    q = st["question"]
    if q["kind"] == "choice":
        en = ["Marmot", "Ibex", "Chamois"]; fr = ["Marmotte", "Bouquetin", "Chamois"]
        assert [fr[en.index(a)] for a in q["a"]] == q["tr"]["fr"]["a"]
    else:
        assert q["tr"]["fr"]["q"]


def test_editor_turns_languages_on_and_off(client):
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    body = {"title": "Farben", "langs": {"base": "de", "more": ["fr", "xx", "de"], "title": {"fr": "Couleurs"}},
            "questions": [{"q": "Welche Farbe hat Gras?", "a": ["Grün", "", "Blau"], "c": 0, "t": 20,
                           "tr": {"fr": {"q": "De quelle couleur est l'herbe ?", "a": ["Vert", "x", ""]}, "it": {"q": "?"}}}]}
    qid = client.post("/api/community/quizzes", json=body, headers=hm).json()["id"]
    q = next(x for x in client.get("/api/community/quizzes", headers=hm).json() if x["id"] == qid)
    assert q["langs"] == {"base": "de", "more": ["fr"], "title": {"fr": "Couleurs"}}
    assert q["questions"][0]["a"] == ["Grün", "Blau"] and q["questions"][0]["tr"] == {"fr": {"q": "De quelle couleur est l'herbe ?", "a": ["Vert", "Blau"]}}
    body["langs"] = None                              # switched off: one language again, translations dropped
    client.put(f"/api/community/quizzes/{qid}", json=body, headers=hm)
    q = next(x for x in client.get("/api/community/quizzes", headers=hm).json() if x["id"] == qid)
    assert q["langs"] is None and "tr" not in q["questions"][0]


def test_a_parent_cancels_a_quiz_a_child_started(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    qid = client.post("/api/community/quizzes", json={"title": "T", "questions": [{"q": "?", "a": ["a", "b"], "c": 0}]}, headers=hm).json()["id"]
    assert client.post("/api/community/quiz/start", json={"quiz_id": qid}, headers=hm).status_code == 200
    assert client.post("/api/community/quiz/abort", headers=hl).status_code == 403          # not leading, not a parent
    assert client.post("/api/community/quiz/abort", headers=ph).status_code == 200
    st = client.get("/api/community/quiz", headers=hl).json()
    assert st is None or st["status"] == "done"


def test_a_quiz_from_a_template_gets_the_template_translations(client, monkeypatch):
    from familyquest import community
    from familyquest.quiz_templates import TEMPLATES
    t = TEMPLATES["schaetzfragen"]
    fake = {"title": "Estimates", "items": [{"q": f"Q{i}", **({"unit": "m"} if x.get("unit") else {})} for i, x in enumerate(t["questions"])]}
    monkeypatch.setattr(community, "_TEMPLATE_TR", {"en": {"schaetzfragen": fake}, "fr": {"schaetzfragen": {"title": "x", "items": []}}})
    ph, mia, _ = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    tpl = next(x for x in client.get("/api/community/templates", headers=hm).json() if x["id"] == "schaetzfragen")
    assert tpl["titles"] == {"en": "Estimates"}                       # fr does not fit the template: left out
    qid = client.post("/api/community/quizzes/from-template", json={"template": "schaetzfragen"}, headers=hm).json()["id"]
    q = next(x for x in client.get("/api/community/quizzes", headers=hm).json() if x["id"] == qid)
    assert q["langs"] == {"base": "de", "more": ["en"], "title": {"en": "Estimates"}}
    assert q["questions"][0]["tr"]["en"]["q"] == "Q0"
