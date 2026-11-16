"""Wichteln: random drawing with rules – everybody sees only whom they give to."""
import random

import pytest

from familyquest.community import CommunityError
from familyquest.wichteln import draw
from test_api import setup_family


def _people(parents, kids):
    return [{"id": i, "role": "parent"} for i in range(parents)] + [{"id": 100 + i, "role": "kid"} for i in range(kids)]


def test_draw_respects_rules():
    for seed in range(50):
        ppl = _people(2, 3)
        role = {p["id"]: p["role"] for p in ppl}
        pairs = draw(ppl, no_parent_pairs=True, no_kid_pairs=False, rng=random.Random(seed))
        assert sorted(pairs) == sorted(pairs.values()) == sorted(role)
        assert all(a != b for a, b in pairs.items())
        assert not any(role[a] == role[b] == "parent" for a, b in pairs.items())
    pairs = draw(_people(2, 2), no_parent_pairs=True, no_kid_pairs=True, rng=random.Random(1))
    assert all((a < 100) != (b < 100) for a, b in pairs.items())


def test_draw_impossible():
    with pytest.raises(CommunityError):
        draw(_people(1, 3), no_kid_pairs=True)          # three children, one parent: the children would need each other


def test_wichteln_api(client):
    ph, mia, leo = setup_family(client)
    papa = next(p["id"] for p in client.get("/api/profiles").json() if p["name"] == "Papa")
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    hp = {"X-FQ-Token": client.post("/api/login", json={"profile_id": papa, "pin": "1234"}).json()["token"]}
    d = client.get("/api/community/wichteln", headers=hm).json()
    assert d["items"] == [] and {m["id"] for m in d["members"]} == {mia, leo, papa}
    assert client.post("/api/community/wichteln", json={"title": "", "participants": [mia, leo]}, headers=hm).status_code == 400
    assert client.post("/api/community/wichteln", json={"title": "X", "participants": [mia]}, headers=hm).status_code == 400
    assert client.post("/api/community/wichteln", json={"title": "X", "participants": [mia, leo, papa], "no_kid_pairs": True},
                       headers=hm).status_code == 400                       # two kids, one parent: impossible
    r = client.post("/api/community/wichteln", json={"title": "Weihnachten", "participants": [mia, leo, papa]}, headers=hm)
    assert r.status_code == 200, r.text
    seen = {}
    for who, h in ((mia, hm), (leo, hl), (papa, hp)):
        items = client.get("/api/community/wichteln", headers=h).json()["items"]
        w = items[0]
        assert w["title"] == "Weihnachten" and "pairs" not in w and len(w["people"]) == 3
        assert w["mine"] and w["mine"]["id"] != who
        seen[who] = w["mine"]["id"]
    assert sorted(seen.values()) == sorted(seen)
    wid = w["id"]
    # Leo neither made it nor is a parent
    assert client.delete(f"/api/community/wichteln/{wid}", headers=hl).status_code == 400
    assert client.delete(f"/api/community/wichteln/{wid}", headers=hp).status_code == 200
    assert client.get("/api/community/wichteln", headers=hm).json()["items"] == []


class FakePlaner:
    def __init__(self):
        self.todos, self.n = {}, 0

    def add_todo(self, pid, title):
        self.n += 1
        self.todos[f"t{self.n}"] = {"pid": pid, "title": title, "done": False}
        return f"t{self.n}"

    def todo_done(self, tid):
        return self.todos[tid]["done"] if tid in self.todos else None

    def set_todo(self, tid, done):
        self.todos[tid]["done"] = done

    def delete_todo(self, tid):
        self.todos.pop(tid, None)


def test_wichteln_date_gives_todos(client):
    ph, mia, leo = setup_family(client)
    fq = client.app.state.fq
    fp = FakePlaner()
    fq.wichteln.planer = lambda: fp
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    try:
        assert client.post("/api/community/wichteln", json={"title": "X", "participants": [mia, leo], "due": "kein"},
                           headers=hm).status_code == 400
        client.post("/api/community/wichteln", json={"title": "Weihnachten", "participants": [mia, leo], "due": "2026-12-24"}, headers=hm)
        assert sorted(t["pid"] for t in fp.todos.values()) == sorted([mia, leo])
        # the to-do never tells whom you give to
        assert all(t["title"] == "🎁 Wichteln: Weihnachten · 24.12." for t in fp.todos.values())
        w = client.get("/api/community/wichteln", headers=hm).json()["items"][0]
        assert w["due"] == "2026-12-24" and w["done"] is False
        client.post(f"/api/community/wichteln/{w['id']}/done", json={"done": True}, headers=hm)
        assert client.get("/api/community/wichteln", headers=hm).json()["items"][0]["done"] is True
        assert client.get("/api/community/wichteln", headers=hl).json()["items"][0]["done"] is False
        # ticked off in the planner counts as well
        leo_tid = next(k for k, t in fp.todos.items() if t["pid"] == leo)
        fp.todos[leo_tid]["done"] = True
        assert client.get("/api/community/wichteln", headers=hl).json()["items"][0]["done"] is True
        client.delete(f"/api/community/wichteln/{w['id']}", headers=hm)
        assert fp.todos == {}
    finally:
        fq.wichteln.planer = lambda: fq.planer_host
