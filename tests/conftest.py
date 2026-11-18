import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "family_quest" / "app"))

from familyquest.settings import BUILTIN_PACKS, Settings  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "game_prices: the real default game prices, rents and free tries (gamepasses.py)")
    config.addinivalue_line("markers", "battery: the game battery switched on as by default (battery.py)")


@pytest.fixture(autouse=True)
def _no_battery_by_default(request, monkeypatch):
    """The game tests start many games in a row: the game battery (battery.py, on by default with 5 segments) is off
    for them. Tests marked `battery` use the real default."""
    if request.node.get_closest_marker("battery"):
        return
    from familyquest import battery
    monkeypatch.setitem(battery.DEFAULT, "on", False)


@pytest.fixture(autouse=True)
def _free_games_by_default(request, monkeypatch):
    """The game tests play the quick games and the game corner as before game prices came: no default rent and no free
    tries (an explicit price is still locked at once). Tests marked `game_prices` use the real defaults."""
    if request.node.get_closest_marker("game_prices"):
        return
    from familyquest import gamepasses
    monkeypatch.setattr(gamepasses, "DEFAULT_RENT", {})
    monkeypatch.setattr(gamepasses, "DEFAULT_PREVIEW", 0)


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, packs_dirs=[BUILTIN_PACKS], ha_enabled=False, ha_url="", ha_token=None,
                    secret=b"x" * 32, version="test")


@pytest.fixture
def fq(settings):
    from familyquest.services import FamilyQuest
    core = FamilyQuest(settings)
    core.packs.sync_folders(settings.packs_dirs)
    core.db.set_setting("game_starter", "leader")     # the tests know who begins; the dice is tested on its own
    return core


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient
    from familyquest.main import create_app
    app = create_app(settings)
    app.state.fq.db.set_setting("game_starter", "leader")   # the tests know who begins; the dice is tested on its own
    with TestClient(app) as c:
        yield c


@pytest.fixture
def kid(fq):
    pid = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    fq.packs.activate_defaults(pid)
    return pid
