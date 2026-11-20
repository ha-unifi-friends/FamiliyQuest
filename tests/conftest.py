import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "family_quest" / "app"))

from familyquest.settings import BUILTIN_PACKS, Settings  # noqa: E402
from familyquest import db as _db  # noqa: E402

# a database write on the thread of the asyncio event loop fails the test (db.LOOP_GUARD) – FQ_DEBUG_LOOP_WRITES=log
# only logs it
_db.LOOP_GUARD = os.environ.get("FQ_DEBUG_LOOP_WRITES") or "raise"


def pytest_configure(config):
    config.addinivalue_line("markers", "game_prices: the real default game prices, rents and free tries (gamepasses.py)")
    config.addinivalue_line("markers", "battery: the game battery switched on as by default (battery.py)")
    config.addinivalue_line("markers", "dev_channel: run as the «Family Quest Dev» app (channel.py: the dev games exist)")


@pytest.fixture(autouse=True)
def _channel(request, monkeypatch):
    """The tests run as the normal app (stable / beta: no dev games) – tests marked `dev_channel` as «Family Quest
    Dev». FQ_TEST_CHANNEL=dev runs the whole suite as the dev app."""
    from familyquest import channel
    dev = request.node.get_closest_marker("dev_channel") or os.environ.get("FQ_TEST_CHANNEL") == "dev"
    monkeypatch.setattr(channel, "_channel", "dev" if dev else "")


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


@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    """One database with every migration and the built-in packs synced, made once per test run – every test gets
    its own copy (the per-test sync then only finds «unchanged» packs)."""
    from familyquest.services import FamilyQuest
    d = tmp_path_factory.mktemp("template")
    s = Settings(data_dir=d, packs_dirs=[BUILTIN_PACKS], ha_enabled=False, ha_url="", ha_token=None, secret=b"x" * 32,
                 version="test")
    core = FamilyQuest(s)
    core.packs.sync_folders(s.packs_dirs)
    core.db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    core.db.conn.close()
    return d


def _from_template(template, settings) -> None:
    """A fresh copy of the template data folder for this test (nothing is shared between tests)."""
    if not settings.db_path.exists():
        shutil.copytree(template, settings.data_dir, dirs_exist_ok=True)


@pytest.fixture
def fq(settings, _template_db):
    from familyquest.services import FamilyQuest
    _from_template(_template_db, settings)
    core = FamilyQuest(settings)
    core.packs.sync_folders(settings.packs_dirs)
    core.db.set_setting("game_starter", "leader")     # the tests know who begins; the dice is tested on its own
    return core


@pytest.fixture
def client(settings, _template_db):
    from fastapi.testclient import TestClient
    from familyquest.main import create_app
    _from_template(_template_db, settings)
    app = create_app(settings)
    app.state.fq.db.set_setting("game_starter", "leader")   # the tests know who begins; the dice is tested on its own
    with TestClient(app) as c:
        yield c


@pytest.fixture
def kid(fq):
    pid = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    fq.packs.activate_defaults(pid)
    return pid
