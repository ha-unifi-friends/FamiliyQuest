"""The words of «Zeichnen & Raten» (zeichnen.py): simple, kid-friendly words that can be drawn – German content, not
translated.

Every entry is "Word|alias|alias" – a guess counts when it matches the word or an alias (zeichnen.check). The keys of
the categories are the ones of «Wer bin ich?» (whoami_data.py) where they make sense for drawing, plus «gemischt».
"""
from __future__ import annotations

_RAW = {
    "tiere": ("Tiere", "🐾", [
        "Elefant", "Giraffe", "Löwe", "Tiger", "Zebra", "Krokodil", "Pinguin", "Eisbär", "Känguru|Kaenguruh", "Affe",
        "Hund", "Katze", "Pferd", "Kuh", "Schwein", "Schaf", "Ziege|Geiss", "Huhn|Henne", "Hase|Kaninchen", "Fuchs",
        "Bär", "Igel", "Eule", "Delfin|Delphin", "Hai|Haifisch", "Wal", "Schildkröte", "Schlange", "Frosch", "Schmetterling",
        "Biene", "Marienkäfer", "Schnecke", "Kamel", "Maus", "Fisch", "Vogel", "Ente", "Spinne", "Krebs",
        "Qualle", "Raupe", "Hirsch", "Nilpferd|Flusspferd",
    ]),
    "berufe": ("Berufe", "👩‍🚒", [
        "Feuerwehrmann|Feuerwehrfrau|Feuerwehr", "Polizist|Polizistin|Polizei", "Arzt|Ärztin|Doktor", "Lehrer|Lehrerin",
        "Koch|Köchin", "Bäcker|Bäckerin", "Bauer|Bäuerin|Landwirt", "Pilot|Pilotin", "Astronaut|Astronautin",
        "Zahnarzt|Zahnärztin", "Tierarzt|Tierärztin", "Pöstler|Briefträger|Postbote", "Coiffeur|Friseur|Coiffeuse",
        "Gärtner|Gärtnerin", "Schreiner|Tischler", "Maler|Malerin", "Musiker|Musikerin", "Mechaniker|Mechanikerin",
        "Kapitän|Kapitänin", "Lokführer|Lokführerin", "Busfahrer|Buschauffeur|Busfahrerin", "Verkäufer|Verkäuferin",
        "Bauarbeiter|Bauarbeiterin", "Förster|Försterin", "Fotograf|Fotografin", "Zauberer|Zauberin", "Clown",
        "Tänzer|Tänzerin", "Metzger|Metzgerin", "Elektriker|Elektrikerin", "Taucher|Taucherin", "Pirat|Piratin",
        "Ritter", "König|Königin", "Prinzessin|Prinz", "Detektiv|Detektivin", "Sänger|Sängerin", "Fischer|Fischerin",
        "Imker|Imkerin", "Kaminfeger|Schornsteinfeger",
    ]),
    "essen": ("Essen & Früchte", "🍎", [
        "Apfel", "Banane", "Erdbeere", "Kirsche", "Birne", "Orange|Apfelsine", "Zitrone", "Ananas", "Wassermelone|Melone",
        "Traube|Trauben", "Pizza", "Spaghetti|Pasta|Nudeln", "Pommes|Pommes frites", "Hamburger|Burger", "Wurst|Bratwurst",
        "Brot", "Gipfeli|Croissant", "Käse", "Schokolade", "Glace|Eis|Glacé", "Kuchen", "Torte", "Rüebli|Karotte|Möhre",
        "Kartoffel", "Tomate", "Gurke", "Ei|Spiegelei", "Honig", "Popcorn", "Suppe", "Salat", "Brezel|Bretzel",
        "Sandwich", "Lollipop|Lutscher", "Donut|Krapfen", "Pilz", "Zwiebel", "Paprika|Peperoni", "Mais|Maiskolben",
        "Muffin|Cupcake", "Kokosnuss", "Hotdog",
    ]),
    "gegenstaende": ("Dinge im Haus", "🏠", [
        "Tisch", "Stuhl", "Bett", "Sofa|Couch", "Lampe", "Kühlschrank", "Backofen|Ofen", "Waschmaschine", "Staubsauger",
        "Fernseher|TV", "Telefon|Handy", "Uhr|Wecker", "Spiegel", "Zahnbürste", "Badewanne", "Dusche", "Toilette|WC|Klo",
        "Teppich", "Fenster", "Türe|Tür", "Schrank|Kasten", "Kissen|Kopfkissen", "Pfanne", "Kochtopf|Topf", "Löffel",
        "Gabel", "Messer", "Teller", "Tasse", "Glas", "Schere", "Besen", "Regenschirm|Schirm", "Buch", "Kerze",
        "Bügeleisen", "Föhn|Haartrockner|Fön", "Schlüssel", "Treppe", "Bild|Gemälde", "Vorhang", "Blumentopf",
    ]),
    "sport": ("Sportarten", "⚽", [
        "Fussball|Fußball", "Tennis", "Skifahren|Ski", "Snowboard|Snowboarden", "Schwimmen", "Velofahren|Radfahren|Velo|Fahrrad",
        "Eishockey", "Basketball", "Volleyball", "Handball", "Golf", "Reiten", "Turnen", "Klettern", "Judo", "Karate",
        "Boxen", "Tischtennis|Pingpong", "Badminton|Federball", "Eislaufen|Eiskunstlauf|Schlittschuh", "Langlauf", "Rudern",
        "Segeln", "Surfen", "Tauchen", "Schwingen", "Curling", "Bogenschiessen|Bogenschießen", "Fechten", "Rugby",
        "Baseball", "Skispringen", "Inlineskaten|Rollschuhfahren", "Skateboard|Skateboarden", "Kanu|Kanufahren|Paddeln",
        "Bowling|Kegeln", "Seilspringen|Seilhüpfen", "Trampolin", "Wandern", "Joggen|Laufen|Rennen", "Yoga",
    ]),
    "gemischt": ("Gemischt", "🎲", [
        "Haus", "Baum", "Sonne", "Mond", "Stern", "Wolke", "Regenbogen", "Blume", "Auto", "Zug|Eisenbahn", "Flugzeug",
        "Schiff|Boot", "Rakete", "Ballon|Luftballon", "Drachen", "Schneemann", "Burg|Schloss", "Krone", "Herz", "Brille",
        "Hut", "Schuh", "Socke", "Hose", "Geschenk", "Kuchen", "Ball", "Berg", "Insel", "Zelt", "Leiter", "Fahrrad|Velo",
        "Gitarre", "Trommel", "Glocke", "Schatztruhe|Schatz", "Roboter", "Gespenst|Geist", "Hexe", "Drache", "Einhorn",
        "Kaktus", "Pilz", "Blitz", "Regen", "Schneeflocke", "Vulkan", "Leuchtturm", "Brücke", "Anker",
    ]),
}

CATEGORIES: dict[str, dict] = {}
for _key, (_title, _emoji, _items) in _RAW.items():
    _words = []
    for _s in _items:
        _name, *_aliases = [x.strip() for x in _s.split("|")]
        _words.append({"name": _name, "aliases": _aliases})
    CATEGORIES[_key] = {"title": _title, "emoji": _emoji, "words": _words}

DEFAULT = "gemischt"
