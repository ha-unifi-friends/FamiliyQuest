"""Pack format (YAML, German keys as in the concept) and its normalised form.

A *pack* has units; a unit either lists cards (fixed content) or names a generator.
A *bundle* (Stufenpaket) groups packs per semester.

    id: franz-5kl-la-maison
    titel: "Französisch 5. Klasse – La maison"
    fach: franzoesisch
    stufe: 5. Klasse
    sprache: fr            # language that is learnt (answer side)
    quellsprache: de       # language of the prompt (default de)
    einheiten:
      - id: zimmer
        titel: Zimmer im Haus
        karten:
          - {de: das Haus, fr: la maison, emoji: "🏠"}
        uebungen: [auswahl, eintippen, paare, karteikarte]
      - id: rechnen
        generator: einmaleins
        parameter: {reihen: [6, 7, 8, 9]}
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXERCISE_KINDS = ["auswahl", "eintippen", "paare", "lueckentext", "karteikarte", "zuordnen", "hoeren"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,80}$")


def slug(s: str) -> str:
    t = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e"), ("à", "a"), ("ç", "c")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60] or "x"


class Unit(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    titel: str = ""
    beschreibung: str = ""
    icon: str = ""
    karten: list[dict[str, Any]] = Field(default_factory=list)
    uebungen: list[str] = Field(default_factory=list)
    generator: str | None = None
    parameter: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, v: Any) -> str:
        v = slug(str(v))
        return v

    @field_validator("uebungen")
    @classmethod
    def _kinds(cls, v: list[str]) -> list[str]:
        bad = [k for k in v if k not in EXERCISE_KINDS]
        if bad:
            raise ValueError(f"unknown exercise type(s): {', '.join(bad)}")
        return v

    @model_validator(mode="after")
    def _content(self) -> "Unit":
        if not self.karten and not self.generator:
            raise ValueError(f"unit '{self.id}' needs 'karten' or 'generator'")
        if not self.titel:
            self.titel = self.id.replace("-", " ").capitalize()
        return self


class Pack(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    titel: str
    fach: str = "allgemein"
    stufe: str = ""
    sprache: str = ""
    quellsprache: str = "de"
    version: str = "1"
    farbe: str = ""
    icon: str = ""
    beschreibung: str = ""
    beschreibung_i18n: dict[str, str] | None = None   # {"en": "…", "fr": "…"}: the description in other app languages
    quelle: str = ""
    privat: bool = False
    pfad: bool = False              # False = every unit open (default), True = units unlock one after the other
    standard: bool = True           # False = not switched on automatically for new profiles (e.g. language courses)
    selbst: bool = False            # True = learners switch it on themselves in the learning app (course catalogue)
    einheiten: list[Unit] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        # top-level `generator:` = pack with one generator unit (concept example)
        if isinstance(data, dict) and data.get("generator") and not data.get("einheiten"):
            data = dict(data)
            data["einheiten"] = [{"id": data.get("id", "u1"), "titel": data.get("titel", ""),
                                  "generator": data.pop("generator"), "parameter": data.pop("parameter", {})}]
        if isinstance(data, dict) and "titel" not in data and "id" in data:
            data = dict(data, titel=str(data["id"]))
        return data

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError("id: lower case letters, digits, '-', '_' and '.' only")
        return v

    @field_validator("fach", mode="before")
    @classmethod
    def _fach(cls, v: Any) -> str:
        return slug(str(v or "allgemein"))

    @field_validator("version", mode="before")
    @classmethod
    def _ver(cls, v: Any) -> str:
        return str(v)

    @model_validator(mode="after")
    def _units(self) -> "Pack":
        if not self.einheiten:
            raise ValueError("pack needs at least one unit ('einheiten')")
        seen = set()
        for u in self.einheiten:
            if u.id in seen:
                raise ValueError(f"duplicate unit id '{u.id}'")
            seen.add(u.id)
        return self


class Semester(BaseModel):
    id: str
    titel: str = ""
    pakete: list[str] = Field(default_factory=list)


class Bundle(BaseModel):
    """Stufenpaket, e.g. «5. Klasse Thurgau»."""
    model_config = ConfigDict(extra="allow")
    stufenpaket: str
    titel: str
    lehrplan: str = ""
    stufe: str = ""
    kanton: str = ""
    version: str = "1"
    faecher: list[str] = Field(default_factory=list)
    semester: list[Semester] = Field(default_factory=list)

    @field_validator("stufenpaket")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_RE.match(v):
            raise ValueError("stufenpaket: lower case letters, digits, '-', '_' and '.' only")
        return v

    @field_validator("version", mode="before")
    @classmethod
    def _ver(cls, v: Any) -> str:
        return str(v)

    @property
    def id(self) -> str:
        return self.stufenpaket

    def pack_ids(self) -> list[str]:
        out: list[str] = []
        for s in self.semester:
            for p in s.pakete:
                if p not in out:
                    out.append(p)
        return out


# ---------------------------------------------------------------- normalised cards
def card_view(pack: Pack | dict, card: dict) -> dict:
    """Prompt/answer of a card regardless of how it was written."""
    p = pack if isinstance(pack, dict) else pack.model_dump()
    src, tgt = p.get("quellsprache") or "de", p.get("sprache") or ""
    prompt = card.get("frage")
    answer = card.get("antwort")
    if prompt is None and src in card:
        prompt = card.get(src)
    if answer is None and tgt and tgt in card:
        answer = card.get(tgt)
    if prompt is None or answer is None:  # two plain language keys, e.g. {de: .., en: ..}
        langs = [k for k in card if re.fullmatch(r"[a-z]{2}", k)]
        if len(langs) >= 2:
            prompt = prompt if prompt is not None else card[langs[0]]
            answer = answer if answer is not None else card[langs[1]]
    alts = card.get("auch") or card.get("alternativen") or []
    if isinstance(alts, str):
        alts = [a.strip() for a in alts.split("|") if a.strip()]
    opts = card.get("optionen") or []
    if isinstance(opts, str):
        opts = [a.strip() for a in opts.split("|") if a.strip()]
    return {
        "prompt": "" if prompt is None else str(prompt),
        "answer": "" if answer is None else str(answer),
        "also": [str(a) for a in alts],
        "options": [str(o) for o in opts],
        "sentence": str(card.get("satz") or ""),
        "image": str(card.get("bild") or ""),
        "emoji": str(card.get("emoji") or ""),
        "hint": str(card.get("hinweis") or ""),
    }


def card_key(pack_id: str, unit_id: str, card: dict, view: dict | None = None) -> str:
    """Stable key: survives re-ordering cards in the YAML; changes when the content changes."""
    v = view or {}
    base = f"{v.get('prompt', card.get('frage', ''))}␟{v.get('answer', card.get('antwort', ''))}␟{v.get('sentence', '')}"
    if v and not v.get("prompt") and v.get("image"):
        base += f"␟{v['image']}"           # photo cards («who is this?»): the photo is the question
    if not v:
        base = repr(sorted(card.items()))
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"{pack_id}:{unit_id}:{h}"


def skill_key(pack_id: str, unit_id: str, skill: str) -> str:
    return f"{pack_id}:{unit_id}:@{skill}"
