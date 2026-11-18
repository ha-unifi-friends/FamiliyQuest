"""Bring a beta or a stable release to the branch Home Assistant reads (main).

Development happens on a work branch: family_quest/ there is always the newest code. main is what Home Assistant
installs, so family_quest/ on main changes only with a stable release – a new install never gets unreleased code.

    python3 tools/release.py beta 0.3.0-beta.3 "What is new" ["more" …]
        writes family_quest_beta/ (tools/publish_beta.py), commits it on the work branch and puts ONLY that
        folder on main → Home Assistant offers the update for «Family Quest Beta».

    python3 tools/release.py dev 1.1.1-dev.1 "What is new" ["more" …]
        the same for the dev app: writes family_quest_dev/ (tools/publish_dev.py), commits it on the work branch and
        puts ONLY that folder on main → Home Assistant offers the update for «Family Quest Dev».

    python3 tools/release.py stable
        main gets the complete state of the work branch (raise the version in family_quest/config.yaml and
        write the changelog first) → Home Assistant offers the update for «Family Quest».

Add --no-push to prepare the commit on main without pushing it.
Release notes are written in English (they appear in Home Assistant's «Changelog» and in the parent area).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = {"beta": ("family_quest_beta", "Family Quest Beta"), "dev": ("family_quest_dev", "Family Quest Dev")}
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01Qq55cLdzUHFMJ42xWMEhQC\n")


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


def version_of(cfg: Path) -> str:
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return "?"


def to_main(paths: list[str], message: str, push: bool) -> None:
    work = git("rev-parse", "HEAD")
    git("fetch", "-q", "origin", "main")
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "main"
        git("worktree", "add", "-q", "--detach", str(wt), "origin/main")
        try:
            git("restore", f"--source={work}", "--staged", "--worktree", "--", *paths, cwd=wt)
            if not git("status", "--porcelain", cwd=wt):
                print("main is already up to date")
                return
            git("commit", "-q", "-m", message + TRAILER, cwd=wt)
            if push:
                git("push", "-q", "origin", "HEAD:main", cwd=wt)
                print("pushed to main:", git("log", "--oneline", "-1", cwd=wt))
            else:
                print("committed (not pushed):", git("log", "--oneline", "-1", cwd=wt))
        finally:
            git("worktree", "remove", "--force", str(wt), check=False)


def main(argv: list[str]) -> None:
    push = "--no-push" not in argv
    argv = [a for a in argv if a != "--no-push"]
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("commit your changes on the work branch first")
    if argv[:1] in (["beta"], ["dev"]) and len(argv) >= 2:
        folder, name = CHANNELS[argv[0]]
        subprocess.run([sys.executable, str(ROOT / "tools" / f"publish_{argv[0]}.py"), *argv[1:]], check=True)
        git("add", folder)
        if git("status", "--porcelain"):
            git("commit", "-q", "-m", f"{name} {argv[1]}" + TRAILER)
            git("push", "-q", "origin", "HEAD")
        to_main([folder], f"{name} {argv[1]}", push)
    elif argv[:1] == ["stable"]:
        # everything except the beta and dev folders: on main they may already be newer than this stable state
        to_main([".", *(f":(exclude){f}" for f, _ in CHANNELS.values())], f"Family Quest {version_of(ROOT / 'family_quest' / 'config.yaml')}", push)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
