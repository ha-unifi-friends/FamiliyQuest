"""Cube solver of the game corner (web/cubesolver.js + web/cube.js): solver and colour check run in node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from websrc import parent_js

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "family_quest" / "app" / "web"
NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_random_scrambles_are_solved_and_impossible_cubes_rejected():
    r = subprocess.run([NODE, str(ROOT / "tests" / "cube_solver_harness.js"), "3000", "500"],
                       capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ok"]
    assert out["n3"]["count"] == 3000 and out["n3"]["max"] < 250        # layer by layer: longer than optimal, always correct
    assert out["n2"]["count"] == 500 and out["n2"]["max"] <= 11          # 2×2: the shortest way
    assert out["rejects"] == 10


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_scripts_parse():
    for f in ("cubesolver.js", "cube.js", "minigames.js"):
        r = subprocess.run([NODE, "--check", str(WEB / f)], capture_output=True, text=True)
        assert r.returncode == 0, f + r.stderr


def test_registered_in_the_game_corner_and_switchable(client):
    from familyquest.services import FamilyQuest
    from test_api import setup_family
    assert "cube" in FamilyQuest.GAMES
    assert '["cube", "🧊", T("Cube solver")]' in parent_js()
    assert "cube: cubeGame" in (WEB / "minigames.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "cubesolver.js" in html and "cube.js" in html
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert "cube" in client.get("/api/me", headers=h).json()["games_list"]
    # parents switch it off like the other games
    client.put("/api/parent/settings", json={"games_access": {"cube": {"mode": "off", "profiles": []}}}, headers=ph)
    assert "cube" not in client.get("/api/me", headers=h).json()["games_list"]
