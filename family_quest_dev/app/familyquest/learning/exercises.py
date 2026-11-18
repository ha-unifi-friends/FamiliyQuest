"""Turning cards and generator tasks into exercise steps.

A step has a public part (sent to the client, no solution) and a solution part
(kept in the session on the server). Grading happens only on the server.
"""
from __future__ import annotations

import random

from .. import generators
from ..i18n import _t
from ..packs.registry import PackInfo, UnitInfo
from ..packs.schema import skill_key
from . import grading

KEYBOARDS = {
    "fr": list("éèêëàâçùûôîïœ"),
    "de": list("äöüß"),
    "it": list("àèéìòù"),
    "es": list("áéíóúñü¿¡"),
    "en": [],
}


def _media(pack_id: str, v: dict) -> dict:
    img = v.get("image") or ""
    if img and "." in img and ":" not in img and not img.startswith("http"):
        img = f"media/{pack_id}/{img}"
    elif img.startswith("mdi:"):
        img = ""
    return {"image": img, "emoji": v.get("emoji", "")}


def _distractors(right: str, pool: list[str], own: list[str], rng: random.Random, n: int = 3) -> list[str]:
    out: list[str] = []
    rn = grading.norm(right)
    for o in own + rng.sample(pool, len(pool)):
        if grading.norm(o) != rn and all(grading.norm(o) != grading.norm(x) for x in out) and o:
            out.append(o)
        if len(out) >= n:
            break
    return out


def _langs(pack: PackInfo) -> tuple[str, str]:
    """(language learnt, language of the prompt) – empty when the pack is not a language pack."""
    tgt = pack.lang
    src = getattr(pack.model, "quellsprache", "") or "de"
    return (tgt, src) if tgt else ("", "")


def _side(item: dict, reverse: bool) -> tuple[str, str]:
    v = item["view"]
    return (v["answer"], v["prompt"]) if reverse else (v["prompt"], v["answer"])


def choice_step(pack: PackInfo, unit: UnitInfo, item: dict, pool_items: list[dict], rng: random.Random,
                reverse: bool = False, timer: int = 0) -> dict:
    if not item["view"]["prompt"]:
        reverse = False            # photo card: the photo is the question, it cannot be an answer option
    q, a = _side(item, reverse)
    pool = [(_side(i, reverse)[1]) for i in pool_items if i["key"] != item["key"]]
    own = [] if reverse else item["view"]["options"]
    opts = _distractors(a, pool, own, rng) + [a]
    rng.shuffle(opts)
    instr = _t("What does it mean?") if reverse else _t("Choose the right answer")
    return {"kind": "auswahl", "pack": pack.id, "unit": unit.id, "keys": [item["key"]],
            "public": {"instruction": instr, "prompt": q, "options": opts, "timer": timer, **_media(pack.id, item["view"]),
                       "answer_lang": _langs(pack)[1 if reverse else 0]},
            "solution": {"answer": a}}


def type_step(pack: PackInfo, unit: UnitInfo, item: dict) -> dict:
    v = item["view"]
    lang = pack.lang
    return {"kind": "eintippen", "pack": pack.id, "unit": unit.id, "keys": [item["key"]],
            "public": {"instruction": _t("Type the answer"), "prompt": v["prompt"], "keys": KEYBOARDS.get(lang, []),
                       "answer_lang": _langs(pack)[0],
                       "lang": lang, "hint": v["hint"], **_media(pack.id, v)},
            "solution": {"answer": v["answer"], "also": v["also"]}}


def gap_step(pack: PackInfo, unit: UnitInfo, item: dict, pool_items: list[dict], rng: random.Random) -> dict:
    v = item["view"]
    pool = [i["view"]["answer"] for i in pool_items if i["key"] != item["key"]]
    opts = _distractors(v["answer"], pool, v["options"], rng, 2) + [v["answer"]]
    rng.shuffle(opts)
    return {"kind": "lueckentext", "pack": pack.id, "unit": unit.id, "keys": [item["key"]],
            "public": {"instruction": _t("Fill the gap"), "sentence": v["sentence"], "prompt": v["prompt"], "options": opts,
                       "answer_lang": _langs(pack)[0]},
            "solution": {"answer": v["answer"]}}


def card_step(pack: PackInfo, unit: UnitInfo, item: dict) -> dict:
    v = item["view"]
    return {"kind": "karteikarte", "pack": pack.id, "unit": unit.id, "keys": [item["key"]],
            "public": {"instruction": _t("Think of the answer, then flip the card"), "prompt": v["prompt"],
                       "answer_lang": _langs(pack)[0],
                       "back": v["answer"], "lang": pack.lang, **_media(pack.id, v)},
            "solution": {"answer": v["answer"]}}


def listen_step(pack: PackInfo, unit: UnitInfo, item: dict, pool_items: list[dict], rng: random.Random) -> dict:
    v = item["view"]
    pool = [i["view"]["prompt"] for i in pool_items if i["key"] != item["key"]]
    opts = _distractors(v["prompt"], pool, [], rng) + [v["prompt"]]
    rng.shuffle(opts)
    return {"kind": "hoeren", "pack": pack.id, "unit": unit.id, "keys": [item["key"]],
            "public": {"instruction": _t("Listen and choose"), "say": v["answer"], "lang": pack.lang, "options": opts,
                       "answer_lang": _langs(pack)[1]},
            "solution": {"answer": v["prompt"]}}


def pairs_step(pack: PackInfo, unit: UnitInfo, items: list[dict], rng: random.Random) -> dict:
    left = [{"id": f"l{i}", "text": it["view"]["prompt"], **_media(pack.id, it["view"])} for i, it in enumerate(items)]
    right = [{"id": f"r{i}", "text": it["view"]["answer"]} for i, it in enumerate(items)]
    rng.shuffle(right)
    return {"kind": "paare", "pack": pack.id, "unit": unit.id, "keys": [it["key"] for it in items],
            "public": {"instruction": _t("Match the pairs"), "left": left, "right": right},
            "solution": {"pairs": {f"l{i}": f"r{i}" for i in range(len(items))},
                         "texts": {f"r{i}": it["view"]["answer"] for i, it in enumerate(items)}}}


def sort_step(pack: PackInfo, unit: UnitInfo, items: list[dict], rng: random.Random, all_items: list[dict]) -> dict:
    """Drag & drop: drag each chip onto the field it belongs to (e.g. municipality → district)."""
    targets: list[str] = []
    for it in items:
        if it["view"]["answer"] not in targets:
            targets.append(it["view"]["answer"])
    # with only one or two categories in the sample, add others from the unit so it stays a choice
    for it in all_items:
        if len(targets) >= min(5, max(3, len(targets))):
            break
        if it["view"]["answer"] not in targets:
            targets.append(it["view"]["answer"])
    rng.shuffle(targets)
    chips = [{"id": f"c{i}", "text": it["view"]["prompt"], **_media(pack.id, it["view"])} for i, it in enumerate(items)]
    rng.shuffle(chips)
    tmap = {t: f"t{i}" for i, t in enumerate(targets)}
    return {"kind": "zuordnen", "pack": pack.id, "unit": unit.id, "keys": [it["key"] for it in items],
            "public": {"instruction": _t("Drag each card to where it belongs"),
                       "targets": [{"id": tmap[t], "text": t} for t in targets], "chips": chips,
                       "layout": (getattr(pack.model, "model_extra", None) or {}).get("layout", "")},
            "solution": {"map": {f"c{i}": tmap[it["view"]["answer"]] for i, it in enumerate(items)},
                         "keys": {f"c{i}": it["key"] for i, it in enumerate(items)},
                         "targets": {v: k for k, v in tmap.items()}}}


def generator_step(pack: PackInfo, unit: UnitInfo, skill: str, rng: random.Random, timer: int = 0) -> dict:
    g = generators.get(unit.generator or "")
    task = g.make(skill, unit.params, rng)
    public = {"instruction": task["instruction"], "expr": task["expr"], "input": task["input"], "timer": timer}
    if task["input"] == "choice":
        public["options"] = task["options"]
    return {"kind": "rechnen", "pack": pack.id, "unit": unit.id, "keys": [skill_key(pack.id, unit.id, skill)],
            "skill": skill, "public": public,
            "solution": {"answer": task["answer"], "input": task["input"], "reduced": task.get("reduced", False)}}


# ---------------------------------------------------------------- grading
def grade(step: dict, answer) -> dict:
    """Returns {"results": {item_key: correct|almost|wrong}, "correct": bool, "note", "solution"}."""
    kind, sol = step["kind"], step["solution"]
    keys = step["keys"]
    if kind in ("auswahl", "lueckentext", "hoeren"):
        ok = grading.norm(str(answer)) == grading.norm(sol["answer"])
        return {"results": {keys[0]: "correct" if ok else "wrong"}, "correct": ok, "note": "", "solution": sol["answer"]}
    if kind == "eintippen":
        ok, note = grading.check_text(str(answer or ""), sol["answer"], sol.get("also"))
        return {"results": {keys[0]: "correct" if ok else "wrong"}, "correct": ok, "note": note, "solution": sol["answer"]}
    if kind == "karteikarte":
        r = answer if answer in ("correct", "almost", "wrong") else "wrong"
        return {"results": {keys[0]: r}, "correct": r == "correct", "note": "", "solution": sol["answer"]}
    if kind == "paare":
        given = answer if isinstance(answer, dict) else {}
        res, good = {}, 0
        for i, k in enumerate(keys):
            ok = given.get(f"l{i}") == sol["pairs"][f"l{i}"]
            res[k] = "correct" if ok else "wrong"
            good += ok
        return {"results": res, "correct": good == len(keys), "note": "", "solution": sol["pairs"], "score": [good, len(keys)]}
    if kind == "zuordnen":
        given = answer if isinstance(answer, dict) else {}
        res, good = {}, 0
        for cid, tid in sol["map"].items():
            ok = given.get(cid) == tid
            res[sol["keys"][cid]] = "correct" if ok else "wrong"
            good += ok
        return {"results": res, "correct": good == len(sol["map"]), "note": "", "solution": sol["map"],
                "score": [good, len(sol["map"])]}
    if kind == "rechnen":
        inp, a = sol["input"], sol["answer"]
        note = ""
        if inp == "number":
            ok = grading.check_number(answer, a)
        elif inp == "fraction":
            ok, note = grading.check_fraction(answer, a, sol.get("reduced", False))
        elif inp == "div_rest":
            try:
                ok = int(answer[0]) == a[0] and int(answer[1]) == a[1]
            except (TypeError, ValueError, IndexError):
                ok = False
        else:
            ok = grading.norm(str(answer)) == grading.norm(str(a))
        return {"results": {keys[0]: "correct" if ok else "wrong"}, "correct": ok, "note": note, "solution": a}
    return {"results": {}, "correct": False, "note": "", "solution": None}
