"""Templates for an AI (learning packs, quizzes) and importing what the AI answers."""
import json

from familyquest.jsonish import loads
from test_api import setup_family


def test_json_as_ais_write_it():
    assert loads('{"a": 1}') == {"a": 1}
    text = 'Here is your pack:\n```json\n{\n  "a": [1, 2,], // two numbers\n  /* a note */ "b": "x // not a comment"\n}\n```\nHave fun!'
    assert loads(text) == {"a": [1, 2], "b": "x // not a comment"}


def test_template_download(client):
    for kind in ("pack", "quiz"):
        r = client.get(f"/api/ai-template/{kind}")
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        assert "Instructions for the AI" in r.text and "only the JSON" in r.text
    assert client.get("/api/ai-template/nope").status_code == 404


def test_pack_from_an_ai_answer(client):
    ph = {"X-FQ-Parent": client.post("/api/setup", json={"name": "Mama", "pin": "4321"}).json()["parent_token"]}
    answer = '''Sure! ```json
{
  "id": "spanish-4-animals",   // unique
  "titel": "Spanish 4th grade – Animals",
  "fach": "spanisch", "stufe": "4th grade", "sprache": "es", "quellsprache": "en", "privat": true,
  "einheiten": [
    {"id": "farm", "titel": "Farm", "icon": "🐄",
     "karten": [
       {"frage": "the cow", "antwort": "la vaca", "emoji": "🐄"},
       {"frage": "the dog", "antwort": "el perro", "auch": ["perro"]},
       {"frage": "the cat", "antwort": "el gato", "satz": "El ___ duerme.",},
     ]}
  ]
}
```'''
    r = client.post("/api/parent/import/file", files={"file": ("answer.json", answer.encode())}, headers=ph)
    assert r.status_code == 200, r.text
    d = r.json()["drafts"][0]
    assert d["id"] == "spanish-4-animals"


def test_quiz_from_an_ai_answer(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    quiz = {"title": "Animals of the Alps", "questions": [
        {"type": "choice", "question": "Which animal whistles?", "answers": ["Marmot", "Ibex", "Chamois"], "correct": 0, "seconds": 15},
        {"type": "choice", "question": "King of the birds?", "answers": ["Sparrow", "Golden eagle"], "correct": "Golden eagle"},
        {"type": "estimate", "question": "Weight of an ibex?", "answer": 100, "min": 0, "max": 300, "unit": "kg"},
        {"type": "map", "question": "Where is the Matterhorn?", "lat": 45.98, "lon": 7.66, "map": "ch", "label": "Matterhorn"}]}
    text = "```json\n" + json.dumps(quiz) + "\n```"
    r = client.post("/api/community/quizzes/import", json={"text": text}, headers=hm)
    assert r.status_code == 200, r.text
    qid = r.json()["ids"][0]
    q = next(x for x in client.get("/api/community/quizzes", headers=hm).json() if x["id"] == qid)
    assert q["title"] == "Animals of the Alps"
    qs = json.loads(client.app.state.fq.db.val("SELECT questions FROM quiz WHERE id=?", qid))
    assert qs[0]["a"] == ["Marmot", "Ibex", "Chamois"] and qs[0]["c"] == 0 and qs[0]["t"] == 15
    assert qs[1]["c"] == 1 and qs[2]["kind"] == "estimate" and qs[2]["unit"] == "kg" and qs[3]["kind"] == "pin" and qs[3]["map"] == "ch"
    # several at once, and errors with a clear message
    r = client.post("/api/community/quizzes/import", json={"text": json.dumps([quiz, {**quiz, "title": "Second"}])}, headers=hm)
    assert len(r.json()["ids"]) == 2
    bad = {"title": "Bad", "questions": [{"type": "choice", "question": "?", "answers": ["only one"], "correct": 0}]}
    r = client.post("/api/community/quizzes/import", json={"text": json.dumps(bad)}, headers=hm)
    assert r.status_code == 400 and "Bad" in r.json()["detail"]
    assert client.post("/api/community/quizzes/import", json={"text": "no json here"}, headers=hm).status_code == 400


def test_the_examples_in_the_templates_import():
    import re
    from pathlib import Path
    from familyquest.community import Community, quiz_question
    from familyquest.packs.loader import parse_json
    root = Path(__file__).resolve().parent.parent / "family_quest/app/familyquest/ai_templates"
    pack = re.search(r"```\n(\{.*?\})\n```", (root / "pack.md").read_text(), re.S).group(1)
    assert parse_json(pack)[0].id == "french-5-unit-3"
    quiz = loads(re.search(r"```\n(\{.*?\})\n```", (root / "quiz.md").read_text(), re.S).group(1))
    assert len(Community.clean_questions([quiz_question(q) for q in quiz["questions"]])) == 3
