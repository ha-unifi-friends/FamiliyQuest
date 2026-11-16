"""Runtime settings: add-on options (/data/options.json) and environment overrides.

Environment variables (handy for local development and tests):
  FQ_DATA_DIR      where the SQLite file, media and secret live (default /data)
  FQ_PACKS_DIRS    extra pack folders, separated by ':' (default /share/family_quest/packs)
  FQ_HA_DISABLED   "1" = do not talk to Home Assistant
  FQ_HA_URL        Home Assistant base URL (default http://supervisor/core)
  FQ_HA_MEDIA_DIR  Home Assistant's media folder («My media», mapped read-only; default /media)
  SUPERVISOR_TOKEN set by the Supervisor inside the add-on
"""
from __future__ import annotations

import json
import re
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent          # family_quest/app
ADDON_DIR = APP_DIR.parent                                 # family_quest/
WEB_DIR = APP_DIR / "web"
BUILTIN_PACKS = ADDON_DIR / "packs" if (ADDON_DIR / "packs").is_dir() else APP_DIR / "packs"


def _config_value(key: str, default: str) -> str:
    for p in (ADDON_DIR / "config.yaml", APP_DIR / "config.yaml"):
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith(key + ":"):
                    return line.split(":", 1)[1].strip().strip('"')
    return default


def default_port() -> int | None:
    """Host port preset for direct access in config.yaml (ports: 8099/tcp: N)."""
    v = _config_value("  8099/tcp", "")
    return int(v) if v.isdigit() else None


def _version() -> str:
    return _config_value("version", "dev")


@dataclass
class Settings:
    data_dir: Path
    packs_dirs: list[Path]
    ha_enabled: bool
    ha_url: str
    ha_token: str | None
    direct_access: bool = False
    log_level: str = "info"
    version: str = "dev"
    secret: bytes = b""
    options: dict = field(default_factory=dict)
    # prefix of entities, events and notifications in Home Assistant = the app slug
    # (family_quest, or family_quest_beta for the beta channel, so both can run side by side)
    entity_prefix: str = "family_quest"
    # Home Assistant's media folder (Media → My media), mapped read-only: pictures for the pairs game and the crest
    ha_media_dir: Path = field(default_factory=lambda: Path(os.environ.get("FQ_HA_MEDIA_DIR", "/media")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "family_quest.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def _s6_env(name: str) -> str | None:
    """Fallback: the s6-overlay keeps the container environment in files (if the app was not started with-contenv)."""
    try:
        v = (Path("/run/s6/container_environment") / name).read_text(encoding="utf-8").strip()
        return v or None
    except OSError:
        return None


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("FQ_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    options: dict = {}
    opt_file = data_dir / "options.json"
    if opt_file.is_file():
        try:
            options = json.loads(opt_file.read_text(encoding="utf-8"))
        except ValueError:
            options = {}
    packs_env = os.environ.get("FQ_PACKS_DIRS", "/share/family_quest/packs")
    packs_dirs = [BUILTIN_PACKS] + [Path(p) for p in packs_env.split(":") if p]
    token = os.environ.get("SUPERVISOR_TOKEN") or _s6_env("SUPERVISOR_TOKEN")
    ha_enabled = os.environ.get("FQ_HA_DISABLED") != "1" and bool(token)
    secret_file = data_dir / "secret.key"
    if not secret_file.is_file():
        secret_file.write_bytes(secrets.token_bytes(32))
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass
    return Settings(
        data_dir=data_dir,
        packs_dirs=packs_dirs,
        ha_enabled=ha_enabled,
        ha_url=os.environ.get("FQ_HA_URL", "http://supervisor/core"),
        ha_token=token,
        direct_access=bool(options.get("direct_access", False)) or os.environ.get("FQ_DIRECT_ACCESS") == "1",
        log_level=str(options.get("log_level", "info")),
        version=_version(),
        secret=secret_file.read_bytes(),
        options=options,
        entity_prefix=re.sub(r"[^a-z0-9_]", "_", _config_value("slug", "family_quest").lower()) or "family_quest",
    )
