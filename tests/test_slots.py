"""Game corner: the one-armed bandit – bought once, 1 coin a spin, 3 spins a day, drawn on the server."""
from familyquest import slots
from test_api import setup_family


def login(client, pid, pin="1111"):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, "pin": pin}).json()["token"]}


def test_pay_table_returns_a_bit_more_than_a_casino():
    assert 0.96 < slots.expected_return() < 1.0
    assert slots.payout(["seven"] * 3) == 100 and slots.payout(["cherry", "cherry", "bell"]) == 2
    assert slots.payout(["cherry", "bell", "lemon"]) == 1 and slots.payout(["bell", "lemon", "star"]) == 0


def test_buy_spin_and_daily_limit(client):
    ph, mia, _ = setup_family(client)
    h = login(client, mia)
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 160}, headers=ph)
    assert client.get("/api/me/slots", headers=h).json()["owned"] is False
    assert client.post("/api/me/slots/spin", headers=h).status_code == 400          # buy it first
    st = client.post("/api/me/slots/buy", headers=h).json()
    assert st["owned"] and st["coins"] == 10 and st["left"] == 3
    assert client.post("/api/me/slots/buy", headers=h).status_code == 400           # once is enough
    fq = client.app.state.fq
    seq = iter(["seven", "seven", "seven", "bell", "lemon", "star", "cherry", "lemon", "orange"])
    fq.slots.draw = lambda: next(seq)
    r = client.post("/api/me/slots/spin", headers=h).json()
    assert r["reels"] == ["seven"] * 3 and r["win"] == 100 and r["coins"] == 109 and r["left"] == 2
    r = client.post("/api/me/slots/spin", headers=h).json()
    assert r["win"] == 0 and r["coins"] == 108
    r = client.post("/api/me/slots/spin", headers=h).json()
    assert r["win"] == 1 and r["coins"] == 108 and r["left"] == 0
    assert client.post("/api/me/slots/spin", headers=h).status_code == 400          # 3 a day


def test_parents_can_switch_it_off(client):
    ph, mia, _ = setup_family(client)
    h = login(client, mia)
    client.put("/api/parent/settings", json={"games_access": {"slots": {"mode": "off", "profiles": []}}}, headers=ph)
    assert client.get("/api/me/slots", headers=h).status_code == 403
