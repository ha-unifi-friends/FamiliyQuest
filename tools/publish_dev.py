"""Write the dev app «Family Quest Dev» (folder family_quest_dev/) from the current app (family_quest/).

The third channel next to «Family Quest» (stable) and «Family Quest Beta»: its own slug (family_quest_dev), so it
installs beside the other two with its own data; its entities/events start with family_quest_dev_, direct access uses
port 8097 (stable 8099, beta 8098), and its icon is tinted purple with a «DEV» band (tools/dev/, made by
tools/make_beta_icons.py dev). It carries the marker app/CHANNEL = «dev» (familyquest/channel.py): games still in
development (channel.DEV_GAMES) exist only here.

    python3 tools/publish_dev.py 1.1.1-dev.1 "What is new in this dev build" ["more lines" …]

Release with tools/release.py dev … – that puts only family_quest_dev/ on main.
"""
from __future__ import annotations

import sys

from publish_beta import ROOT, publish

SLUG = "family_quest_dev"
NAME = "Family Quest Dev"
DEV_PORT = 8097


def main(version: str, notes: list[str]) -> None:
    publish(SLUG, NAME, "DEV", DEV_PORT, ROOT / "tools" / "dev", version, notes, channel="dev")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
