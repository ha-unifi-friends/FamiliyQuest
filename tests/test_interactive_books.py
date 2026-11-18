"""Interactive books (stories.py): pages that simply go on (`next`, «Next ▶»), a few branch points, several happy
endings, ◀ back to the page read before (history on the server), the file format with `next`, old books unchanged."""
import json

from familyquest import stories as S
from test_stories import BOOK, _book, _logins, codes, end, scene


def page(pid, text, nxt, give=None):
    return {"id": pid, "kind": "scene", "text": text, "pic": {"k": "emoji", "v": "🦊"}, "give": give, "next": nxt, "choices": []}


# 1 → 2 (gives a balloon) → 3: branch A → 4 → good 6 · B → 5 → good 7 (both endings happy, no bad ending)
LINEAR = {"start": 1, "pages": [
    page(1, "Morning", 2), page(2, "Balloon", 3, give="🎈 Balloon"),
    scene(3, "Who comes?", ("Rabbits", 4, None), ("Bear", 5, None)),
    page(4, "Carrots", 6), page(5, "Honey", 7),
    end(6, "good", "Carrot cake"), end(7, "good", "Honey cake")]}


def test_clean_keeps_linear_pages_and_old_books():
    d = S.clean(LINEAR)
    assert S.linear(d["pages"][0]) and d["pages"][0]["next"] == 2 and d["pages"][0]["choices"] == []
    assert not S.linear(d["pages"][2]) and "next" not in d["pages"][2] and len(d["pages"][2]["choices"]) == 2
    assert S.check(d, "Fox") == [] and S.reachable(d) == {1, 2, 3, 4, 5, 6, 7}
    # a page with choices stays a branch point even if it also has «next»
    d = S.clean({"start": 1, "pages": [{**scene(1, "a", ("x", 2, None), ("y", 2, None)), "next": 2}, end(2)]})
    assert not S.linear(d["pages"][0]) and "next" not in d["pages"][0]
    # a target that is gone: no next page
    d = S.clean({"start": 1, "pages": [page(1, "a", 9), end(2)]})
    assert d["pages"][0]["next"] is None and S.linear(d["pages"][0])
    # books of older versions (only branch points) are unchanged and valid
    old = S.clean(BOOK)
    assert old == S.clean(json.loads(json.dumps(old))) and S.check(old, "Lion") == [] and not any(S.linear(p) for p in old["pages"])


def test_checker_for_linear_pages():
    c = codes(S.check(S.clean({"start": 1, "pages": [page(1, "a", None), end(2)]}), "T"))
    assert "no_next" in c and "unreachable" in c
    c = codes(S.check(S.clean({"start": 1, "pages": [page(1, "a", 1), end(2)]}), "T"))       # itself is no next page
    assert "no_next" in c
    # a loop of pages nobody gets out of
    d = S.clean({"start": 1, "pages": [scene(1, "a", ("x", 2, None), ("y", 4, None)), page(2, "b", 3), page(3, "c", 2), end(4)]})
    issues = S.check(d, "T")
    assert codes(issues) == ["no_way_out", "no_way_out"] and {i["page"] for i in issues} == {2, 3}
    assert issues[0]["msg"] == "Page {0}: from here no path leads to an ending"
    # only happy endings are fine, one ending is enough
    assert S.check(S.clean({"start": 1, "pages": [page(1, "a", 2), end(2)]}), "T") == []
    assert codes(S.check(S.clean({"start": 1, "pages": [page(1, "a", 2), end(2, "bad")]}), "T")) == ["no_good"]
    # a new book starts with one page that goes on
    assert S.linear(S.empty_book("adventure")["pages"][0])


def test_read_next_back_and_happy_endings(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, ed = _book(client, hm, LINEAR, "Fox")
    assert ed["issues"] == [] and client.post(f"/api/stories/{sid}/publish", headers=hm).json()["status"] == "live"
    r = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert r["page"]["id"] == 1 and r["page"]["linear"] and r["page"]["next"] and not r["back"] and r["step"] == 1
    assert client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).status_code == 400   # no choice here
    assert client.post(f"/api/stories/{sid}/read/back", headers=hl).status_code == 400                    # the first page
    r = client.post(f"/api/stories/{sid}/read/next", headers=hl).json()
    assert r["page"]["id"] == 2 and r["items"] == ["🎈 Balloon"] and r["back"] and r["step"] == 2
    r = client.post(f"/api/stories/{sid}/read/next", headers=hl).json()
    assert r["page"]["id"] == 3 and not r["page"]["linear"] and not r["page"]["next"] and len(r["page"]["choices"]) == 2
    assert client.post(f"/api/stories/{sid}/read/next", headers=hl).status_code == 400                    # a branch point
    # ◀ goes back to the page read before – with the backpack of then
    r = client.post(f"/api/stories/{sid}/read/back", headers=hl).json()
    assert r["page"]["id"] == 2 and r["step"] == 2
    r = client.post(f"/api/stories/{sid}/read/back", headers=hl).json()
    assert r["page"]["id"] == 1 and r["items"] == [] and not r["back"]
    for _ in range(2):
        client.post(f"/api/stories/{sid}/read/next", headers=hl)
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 1}, headers=hl).json()
    assert r["page"]["id"] == 5 and r["step"] == 4
    r = client.post(f"/api/stories/{sid}/read/next", headers=hl).json()
    assert r["page"]["kind"] == "good" and r["new_ending"] and r["found"] == 1 and r["endings"] == 2 and r["finished"] == 1
    # back from an ending: the ending stays found, the other happy ending is still to find
    r = client.post(f"/api/stories/{sid}/read/back", headers=hl).json()
    assert r["page"]["id"] == 5 and r["found"] == 1
    assert client.post(f"/api/stories/{sid}/read/back", headers=hl).json()["page"]["id"] == 3
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).json()
    r = client.post(f"/api/stories/{sid}/read/next", headers=hl).json()
    assert r["page"]["id"] == 6 and r["new_ending"] and r["found"] == 2 and r["finished"] == 2
    # the history is per reader and «read again» empties it
    assert client.get(f"/api/stories/{sid}/read", headers=hm).json()["step"] == 1
    r = client.post(f"/api/stories/{sid}/read/restart", headers=hl).json()
    assert r["page"]["id"] == 1 and not r["back"] and r["found"] == 2
    # a new version without the page read before: back skips it
    client.post(f"/api/stories/{sid}/read/next", headers=hl)
    client.post(f"/api/stories/{sid}/read/next", headers=hl)
    data = json.loads(json.dumps(LINEAR))
    data["pages"][0]["next"] = 3
    data["pages"].pop(1)
    client.put(f"/api/stories/{sid}", json={"data": data}, headers=hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    r = client.post(f"/api/stories/{sid}/read/back", headers=hl).json()
    assert r["page"]["id"] == 1 and not r["back"]


def test_old_books_read_as_before(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, ed = _book(client, hm)
    client.post(f"/api/stories/{sid}/publish", headers=hm)
    r = client.get(f"/api/stories/{sid}/read", headers=hl).json()
    assert not r["page"]["linear"] and len(r["page"]["choices"]) == 2
    r = client.post(f"/api/stories/{sid}/read/choose", json={"i": 0}, headers=hl).json()
    assert r["page"]["id"] == 2 and r["back"]
    r = client.post(f"/api/stories/{sid}/read/back", headers=hl).json()
    assert r["page"]["id"] == 1 and r["items"] == []


def test_export_import_with_next(client):
    ph, hm, hl, mia, leo = _logins(client)
    sid, _ = _book(client, hm, LINEAR, "Fox")
    doc = client.get(f"/api/stories/{sid}/export", headers=hm).json()
    pages = doc["books"][0]["pages"]
    assert pages[0]["next"] == "p2" and "choices" not in pages[0] and "next" not in pages[2] and len(pages[2]["choices"]) == 2
    assert "next" not in pages[5] and "choices" not in pages[5]
    [b] = S.import_books(json.dumps(doc))
    assert b["data"] == S.clean(LINEAR)
    # an AI answer with own ids, «next» on pages; old files (only choices) still come in
    ai = {"title": "Fox", "start": "a", "pages": [{"id": "a", "type": "scene", "text": "x", "next": "b"},
                                                 {"id": "b", "type": "good_ending", "text": "y"}]}
    [b] = S.import_books(json.dumps({"_format": S.STORY_FORMAT, "books": [ai]}))
    assert S.linear(b["data"]["pages"][0]) and b["data"]["pages"][0]["next"] == 2 and S.check(b["data"], b["title"]) == []
    old = S.story_document([S.export_book("Lion", "🦁", "en", S.clean(BOOK))])
    [b] = S.import_books(json.dumps(old))
    assert b["data"] == S.clean(BOOK)
    r = client.post("/api/stories/import", json={"text": json.dumps(doc)}, headers=hl)
    assert r.status_code == 200
    ed = client.get(f"/api/stories/{r.json()['ids'][0]}", headers=hl).json()
    assert ed["issues"] == [] and ed["data"]["pages"][0]["next"] == 2


def test_new_templates_in_every_language():
    for lang in S.LANGS:
        for key in ("princess", "fox"):
            t = S.template(key, lang)
            d = S.clean(t["data"])
            assert S.check(d, t["title"]) == [] and t["lang"] == lang
            assert [p["id"] for p in d["pages"] if p.get("choices")] == {"princess": [3, 9], "fox": [3, 7]}[key]
            assert all(p["kind"] == "good" for p in d["pages"] if p["kind"] != "scene")
            assert all(p["bg"] in S.BACKGROUNDS and p["pic"]["k"] == "emoji" for p in d["pages"])
    # natively written – not the English text
    assert S.template("princess", "de-CH")["title"] != S.template("princess", "de-DE")["title"] != S.template("princess", "en")["title"]
    assert S.template("fox", "fr-FR")["data"]["pages"][0]["text"].startswith("Le petit renard")
