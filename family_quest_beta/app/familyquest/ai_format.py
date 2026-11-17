"""Self-describing JSON for learning packs and quizzes – the same file is template, export and import.

Keys that start with "_" carry English instructions and a field guide written for an AI (ChatGPT, Claude, Gemini,
a local model …): what every field means and how to fill it. Import ignores them (strip_meta), so a family can
download a template or an export, let any AI fill, extend or translate it, and import the answer again.
"""
from __future__ import annotations

QUIZ_FORMAT = "family-quest-quiz/1"
PACK_FORMAT = "family-quest-pack/1"

_COMMON = [
    "This file belongs to Family Quest, a family app in Home Assistant. Children (about 6–14) and adults use it.",
    "Your answer must be ONE JSON object in exactly this structure – no text before or after it, no Markdown code "
    "fence, no comments. Keep all keys that start with '_' unchanged (they only explain the format).",
    "If you got this file with content (an export), change, extend or translate it as the user asks and keep "
    "everything else as it is. If you got it as a template, replace the example content with new content.",
    "Facts must be correct and suitable for children. If you are not sure about something, leave it out. "
    "Do not invent facts or words that the user did not ask for or that are not on an attached page.",
]

QUIZ_INSTRUCTIONS = _COMMON + [
    "Fill 'quizzes' with one or more quizzes. The whole family plays a quiz live together, each on their own phone. "
    "Make it fun and fair: mix easy and harder questions so children can win too.",
    "Mix the question types (see _field_guide): multiple choice with text or flag answers, questions with a "
    "picture (flag, emoji, own SVG drawing, Swiss canton outline / map / coat of arms), estimation and map questions.",
    "Short questions, short answers (max. ~40 characters). Multiple choice: 2–4 answers, exactly one is right, "
    "the wrong ones are plausible. 10–20 questions are a good length for a family evening.",
    "Write in the language the user writes in (or the one they ask for).",
]

QUIZ_GUIDE = {
    "quizzes[]": {
        "title": "Name of the quiz, max. 80 characters.",
        "questions": "List of questions; every question has 'type', 'question' and optionally 'seconds'.",
    },
    "question.type": {
        "choice": "Multiple choice. Fields: 'answers' (2–4 strings), 'correct' (index of the right answer, 0 = first; "
                  "the game shuffles the order). Optional 'image'.",
        "estimate": "Everybody sets a number on a slider, the closest wins. Fields: 'answer' (the right number), "
                    "'min' and 'max' (slider range, min < answer < max), optional 'unit' (e.g. 'm', 'kg') and 'step' "
                    "(e.g. 1 or 0.1).",
        "map": "Everybody taps a place on a map, the closest wins. Fields: 'lat', 'lon' (decimal degrees), "
               "'map': 'ch' (Switzerland) or 'europe', optional 'label' (name shown after the answer). "
               "The place must lie inside the chosen map.",
    },
    "question.question": "The question text. May contain emoji and flag emoji.",
    "question.seconds": "Time to answer, 5–120. Default 20 for 'choice', 30 for 'estimate' and 'map'.",
    "question.answers": "For 'choice'. Answers may also be flag emoji (🇫🇷 🇮🇹 🇨🇭 …) – the app shows them as big, "
                        "sharp flags (good for «Which flag belongs to …?»).",
    "question.image": {
        "_": "Optional picture of a 'choice' question – exactly one of the following objects.",
        "flag": "{\"flag\": \"JP\"} – a big country flag; ISO 3166 two-letter code (JP, DE, CH, BR …, also EU).",
        "emoji": "{\"emoji\": \"🦒\"} – one big emoji as the picture («Which animal is this?»).",
        "svg": "{\"svg\": \"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>…</svg>\"} – an own simple "
               "drawing (shapes, a clock face, a fraction, a geometric figure). Plain SVG elements only, no scripts, "
               "no external images or fonts, max. 30 KB. Use single quotes inside the SVG so the JSON stays valid.",
        "canton_outline": "{\"type\": \"canton_outline\", \"canton\": \"GR\"} – outline of a Swiss canton.",
        "canton_map": "{\"type\": \"canton_map\", \"canton\": \"GR\"} – map of Switzerland with this canton marked.",
        "canton_arms": "{\"type\": \"canton_arms\", \"canton\": \"GR\"} – coat of arms of this canton.",
        "canton codes": "ZH BE LU UR SZ OW NW GL ZG FR SO BS BL SH AR AI SG GR AG TG TI VD VS NE GE JU",
    },
}

QUIZ_EXAMPLE = {
    "title": "Around Europe",
    "questions": [
        {"type": "choice", "question": "What is the capital of Italy?", "answers": ["Rome", "Milan", "Naples", "Turin"], "correct": 0},
        {"type": "choice", "question": "Which flag belongs to Sweden?", "answers": ["🇸🇪", "🇳🇴", "🇫🇮", "🇩🇰"], "correct": 0, "seconds": 15},
        {"type": "choice", "question": "Which country has this flag?", "image": {"flag": "PT"},
         "answers": ["Portugal", "Spain", "Brazil"], "correct": 0},
        {"type": "choice", "question": "Which animal is this?", "image": {"emoji": "🦔"}, "answers": ["Hedgehog", "Porcupine", "Mole"], "correct": 0},
        {"type": "choice", "question": "How much of the circle is coloured?",
         "image": {"svg": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='#eee' "
                          "stroke='#333' stroke-width='2'/><path d='M50 50 L50 5 A45 45 0 0 1 95 50 Z' fill='#4dabf7'/></svg>"},
         "answers": ["a quarter", "a half", "a third"], "correct": 0},
        {"type": "choice", "question": "Which canton has this shape?", "image": {"type": "canton_outline", "canton": "TI"},
         "answers": ["Ticino", "Valais", "Grisons"], "correct": 0},
        {"type": "estimate", "question": "How tall is the Eiffel Tower?", "answer": 330, "min": 100, "max": 600, "unit": "m"},
        {"type": "map", "question": "Where is Vienna?", "lat": 48.2082, "lon": 16.3738, "map": "europe", "label": "Vienna"},
    ],
}

PACK_INSTRUCTIONS = _COMMON + [
    "Fill 'pakete' with one or more learning packs. A pack is a subject topic for one school year, split into units "
    "(chapters); a unit has cards. The app turns the cards into flash cards, multiple choice, typing, matching pairs, "
    "gap texts, listening and drag & drop – and repeats them with spaced repetition.",
    "Fit the age and school year the user names. One fact or word per card, short questions.",
    "Keep spelling exactly right, with all accents (é è à ç ü ñ …). Nouns in a foreign language with their article "
    "(«la maison», «der Hund»).",
    "8–25 cards per unit; split bigger topics into several units. Add an 'emoji' for concrete things, a 'satz' "
    "(example sentence with ___) where it helps, 'auch' for other correct answers.",
    "Field names are partly German (titel, fach, einheiten, karten …) – keep them exactly as they are.",
]

PACK_GUIDE = {
    "pakete[] (pack)": {
        "id": "Unique id, lowercase letters, digits, - _ . only (e.g. 'french-5-unit-3').",
        "titel": "Title of the pack.",
        "fach": "Subject: deutsch, mathematik, nmg (nature, people, society), englisch, franzoesisch, italienisch, "
                "spanisch, allgemein … (free text allowed).",
        "stufe": "School level / grade, free text (e.g. '5. Klasse', '3rd grade').",
        "sprache": "Language that is LEARNT – the answer side: fr, en, de, it, es … ('' if no language is learnt).",
        "quellsprache": "Language of the question side (the child's language), e.g. 'de' or 'en'.",
        "privat": "true for content from school books (never shared).",
        "quelle": "Optional: where the content comes from (e.g. 'Workbook p. 34').",
        "beschreibung": "Optional short description.",
        "icon": "Optional emoji of the pack.",
        "pfad": "Optional: true = units unlock one after the other (default false: all units open).",
        "einheiten": "List of units.",
    },
    "einheiten[] (unit)": {
        "id": "Unique inside the pack, lowercase.",
        "titel": "Title of the unit.",
        "icon": "One emoji.",
        "uebungen": "Optional learning forms (without it the app chooses): auswahl = multiple choice, eintippen = typing, "
                    "paare = matching pairs, lueckentext = gap text (cards need 'satz'), hoeren = listening (language "
                    "packs), karteikarte = flash card, zuordnen = drag & drop into groups (few different answers, e.g. "
                    "animal → continent).",
        "karten": "List of cards (or a 'generator' instead, see below).",
        "generator": "Maths only, instead of cards – endless generated tasks: einmaleins (times tables), division_rest, "
                     "schriftlich (written arithmetic), brueche (fractions), brueche_kuerzen, dezimal (decimals).",
        "parameter": "Settings of the generator, e.g. {\"reihen\": \"6-9\", \"modus\": \"gemischt\"} for einmaleins "
                     "(modus: mal | geteilt | gemischt).",
    },
    "karten[] (card)": {
        "frage": "Question side (what the child sees), required.",
        "antwort": "Answer side, required.",
        "emoji": "Optional picture as one emoji.",
        "auch": "Optional list of other correct answers (synonyms, spelling without accents).",
        "optionen": "Optional list of wrong answers for multiple choice (otherwise taken from the other cards).",
        "satz": "Optional sentence with ___ where the answer belongs (for the gap text).",
        "hinweis": "Optional short tip shown with the question.",
        "language keys": "Instead of frage/antwort a card may use the language codes, e.g. {\"de\": \"das Haus\", "
                         "\"fr\": \"la maison\"} (quellsprache → sprache).",
    },
}

PACK_EXAMPLE = {
    "id": "french-5-unit-3",
    "titel": "French 5th grade – Unit 3: La maison",
    "fach": "franzoesisch", "stufe": "5. Klasse", "sprache": "fr", "quellsprache": "de", "privat": True,
    "quelle": "Workbook p. 34",
    "einheiten": [
        {"id": "rooms", "titel": "Rooms of the house", "icon": "🏠", "uebungen": ["auswahl", "eintippen", "paare", "karteikarte"],
         "karten": [
             {"frage": "das Haus", "antwort": "la maison", "emoji": "🏠"},
             {"frage": "die Küche", "antwort": "la cuisine", "emoji": "🍳", "satz": "Maman prépare le dîner dans ___.", "hinweis": "a room for cooking"},
             {"frage": "die Schwester", "antwort": "la sœur", "auch": ["la soeur"]},
             {"frage": "das Zimmer", "antwort": "la chambre", "emoji": "🛏️"},
         ]},
        {"id": "times-tables", "titel": "Times tables 6–9", "icon": "✖️", "generator": "einmaleins",
         "parameter": {"reihen": "6-9", "modus": "gemischt"}},
    ],
}


def quiz_document(quizzes: list[dict], template: bool = False) -> dict:
    return {"_format": QUIZ_FORMAT, "_ai_instructions": QUIZ_INSTRUCTIONS, "_field_guide": QUIZ_GUIDE,
            "quizzes": [QUIZ_EXAMPLE] if template else quizzes}


def pack_document(packs: list[dict], template: bool = False) -> dict:
    return {"_format": PACK_FORMAT, "_ai_instructions": PACK_INSTRUCTIONS, "_field_guide": PACK_GUIDE,
            "pakete": [PACK_EXAMPLE] if template else packs}


def strip_meta(data):
    """Drop the explanation keys ("_…") everywhere – what remains is the content."""
    if isinstance(data, dict):
        return {k: strip_meta(v) for k, v in data.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(data, list):
        return [strip_meta(x) for x in data]
    return data


# ---------------------------------------------------------------- quiz: inner format → this format
def export_question(q: dict) -> dict:
    """A stored question (kind / q / a / c / t / img) in the format of this file (inverse of community.quiz_question)."""
    kind = q.get("kind") or "choice"
    if kind == "estimate":
        out = {"type": "estimate", "question": q.get("q", ""), "answer": q.get("answer"), "min": q.get("min"), "max": q.get("max")}
        out.update({k: q[k] for k in ("unit", "step") if q.get(k) not in (None, "")})
    elif kind == "pin":
        out = {"type": "map", "question": q.get("q", ""), "lat": q.get("lat"), "lon": q.get("lon"), "map": q.get("map", "europe")}
        if q.get("label"):
            out["label"] = q["label"]
    else:
        out = {"type": "choice", "question": q.get("q", ""), "answers": list(q.get("a") or []), "correct": q.get("c", 0)}
        img = q.get("img")
        if isinstance(img, dict):
            if img.get("geo") == "canton":
                out["image"] = {"type": f"canton_{img.get('mode') or 'outline'}", "canton": img.get("id")}
            else:
                out["image"] = {k: img[k] for k in ("flag", "emoji", "svg") if img.get(k)}
    if q.get("t") is not None:
        out["seconds"] = q["t"]
    return out
