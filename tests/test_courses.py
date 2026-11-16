"""Language courses (A1–B1 in German, French, English, Spanish) and general knowledge: chosen by the learner."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_all_builtin_packs_are_valid():
    files = sorted(str(p) for p in (ROOT / "family_quest" / "packs").glob("*.yaml"))
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_pack.py"), *files], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    for lang in ("de", "fr", "en", "es"):
        for level in ("a1", "a2", "b1"):
            assert (ROOT / "family_quest" / "packs" / f"sprache-{lang}-{level}.yaml").is_file()


def test_courses_are_chosen_by_the_learner(client):
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"}).json()
    ph = {"X-FQ-Parent": r["parent_token"]}
    mia = client.post("/api/parent/profiles", json={"name": "Mia"}, headers=ph).json()["id"]
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia}).json()["token"]}
    subjects = {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    assert not any(p.startswith("sprache-") for p in subjects) and "allgemeinwissen" not in subjects   # not switched on by default
    courses = client.get("/api/me/courses", headers=h).json()
    ids = {c["id"] for c in courses}
    assert {"sprache-fr-a1", "sprache-es-b1", "sprache-de-a2", "allgemeinwissen"} <= ids
    fr = next(c for c in courses if c["id"] == "sprache-fr-a1")
    assert fr["level"] == "A1" and fr["lang"] == "fr" and fr["cards"] > 50 and not fr["on"]
    assert client.post("/api/me/courses/sprache-fr-a1", json={"on": True}, headers=h).json()["on"]
    assert "sprache-fr-a1" in {s["pack"] for s in client.get("/api/me", headers=h).json()["subjects"]}
    # a lesson in the course works; units unlock one after the other (learning path)
    pack = client.get("/api/me/packs/sprache-fr-a1", headers=h).json()
    first = pack["pack"]["units"][0]["id"]
    assert pack["pack"]["path"] is True
    s = client.post("/api/me/session", json={"mode": "path", "pack": "sprache-fr-a1", "unit": first}, headers=h).json()
    assert s["steps"]
    # only self-service packs can be switched on by the learner
    assert client.post("/api/me/courses/mathe-5kl", json={"on": True}, headers=h).status_code == 404
    assert client.post("/api/me/courses/sprache-fr-a1", json={"on": False}, headers=h).status_code == 200
