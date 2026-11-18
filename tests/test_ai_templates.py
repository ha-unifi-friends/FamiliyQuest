"""Self-describing JSON for an AI (ai_format.py): template = export = import, for learning packs and quizzes."""
import json

from familyquest.jsonish import loads
from test_api import setup_family


def test_json_as_ais_write_it():
    assert loads('{"a": 1}') == {"a": 1}
    text = 'Here is your pack:\n```json\n{\n  "a": [1, 2,], // two numbers\n  /* a note */ "b": "x // not a comment"\n}\n```\nHave fun!'
    assert loads(text) == {"a": [1, 2], "b": "x // not a comment"}


def test_templates_explain_themselves_and_import(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Mama", "pin": "4321"}).json()["parent_token"]}
    for kind in ("pack", "quiz"):
        r = client.get(f"/api/ai-template/{kind}")
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.json"')
        doc = r.json()
        assert doc["_format"].startswith("family-quest-") and doc["_ai_instructions"] and doc["_field_guide"]
    assert client.get("/api/ai-template/nope").status_code == 404
    # the pack template as it is: imports (the example has cards and a maths generator)
    r = client.post("/api/parent/import/file", files={"file": ("t.json", client.get("/api/ai-template/pack").content)}, headers=ph)
    assert r.status_code == 200, r.text and r.json()["drafts"][0]["id"] == "french-5-unit-3"
    # the quiz template as it is: imports with all 8 question types
    hq = ph
    r = client.post("/api/community/quizzes/import", json={"text": client.get("/api/ai-template/quiz").text}, headers=hq)
    assert r.status_code == 200, r.text
    qs = json.loads(client.app.state.fq.db.val("SELECT questions FROM quiz WHERE id=?", r.json()["ids"][0]))
    imgs = [q.get("img") for q in qs]
    assert len(qs) == 8 and imgs[2] == {"flag": "PT"} and imgs[3] == {"emoji": "🦔"} and imgs[4]["svg"].startswith("<svg")
    assert imgs[5] == {"geo": "canton", "id": "TI", "mode": "outline"} and qs[6]["kind"] == "estimate" and qs[7]["kind"] == "pin"


def test_pack_from_an_ai_answer(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Mama", "pin": "4321"}).json()["parent_token"]}
    answer = '''Sure! ```json
{
  "_format": "family-quest-pack/1", "_ai_instructions": ["…"],
  "pakete": [{
    "id": "spanish-4-animals",   // unique
    "titel": "Spanish 4th grade – Animals", "fach": "spanisch", "stufe": "4th grade", "sprache": "es", "quellsprache": "en",
    "einheiten": [{"id": "farm", "titel": "Farm", "_note": "ignored",
      "karten": [{"frage": "the cow", "antwort": "la vaca", "emoji": "🐄"}, {"frage": "the dog", "antwort": "el perro"},]}]
  }]
}
```'''
    r = client.post("/api/parent/import/file", files={"file": ("answer.json", answer.encode())}, headers=ph)
    assert r.status_code == 200, r.text
    assert r.json()["drafts"][0]["id"] == "spanish-4-animals"


def test_pack_export_explains_itself_and_imports_again(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Mama", "pin": "4321"}).json()["parent_token"]}
    pid = next(p.id for p in client.app.state.fq.packs.all() if "id" in (client.app.state.fq.packs.raw(p.id) or {}))
    doc = client.get(f"/api/parent/packs/{pid}/export?format=json", headers=ph).json()
    assert doc["_format"] == "family-quest-pack/1" and doc["_field_guide"] and doc["pakete"][0]["id"] == pid
    every = client.get("/api/parent/packs/export", headers=ph).json()
    assert every["_ai_instructions"] and len(every["pakete"]) >= 1
    r = client.post("/api/parent/import/file", files={"file": ("x.json", json.dumps(doc).encode())}, headers=ph)
    assert r.status_code == 200, r.text


def test_quiz_export_round_trip(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    tpl = client.get("/api/ai-template/quiz").text
    qid = client.post("/api/community/quizzes/import", json={"text": tpl}, headers=hm).json()["ids"][0]
    fq = client.app.state.fq
    before = json.loads(fq.db.val("SELECT questions FROM quiz WHERE id=?", qid))
    r = client.get(f"/api/community/quizzes/{qid}/export", headers=hm)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    doc = r.json()
    assert doc["_format"] == "family-quest-quiz/1" and doc["_field_guide"]["question.image"]
    assert [q["type"] for q in doc["quizzes"][0]["questions"]] == ["choice"] * 6 + ["estimate", "map"]
    qid2 = client.post("/api/community/quizzes/import", json={"text": r.text}, headers=hm).json()["ids"][0]
    assert json.loads(fq.db.val("SELECT questions FROM quiz WHERE id=?", qid2)) == before          # nothing lost
    assert len(client.get("/api/community/quizzes/export", headers=hm).json()["quizzes"]) >= 2
    assert client.get("/api/community/quizzes/99999/export", headers=hm).status_code == 400
    # several at once, and errors with a clear message
    bad = {"title": "Bad", "questions": [{"type": "choice", "question": "?", "answers": ["only one"], "correct": 0}]}
    r = client.post("/api/community/quizzes/import", json={"text": json.dumps(bad)}, headers=hm)
    assert r.status_code == 400 and "Bad" in r.json()["detail"]
    assert client.post("/api/community/quizzes/import", json={"text": "no json here"}, headers=hm).status_code == 400


def test_pictures_of_questions(client):
    import pytest
    from familyquest.community import CommunityError, clean_image
    assert clean_image({"flag": "ch"}) == {"flag": "CH"} and clean_image({"flag": "XX"}) is None
    assert clean_image({"geo": "canton", "id": "ZH", "mode": "arms"})["mode"] == "arms"
    assert clean_image({"emoji": "🦒"}) == {"emoji": "🦒"}
    assert clean_image({"svg": "<svg viewBox='0 0 1 1'/>"})["svg"]
    with pytest.raises(CommunityError):
        clean_image({"svg": "<script>alert(1)</script>"})
    with pytest.raises(CommunityError):
        clean_image({"svg": "<svg>" + "x" * 40000 + "</svg>"})
