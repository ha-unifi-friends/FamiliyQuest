# Family Planer in Family Quest – Etappenplan

Ziel: Alle Funktionen des [Family Planer](https://github.com/magi1982/family-planer) (MIT, magibuilds) laufen in
Family Quest – eine App statt zwei. Der Code wird übernommen und an die Architektur von Family Quest angepasst
(FastAPI + SQLite als HA-App, Home Assistant nur über REST/WebSocket). Bestehende Planer-Daten lassen sich importieren.

## Etappen

| Etappe | Inhalt | Stand |
|---|---|---|
| **A – Logik** | Reine Logik unverändert übernommen nach `familyquest/planer/` (engine, schedule, rewards, awards, levels, sonder, seasons, vacation, lists, msgqueue, persontodos, speech, validate, settings_spec, const) inkl. der 114 Planer-Tests (`tests/planer/`) und den Oberflächen-Quellen (`web/planer/src/`) | ✅ |
| **B – Planer-Kern** | `planner.py` portiert: Speicher in SQLite (ein JSON-Dokument wie der HA-Store), Tageswechsel, Mutationen (Ämtli, Personen, Belohnungen, To-dos, Sonderämtli, Ferien-Entscheide, PIN), Snapshot; Zeitsteuerung mit asyncio statt `async_track_*` | ✅ |
| **C – Home Assistant** | Kalender (`calendar.get_events`), To-do-Listen (`todo.get_items`/`update_item`, Statusänderungen), Wetter, KI-Aufgabe (`ai_task.generate_data`), Ansagen (`tts.speak`/`notify.send_message`, Bewegungsmelder), Mitteilungen | Grundlage ✅ (Zustände, Dienste mit Antwort, Zeitzone, Sprache); Feinschliff offen |
| **D – Oberfläche** | Planer-Oberfläche (Wochenplan, Heute, Ämtliplan, Listen, Belohnungen, Einstellungen, Sonderämtli, To-dos, Avatar-Baukasten, Saisons, Designs) in der Web-App von Family Quest: WebSocket-Endpunkt im HA-Format, `hass`-Brücke, `ha-icon`-Ersatz mit MDI-Symbolen | offen |
| **E – Zusammenführen** | Ein Personen-/Profilsystem (Planer-Personen = Family-Quest-Profile), ein Punktekonto (Planer-Punkte = Batzen, Level/Auszeichnungen gemeinsam), Belohnungs-Shop vereint, Avatar: Planer-Baukasten für alle; eigener einfacher Ämtliplan von Family Quest geht im Planer-Ämtliplan auf | Beta 0.3.0-beta.3 ✅ (Personen = Profile, Punkte = gemeinsames Konto; eigener FQ-Ämtliplan bleibt vorerst daneben) |
| **F – Import** | Einmaliger Import aus `/homeassistant/.storage/family_planer.<entry_id>` (Personen, Ämtliplan, besondere Ämtli, Verlauf, Punkte, Belohnungen, Listen, Avatare, Einstellungen); Hinweis zum Deinstallieren des Planers | Beta 0.3.0-beta.3 ✅ (aus HA-Konfiguration oder Datei-Upload, Fotos, Punkte zusammengezählt) |
| **G – Übersetzungen** | Planer-Texte (heute Deutsch/Englisch) ins i18n-System von Family Quest (9 Sprachen) | Beta 0.3.0-beta.8 ✅ (Deutsch: Planer-Originaltexte; andere Sprachen: englische Planer-Texte + `i18n/planer/<lang>.json`, Schlüssel mit `tools/planer_i18n_keys.js` sammeln) |
| **H – Gemeinschaft** | Neuer Bereich: Gesellschaftsspiele in Echtzeit (eigene Namen und Gestaltung, nur freie Mechaniken – «Heimwärts» nach Pachisi/Ludo, «Kartenlauf» nach Tock, «Dorfmarkt» nach The Landlord's Game, Jass, Tschau Sepp, Mühle, Dame, Vier in einer Reihe, Seeschlacht, Paare finden, Fünf Würfel, Zeichnen & Raten, Verbotene Wörter, Werwölfe), «Familienquiz» (Fragen vorbereiten, alle spielen live mit) und «Familienrat» (Vorschläge sammeln, abstimmen); Spielgewinne und Abstimmungsergebnisse im persönlichen Verlauf | teilweise: Familienquiz (mit Vorlagen, Kinder erstellen eigene Quizze), Familienrat und Verlauf in Beta 0.3.0-beta.9 ✅ – Brett- und Kartenspiele offen |
| **S – Sichern & Wiederherstellen** | Alles (Datenbank inkl. Planer-Daten, Pakete, Bilder, Einstellungen) in eine Datei sichern und daraus wiederherstellen, im Elternbereich | als Nächstes |

## Lizenz

Übernommene Dateien tragen einen Herkunftsvermerk; der Lizenztext liegt bei
`family_quest/app/familyquest/planer/LICENSE.family-planer` und `family_quest/app/web/planer/LICENSE.family-planer`.

## Notizen Etappe H – «Dorfmarkt» (Mechanik nach The Landlord's Game, eigene Begriffe und Gestaltung)

- **Spielort wählbar:** Land (Schweiz, Deutschland, Österreich, …) und Gliedstaat (Kanton, Bundesland); das Brett
  wird aus den grösseren Orten und Strassen gebaut, z. B. Kanton Thurgau (Frauenfeld, Kreuzlingen, Arbon, Weinfelden, …).
  Ortsdaten als Pakete (wie Lernpakete), erweiterbar.
- **Ein Kartenstapel** «Ereigniskarten» mit guten und harten Karten; Inhalt und Mischung (mehr gute / mehr harte) einstellbar.
- **Hausregeln editierbar:** Startgeld, Lohn pro Runde, Mieten/Bauen, wie man aus der «Pause-Ecke» kommt
  (Pasch würfeln, zahlen, Runden aussetzen), Ende des Spiels (Zeit, Runden, Bankrott).
- **Robotaxi-Stationen** statt Bahnhöfe.
- Eigene Begriffe und eigenes Brettbild; keine Original-Namen, -Texte oder -Feldbezeichnungen.

## Notizen Etappe H – «Kartenlauf» (Mechanik nach Tock) und Jass

- **Kartenlauf:** Hausregeln: mit der 7 alle Figuren / nur eigene / alle im Team ziehen; Joker darf (nicht) die letzte,
  gewinnende Karte sein. Virtuelle Mitspieler: Anzahl wählbar, Stärke in 3 Stufen.
- **Jass (Schieber):** virtuelle Mitspieler in 3 Stärken; Deutschschweizer oder französische Karten; Trumpf-Wertungen,
  Stöck/Wys/Stich oder eigene Hausregeln; Jassteppich wählbar: klassisch grün, grün mit den 4 Farben (deutsch / französisch),
  mit Home-Assistant-Logo (Markenrichtlinien vor Veröffentlichung prüfen, sonst neutraler Smart-Home-Teppich), mit Familienwappen.
- **Familienwappen** in den allgemeinen Einstellungen hochladen (auch für Teppich, Startseite, Urkunden nutzbar).
- **Kartenrücken** für alle Kartenspiele (Jass, Tschau Sepp, Kartenlauf, Paare finden) wählbar: klassische Muster in
  mehreren Farben, Familienwappen, eigenes Foto (Upload) – pro Spiel oder als Standard in den allgemeinen Einstellungen.
- **Paare finden (Spiel):** eigene Fotosätze hochladen (z. B. Familie, Ferien); dieselbe Foto-Ablage wie bei den
  Lernkarten. In den Lernpaketen gibt es eigene Fotos bereits (Karteneditor → 📷, Übung «Paare»).

## Release-Ablauf (Beta → stabil)

Beide Apps liegen in diesem Repository (HA zeigt sie nebeneinander): `family_quest/` (stabil) und
`family_quest_beta/` (Beta, Slug `family_quest_beta`, Icon mit «BETA»-Band aus `tools/beta/`).
Entwickelt wird auf dem Arbeitsbranch; `main` ist das, was Home Assistant installiert.

1. Beta: `python3 tools/release.py beta 0.3.0-beta.N "Neu: …"` – schreibt `family_quest_beta/` aus dem aktuellen
   Stand, committet und bringt **nur** diesen Ordner auf `main`. HA bietet das Update für «Family Quest Beta» an.
2. Stabil: Version in `family_quest/config.yaml` erhöhen, Changelog, committen, dann `python3 tools/release.py stable`
   – `main` bekommt den ganzen Stand des Arbeitsbranchs.
