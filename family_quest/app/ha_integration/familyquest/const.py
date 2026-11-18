"""Constants of the Family Quest integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "familyquest"
CONF_URL = "url"
CONF_TOKEN = "token"
DEFAULT_URL = "http://local-family-quest:8099"
SCAN_INTERVAL = timedelta(seconds=30)
MANUFACTURER = "Family Quest"
PLATFORMS = ["sensor", "binary_sensor", "switch"]
