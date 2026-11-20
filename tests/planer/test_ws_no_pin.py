"""No planner PIN in Family Quest: the signed-in profile is the identity.

A child adds and deletes its own to-dos without a PIN, is told «only parents» for parent actions (no PIN pad); a
parent – with a parent token, or a parent profile signed in in the app (PIN or Home Assistant) – never needs a PIN.
"""
import time

from test_api import setup_family


def _call(ws, mid, msg):
    ws.send_json({"id": mid, **msg})
    while True:
        r = ws.receive_json()
        if r.get("id") == mid and r.get("type") == "result":
            return r


def _me(ws):
    r = _call(ws, 900, {"type": "fq/me"})
    assert r["success"]
    return r["result"]


def _linked(client, ws):
    """The bridge links the profiles with planner persons – wait until the child has its person."""
    for _ in range(50):
        me = _me(ws)
        if me["person"]:
            return me
        time.sleep(0.1)
    raise AssertionError("child not linked with a planner person")


def _family(client):
    ph, mia, leo = setup_family(client)
    mia_tok = client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]
    papa = client.app.state.fq.db.val("SELECT id FROM profile WHERE role='parent'")
    papa_tok = client.post("/api/login", json={"profile_id": papa, "pin": "1234"}).json()["token"]
    bridge = client.app.state.fq.planer_host.bridge
    bridge.request()                                     # profiles → planner persons (the bridge links them)
    for _ in range(100):
        if bridge.person_of(mia):
            break
        time.sleep(0.1)
    assert bridge.person_of(mia)
    return ph, mia_tok, papa_tok


def test_kid_adds_and_deletes_own_todo_without_pin(client):
    _ph, mia_tok, _papa_tok = _family(client)
    planner = client.app.state.fq.planer_host.planner
    with client.websocket_connect(f"/api/planer/ws?token={mia_tok}") as ws:
        me = _linked(client, ws)
        assert me["parent"] is False
        r = _call(ws, 1, {"type": "family_planer/todo/save", "person_id": me["person"], "title": "Zimmer aufräumen"})
        assert r["success"], r
        tid = r["result"]["todo_id"]
        assert planner.data["todos"][tid]["person_id"] == me["person"]
        r = _call(ws, 2, {"type": "family_planer/todo/save", "todo_id": tid, "person_id": me["person"], "title": "Zimmer gründlich aufräumen"})
        assert r["success"], r
        r = _call(ws, 3, {"type": "family_planer/todo/delete", "todo_id": tid})
        assert r["success"], r
        assert tid not in planner.data["todos"]


def test_kid_cannot_do_parent_only_actions(client):
    _ph, mia_tok, _papa_tok = _family(client)
    planner = client.app.state.fq.planer_host.planner
    other = None
    with client.websocket_connect(f"/api/planer/ws?token={mia_tok}") as ws:
        me = _linked(client, ws)
        other = next(pid for pid in planner.data["persons"] if pid != me["person"])
        # a to-do for somebody else, or with points: a clear «no», never a PIN request
        r = _call(ws, 1, {"type": "family_planer/todo/save", "person_id": other, "title": "Abwaschen"})
        assert not r["success"] and r["error"]["code"] == "own_only"
        r = _call(ws, 2, {"type": "family_planer/todo/save", "person_id": me["person"], "title": "Velo putzen", "size": "l"})
        assert not r["success"] and r["error"]["code"] == "points_parent"
        for i, msg in enumerate([
            {"type": "family_planer/chore/save", "title": "Hund füttern"},
            {"type": "family_planer/settings/get"},
            {"type": "family_planer/settings/person", "data": {"name": "Lea", "color": "#ff0000", "role": "kid"}},
            {"type": "family_planer/theme/set", "theme": "dark"},
            {"type": "family_planer/reward/decide", "request_id": "x", "approve": True},
            {"type": "family_planer/points/adjust", "person_id": me["person"], "points": 100},
            {"type": "family_planer/sonder/list"},
            {"type": "family_planer/person/order", "order": [me["person"]]},
        ], start=10):
            r = _call(ws, i, msg)
            assert not r["success"] and r["error"]["code"] == "parent_only", (msg, r)
            assert "PIN" not in r["error"]["message"]
    assert "lea" not in planner.data["persons"]


def test_parent_without_pin_does_parent_actions_in_the_app(client):
    _ph, _mia_tok, papa_tok = _family(client)
    planner = client.app.state.fq.planer_host.planner
    with client.websocket_connect(f"/api/planer/ws?token={papa_tok}") as ws:        # the app login, no planner PIN
        assert _me(ws)["parent"] is True
        some = next(iter(planner.data["persons"]))
        r = _call(ws, 1, {"type": "family_planer/todo/save", "person_id": some, "title": "Steuern", "size": "l"})
        assert r["success"], r                                                         # points too, without a token
        assert planner.data["todos"][r["result"]["todo_id"]]["size"] == "l"
        r = _call(ws, 2, {"type": "family_planer/settings/get"})
        assert r["success"], r
        r = _call(ws, 3, {"type": "family_planer/sonder/list"})
        assert r["success"], r
        r = _call(ws, 4, {"type": "family_planer/chore/save", "title": "Hund füttern"})
        assert r["success"], r


def test_parent_area_token_needs_no_pin(client):
    ph, _mia_tok, _papa_tok = _family(client)
    with client.websocket_connect(f"/api/planer/ws?parent={ph['X-FQ-Parent']}") as ws:
        r = _call(ws, 1, {"type": "family_planer/settings/person", "data": {"name": "Lea", "color": "#ff0000", "role": "kid"}})
        assert r["success"], r                           # no token, no PIN


def test_parent_only_in_home_assistant(client):
    """«Parent area only in Home Assistant»: a parent in the app outside Home Assistant is told so (no PIN pad)."""
    _ph, _mia_tok, papa_tok = _family(client)
    client.app.state.fq.db.set_setting("parent_ha_only", True)
    with client.websocket_connect(f"/api/planer/ws?token={papa_tok}") as ws:
        assert _me(ws)["parent"] is False
        r = _call(ws, 1, {"type": "family_planer/settings/get"})
        assert not r["success"] and r["error"]["code"] == "parent_network"
