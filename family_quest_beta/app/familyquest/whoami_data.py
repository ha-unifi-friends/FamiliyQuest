"""The characters of «Wer bin ich?» (whoami.py): categories with German names (content, not translated).

Every entry is "Name|alias|alias" – a guess counts when it matches the name or an alias (whoami.matches).
Only public-domain figures: traditional fairy tales and legends, historical persons who died long ago.
"""
from __future__ import annotations

_RAW = {
    "tiere": ("Tiere", "🐾", [
        "Elefant", "Giraffe", "Löwe|Loewe", "Tiger", "Zebra", "Krokodil", "Pinguin", "Eisbär|Eisbaer", "Känguru|Kaenguru|Kanguruh",
        "Affe|Schimpanse", "Hund", "Katze", "Pferd", "Kuh", "Schwein", "Schaf", "Ziege|Geiss", "Huhn|Henne", "Hase|Kaninchen",
        "Fuchs", "Wolf", "Bär|Baer|Braunbär", "Eichhörnchen|Eichhoernchen", "Igel", "Eule", "Adler", "Delfin|Delphin", "Hai|Haifisch",
        "Wal|Blauwal", "Schildkröte|Schildkroete", "Schlange", "Frosch", "Schmetterling", "Biene", "Marienkäfer|Marienkaefer",
        "Schnecke", "Kamel", "Nilpferd|Flusspferd", "Murmeltier", "Steinbock",
    ]),
    "berufe": ("Berufe", "👩‍🚒", [
        "Feuerwehrmann|Feuerwehrfrau|Feuerwehr", "Polizist|Polizistin|Polizei", "Arzt|Ärztin|Aerztin|Doktor", "Lehrer|Lehrerin",
        "Koch|Köchin|Koechin", "Bäcker|Bäckerin|Baecker", "Bauer|Bäuerin|Landwirt", "Pilot|Pilotin", "Astronaut|Astronautin",
        "Zahnarzt|Zahnärztin", "Tierarzt|Tierärztin", "Pöstler|Briefträger|Pöstlerin|Postbote", "Coiffeur|Friseur|Coiffeuse",
        "Gärtner|Gärtnerin|Gaertner", "Schreiner|Schreinerin|Tischler", "Maler|Malerin", "Musiker|Musikerin",
        "Krankenpfleger|Pflegefachfrau|Krankenschwester", "Mechaniker|Mechanikerin", "Kapitän|Kapitaen|Kapitänin",
        "Lokführer|Lokführerin|Lokfuehrer", "Buschauffeur|Busfahrer|Busfahrerin", "Verkäufer|Verkäuferin|Verkaeufer",
        "Bauarbeiter|Bauarbeiterin", "Förster|Försterin|Foerster", "Fotograf|Fotografin", "Zauberer|Zauberin|Magier",
        "Clown", "Tänzer|Tänzerin|Taenzer", "Metzger|Metzgerin|Fleischer", "Elektriker|Elektrikerin", "Bergführer|Bergführerin",
        "Richter|Richterin", "Journalist|Journalistin", "Kassierer|Kassiererin",
    ]),
    "essen": ("Essen & Früchte", "🍎", [
        "Apfel", "Banane", "Erdbeere", "Kirsche", "Birne", "Orange|Apfelsine", "Zitrone", "Ananas", "Wassermelone|Melone",
        "Traube|Trauben", "Pizza", "Spaghetti|Pasta", "Pommes|Pommes frites", "Rösti|Roesti", "Fondue", "Raclette",
        "Hamburger|Burger", "Bratwurst|Wurst", "Brot", "Zopf|Butterzopf", "Gipfeli|Croissant", "Käse|Kaese", "Schokolade",
        "Glace|Eis|Glacé", "Kuchen", "Rüebli|Karotte|Möhre|Ruebli", "Kartoffel|Härdöpfel", "Tomate", "Gurke", "Ei|Spiegelei",
        "Honig", "Popcorn", "Müesli|Muesli|Müsli", "Suppe", "Salat",
    ]),
    "laender": ("Länder", "🌍", [
        "Schweiz", "Deutschland", "Österreich|Oesterreich", "Frankreich", "Italien", "Spanien", "Portugal", "England|Grossbritannien",
        "Irland", "Niederlande|Holland", "Belgien", "Schweden", "Norwegen", "Dänemark|Daenemark", "Finnland", "Island", "Polen",
        "Griechenland", "Türkei|Tuerkei", "Ägypten|Aegypten", "Marokko", "Südafrika|Suedafrika", "Kenia", "USA|Amerika|Vereinigte Staaten",
        "Kanada", "Mexiko", "Brasilien", "Argentinien", "China", "Japan", "Indien", "Australien", "Neuseeland", "Russland", "Thailand",
    ]),
    "schweiz": ("Schweizer Orte & Berge", "🏔️", [
        "Zürich|Zuerich", "Bern", "Basel", "Genf", "Lausanne", "Luzern", "St. Gallen|Sankt Gallen", "Lugano", "Winterthur",
        "Chur", "Zug", "Schaffhausen", "Freiburg|Fribourg", "Neuenburg|Neuchâtel", "Sion|Sitten", "Bellinzona", "Locarno",
        "Interlaken", "Zermatt", "Davos", "St. Moritz|Sankt Moritz", "Grindelwald", "Appenzell", "Einsiedeln", "Matterhorn",
        "Eiger", "Jungfrau", "Pilatus", "Rigi", "Säntis|Saentis", "Titlis", "Gotthard", "Rheinfall", "Vierwaldstättersee",
        "Bodensee", "Genfersee|Lac Léman",
    ]),
    "maerchen": ("Märchen & Sagen", "🧚", [
        "Rotkäppchen|Rotkaeppchen", "Schneewittchen", "Hänsel|Haensel", "Gretel", "Aschenputtel", "Rumpelstilzchen", "Frau Holle",
        "Dornröschen|Dornroeschen", "Rapunzel", "Der gestiefelte Kater|Gestiefelter Kater", "Der Froschkönig|Froschkönig|Froschkoenig",
        "Pinocchio", "Heidi", "Wilhelm Tell|Tell", "Robin Hood", "König Artus|Koenig Artus|Artus", "Aladin", "Sindbad|Sindbad der Seefahrer",
        "Däumelinchen|Daeumelinchen", "Die kleine Meerjungfrau|Kleine Meerjungfrau|Meerjungfrau", "Der böse Wolf|Wolf|Böser Wolf",
        "Die sieben Geisslein|Sieben Geisslein|Geisslein", "Struwwelpeter", "Die Hexe|Hexe", "Der Rattenfänger von Hameln|Rattenfänger",
        "Das hässliche Entlein|Hässliches Entlein|Entlein", "Der Zwerg|Zwerg|Die sieben Zwerge", "Die Bremer Stadtmusikanten|Stadtmusikanten",
        "Max und Moritz", "Der Drache|Drache", "Die Schneekönigin|Schneekönigin", "Der Rübezahl|Rübezahl|Ruebezahl",
        "Ali Baba", "Münchhausen|Baron Münchhausen|Muenchhausen", "Merlin", "Der Riese|Riese",
    ]),
    "gegenstaende": ("Dinge im Haus", "🏠", [
        "Tisch", "Stuhl", "Bett", "Sofa|Couch", "Lampe", "Kühlschrank|Kuehlschrank", "Backofen|Ofen", "Waschmaschine", "Staubsauger",
        "Fernseher|Fernsehen|TV", "Telefon|Handy", "Uhr|Wecker", "Spiegel", "Zahnbürste|Zahnbuerste", "Badewanne", "Dusche",
        "Toilette|WC|Klo", "Teppich", "Fenster", "Türe|Tür|Tuer", "Schrank|Kasten", "Kissen|Kopfkissen", "Bettdecke|Decke|Duvet",
        "Pfanne", "Kochtopf|Topf", "Löffel|Loeffel", "Gabel", "Messer", "Teller", "Tasse", "Glas", "Schere", "Besen", "Regenschirm|Schirm",
        "Buch", "Kerze", "Bügeleisen|Buegeleisen", "Föhn|Haartrockner|Fön",
    ]),
    "sport": ("Sportarten", "⚽", [
        "Fussball|Fußball", "Tennis", "Skifahren|Ski", "Snowboard|Snowboarden", "Schwimmen", "Velofahren|Radfahren|Velo",
        "Eishockey", "Basketball", "Volleyball", "Handball", "Unihockey|Floorball", "Golf", "Reiten", "Turnen", "Leichtathletik",
        "Klettern", "Judo", "Karate", "Boxen", "Tischtennis|Pingpong", "Badminton|Federball", "Eiskunstlauf|Eislaufen",
        "Langlauf", "Rudern", "Segeln", "Surfen", "Tauchen", "Schwingen", "Hornussen", "Curling", "Bogenschiessen|Bogenschießen",
        "Fechten", "Rugby", "Baseball", "Skispringen", "Rollschuhfahren|Inlineskaten",
    ]),
    "personen": ("Berühmte Personen", "⭐", [
        "Albert Einstein|Einstein", "Wolfgang Amadeus Mozart|Mozart", "Leonardo da Vinci|Leonardo|Da Vinci", "Kleopatra|Cleopatra",
        "Napoleon|Napoleon Bonaparte", "Marie Curie|Curie", "Christoph Kolumbus|Kolumbus|Columbus", "Julius Caesar|Caesar|Cäsar",
        "Galileo Galilei|Galilei|Galileo", "Ludwig van Beethoven|Beethoven", "Henri Dunant|Dunant", "Johanna Spyri|Spyri",
        "Isaac Newton|Newton", "Charles Darwin|Darwin", "Florence Nightingale|Nightingale", "Johannes Gutenberg|Gutenberg",
        "Johann Sebastian Bach|Bach", "Michelangelo", "William Shakespeare|Shakespeare", "Johann Wolfgang von Goethe|Goethe",
        "Friedrich Schiller|Schiller", "Martin Luther|Luther", "Karl der Grosse|Karl der Große|Charlemagne", "Alexander der Grosse|Alexander der Große",
        "Marco Polo", "Jeanne d'Arc|Johanna von Orléans|Jeanne d Arc", "Tutanchamun", "Abraham Lincoln|Lincoln",
        "Rembrandt", "Vincent van Gogh|van Gogh", "Thomas Edison|Edison", "Nikola Tesla|Tesla", "Ferdinand Magellan|Magellan",
        "Mahatma Gandhi|Gandhi", "Pestalozzi|Johann Heinrich Pestalozzi", "Albert Anker|Anker",
    ]),
}

CATEGORIES: dict[str, dict] = {}
for _key, (_title, _emoji, _items) in _RAW.items():
    _chars = []
    for _s in _items:
        _name, *_aliases = [x.strip() for x in _s.split("|")]
        _chars.append({"name": _name, "aliases": _aliases})
    CATEGORIES[_key] = {"title": _title, "emoji": _emoji, "chars": _chars}

DEFAULT = "tiere"
