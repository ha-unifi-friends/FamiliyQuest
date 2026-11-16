"""Shopping lists of Home Assistant (Bring!) offered for the planner."""
from test_api import setup_family


class FakeHA:
    connected = True

    def todo_lists(self):
        return [{"entity_id": "todo.shopping_list", "name": "Shopping List", "platform": "shopping_list", "count": "2"},
                {"entity_id": "todo.zuhause", "name": "Zuhause", "platform": "bring", "count": "5"}]


def test_bring_lists_are_offered(client):
    ph, _, _ = setup_family(client)
    assert client.get("/api/planer/shopping", headers=ph).json() == {"ha": False, "lists": []}
    client.app.state.fq.ha = FakeHA()
    r = client.get("/api/planer/shopping", headers=ph).json()
    assert r["ha"] and [x["entity_id"] for x in r["lists"]] == ["todo.zuhause", "todo.shopping_list"]   # Bring! first
    assert r["lists"][0]["bring"] and not r["lists"][0]["linked"]
    assert client.post("/api/planer/shopping", json={"entity": "todo.nope"}, headers=ph).status_code in (400, 404)
    if client.app.state.fq.planer_host:
        assert client.post("/api/planer/shopping", json={"entity": "todo.zuhause"}, headers=ph).json()["ok"]
        assert client.get("/api/planer/shopping", headers=ph).json()["lists"][0]["linked"]
        lst = [x for x in client.app.state.fq.planer_host.planner.data["lists"].values() if x["entity"] == "todo.zuhause"][0]
        assert lst["name"] == "Zuhause" and lst["icon"] == "mdi:cart"
    client.app.state.fq.ha = None
