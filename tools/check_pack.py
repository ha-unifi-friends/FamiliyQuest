"""Check learning pack files: valid format, every card readable (prompt and answer), no duplicate cards.

    python3 tools/check_pack.py family_quest/packs/sprache-fr-a1.yaml [more files …]

Prints the units with their number of cards; exit code 1 on any problem.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "family_quest" / "app"))

from familyquest.packs.loader import PackError, pack_dict, parse_text  # noqa: E402
from familyquest.packs.registry import build_info  # noqa: E402
from familyquest.packs.schema import EXERCISE_KINDS, Pack, card_view  # noqa: E402


def check(path: Path) -> list[str]:
    problems = []
    try:
        docs = parse_text(path.name, path.read_text(encoding="utf-8"))
    except PackError as e:
        return [f"{path.name}: {e}"]
    for p in docs:
        if not isinstance(p, Pack):
            continue
        info = build_info({"id": p.id, "kind": "pack", "title": p.titel, "subject": p.fach, "level": p.stufe,
                           "status": "active", "source": "check", "version": p.version, "updated_at": "", "hash": "", "data": json.dumps(pack_dict(p), ensure_ascii=False)})
        print(f"{path.name}: {p.id} «{p.titel}» ({p.sprache or '-'} from {p.quellsprache})")
        for u, ui in zip(p.einheiten, info.units):
            if u.generator:
                continue
            for c in u.karten:
                v = card_view(p, c)
                if not v["prompt"] or not v["answer"]:
                    problems.append(f"{p.id}/{u.id}: card without prompt or answer: {c}")
                if v["sentence"] and "___" not in v["sentence"]:
                    problems.append(f"{p.id}/{u.id}: gap sentence without ___: {c}")
                if "lueckentext" in u.uebungen and not v["sentence"]:
                    problems.append(f"{p.id}/{u.id}: unit has lueckentext but card has no satz: {c}")
            if len(ui.items) != len(u.karten):
                problems.append(f"{p.id}/{u.id}: {len(u.karten) - len(ui.items)} duplicate or empty card(s)")
            bad = [x for x in u.uebungen if x not in EXERCISE_KINDS]
            if bad:
                problems.append(f"{p.id}/{u.id}: unknown exercise(s) {bad}")
            print(f"  {u.id:<24} {len(ui.items):>3} cards  {', '.join(u.uebungen)}")
    return problems


if __name__ == "__main__":
    allp = []
    for f in sys.argv[1:]:
        allp += check(Path(f))
    for x in allp:
        print("PROBLEM", x)
    sys.exit(1 if allp else 0)
