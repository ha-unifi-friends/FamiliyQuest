"""Import of word lists from CSV or Excel: upload → choose columns → draft pack."""
from __future__ import annotations

import csv
import io
import json
import secrets
from pathlib import Path

from ..packs.loader import PackError
from ..packs.schema import slug
from .common import draft_from_dict, suggest_meta  # noqa: F401  (suggest_meta re-exported for the API)
from ..i18n import _t

TABLE_EXT = (".csv", ".tsv", ".xlsx", ".xlsm")
GUESS = {
    "prompt": ["de", "deutsch", "frage", "question", "wort", "begriff", "prompt", "german"],
    "answer": ["fr", "français", "francais", "franzoesisch", "französisch", "en", "english", "englisch", "it",
               "antwort", "answer", "lösung", "loesung", "uebersetzung", "übersetzung"],
    "image": ["bild", "image", "emoji", "picture"],
    "unit": ["einheit", "unit", "lektion", "kapitel", "thema"],
    "sentence": ["satz", "sentence", "lückentext", "lueckentext"],
    "hint": ["hinweis", "hint", "tipp"],
    "also": ["auch", "alternativen", "also", "synonym"],
}
LANG_HEADERS = {"fr": ["fr", "français", "francais", "franzoesisch", "französisch", "french"],
                "en": ["en", "english", "englisch"], "it": ["it", "italiano", "italienisch"]}


def is_table(name: str) -> bool:
    return name.lower().endswith(TABLE_EXT)


def _rows(name: str, raw: bytes) -> list[list[str]]:
    if name.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001 – openpyxl raises many types
            raise PackError(_t("Excel file cannot be read: {0}").replace("{0}", str(e))) from None
        ws = wb.worksheets[0]
        return [["" if v is None else str(v).strip() for v in row] for row in ws.iter_rows(values_only=True)]
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)]


def _upload_dir(fq) -> Path:
    d = fq.settings.data_dir / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage(fq, name: str, raw: bytes) -> dict:
    rows = [r for r in _rows(name, raw) if any(c for c in r)]
    if len(rows) < 2:
        raise PackError("the table needs a header row and at least one row")
    header = rows[0]
    width = max(len(r) for r in rows)
    header = [h or f"Spalte {i + 1}" for i, h in enumerate(header + [""] * (width - len(header)))]
    body = [r + [""] * (width - len(r)) for r in rows[1:]]
    uid = secrets.token_hex(8)
    (_upload_dir(fq) / f"{uid}.json").write_text(json.dumps({"name": name, "header": header, "rows": body}), encoding="utf-8")
    low = [h.lower().strip() for h in header]
    guess: dict[str, int | None] = {}
    for field, words in GUESS.items():
        guess[field] = next((i for i, h in enumerate(low) if h in words), None)
    if guess["prompt"] is None:
        guess["prompt"] = 0
    if guess["answer"] is None or guess["answer"] == guess["prompt"]:
        guess["answer"] = 1 if width > 1 else None
    meta = suggest_meta(name)
    ans_head = low[guess["answer"]] if guess["answer"] is not None else ""
    for lang, words in LANG_HEADERS.items():
        if ans_head in words:
            meta["sprache"] = lang
    return {"upload_id": uid, "header": header, "preview": body[:8], "count": len(body), "columns": guess, "meta": meta}


def build(fq, upload_id: str, meta: dict, columns: dict) -> list[dict]:
    if not upload_id.isalnum():
        raise PackError("unknown upload")
    f = _upload_dir(fq) / f"{upload_id}.json"
    if not f.is_file():
        raise PackError("upload expired – please upload the file again")
    staged = json.loads(f.read_text(encoding="utf-8"))

    def col(row: list[str], field: str) -> str:
        i = columns.get(field)
        if i is None or i == "" or int(i) >= len(row):
            return ""
        return row[int(i)].strip()

    if columns.get("prompt") in (None, "") or columns.get("answer") in (None, ""):
        raise PackError("choose a column for question and answer")
    units: dict[str, list[dict]] = {}
    for row in staged["rows"]:
        p, a = col(row, "prompt"), col(row, "answer")
        if not p or not a:
            continue
        card: dict = {"frage": p, "antwort": a}
        img = col(row, "image")
        if img:
            card["emoji" if len(img) <= 4 and not img.isascii() else "bild"] = img
        for field, key in (("sentence", "satz"), ("hint", "hinweis")):
            v = col(row, field)
            if v:
                card[key] = v
        also = col(row, "also")
        if also:
            card["auch"] = [x.strip() for x in also.replace(";", "|").split("|") if x.strip()]
        units.setdefault(col(row, "unit") or meta.get("einheit") or "Wörter", []).append(card)
    if not units:
        raise PackError("no rows with question and answer found")
    title = (meta.get("titel") or staged["name"]).strip()
    data = {
        "id": slug(meta.get("id") or title),
        "titel": title,
        "fach": meta.get("fach") or "allgemein",
        "stufe": meta.get("stufe") or "",
        "sprache": meta.get("sprache") or "",
        "quellsprache": meta.get("quellsprache") or "de",
        "privat": bool(meta.get("privat", True)),
        "quelle": meta.get("quelle") or f"Import {staged['name']}",
        "einheiten": [{"id": slug(name), "titel": name, "karten": cards} for name, cards in units.items()],
    }
    out = [draft_from_dict(fq, data, "import")]
    f.unlink(missing_ok=True)
    return out
