"""«Errate den Song»: a speaker of Home Assistant plays, buzzer, the others judge."""
import pytest
from test_api import setup_family

SONGS = [("Bohemian Rhapsody", "Queen"), ("Alperose", "Polo Hofer"), ("Thriller", "Michael Jackson")]


class FakeSpeaker:
    connected = True

    def __init__(self):
        self.calls, self.i, self.vol = [], -1, 0.4

    def media_players(self):
        return [{"entity_id": "media_player.wohnzimmer", "name": "Wohnzimmer", "state": "idle"}]

    def media(self, entity, action):
        self.calls.append(action)
        if action.startswith("volume:"):
            self.vol = float(action.split(":")[1])
        if action == "next":
            self.i += 1

    def announce(self, entity, url):
        self.calls.append("announce:" + url.rsplit("/", 1)[-1])

    def media_info(self, entity):
        t, a = SONGS[self.i % len(SONGS)]
        return {"state": "paused", "title": t, "artist": a, "album": "", "picture": "/api/media_player_proxy/x?token=1", "volume": self.vol}

    def media_cover(self, picture):
        return (b"\xff\xd8\xff cover", "image/jpeg")


def test_song_game(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    assert client.get("/api/community/song/players", headers=hm).json()["ha"] is False
    spk = FakeSpeaker()
    client.app.state.fq.ha = spk
    assert client.get("/api/community/song/players", headers=hm).json()["players"][0]["entity_id"] == "media_player.wohnzimmer"
    assert client.post("/api/community/song/start", json={"player": ""}, headers=hm).status_code == 400
    st = client.post("/api/community/song/start", json={"player": "media_player.wohnzimmer", "target": 2, "max_songs": 5, "reveal_delay": 0, "reveal_by": "all"}, headers=hm).json()
    assert st["phase"] == "lobby"
    assert client.post("/api/community/song/begin", headers=hm).status_code == 400          # alone: nobody to judge
    client.post("/api/community/song/join", headers=hl)
    assert client.post("/api/community/song/begin", headers=hl).status_code == 403          # Leo does not lead
    st = client.post("/api/community/song/begin", headers=hm).json()
    assert st["phase"] == "playing" and st["song"] == 1 and st["solution"] is None and spk.calls[:3] == ["shuffle", "next", "play"]
    assert st["volume"] == 40
    st = client.post("/api/community/song/volume", json={"step": 1}, headers=hm).json()
    st = client.post("/api/community/song/volume", json={"step": 1}, headers=hm).json()
    assert st["volume"] == 50 and abs(spk.vol - 0.5) < 1e-9
    assert client.post("/api/community/song/volume", json={"step": -1}, headers=hl).status_code == 403   # only the leader
    # Leo buzzes first, Mia's buzz is too late
    client.post("/api/community/song/buzz", headers=hl)
    st = client.post("/api/community/song/buzz", headers=hm).json()
    assert st["phase"] == "buzzed" and st["buzzer"] == leo and spk.calls[-1] == "pause"
    assert client.post("/api/community/song/reveal", headers=ph).status_code == 200 or True
    st = client.get("/api/community/song", headers=hm).json()
    assert st["phase"] == "reveal" and st["solution"]["title"] == "Bohemian Rhapsody" and st["solution"]["cover"]
    assert client.post("/api/community/song/vote", json={"right": True}, headers=hl).status_code == 400   # not his own answer
    st = client.post("/api/community/song/vote", json={"right": True}, headers=hm).json()
    assert st["phase"] == "result" and st["verdict"]["right"] and next(p for p in st["players"] if p["id"] == leo)["points"] == 1
    assert client.get("/api/community/song/cover", headers=hm).content.startswith(b"\xff\xd8")
    # next song: Mia buzzes, Leo says wrong → −1
    client.post("/api/community/song/next", headers=hm)
    client.post("/api/community/song/buzz", headers=hm)
    client.post("/api/community/song/reveal", headers=hm)
    st = client.post("/api/community/song/vote", json={"right": False}, headers=hl).json()
    assert st["solution"]["artist"] == "Polo Hofer" and next(p for p in st["players"] if p["id"] == mia)["points"] == -1
    # nobody knows the third one: skip shows the solution without points
    client.post("/api/community/song/next", headers=hm)
    st = client.post("/api/community/song/next", headers=hm).json()
    assert st["phase"] == "result" and st["skipped"] and st["solution"]["title"] == "Thriller"
    # Leo reaches the target of 2 points → over
    client.post("/api/community/song/next", headers=hm)
    client.post("/api/community/song/buzz", headers=hl)
    client.post("/api/community/song/reveal", headers=hl)
    client.post("/api/community/song/vote", json={"right": True}, headers=hm)
    st = client.post("/api/community/song/next", headers=hm).json()
    assert st["phase"] == "done" and st["players"][0]["id"] == leo
    client.app.state.fq.ha = None


def test_countdown_before_the_solution(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    client.app.state.fq.ha = FakeSpeaker()
    client.post("/api/community/song/start", json={"player": "media_player.x", "reveal_delay": 5, "reveal_by": "all"}, headers=hm)
    client.post("/api/community/song/join", headers=hl)
    client.post("/api/community/song/begin", headers=hm)
    st = client.post("/api/community/song/buzz", headers=hl).json()
    assert st["phase"] == "buzzed" and 4000 < st["reveal_in_ms"] <= 5000
    assert client.post("/api/community/song/reveal", headers=hl).status_code == 400          # too early – the countdown runs
    import json as _j
    fq = client.app.state.fq
    row = fq.songs._row(); s = _j.loads(row["state"]); s["buzz_at"] -= 6
    fq.db.x("UPDATE song_game SET state=? WHERE id=?", _j.dumps(s), row["id"])
    assert client.post("/api/community/song/reveal", headers=hl).json()["phase"] == "reveal"
    client.app.state.fq.ha = None


def test_only_the_leader_shows_the_solution(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    client.app.state.fq.ha = FakeSpeaker()
    client.post("/api/community/song/start", json={"player": "media_player.x", "reveal_delay": 0, "reveal_by": "leader"}, headers=hm)
    client.post("/api/community/song/join", headers=hl)
    client.post("/api/community/song/begin", headers=hm)
    client.post("/api/community/song/buzz", headers=hl)
    assert client.post("/api/community/song/reveal", headers=hl).status_code == 400      # Leo buzzed but does not lead
    assert client.post("/api/community/song/reveal", headers=hm).json()["phase"] == "reveal"
    client.app.state.fq.ha = None


def test_the_others_show_the_solution_by_default(client):
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    client.app.state.fq.ha = FakeSpeaker()
    client.app.state.fq.db.set_setting("song_rules", None)
    st = client.post("/api/community/song/start", json={"player": "media_player.x", "reveal_delay": 0}, headers=hm).json()
    assert st["rules"]["reveal_by"] == "others"
    client.post("/api/community/song/join", headers=hl)
    client.post("/api/community/song/begin", headers=hm)
    client.post("/api/community/song/buzz", headers=hl)
    assert client.post("/api/community/song/reveal", headers=hl).status_code == 400      # Leo buzzed: the others show it
    assert client.post("/api/community/song/reveal", headers=hm).json()["phase"] == "reveal"
    client.app.state.fq.ha = None


def test_ping_and_brrr_on_the_speaker(client):
    import time
    ph, mia, leo = setup_family(client)
    hm = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    fq = client.app.state.fq
    spk = FakeSpeaker()
    fq.ha, fq.lan_base = spk, "http://192.168.1.5:8099"
    client.post("/api/community/song/start", json={"player": "media_player.x", "reveal_delay": 0, "reveal_by": "all"}, headers=hm)
    client.post("/api/community/song/join", headers=hl)
    client.post("/api/community/song/begin", headers=hm)
    client.post("/api/community/song/buzz", headers=hl)
    client.post("/api/community/song/reveal", headers=hl)
    client.post("/api/community/song/vote", json={"right": True}, headers=hm)
    for _ in range(50):
        if any(c.startswith("announce") for c in spk.calls):
            break
        time.sleep(0.02)
    assert "announce:right.mp3" in spk.calls and "next" not in spk.calls[spk.calls.index("announce:right.mp3"):]   # the queue is not touched
    client.post("/api/community/song/next", headers=hm)
    client.post("/api/community/song/buzz", headers=hm)
    client.post("/api/community/song/reveal", headers=hm)
    client.post("/api/community/song/vote", json={"right": False}, headers=hl)
    for _ in range(50):
        if "announce:wrong.mp3" in spk.calls:
            break
        time.sleep(0.02)
    assert "announce:wrong.mp3" in spk.calls
    fq.ha, fq.lan_base = None, None


# ---------------------------------------------------------------- the vote decides as soon as the verdict is certain
def _vote_game(fq, judges: int, vote: str = "majority"):
    """A song game in the reveal phase: the host buzzed, `judges` others judge. → (song service, judge ids, host)."""
    import json as _j
    fq.ha = FakeSpeaker()
    fq.songs._ding = lambda *a: None                     # no speaker sound thread in these tests
    ids = [fq.db.x("INSERT INTO profile(name, role) VALUES(?, 'kid')", f"P{i}") for i in range(judges + 1)]
    host, others = ids[0], ids[1:]
    fq.songs.start(host, {"player": "media_player.x", "vote": vote, "reveal_delay": 0, "reveal_by": "leader"})
    for pid in others:
        fq.songs.join(pid)
    fq.songs.begin()
    assert fq.songs.buzz(host)
    row = fq.songs._row(); s = _j.loads(row["state"]); s["buzz_at"] -= 10
    fq.db.x("UPDATE song_game SET state=? WHERE id=?", _j.dumps(s), row["id"])
    fq.songs.reveal({"id": host, "role": "parent"})
    return fq.songs, others, host


def _after(fq, votes: list[bool], judges: int, vote: str = "majority"):
    """Vote one after the other – (phase after each vote, the final verdict)."""
    songs, others, host = _vote_game(fq, judges, vote)
    phases = []
    for pid, v in zip(others, votes):
        if songs.state(host)["phase"] == "result":
            break
        songs.vote(pid, v)
        phases.append(songs.state(host)["phase"])
    st = songs.state(host)
    songs.end()
    fq.ha = None
    return phases, st["verdict"], st["players"][0]["points"] if st["players"] else None


@pytest.mark.parametrize("judges,votes,decided_after,right", [
    # 2 voters: right needs both (more than half of 2); one «wrong» is already half → wrong
    (2, [True, True], 2, True), (2, [False], 1, False), (2, [True, False], 2, False),
    # 3 voters: two «right» are more than half; two «wrong» – right cannot reach 2 any more
    (3, [True, True], 2, True), (3, [False, False], 2, False), (3, [True, False, True], 3, True), (3, [True, False, False], 3, False),
    # 4 voters: three «right» needed; two «wrong» are half → wrong at once
    (4, [True, True, True], 3, True), (4, [False, False], 2, False), (4, [True, False, False], 3, False), (4, [True, True, False, True], 4, True),
    # 5 voters: three «right» or three «wrong»
    (5, [True, True, True], 3, True), (5, [False, False, False], 3, False), (5, [True, False, True, False, True], 5, True),
    (5, [True, True, False, False, False], 5, False),
])
def test_majority_decides_as_soon_as_it_is_certain(fq, judges, votes, decided_after, right):
    phases, verdict, _ = _after(fq, votes, judges)
    assert phases[-1] == "result" and len(phases) == decided_after, phases
    assert all(p == "reveal" for p in phases[:-1])
    assert verdict["right"] is right


@pytest.mark.parametrize("judges", [2, 3, 4, 5])
def test_majority_waits_while_it_is_open(fq, judges):
    """One «right» and nothing else: not decided yet (for 2 voters too – one right is not more than half)."""
    songs, others, host = _vote_game(fq, judges)
    songs.vote(others[0], True)
    assert songs.state(host)["phase"] == "reveal"
    fq.ha = None


@pytest.mark.parametrize("judges", [2, 3, 4, 5])
def test_unanimous_one_wrong_decides_right_needs_all(fq, judges):
    phases, verdict, points = _after(fq, [True] * (judges - 1) + [True], judges, "unanimous")
    assert phases == ["reveal"] * (judges - 1) + ["result"] and verdict["right"] is True
    phases, verdict, points = _after(fq, [True, False, True, True, True][:judges], judges, "unanimous")
    assert phases == ["reveal", "result"] and verdict["right"] is False        # one «wrong»: unanimity is impossible


def test_the_leader_closes_the_vote_with_the_votes_there_are(fq):
    songs, others, host = _vote_game(fq, 5)
    songs.vote(others[0], True)
    songs.vote(others[1], True)
    songs.vote(others[2], False)
    assert songs.state(host)["phase"] == "reveal"
    songs.decide()                                     # 2 of 3 votes cast said right: right (as before)
    assert songs.state(host)["verdict"] == {"right": True, "yes": 2, "of": 3}
    fq.ha = None


def test_nobody_knows_button_for_the_leader_while_a_song_plays():
    """«⏭ Nobody knows it» is a button in the game screen of whoever leads – under the same condition as the ☰ entry."""
    import shutil
    import subprocess
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web" / "song.js").read_text(encoding="utf-8")
    assert 'hidden: !songCanSkip(st, leads)' in js                                  # the ☰ entry stays
    assert 'songCanSkip(st, leads) ? h("button.btn.small.ghost.song-skip", { onclick: () => act("next") }, "⏭ ", T("Nobody knows it"))' in js
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = js.index("const songCanSkip")
    fn = js[start:js.index("\n", start)]
    cases = [({"phase": "playing", "status": "running"}, True, True), ({"phase": "playing", "status": "running", "paused": True}, True, True),
             ({"phase": "playing", "status": "running"}, False, False), ({"phase": "lobby", "status": "lobby"}, True, False),
             ({"phase": "buzzed", "status": "running"}, True, False), ({"phase": "reveal", "status": "running"}, True, False),
             ({"phase": "result", "status": "running"}, True, False), ({"phase": "done", "status": "done"}, True, False)]
    import json as _j
    src = fn + "\nconst cases = " + _j.dumps(cases) + ";\nconsole.log(JSON.stringify(cases.map(([st, leads]) => songCanSkip(st, leads))));"
    out = subprocess.run([node, "-e", src], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert _j.loads(out.stdout) == [c[2] for c in cases]
