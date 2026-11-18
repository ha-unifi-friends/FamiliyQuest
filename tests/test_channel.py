"""Release channels (channel.py): the dev games («24h Endurance», «Beat the Bureaucracy») exist only in «Family Quest
Dev» – in stable and beta they are in no games list, no access setting, no FamilyTime list, no guest invitation, and
their API answers 404. History entries of families that played them keep showing."""
import json

import pytest

from familyquest import channel
from test_api import setup_family

DEV = sorted(channel.DEV_GAMES)


@pytest.fixture(autouse=True)
def _normal_unless_marked(request, monkeypatch):
    """These tests choose the channel themselves – also when the suite runs with FQ_TEST_CHANNEL=dev."""
    monkeypatch.setattr(channel, "_channel", "dev" if request.node.get_closest_marker("dev_channel") else "")


def login(client, pid, pin=None):
    return {"X-FQ-Token": client.post("/api/login", json={"profile_id": pid, **({"pin": pin} if pin else {})}).json()["token"]}


def test_marker_file_and_env(tmp_path, monkeypatch):
    monkeypatch.setattr(channel, "CHANNEL_FILE", tmp_path / "CHANNEL")
    monkeypatch.delenv("FQ_CHANNEL", raising=False)
    monkeypatch.setattr(channel, "_channel", None)
    assert channel.channel() == "" and not channel.is_dev() and channel.hidden_games() == channel.DEV_GAMES
    (tmp_path / "CHANNEL").write_text("dev\n")
    monkeypatch.setattr(channel, "_channel", None)
    assert channel.is_dev() and channel.hidden_games() == frozenset()
    monkeypatch.setenv("FQ_CHANNEL", "")                      # the environment wins over the file
    monkeypatch.setattr(channel, "_channel", None)
    assert not channel.is_dev()


def test_normal_channel_hides_the_dev_games(client):
    from familyquest.services import FamilyQuest
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    for g in DEV:
        assert g not in FamilyQuest.GAMES and g not in fq.BOT_GAMES and g not in fq.games_access()
    me = client.get("/api/me", headers=hm).json()
    assert not set(DEV) & set(me["games_list"]) and "jump" in me["games_list"]
    assert me["community"].get("langstrecke") is None and me["community"].get("stempeljagd") is None
    games = client.get("/api/parent/games", headers=phd).json()
    assert not set(DEV) & set(games["access"]) and not set(DEV) & set(games["bot_games"])
    assert not set(DEV) & set(client.get("/api/parent/game-rewards", headers=phd).json())
    assert client.put("/api/parent/game-rewards", json={"langstrecke": [1, 1, 1]}, headers=phd).status_code == 400
    assert client.put("/api/parent/games", json={"access": {"stempeljagd": {"mode": "off", "profiles": []}}}, headers=phd).status_code == 400
    # the API of the dev games does not exist – also not for parents
    for g in DEV:
        assert client.get(f"/api/community/{g}", headers=hm).status_code == 404
        assert client.get(f"/api/community/{g}/rules", headers=phd).status_code == 404
        assert client.post(f"/api/community/{g}/start", json={"solo": True}, headers=phd).status_code == 404
    # FamilyTime wishes, guests
    parent = fq.db.q1("SELECT * FROM profile WHERE role='parent'")
    assert not set(DEV) & set(fq.familytime.allowed_games(parent))
    from familyquest.familytime import choice_of
    from familyquest.community import CommunityError
    with pytest.raises(CommunityError):
        choice_of("langstrecke", None)
    from familyquest.guests import GuestError
    with pytest.raises(GuestError):
        fq.guests.invite("stempeljagd")


def test_history_of_a_dev_game_still_shows(client):
    phd, mia, leo = setup_family(client)
    fq = client.app.state.fq
    hm = login(client, mia, "1111")
    fq.community.add_history(mia, "langstrecke", {"place": 1, "players": 2, "laps": 12})
    hist = client.get("/api/community/history", headers=hm)
    assert hist.status_code == 200 and "langstrecke" in json.dumps(hist.json())


def test_facts_leave_out_the_dev_games(fq):
    from familyquest import facts
    a = fq.db.x("INSERT INTO profile(name, role, color) VALUES('A','kid','#fff')")
    b = fq.db.x("INSERT INTO profile(name, role, color) VALUES('B','kid','#fff')")
    fq.db.set_setting("langstrecke_pit", {str(a): 52, str(b): 70})
    fq.db.set_setting("langstrecke_best", {str(a): 30, str(b): 10})
    gens = {c["gen"] for c in facts.Facts(fq).candidates()}
    assert "record_pit" not in gens and not any("langstrecke" in g for g in gens)
    channel._channel = "dev"                       # the same data in «Family Quest Dev» (monkeypatch resets it)
    gens = {c["gen"] for c in facts.Facts(fq).candidates()}
    assert "record_pit" in gens and any("langstrecke" in g for g in gens)


@pytest.mark.dev_channel
def test_dev_channel_has_the_dev_games(client):
    phd, mia, leo = setup_family(client)
    hm = login(client, mia, "1111")
    assert set(DEV) <= set(client.get("/api/me", headers=hm).json()["games_list"])
    assert set(DEV) <= set(client.get("/api/parent/games", headers=phd).json()["access"])
    for g in DEV:
        assert client.get(f"/api/community/{g}", headers=hm).status_code == 200
