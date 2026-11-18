"""Write the beta app «Family Quest Beta» (folder family_quest_beta/) from the current app (family_quest/).

Both apps live in this repository, so Home Assistant shows them side by side under «Family Quest».
The beta has its own slug (family_quest_beta): it installs next to the stable app, with its own data, and its
entities/events start with family_quest_beta_. Its icon carries an orange «BETA» band (tools/beta/).

    python3 tools/publish_beta.py 0.3.0-beta.2 "What is new in this beta" ["more lines" …]

Then commit and push to main: Home Assistant offers the update for «Family Quest Beta» only – the stable app
updates only when the version in family_quest/config.yaml changes. Once a beta is good, raise that version
(e.g. 0.3.0) and push – that is the stable release.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = "family_quest_beta"
URL = "https://github.com/ha-unifi-friends/FamiliyQuest"
BETA_PORT = 8098


def main(version: str, notes: list[str]) -> None:
    publish(SLUG, "Family Quest Beta", "BETA", BETA_PORT, ROOT / "tools" / "beta", version, notes)


def publish(slug: str, name: str, tag: str, port: int, icons: Path, version: str, notes: list[str], channel: str = "") -> None:
    """Write the app `slug` (a copy of family_quest/ with its own name, slug, port, icon and changelog) – also used by
    tools/publish_dev.py. `channel`: written to app/CHANNEL (familyquest/channel.py), e.g. «dev»."""
    dst = ROOT / slug
    old_log = (dst / "CHANGELOG.md").read_text(encoding="utf-8") if (dst / "CHANGELOG.md").is_file() else ""
    if dst.exists():
        shutil.rmtree(dst)
    # only files tracked by git – nothing local or private (e.g. school material) can end up in the beta
    files = subprocess.run(["git", "ls-files", "-z", "family_quest"], cwd=ROOT, check=True,
                           capture_output=True).stdout.decode().split("\0")
    for rel in filter(None, files):
        out = dst / Path(rel).relative_to("family_quest")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, out)
    for icon in ("icon.png", "logo.png"):
        shutil.copy2(icons / icon, dst / icon)
    if channel:
        (dst / "app" / "CHANNEL").write_text(channel + "\n", encoding="utf-8")

    cfg = dst / "config.yaml"
    text = cfg.read_text(encoding="utf-8")
    for key, value in (("name", f'"{name}"'), ("version", f'"{version}"'), ("slug", slug),
                       ("url", URL), ("panel_title", f'"{name}"')):
        text, n = re.subn(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
        assert n, f"config.yaml has no '{key}'"
    text = re.sub(r'^description: "(.*)"$', rf'description: "{tag} – \1"', text, count=1, flags=re.M)
    # Home Assistant shows the orange «🧪 Experimental» badge in the add-on store for beta and dev
    text = re.sub(r"^stage:.*\n", "", text, flags=re.M)
    text = re.sub(r"^(version: .*)$", r"\1\nstage: experimental", text, count=1, flags=re.M)
    # own host port for direct access, so the apps can run with direct access at the same time
    text, n = re.subn(r"^  8099/tcp: .*$", f"  8099/tcp: {port}", text, count=1, flags=re.M)
    assert n, "config.yaml has no port 8099/tcp"
    cfg.write_text(text, encoding="utf-8")
    # AppArmor profile named after the app's slug (the Supervisor loads it under the add-on's slug)
    aa = dst / "apparmor.txt"
    if aa.is_file():
        aa.write_text(aa.read_text(encoding="utf-8").replace("profile family_quest ", f"profile {slug} ", 1), encoding="utf-8")

    # the app keeps its own changelog: new entry on top of its previous changelog
    head = "# Changelog\n\n"
    body = old_log[len(head):] if old_log.startswith(head) else (dst / "CHANGELOG.md").read_text(encoding="utf-8")[len(head):]
    if f"## {version}\n" not in body:
        entry = f"## {version}\n\n" + "".join(f"- {n}\n" for n in notes or ["Development state of the next version."]) + "\n"
        body = entry + body
    (dst / "CHANGELOG.md").write_text(head + body, encoding="utf-8")
    print(f"{name} {version} written to {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
