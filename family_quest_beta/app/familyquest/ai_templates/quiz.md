# Family Quest – family quiz template for an AI

> **How to use this file:** copy everything below into the chat of your favourite AI (ChatGPT, Claude, Gemini,
> Copilot, a local model …), then add one line with your wish, for example:
> *«Make a family quiz with 15 questions about Europe – flags, capitals, a few maps and estimations – for children
> from 8 and their grandparents.»*
> Save the AI's answer as a `.json` file and import it in Family Quest: **New quiz › Import**.
> The quiz can then be played live on everybody's phone.

---

## Instructions for the AI

You write a quiz for **Family Quest**, a family app. The whole family plays it live together, each on their own
phone – children (from about 6) and adults. Make it fun, fair and correct.

**Your answer must be exactly one JSON object – no text before or after it, no Markdown code fence, no comments.**

### Rules for good questions
- Facts must be correct and not out of date. If you are not sure, leave the question out.
- Mix easy and harder questions so children can win too. Short questions, short answers (max. ~40 characters).
- Multiple choice: 2–4 answers, exactly one is right, the wrong ones are plausible.
- **Mix the question types** below – a quiz with pictures, flags, estimations and maps is more fun.
- Write the quiz in the language the user writes in (or the one they ask for).

### Question types

Every question has `"type"`, `"question"` and optionally `"seconds"` (time to answer, 5–120; default 20 for
multiple choice, 30 for the others).

**1. Multiple choice** – `"type": "choice"`
- `"answers"`: 2–4 answers. `"correct"`: index of the right one (0 = first) – the game shuffles the order.
- Answers may be **flag emoji** (🇫🇷 🇮🇹 🇨🇭 …): the app shows them as big, sharp flags. Good for «Which flag has …?».
- The question text may contain emoji and flag emoji too.

**2. Multiple choice with a picture** – `"type": "choice"` plus `"image"`, one of:
- `{"flag": "JP"}` – a big country flag; the ISO 3166 two-letter country code (JP, DE, CH, BR …; also EU for the European Union).
- `{"emoji": "🦒"}` – one big emoji as the picture («Which animal is this?»).
- `{"svg": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>…</svg>"}` – your own simple drawing
  (shapes, a clock face, a fraction pie, a geometric figure, a simple map). Plain SVG elements only, no scripts,
  no external images or fonts, max. 30 KB. Use single quotes inside the SVG so the JSON stays valid.
- `{"type": "canton_outline", "canton": "GR"}` – the outline of a Swiss canton («Which canton has this shape?»)
- `{"type": "canton_map", "canton": "GR"}` – the map of Switzerland with this canton marked
- `{"type": "canton_arms", "canton": "GR"}` – the coat of arms of this canton
  (canton codes: ZH BE LU UR SZ OW NW GL ZG FR SO BS BL SH AR AI SG GR AG TG TI VD VS NE GE JU)

**3. Estimation** – `"type": "estimate"`: everybody sets a number on a slider, the closest wins.
- `"answer"`: the right number, `"min"` / `"max"`: the slider range (min < answer < max), `"unit"` (optional),
  `"step"` (optional, e.g. 1 or 0.1).

**4. Map** – `"type": "map"`: everybody taps a place on a map, the closest wins.
- `"lat"` / `"lon"`: the right place in decimal degrees, `"map"`: `"ch"` (Switzerland) or `"europe"`,
  `"label"`: name shown after the answer (optional). Only places inside the chosen map.

### JSON structure (example with every type)

```
{
  "title": "Around Europe",                       // name of the quiz (max. 80 characters)
  "questions": [
    { "type": "choice", "question": "What is the capital of Italy?",
      "answers": ["Rome", "Milan", "Naples", "Turin"], "correct": 0 },

    { "type": "choice", "question": "Which flag belongs to Sweden?",
      "answers": ["🇸🇪", "🇳🇴", "🇫🇮", "🇩🇰"], "correct": 0, "seconds": 15 },

    { "type": "choice", "question": "Which country has this flag?", "image": { "flag": "PT" },
      "answers": ["Portugal", "Spain", "Brazil"], "correct": 0 },

    { "type": "choice", "question": "Which animal is this?", "image": { "emoji": "🦔" },
      "answers": ["Hedgehog", "Porcupine", "Mole"], "correct": 0 },

    { "type": "choice", "question": "How much of the circle is coloured?",
      "image": { "svg": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='#eee' stroke='#333' stroke-width='2'/><path d='M50 50 L50 5 A45 45 0 0 1 95 50 Z' fill='#4dabf7'/></svg>" },
      "answers": ["a quarter", "a half", "a third"], "correct": 0 },

    { "type": "choice", "question": "Which canton has this shape?",
      "image": { "type": "canton_outline", "canton": "TI" },
      "answers": ["Ticino", "Valais", "Grisons"], "correct": 0 },

    { "type": "estimate", "question": "How tall is the Eiffel Tower?",
      "answer": 330, "min": 100, "max": 600, "unit": "m" },

    { "type": "map", "question": "Where is Vienna?", "lat": 48.2082, "lon": 16.3738,
      "map": "europe", "label": "Vienna" }
  ]
}
```

10–20 questions are a good length for a family evening. Several quizzes at once: answer with a JSON list
`[ {quiz}, {quiz} ]`.

Remember: **output only the JSON object (or list), nothing else.**
