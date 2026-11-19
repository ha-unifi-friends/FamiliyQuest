# Paketformat

Inhalte sind gegliedert in **Fach → Paket → Einheit → Übung**. Ein Paket ist eine YAML-Datei (oder ein ZIP mit
YAML plus Bildern/Audio). Mehrere Pakete dürfen in einer Datei stehen, getrennt durch `---`.

## Paket mit Karten

```yaml
id: franz-5kl-einheit-3          # Kleinbuchstaben, Ziffern, - _ .
titel: "Französisch 5. Klasse – Einheit 3: La maison"
fach: franzoesisch               # deutsch, mathematik, nmg, englisch, franzoesisch, italienisch, … (frei)
stufe: 5. Klasse
sprache: fr                      # was gelernt wird (Antwortseite)
quellsprache: de                 # Sprache der Frage (Standard de)
version: 1
pfad: false                      # Standard: alle Einheiten offen; true = Einheiten schalten nacheinander frei
privat: true                     # aus Schulmaterial – nie teilen
quelle: Wortliste aus dem Heft
einheiten:
  - id: zimmer
    titel: Zimmer im Haus
    icon: "🏠"
    uebungen: [auswahl, eintippen, paare, hoeren, karteikarte]
    karten:
      - {de: das Haus, fr: la maison, emoji: "🏠"}
      - {de: die Küche, fr: la cuisine, bild: kueche.png}      # Bild aus dem ZIP
      - {de: die Schwester, fr: la sœur, auch: [la soeur]}     # weitere richtige Antworten
```

Eine Karte kann statt der Sprachschlüssel auch `frage` und `antwort` haben. Weitere Felder:

| Feld | Bedeutung |
| --- | --- |
| `emoji` / `bild` | Bild zur Frage (Emoji oder Dateiname im ZIP) |
| `auch` | weitere richtige Antworten (Liste oder `a | b`) |
| `optionen` | falsche Antworten für die Auswahl (sonst aus den anderen Karten) |
| `satz` | Satz mit `___` für den Lückentext |
| `hinweis` | Tipp, der bei der Frage steht |

## Mehrsprachige Pakete

Ein Paket kann in allen App-Sprachen erscheinen. Die Frage wird in der Sprache des Lernenden gezeigt (App-Sprache des
Geräts, sonst Familiensprache = Sprache des Elternbereichs, sonst Englisch, sonst die `quellsprache`); die Antwortseite
(`sprache`) bleibt. Der Lernfortschritt hängt an der Karte (Schlüssel aus der `quellsprache`), ein Sprachwechsel
verliert also nichts. Ein Sprachkurs wird nie in der Sprache gefragt, die er unterrichtet, und Lernenden mit dieser
Muttersprache gar nicht angeboten (kein Französischkurs für französischsprachige Kinder).

```yaml
quellsprache: de                       # Kanon: daraus entsteht der Kartenschlüssel – nicht nachträglich ändern
quellsprachen: [en, it, es, nl, pl, pt, sv]   # weitere Fragesprachen, die jede Karte trägt
titel_i18n: {de: "Französisch A1 – Einstieg", fr: "Français A1 – Débutant", …}
stufe_i18n: {de: "5. Klasse", fr: "5e année", …}
beschreibung_i18n: {fr: "…", …}
einheiten:
  - id: zahlen
    titel: Zahlen
    titel_i18n: {fr: "Les nombres", …}
    karten:
      - {de: eins, fr: un, en: one, it: uno, …}                       # Frage je nach Sprache, Antwort fr
      - {frage: "être – je", antwort: suis, satz: "Je ___ content."}  # neutral: gleich für alle
      - {frage: "Partizip – sehen", frage_i18n: {fr: "Participe – sehen", …}, antwort: gesehen, satz: "…"}
```

**Pakete in einer Sprache:** `optional: true` und `sprachen: [de]` – solche Pakete werden bei einer neuen Installation
nicht installiert, sondern stehen im Elternbereich unter **➕ Weitere Pakete** (Status `available`) und sind dort mit
der Inhaltssprache beschriftet. «Hinzufügen» macht sie aktiv, danach werden sie pro Kind eingeschaltet.

## Übungstypen

| `uebungen` | Lernform |
| --- | --- |
| `auswahl` | 2–4 farbige Antwortkacheln |
| `eintippen` | Antwort eintippen, mit Sondertasten é è à ç (je nach `sprache`) |
| `paare` | 4 Paare verbinden |
| `lueckentext` | Satz mit Lücke (`satz`), Auswahl |
| `hoeren` | Wort wird vorgesprochen (Sprachausgabe des Geräts), Bedeutung wählen |
| `karteikarte` | Karte umdrehen, selbst einschätzen |
| `zuordnen` | Drag & Drop: jede Karte in das richtige Feld ziehen. Die Felder sind die verschiedenen `antwort`-Werte, z. B. Gemeinde → Bezirk |

Ohne `uebungen` schlägt der Import passende Typen vor (wenige verschiedene Antworten → `zuordnen`).

## Generatoren (Mathematik)

```yaml
einheiten:
  - id: einmaleins
    titel: Einmaleins 6er bis 9er
    generator: einmaleins
    parameter: {reihen: "6-9", modus: gemischt}     # mal | geteilt | gemischt
```

| Generator | Parameter |
| --- | --- |
| `einmaleins` | `reihen` (Liste oder `"6-9"`), `modus`, `von`, `bis` |
| `division_rest` | `teiler`, `max_quotient`, `immer_rest` |
| `schriftlich` | `arten` (addieren, subtrahieren, multiplizieren, dividieren), `max`, `max_faktor`, `zweistellig` |
| `brueche` | `arten` (kuerzen, erweitern, addieren_gleich, addieren_ungleich, subtrahieren_ungleich, vergleichen, von_zahl), `nenner_max` |
| `brueche_kuerzen` | `nenner_max` |
| `dezimal` | `arten` (addieren, subtrahieren, mal10, durch10, runden, vergleichen), `stellen` |

Der Lernstand gilt pro Teilfähigkeit (z. B. «× 7», «+ ungleiche Nenner»); schwache Teilfähigkeiten kommen häufiger.

## Stufenpaket

```yaml
stufenpaket: tg-5-klasse
titel: 5. Klasse Thurgau
lehrplan: Lehrplan Volksschule Thurgau (Lehrplan 21)
faecher: [deutsch, mathematik, nmg, englisch, franzoesisch]
semester:
  - id: s1
    titel: 1. Semester
    pakete: [mathe-5kl, franz-5kl-la-maison, engl-5kl-unit-1, geo-tg, deutsch-5kl]
```

Wird ein Stufenpaket für ein Kind eingeschaltet, werden alle seine Pakete mit eingeschaltet.

## Tabellen (CSV/Excel)

Eine Zeile pro Karte, erste Zeile = Spaltennamen, z. B. `Deutsch;Französisch;Einheit;Bild`. Beim Import ordnest du die
Spalten zu (Frage, Antwort, Einheit, Bild/Emoji, Satz mit Lücke, Hinweis, auch richtig). Doppelte Karten werden
zusammengeführt.

## JSON

Jedes Paket und jedes Stufenpaket kann auch als JSON geschrieben werden – gleiche Felder wie in YAML.
Eine JSON-Datei darf ein Paket, eine Liste von Paketen oder `{"pakete": [...]}` enthalten.

| Was | Wie |
| --- | --- |
| Import Datei | Elternbereich › Import, oder `POST /api/parent/import/file` mit `.json` (auch innerhalb eines ZIP) |
| Import Daten | `POST /api/parent/import/json` mit dem JSON im Body |
| Export ein Paket | `GET /api/parent/packs/<id>/export?format=json` (oder `yaml`, `zip` mit Bildern) |
| Export alle | `GET /api/parent/packs/export` → `{"format": "family-quest-packs", "version": 1, "pakete": [...]}` – lässt sich als Ganzes wieder importieren |

Alle API-Aufrufe brauchen das Eltern-Token im Header `X-FQ-Parent` (aus `POST /api/parent/login` mit der Eltern-PIN).
Importiertes landet immer zuerst als Entwurf und wird erst nach dem Freigeben für Kinder sichtbar.
