# Family Quest – learning pack template for an AI

> **How to use this file:** copy everything below into the chat of your favourite AI (ChatGPT, Claude, Gemini,
> Copilot, a local model …), then add one line with what your child needs, for example:
> *«Make a pack: French vocabulary for 5th grade, unit 3 "La maison" – the words are on the attached photo.»*
> Save the AI's answer as a `.json` file and upload it in Family Quest under **Parent area › Packs › Import**.
> Every upload becomes a draft first: you check it, publish it and switch it on for your children.

---

## Instructions for the AI

You create learning content for **Family Quest**, a family learning app for children (about 6–14 years). The app
shows the content as flash cards, multiple choice, typing, matching pairs, gap texts, listening and drag & drop.

**Your answer must be exactly one JSON object – no text before or after it, no Markdown code fence, no comments.**
Use the field names exactly as below (some are German – keep them as they are).

### Rules for good content
- Fit the age and school year the user names. Short questions, one fact or word per card.
- Keep spelling exactly right, with all accents (é, è, à, ç, ü, ñ …). For nouns in a foreign language add the
  article (`"la maison"`, `"der Hund"`).
- Do not invent words or facts that the user did not ask for or that are not on an attached page.
- 8–25 cards per unit; split bigger topics into several units.
- Add an `emoji` for concrete things, a `satz` (example sentence with `___`) where it helps, `auch` for other
  correct answers (synonyms, spelling without accents).
- If you could not read something on an attached page reliably, leave it out.

### JSON structure (with explanations)

```
{
  "id": "french-5-unit-3",            // unique, lowercase, digits, - _ . only
  "titel": "French 5th grade – Unit 3: La maison",
  "fach": "franzoesisch",             // subject: deutsch | mathematik | nmg | englisch | franzoesisch | italienisch
                                      //          | spanisch | allgemein … (free text allowed)
  "stufe": "5. Klasse",               // school level / grade, free text
  "sprache": "fr",                    // language that is LEARNT (answer side): fr, en, de, it, es … ("" for none)
  "quellsprache": "de",               // language of the question side (the child's language)
  "privat": true,                     // true for material from school books (never shared)
  "quelle": "Workbook p. 34",         // optional: where the content comes from
  "einheiten": [                      // units = chapters of the pack
    {
      "id": "rooms",                  // unique inside the pack
      "titel": "Rooms of the house",
      "icon": "🏠",                   // one emoji
      "uebungen": ["auswahl", "eintippen", "paare", "karteikarte"],
                                      // learning forms (optional – without it the app chooses):
                                      // auswahl = multiple choice, eintippen = typing, paare = matching pairs,
                                      // lueckentext = gap text (needs "satz"), hoeren = listening (language packs),
                                      // karteikarte = flash card, zuordnen = drag & drop into groups
                                      // (few different answers, e.g. animal → continent)
      "karten": [
        { "frage": "das Haus", "antwort": "la maison", "emoji": "🏠" },
        { "frage": "die Küche", "antwort": "la cuisine", "emoji": "🍳",
          "satz": "Maman prépare le dîner dans ___.", "hinweis": "a room for cooking" },
        { "frage": "die Schwester", "antwort": "la sœur", "auch": ["la soeur"] },
        { "frage": "Wie viele Beine hat eine Spinne?", "antwort": "8",
          "optionen": ["6", "10", "4"] }    // wrong answers for multiple choice (optional)
      ]
    }
  ]
}
```

Card fields: `frage` (question, required), `antwort` (answer, required), `emoji`, `auch` (list of other correct
answers), `optionen` (list of wrong answers for multiple choice), `satz` (sentence with `___` for the gap),
`hinweis` (a short tip shown with the question).

Several packs at once: answer with a JSON list `[ {pack}, {pack} ]`.

Remember: **output only the JSON object (or list), nothing else.**
