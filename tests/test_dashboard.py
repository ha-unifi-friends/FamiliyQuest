from test_api import setup_family


def test_kiosk_dashboard(client):
    ph, mia, leo = setup_family(client)
    assert client.get("/api/dashboard?key=x").status_code == 403                      # off
    c = client.put("/api/parent/dashboard", json={"enabled": True, "widgets": ["clock", "weather", "coins", "learning", "crown", "chores"]},
                   headers=ph).json()
    assert c["enabled"] and len(c["key"]) > 16
    assert client.get("/api/dashboard?key=wrong").status_code == 403
    client.post(f"/api/parent/weather/{mia}", json={"level": "storm"}, headers=ph)
    client.post(f"/api/parent/profiles/{mia}/crown", json={"on": True}, headers=ph)
    d = client.get(f"/api/dashboard?key={c['key']}").json()
    k = {x["name"]: x for x in d["kids"]}
    assert set(k) == {"Mia", "Leo"} and k["Mia"]["weather"]["icon"] == "⛈️" and k["Mia"]["crown"]
    assert k["Mia"]["balances"][0]["value"] == -10 and "learning" in k["Mia"]
    assert "mood" not in str(d) and "pin" not in str(d).lower()                      # nothing private
    # only chosen children and content
    c2 = client.put("/api/parent/dashboard", json={"kids": [leo], "widgets": ["clock"]}, headers=ph).json()
    d = client.get(f"/api/dashboard?key={c2['key']}").json()
    assert [x["name"] for x in d["kids"]] == ["Leo"] and "weather" not in d["kids"][0] and not d["kids"][0]["crown"]
    # a new key locks out the old link
    new = client.post("/api/parent/dashboard/key", headers=ph).json()["key"]
    assert client.get(f"/api/dashboard?key={c2['key']}").status_code == 403 and client.get(f"/api/dashboard?key={new}").status_code == 200
    assert client.put("/api/parent/dashboard", json={"calendars": ["light.x"]}, headers=ph).status_code == 400
    assert "Family Quest" in client.get("/dashboard").text
