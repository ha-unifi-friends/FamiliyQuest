"""The planer websocket (Home Assistant message format) and its pass-throughs."""


def tokens(client):
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()
    return r["token"], r["parent_token"]


def test_websocket_subscribe_and_commands(client):
    kid, parent = tokens(client)
    with client.websocket_connect(f"/api/planer/ws?token={kid}") as ws:
        ws.send_json({"id": 1, "type": "family_planer/subscribe"})
        res = ws.receive_json()
        assert res == {"id": 1, "type": "result", "success": True, "result": None}
        ev = ws.receive_json()
        assert ev["id"] == 1 and ev["type"] == "event" and "persons" in ev["event"]
        # changes need the parent PIN – inside Family Quest that is the PIN of a Family Quest parent
        ws.send_json({"id": 2, "type": "family_planer/pin/unlock", "pin": "123456"})
        r = ws.receive_json()
        while r.get("id") != 2:
            r = ws.receive_json()
        assert not r["success"] and r["error"]["code"] == "pin_wrong"
        ws.send_json({"id": 3, "type": "family_planer/pin/unlock", "pin": "1234"})
        r = ws.receive_json()
        while r.get("id") != 3:
            r = ws.receive_json()
        assert r["success"]
        tok = r["result"]["token"]
        ws.send_json({"id": 4, "type": "family_planer/settings/person", "token": tok, "data": {"name": "Lea", "color": "#ff0000", "role": "kid"}})
        got_event = False
        while True:
            r = ws.receive_json()
            if r.get("id") == 1 and r["type"] == "event" and any(p.get("name") == "Lea" for p in (r["event"]["persons"].values() if isinstance(r["event"]["persons"], dict) else r["event"]["persons"])) :
                got_event = True
            if r.get("id") == 4:
                assert r["success"], r
                break
        ws.send_json({"id": 5, "type": "family_planer/unknown"})
        r = ws.receive_json()
        while r.get("id") != 5:
            r = ws.receive_json()
        assert not r["success"] and r["error"]["code"] == "unknown_command"
        ws.send_json({"id": 6, "type": "lovelace/config"})
        r = ws.receive_json()
        while r.get("id") != 6:
            r = ws.receive_json()
        assert r["success"] and r["result"] is None
    assert "lea" in client.app.state.fq.planer_host.planner.data["persons"]


def test_websocket_needs_login(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/planer/ws?token=bad") as ws:
            ws.receive_json()


def test_pass_throughs_are_limited(client):
    kid, _ = tokens(client)
    h = {"X-FQ-Token": kid}
    assert client.get("/api/planer/ha/states", headers=h).json() == []
    assert client.post("/api/planer/ha/service", json={"domain": "light", "service": "turn_on", "data": {}}, headers=h).status_code == 403
    assert client.get("/api/planer/ha/calendars/light.x?start=a&end=b", headers=h).status_code == 400
    assert client.get("/api/planer/ha/states").status_code == 401
