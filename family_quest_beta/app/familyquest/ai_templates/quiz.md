# Family Quest – family quiz template for an AI

> **How to use this file:** copy everything below into the chat of your favourite AI (ChatGPT, Claude, Gemini,
> Copilot, a local model …), then add one line with your wish, for example:
> *«Make a family quiz with 15 questions about animals of the Alps – for children from 8 and their grandparents.»*
> Save the AI's answer as a `.json` file and upload it in Family Quest under **Family › Family quiz › Import**
> (or in the parent area under Community). The quiz can then be played live on everybody's phone.

---

## Instructions for the AI

You write a quiz for **Family Quest**, a family app. The whole family plays it live together, each on their own
phone – children (from about 6) and adults. Make it fun, fair and correct.

**Your answer must be exactly one JSON object – no text before or after it, no Markdown code fence, no comments.**

### Rules for good questions
- Facts must be correct and not out of date. If you are not sure, leave the question out.
- Mix easy and harder questions so children can win too. Short questions, short answers (max. ~40 characters).
- Multiple choice: 2–4 answers, exactly one is right, the wrong ones are plausible.
- Use estimation questions for numbers («How tall is …?») and map questions for places («Where is …?»).
- Write the quiz in the language the user writes in (or the one they ask for).

### JSON structure (with explanations)

```
{
  "title": "Animals of the Alps",                 // name of the quiz (max. 80 characters)
  "questions": [
    {
      "type": "choice",                           // multiple choice
      "question": "Which animal whistles when danger is near?",
      "answers": ["Marmot", "Ibex", "Chamois", "Golden eagle"],   // 2 to 4 answers
      "correct": 0,                               // index of the right answer (0 = first); order is shuffled in the game
      "seconds": 20                               // time to answer, 5–120 (optional, default 20)
    },
    {
      "type": "estimate",                         // guess a number on a slider – closest wins
      "question": "How many kilograms can an adult ibex weigh?",
      "answer": 100, "min": 0, "max": 300,        // the right number and the slider range (min < answer < max)
      "unit": "kg",                               // optional
      "seconds": 30
    },
    {
      "type": "map",                              // tap the place on a map – closest wins
      "question": "Where is the Matterhorn?",
      "lat": 45.9763, "lon": 7.6586,              // the right place (decimal degrees)
      "map": "ch",                                // "ch" = map of Switzerland, "europe" = map of Europe
      "label": "Matterhorn",                      // shown after the answer (optional)
      "seconds": 30
    }
  ]
}
```

10–20 questions are a good length for a family evening. Several quizzes at once: answer with a JSON list
`[ {quiz}, {quiz} ]`.

Remember: **output only the JSON object (or list), nothing else.**
