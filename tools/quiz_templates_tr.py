"""Translations of the built-in quiz templates (familyquest/quiz_templates.py, German).

    python3 tools/quiz_templates_tr.py extract     # write familyquest/quiz_templates_tr/source_de.json
    python3 tools/quiz_templates_tr.py check       # every language file complete and aligned with the source

A language file <lang>.json has the shape of the source: {template id: {"title", "items": [...]}}; an item is
{"q", "a": [right, wrong …]} (multiple choice, same order as the source), {"q", "unit"} (estimate) or {"q", "label"} (map).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "family_quest" / "app"
sys.path.insert(0, str(ROOT))
from familyquest.quiz_templates import TEMPLATES  # noqa: E402

DIR = ROOT / "familyquest" / "quiz_templates_tr"
LANGS = ["en", "fr", "it", "es", "nl", "pl", "pt", "sv"]


def source() -> dict:
    out = {}
    for tid, t in TEMPLATES.items():
        items = []
        for item in t["questions"]:
            if isinstance(item, dict):
                items.append({"q": item["q"], **({"unit": item.get("unit") or ""} if item.get("kind") == "estimate" else {"label": item.get("label") or ""})})
            else:
                img = item[-1] if isinstance(item[-1], dict) else None
                q, *answers = item[:-1] if img else item
                items.append({"q": q, "a": list(answers[:4])})
        out[tid] = {"title": t["title"], "items": items}
    return out


def check() -> int:
    src, bad = source(), 0
    for lang in LANGS:
        f = DIR / f"{lang}.json"
        if not f.is_file():
            print(f"{lang}: missing file"); bad += 1; continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for tid, t in src.items():
            x = d.get(tid)
            if not x or not x.get("title") or len(x.get("items") or []) != len(t["items"]):
                print(f"{lang}: {tid} missing or wrong length"); bad += 1; continue
            for i, (a, b) in enumerate(zip(t["items"], x["items"])):
                if not str(b.get("q") or "").strip() or ("a" in a and len(b.get("a") or []) != len(a["a"])) \
                        or any(k not in b for k in a if k != "q" and a[k]):
                    print(f"{lang}: {tid} #{i} incomplete: {b}"); bad += 1
    print("ok" if not bad else f"{bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["extract"]:
        DIR.mkdir(exist_ok=True)
        (DIR / "source_de.json").write_text(json.dumps(source(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("written", DIR / "source_de.json")
    else:
        sys.exit(check())
