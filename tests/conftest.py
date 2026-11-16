import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "family_quest" / "app"))

from familyquest.settings import BUILTIN_PACKS, Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, packs_dirs=[BUILTIN_PACKS], ha_enabled=False, ha_url="", ha_token=None,
                    secret=b"x" * 32, version="test")


@pytest.fixture
def fq(settings):
    from familyquest.services import FamilyQuest
    core = FamilyQuest(settings)
    core.packs.sync_folders(settings.packs_dirs)
    return core


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient
    from familyquest.main import create_app
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def kid(fq):
    pid = fq.db.x("INSERT INTO profile(name) VALUES('Mia')")
    fq.packs.activate_defaults(pid)
    return pid
