"""💡 Code Workshop (codelab.py, web/codelab.js): program validation (size, depth, unknown blocks), the puzzles (every
level solvable with its reference solution, the grid rules, ⭐ and rewards paid once), privacy and visibility of own
programs like the books, remix, learning time and the dev channel (DEV_FEATURES) – plus the JavaScript engine in node:
loops, if, events, messages, runaway protection and the same puzzle results as the server."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from familyquest import codelab as CL
from familyquest.community import CommunityError
from test_api import setup_family
from websrc import parent_js

pytestmark = pytest.mark.dev_channel
WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"


def _logins(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    return ph, hm, hl, mia, leo


def B(op, args=None, body=None, els=None):
    return CL.expand([op, args or {}] + ([body] if body is not None or els is not None else []) + ([els] if els is not None else []))


def prog(*scripts, sprites=1):
    return {"stage": {"backdrops": ["forest"], "bd": 0},
            "sprites": [{"id": f"s{i + 1}", "name": f"S{i + 1}", "costumes": [{"k": "lib", "v": "fox-1"}],
                         "scripts": list(scripts) if i == 0 else []} for i in range(sprites)]}


# ---------------------------------------------------------------- validation
def test_clean_program_keeps_valid_programs_and_fixes_slots():
    p = prog(B("ev_start", {}, [["repeat", {"n": "4"}, [["move", {"n": 10}], ["turn_r", {"deg": {"op": "random", "args": {"a": 1, "b": 9}}}]]],
                                ["if", {"cond": ["touching", {"what": "s2"}]}, [["say", {"text": "Hi " * 100, "secs": 2}]]]]), sprites=2)
    out = CL.clean_program(p)
    s = out["sprites"][0]
    rep = s["scripts"][0]["body"][0]
    assert rep["op"] == "repeat" and rep["args"]["n"] == 4 and rep["body"][1]["args"]["deg"] == {"op": "random", "args": {"a": 1, "b": 9}}
    say = s["scripts"][0]["body"][1]["body"][0]
    assert len(say["args"]["text"]) == CL.TEXT
    assert s["scripts"][0]["body"][1]["args"]["cond"] == {"op": "touching", "args": {"what": "s2"}}
    assert len({b["id"] for b in [s["scripts"][0], rep, *rep["body"]]}) == 4           # every block got an own id
    # wrong values: sanitised (unknown sprite → edge, key → right, numbers clamped, costume of a library sprite that does not exist)
    p = prog(B("ev_key", {"key": "space"}, [["goto", {"to": "s9"}], ["if", {"cond": ["touching", {"what": "nobody"}]}, []]]))
    p["sprites"][0].update(x=9999, size=-5, rot="spin", costumes=[{"k": "lib", "v": "unicorn-1"}, {"k": "lib", "v": "cat-9"}])
    s = CL.clean_program(p)["sprites"][0]
    assert s["scripts"][0]["args"]["key"] == "right" and s["scripts"][0]["body"][0]["args"]["to"] == "_random"
    assert s["scripts"][0]["body"][1]["args"]["cond"]["args"]["what"] == "_edge"
    assert s["x"] == 240 and s["size"] == 5 and s["rot"] == "all" and s["costumes"] == [{"k": "lib", "v": "ball-1"}]
    # own drawings are cleaned like the pictures of the books
    p = prog()
    p["sprites"][0]["costumes"] = [{"k": "svg", "v": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><script>alert(1)</script>"
                                                    "<circle cx='100' cy='100' r='50' fill='red' onclick='x()'/></svg>"}]
    p["stage"]["backdrops"] = ["nowhere", "hall", {"k": "svg", "v": "<svg><foreignObject/></svg>"}]
    out = CL.clean_program(p)
    svg = out["sprites"][0]["costumes"][0]["v"]
    assert "script" not in svg and "onclick" not in svg and "circle" in svg
    assert out["stage"]["backdrops"][0] == "hall"


@pytest.mark.parametrize("bad", [
    prog(B("ev_start", {}, [["teleport", {}]])),                                     # unknown block
    prog(B("ev_start", {}, [["blocked"]])),                                          # a reporter as a statement
    prog(B("ev_start", {}, [["ev_tap", {}, []]])),                                   # a hat inside a script
    prog(B("ev_start", {}, [["move", {"n": ["touching", {"what": "_edge"}]}]])),     # a condition in a number slot
    prog(B("move", {"n": 3})),                                                       # a script without an event
    prog(B("ev_start", {}, [["move", {"n": ["blocked"]}]])),                         # the puzzle block in a free program
])
def test_clean_program_refuses_unknown_and_misplaced_blocks(bad):
    with pytest.raises(CommunityError):
        CL.clean_program(bad)


def test_clean_program_limits_size_and_depth():
    deep = [["move", {"n": 1}]]
    for _ in range(CL.MAX_DEPTH + 1):
        deep = [["repeat", {"n": 2}, deep]]
    with pytest.raises(CommunityError, match="nested too deeply"):
        CL.clean_program(prog(B("ev_start", {}, deep)))
    ok = [["move", {"n": 1}]]
    for _ in range(CL.MAX_DEPTH - 2):
        ok = [["repeat", {"n": 2}, ok]]
    CL.clean_program(prog(B("ev_start", {}, ok)))
    with pytest.raises(CommunityError, match="at most 800 blocks"):
        CL.clean_program(prog(B("ev_start", {}, [["move", {"n": 1}]] * (CL.MAX_BLOCKS + 1))))
    with pytest.raises(CommunityError, match="12 sprites"):
        CL.clean_program(prog(sprites=CL.MAX_SPRITES + 1))
    big = prog(sprites=6)                       # 6 sprites with 8 large own drawings each: too much data
    art = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>" + ("<path d='M0 0 " + "L1 1 " * 1100 + "' fill='red'/>") * 3
           + "</svg>")
    assert len(CL._costume({"k": "svg", "v": art})["v"]) > 16000
    for sp in big["sprites"]:
        sp["costumes"] = [{"k": "svg", "v": art}] * 8
    with pytest.raises(CommunityError, match="remove a drawing"):
        CL.clean_program(big)
    assert CL.count_blocks(CL.clean_program(prog(B("ev_start", {}, [["repeat", {}, [["move"], ["move"]]]])))["sprites"][0]["scripts"]) == 3


# ---------------------------------------------------------------- puzzles
def _scripts(lv, compact):
    return CL.clean_scripts([CL.expand(s) for s in compact], ops=CL.level_ops(lv), sprites={"s1"})


def test_every_level_is_solvable_with_three_stars():
    lv = CL.levels()
    assert len(lv) == 15 and [x["world"] for x in lv] == [1] * 5 + [2] * 5 + [3] * 5
    for x in lv:
        sc = _scripts(x, x["solution"])
        n = sum(CL.count_blocks(s["body"]) for s in sc)
        assert CL.simulate(x, sc, x.get("solution_inputs")) == "win", x["id"]
        assert CL.stars_for(x, n) == 3 and (not x["max"] or n <= x["max"]), x["id"]
        assert x["star"] != x["fox"][:2] and tuple(x["star"]) not in {tuple(s) for s in x["stones"]}
        assert all(op in CL.OPS for op in CL.level_ops(x)) and x["title"] and x["hint"]


def test_grid_rules():
    lv = CL.level("1-3")                    # fox 0/2 → star 5/2, a stone on 3/2
    assert CL.simulate(lv, _scripts(lv, [["ev_start", [["move", {"n": 5}]]]])) == "stone"
    assert CL.simulate(lv, _scripts(lv, [["ev_start", [["turn_r", {"deg": 90}], ["move", {"n": 9}]]]])) == "edge"
    assert CL.simulate(lv, _scripts(lv, [["ev_start", [["move", {"n": 1}]]]])) == "short"
    assert CL.simulate(lv, _scripts(lv, [["ev_start", [["move", {"n": -1}]]]])) == "edge"       # backwards out of the map
    l2 = CL.level("2-5")
    assert CL.simulate(l2, _scripts(l2, [["ev_start", [["forever", [["turn_r", {"deg": 90}]]]]]])) == "forever"
    l3 = CL.level("3-5")                    # turning right goes in circles here
    assert CL.simulate(l3, _scripts(l3, CL.level("3-3")["solution"])) == "forever"
    l4 = CL.level("3-2")                    # arrows: the same program, a path into a stone
    assert CL.simulate(l4, _scripts(l4, l4["solution"]), ["key:right"] * 3) == "stone"
    assert CL.simulate(l4, _scripts(l4, l4["solution"]), ["key:up"] * 9) == "edge"
    assert CL.simulate(l4, _scripts(l4, l4["solution"]), []) == "short"
    l5 = CL.level("3-1")
    assert CL.simulate(l5, _scripts(l5, l5["solution"])) == "short"                      # nobody tapped the fox
    with pytest.raises(CommunityError):                                                 # a block the level does not have
        _scripts(lv, [["ev_start", [["repeat", {"n": 3}, [["move", {"n": 1}]]]]]])


def test_level_progress_and_reward_once(client):
    ph, hm, hl, mia, leo = _logins(client)
    fq = client.app.state.fq
    home = client.get("/api/codelab", headers=hm).json()
    assert [x["open"] for x in home["levels"][:2]] == [True, False] and home["reward"] == {"xp": 10, "coins": 0}
    lv = client.get("/api/codelab/levels/1-1", headers=hm).json()
    assert "solution" not in lv and lv["start"][0]["op"] == "ev_start" and lv["next"] == "1-2"
    long = [CL.expand(["ev_start", [["move", {"n": 1}]] * 3])]
    r = client.post("/api/codelab/levels/1-1/solve", json={"scripts": long}, headers=hm).json()
    assert r["ok"] and r["stars"] == 2 and r["first"] and r["reward"] == {"xp": 10}
    xp = lambda: fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account='xp' AND event='codelab_level'", mia)
    assert xp() == 10
    best = [CL.expand(["ev_start", [["move", {"n": 3}]]])]
    r = client.post("/api/codelab/levels/1-1/solve", json={"scripts": best}, headers=hm).json()
    assert r["ok"] and r["stars"] == 3 and not r["first"] and r["reward"] is None and xp() == 10
    r = client.post("/api/codelab/levels/1-1/solve", json={"scripts": long}, headers=hm).json()
    assert r["best"] == 3                                                        # the best result is kept
    assert client.post("/api/codelab/levels/1-1/solve", json={"scripts": [CL.expand(["ev_start", [["move", {"n": 1}]]])]},
                       headers=hm).json() == {"ok": False, "why": "short"}
    home = client.get("/api/codelab", headers=hm).json()
    assert home["levels"][0]["stars"] == 3 and home["levels"][1]["open"]
    # the try so far is kept per child
    client.put("/api/codelab/levels/1-2", json={"scripts": best}, headers=hm)
    assert client.get("/api/codelab/levels/1-2", headers=hm).json()["program"][0]["body"][0]["args"]["n"] == 3
    assert client.get("/api/codelab/levels/1-2", headers=hl).json()["program"] is None
    # the block limit and the blocks of the level are checked on the server too
    too_many = [CL.expand(["ev_start", [["repeat", {"n": 7}, [["move", {"n": 1}]]], ["turn_r", {"deg": 90}], ["turn_l", {"deg": 90}]]])]
    assert client.post("/api/codelab/levels/2-1/solve", json={"scripts": too_many}, headers=hm).status_code == 400
    assert client.post("/api/codelab/levels/1-1/solve", json={"scripts": [CL.expand(["ev_start", [["say", {"text": "x", "secs": 1}]]])]},
                       headers=hm).status_code == 400
    # coins as reward (parent setting) – for a new first solve only
    assert client.put("/api/codelab/settings", json={"level_coins": 5}, headers=ph).json()["level_coins"] == 5
    l2 = CL.level("1-2")
    r = client.post("/api/codelab/levels/1-2/solve", json={"scripts": [CL.expand(s) for s in l2["solution"]]}, headers=hm).json()
    assert r["reward"] == {"xp": 10, "coins": 5}
    ov = client.get("/api/codelab/overview", headers=ph).json()
    m = next(k for k in ov["kids"] if k["id"] == mia)
    assert m["solved"] == 2 and m["stars"] == 6 and m["levels"]["1-1"] == 3 and ov["total"] == 15
    assert client.get("/api/codelab/overview", headers=hm).status_code == 401


def test_interactive_levels_replay_the_inputs(client):
    ph, hm, hl, mia, leo = _logins(client)
    lv = CL.level("3-2")
    sc = [CL.expand(s) for s in lv["solution"]]
    assert not client.post("/api/codelab/levels/3-2/solve", json={"scripts": sc, "inputs": []}, headers=hm).json()["ok"]
    r = client.post("/api/codelab/levels/3-2/solve", json={"scripts": sc, "inputs": lv["solution_inputs"]}, headers=hm).json()
    assert r["ok"] and r["stars"] == 3


# ---------------------------------------------------------------- own programs: privacy, visibility, remix
def test_privacy_and_visibility_like_the_books(client):
    ph, hm, hl, mia, leo = _logins(client)
    data = prog(B("ev_start", {}, [["say", {"text": "secret", "secs": 1}]]))
    pid = client.post("/api/codelab/projects", json={"title": "Secret", "data": data, "visibility": "me"}, headers=hm).json()["id"]
    assert client.post("/api/codelab/projects", json={"title": " ", "data": data}, headers=hm).status_code == 400
    papp = {"X-FQ-Token": client.post("/api/login", json={"profile_id": 1, "pin": "1234"}).json()["token"]}
    # private: nobody else – parents neither (app or parent area); in the parent area only that it exists
    for h in (hl, papp, ph):
        assert client.get(f"/api/codelab/projects/{pid}", headers=h).status_code == 400
        assert client.delete(f"/api/codelab/projects/{pid}", headers=h).status_code == 400
        assert client.post(f"/api/codelab/projects/{pid}/remix", headers=h).status_code == 400
    assert pid not in [p["id"] for p in client.get("/api/codelab/projects", headers=hl).json()["others"]]
    ov = client.get("/api/codelab/projects", headers=ph).json()
    assert ov["private"] == [{"id": pid, "private": True, "author": ov["private"][0]["author"], "blocks": 2,
                              "created_at": ov["private"][0]["created_at"], "updated_at": ov["private"][0]["updated_at"]}]
    assert "secret" not in json.dumps(client.get("/api/codelab/overview", headers=ph).json())
    assert "Secret" not in json.dumps(client.get("/api/codelab/overview", headers=ph).json())
    # «kids»: the other children; parents only in the parent area
    assert client.put(f"/api/codelab/projects/{pid}", json={"visibility": "kids"}, headers=hm).json()["visibility"] == "kids"
    assert client.get(f"/api/codelab/projects/{pid}", headers=hl).json()["edit"] is False
    assert client.get(f"/api/codelab/projects/{pid}", headers=papp).status_code == 400
    assert client.get(f"/api/codelab/projects/{pid}", headers=ph).status_code == 200
    # «family»: everybody plays it; only the author changes it
    client.put(f"/api/codelab/projects/{pid}", json={"visibility": "family"}, headers=hm)
    got = client.get(f"/api/codelab/projects/{pid}", headers=papp).json()
    assert got["title"] == "Secret" and not got["edit"] and got["remove"]
    assert client.put(f"/api/codelab/projects/{pid}", json={"title": "Mine now"}, headers=hl).status_code == 400
    assert client.put(f"/api/codelab/projects/{pid}", json={"data": {"sprites": [{"scripts": [{"op": "nope"}]}]}}, headers=hm).status_code == 400
    # remix: an own copy of Leo, the original stays
    rid = client.post(f"/api/codelab/projects/{pid}/remix", headers=hl).json()["id"]
    r = client.get(f"/api/codelab/projects/{rid}", headers=hl).json()
    assert r["edit"] and r["mine"] and r["remix_of"] == pid and r["remix_title"] == "Secret" and r["title"] == "Secret (Remix)"
    assert r["data"]["sprites"][0]["scripts"][0]["body"][0]["args"]["text"] == "secret"
    assert client.put(f"/api/codelab/projects/{rid}", json={"title": "Leo's"}, headers=hl).status_code == 200
    assert client.get(f"/api/codelab/projects/{pid}", headers=hm).json()["title"] == "Secret"
    mine = client.get("/api/codelab", headers=hl).json()["projects"]
    assert [p["id"] for p in mine["mine"]] == [rid] and pid in [p["id"] for p in mine["others"]]
    # a parent removes a shared program (moderation), Leo cannot remove Mia's
    assert client.delete(f"/api/codelab/projects/{pid}", headers=hl).status_code == 400
    assert client.delete(f"/api/codelab/projects/{pid}", headers=ph).status_code == 200
    # a deleted profile takes its programs along
    client.app.state.fq.codelab.author_removed(leo)
    assert client.get(f"/api/codelab/projects/{rid}", headers=hl).status_code == 400


def test_svg_and_settings_per_child(client):
    ph, hm, hl, mia, leo = _logins(client)
    r = client.post("/api/codelab/svg", json={"svg": "<svg viewBox='0 0 200 200'><rect width='10' height='10' onload='x'/></svg>"}, headers=hm)
    assert r.status_code == 200 and "onload" not in r.json()["svg"]
    assert client.post("/api/codelab/svg", json={"svg": "hello"}, headers=hm).status_code == 400
    assert client.get("/api/me", headers=hm).json()["codelab"] is True
    client.put("/api/codelab/settings", json={"off": [leo]}, headers=ph)
    assert client.get("/api/me", headers=hl).json()["codelab"] is False
    assert client.get("/api/codelab", headers=hl).status_code == 400
    assert client.post("/api/codelab/projects", json={"title": "x", "data": prog()}, headers=hl).status_code == 400
    assert client.get("/api/codelab", headers=hm).status_code == 200
    assert client.put("/api/codelab/settings", json={"off": []}, headers=hm).status_code == 401


# ---------------------------------------------------------------- learning time
def test_time_in_the_workshop_is_learning_time(client):
    ph, hm, hl, mia, leo = _logins(client)
    fq = client.app.state.fq
    prof = fq.db.q1("SELECT * FROM profile WHERE id=?", mia)
    cl = fq.codelab
    cl.tick(prof, now=1000.0)                    # the first heartbeat books nothing
    cl.tick(prof, now=1030.0)                    # 30 s
    cl.tick(prof, now=1031.0)                    # too soon: nothing
    cl.tick(prof, now=5000.0)                    # a long pause: at most TICK_MAX
    assert fq.db.val("SELECT seconds FROM daily WHERE profile_id=?", mia) == 30 + CL.TICK_MAX
    assert fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=?", mia, default=0) == 0      # time only, no XP
    # the daily learning limit used up: puzzles and programs do not open (parents are never limited)
    st = json.loads(prof["settings"] or "{}")
    st["learn_limit"] = {"all": 1, "days": {}}
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps(st), mia)
    assert client.post("/api/codelab/tick", headers=hm).json() == {"learn_left": 0}
    r = client.get("/api/codelab/levels/1-1", headers=hm)
    assert r.status_code == 400 and "used up" in r.json()["detail"]
    assert client.get("/api/codelab", headers=hm).json()["learn_left"] == 0
    assert client.get("/api/codelab/levels/1-1", headers=hl).status_code == 200
    assert client.get("/api/codelab/levels/1-1", headers=ph).status_code == 200


# ---------------------------------------------------------------- the dev channel only (for now)
def test_hidden_outside_the_dev_channel(client, monkeypatch):
    from familyquest import channel
    ph, hm, hl, mia, leo = _logins(client)
    monkeypatch.setattr(channel, "_channel", "")
    assert not channel.feature_visible("codelab")
    assert client.get("/api/codelab", headers=hm).status_code == 404
    assert client.get("/api/codelab/overview", headers=ph).status_code == 404
    assert client.post("/api/codelab/tick", headers=hm).status_code == 404
    assert client.get("/api/me", headers=hm).json()["codelab"] is False
    assert client.get("/api/info").json()["codelab"] is False
    monkeypatch.setattr(channel, "_channel", "dev")
    assert client.get("/api/codelab", headers=hm).status_code == 200 and client.get("/api/info").json()["codelab"] is True


def test_the_app_shows_it_only_where_it_exists():
    kid = (WEB / "kid.js").read_text(encoding="utf-8")
    assert 'if (view === "codelab") return S.me.codelab ? codelabView() : go("courses");' in kid
    assert "me.codelab ? codelabTile() : null" in kid
    assert "P.info && P.info.codelab ? await codelabSection()" in parent_js()
    assert '<script src="codelab.js?v=__VERSION__"></script>' in (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "codelab.js").read_text(encoding="utf-8")
    for op in CL.OPS:                                                # the same blocks in the app and on the server
        assert f"\n  {op}: [" in js, op
    for key, (n, _) in CL.SPRITES.items():
        for i in range(1, n + 1):
            assert (WEB / "img" / "codelab" / f"{key}-{i}.svg").is_file()
    assert "eval(" not in js and "new Function" not in js


# ---------------------------------------------------------------- the JavaScript engine (node)
ENGINE_TEST = r"""
global.T = s => s;
const { CwEngine } = require(%(path)s);
const levels = %(levels)s;
const ids = l => { let n = 0; const walk = bs => bs.forEach(b => { b.id = "b" + (++n); walk(b.body || []); walk(b.else || []); }); walk(l); return l; };
const spr = (scripts, extra = {}) => ({ id: "s1", name: "A", costumes: [{ k: "lib", v: "fox-1" }], c: 0, x: 0, y: 0, dir: 90, size: 100, show: true, rot: "all", scripts: ids(scripts), ...extra });
const run = (eng, ms = 5000) => { let t = 0; eng.start(); while (t < ms && (eng.threads.length || eng.grid && !eng.ended)) { t += 16; eng.tick(t); if (eng.grid && !eng.threads.length && eng.ended) break; if (!eng.threads.length && !eng.grid) break; } return t; };
const out = {};
// loops: repeat 10 × move 10 → x 100; nested loops; if / else
{ const e = new CwEngine({ sprites: [spr([{ op: "ev_start", args: {}, body: [{ op: "repeat", args: { n: 10 }, body: [{ op: "move", args: { n: 10 } }] },
    { op: "repeat", args: { n: 3 }, body: [{ op: "repeat", args: { n: 2 }, body: [{ op: "change_y", args: { n: 1 } }] }] },
    { op: "if_else", args: { cond: { op: "gt", args: { a: 5, b: 3 } } }, body: [{ op: "turn_r", args: { deg: 90 } }], else: [{ op: "turn_l", args: { deg: 90 } }] },
    { op: "if", args: { cond: { op: "and", args: { a: { op: "lt", args: { a: 1, b: 2 } }, b: { op: "not", args: { a: { op: "eq", args: { a: 1, b: 1 } } } } } } }, body: [{ op: "hide", args: {} }] }] }])] });
  const frames = run(e) / 16; const s = e.sprites[0];
  out.loops = [Math.round(s.x), s.y, s.dir, s.show, frames >= 16]; }
// events: a message starts the scripts of another sprite; tap and keys
{ const a = spr([{ op: "ev_start", args: {}, body: [{ op: "broadcast", args: { msg: "Go" } }] }, { op: "ev_key", args: { key: "left" }, body: [{ op: "change_x", args: { n: -5 } }] }]);
  const b = spr([{ op: "ev_msg", args: { msg: "go" }, body: [{ op: "say", args: { text: "hi", secs: 0 } }, { op: "size_set", args: { n: 50 } }] },
                 { op: "ev_tap", args: {}, body: [{ op: "next_costume", args: {} }] }], { id: "s2", costumes: [{ k: "lib", v: "cat-1" }, { k: "lib", v: "cat-2" }] });
  const e = new CwEngine({ sprites: [a, b] }); run(e);
  e.on = true; e.trigger("key", "left"); e.trigger("tap", null, e.sprites[1]); for (let t = 6000; t < 6100; t += 16) e.tick(t);
  out.events = [e.sprites[1].size, e.sprites[1].say && e.sprites[1].say.text, e.sprites[0].x, e.sprites[1].c]; }
// wait and glide take their time; stop ends everything
{ const e = new CwEngine({ sprites: [spr([{ op: "ev_start", args: {}, body: [{ op: "wait", args: { secs: 1 } }, { op: "glide", args: { secs: 1, x: 100, y: 50 } }, { op: "stop", args: {} }, { op: "move", args: { n: 999 } }] }])] });
  const t = run(e); out.wait = [t >= 2000 && t < 2300, e.sprites[0].x, e.sprites[0].y, e.on]; }
// runaway: an endless loop without a pause never blocks a frame, and gets the hint; a huge repeat is spread over frames
{ const e = new CwEngine({ sprites: [spr([{ op: "ev_start", args: {}, body: [{ op: "forever", args: {}, body: [{ op: "change_x", args: { n: 0 } }] }] }])] });
  e.start(); const t0 = Date.now(); for (let t = 0; t < 6000 * 16; t += 16) e.tick(t);
  out.runaway = [e.notice, e.threads.length, Date.now() - t0 < 4000]; }
{ const e = new CwEngine({ sprites: [spr([{ op: "ev_start", args: {}, body: [{ op: "repeat", args: { n: 1e9 }, body: [] }] }])] });
  e.start(); const t0 = Date.now(); e.tick(16); out.bigloop = [e.threads.length, Date.now() - t0 < 500]; }
// puzzles: the same result as codelab.py simulate (the reference solutions, and the runaway stop)
out.levels = {};
for (const lv of levels) {
  for (const [name, scripts, inputs] of [["sol", lv.sol, lv.inputs], ["bad", lv.bad, lv.inputs]]) {
    let why = null;
    const e = new CwEngine({ sprites: [spr(JSON.parse(JSON.stringify(scripts)))] }, { grid: lv.level, onEnd: w => { why = w; } });
    e.start(); let t = 0;
    const todo = (inputs || []).slice();
    while (!why && t < 600000) {
      t += 16; e.tick(t);
      if (!e.busy() && todo.length) { const [k, a] = todo.shift().split(":"); k === "tap" ? e.trigger("tap", null, e.sprites[0]) : e.trigger("key", a); }
      else if (!why && !e.busy() && !todo.length && lv.level.inputs) { why = "short"; }
    }
    out.levels[lv.level.id + ":" + name] = why;
  }
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_javascript_engine():
    lv_data, expect = [], {}
    bad = {"default": [["ev_start", [["forever", [["turn_r", {"deg": 90}]]]]]]}
    for lv in CL.levels():
        b = bad["default"] if lv["inputs"] is None else lv["solution"]
        b_inputs = lv.get("solution_inputs")
        sol = [CL.expand(s) for s in lv["solution"]]
        badp = [CL.expand(s) for s in (bad["default"] if lv["inputs"] is None else [["ev_start", [["move", {"n": 1}]]]])]
        lv_data.append({"level": {k: lv[k] for k in ("id", "cols", "rows", "fox", "star", "stones", "inputs")}, "sol": sol, "bad": badp,
                        "inputs": b_inputs})
        for name, sc in (("sol", sol), ("bad", badp)):
            expect[lv["id"] + ":" + name] = CL.simulate(lv, CL.clean_scripts(sc, ops=CL.OPS.keys(), sprites={"s1"}), b_inputs)
        assert b is not None
    code = ENGINE_TEST % {"path": json.dumps(str(WEB / "codelab.js")), "levels": json.dumps(lv_data)}
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=120, check=True).stdout)
    assert out["loops"] == [100, 6, 180, True, True]
    assert out["events"] == [50, "hi", -5, 1]
    assert out["wait"] == [True, 100, 50, False]
    assert out["runaway"] == ["fast", 1, True]
    assert out["bigloop"] == [1, True]
    assert out["levels"] == expect
    assert all(v == "win" for k, v in expect.items() if k.endswith(":sol"))
    assert {v for k, v in expect.items() if k.endswith(":bad")} >= {"forever"}
