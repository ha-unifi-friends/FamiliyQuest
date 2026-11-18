"""The characters of «Wer bin ich?» (whoami.py): categories of things, animals, places and persons.

Every character is an English source text (_t – translated in web/i18n/<lang>.json, so the translation editor shows
it too); the game shows it in each player's language (gamewords.py). The second part is the German entry
"Name|alias|alias" of before the translation: running tables and history entries keep working (`legacy`), and these
German names count as right guesses when a German speaking player is at the table (whoami.Table.guess).
Only public-domain figures: traditional fairy tales and legends, historical persons who died long ago.
"""
from __future__ import annotations

from .i18n import _t

_RAW = {
    "tiere": (_t("Animals"), "🐾", [
        (_t("Elephant"), "Elefant"), (_t("Giraffe"), "Giraffe"),
        (_t("Lion"), "Löwe|Loewe"), (_t("Tiger"), "Tiger"),
        (_t("Zebra"), "Zebra"), (_t("Crocodile"), "Krokodil"),
        (_t("Penguin"), "Pinguin"), (_t("Polar bear"), "Eisbär|Eisbaer"),
        (_t("Kangaroo"), "Känguru|Kaenguru|Kanguruh"), (_t("Monkey"), "Affe|Schimpanse"),
        (_t("Dog"), "Hund"), (_t("Cat"), "Katze"),
        (_t("Horse"), "Pferd"), (_t("Cow"), "Kuh"),
        (_t("Pig"), "Schwein"), (_t("Sheep"), "Schaf"),
        (_t("Goat"), "Ziege|Geiss"), (_t("Chicken"), "Huhn|Henne"),
        (_t("Rabbit"), "Hase|Kaninchen"), (_t("Fox"), "Fuchs"),
        (_t("Wolf"), "Wolf"), (_t("Bear"), "Bär|Baer|Braunbär"),
        (_t("Squirrel"), "Eichhörnchen|Eichhoernchen"), (_t("Hedgehog"), "Igel"),
        (_t("Owl"), "Eule"), (_t("Eagle"), "Adler"),
        (_t("Dolphin"), "Delfin|Delphin"), (_t("Shark"), "Hai|Haifisch"),
        (_t("Whale"), "Wal|Blauwal"), (_t("Turtle"), "Schildkröte|Schildkroete"),
        (_t("Snake"), "Schlange"), (_t("Frog"), "Frosch"),
        (_t("Butterfly"), "Schmetterling"), (_t("Bee"), "Biene"),
        (_t("Ladybird"), "Marienkäfer|Marienkaefer"), (_t("Snail"), "Schnecke"),
        (_t("Camel"), "Kamel"), (_t("Hippo"), "Nilpferd|Flusspferd"),
        (_t("Marmot"), "Murmeltier"), (_t("Ibex"), "Steinbock"),
    ]),
    "berufe": (_t("Jobs"), "👩‍🚒", [
        (_t("Firefighter"), "Feuerwehrmann|Feuerwehrfrau|Feuerwehr"), (_t("Police officer"), "Polizist|Polizistin|Polizei"),
        (_t("Doctor"), "Arzt|Ärztin|Aerztin|Doktor"), (_t("Teacher"), "Lehrer|Lehrerin"),
        (_t("Cook"), "Koch|Köchin|Koechin"), (_t("Baker"), "Bäcker|Bäckerin|Baecker"),
        (_t("Farmer"), "Bauer|Bäuerin|Landwirt"), (_t("Pilot"), "Pilot|Pilotin"),
        (_t("Astronaut"), "Astronaut|Astronautin"), (_t("Dentist"), "Zahnarzt|Zahnärztin"),
        (_t("Vet"), "Tierarzt|Tierärztin"), (_t("Mail carrier"), "Pöstler|Briefträger|Pöstlerin|Postbote"),
        (_t("Hairdresser (job)"), "Coiffeur|Friseur|Coiffeuse"), (_t("Gardener"), "Gärtner|Gärtnerin|Gaertner"),
        (_t("Carpenter"), "Schreiner|Schreinerin|Tischler"), (_t("Painter"), "Maler|Malerin"),
        (_t("Musician"), "Musiker|Musikerin"), (_t("Nurse"), "Krankenpfleger|Pflegefachfrau|Krankenschwester"),
        (_t("Mechanic"), "Mechaniker|Mechanikerin"), (_t("Captain"), "Kapitän|Kapitaen|Kapitänin"),
        (_t("Train driver"), "Lokführer|Lokführerin|Lokfuehrer"), (_t("Bus driver"), "Buschauffeur|Busfahrer|Busfahrerin"),
        (_t("Salesperson"), "Verkäufer|Verkäuferin|Verkaeufer"), (_t("Construction worker"), "Bauarbeiter|Bauarbeiterin"),
        (_t("Forest ranger"), "Förster|Försterin|Foerster"), (_t("Photographer"), "Fotograf|Fotografin"),
        (_t("Magician"), "Zauberer|Zauberin|Magier"), (_t("Clown"), "Clown"),
        (_t("Dancer"), "Tänzer|Tänzerin|Taenzer"), (_t("Butcher"), "Metzger|Metzgerin|Fleischer"),
        (_t("Electrician"), "Elektriker|Elektrikerin"), (_t("Mountain guide"), "Bergführer|Bergführerin"),
        (_t("Judge"), "Richter|Richterin"), (_t("Journalist"), "Journalist|Journalistin"),
        (_t("Cashier"), "Kassierer|Kassiererin"),
    ]),
    "essen": (_t("Food & fruit"), "🍎", [
        (_t("Apple"), "Apfel"), (_t("Banana"), "Banane"),
        (_t("Strawberry"), "Erdbeere"), (_t("Cherry"), "Kirsche"),
        (_t("Pear"), "Birne"), (_t("Orange (fruit)"), "Orange|Apfelsine"),
        (_t("Lemon"), "Zitrone"), (_t("Pineapple"), "Ananas"),
        (_t("Watermelon"), "Wassermelone|Melone"), (_t("Grapes"), "Traube|Trauben"),
        (_t("Pizza"), "Pizza"), (_t("Spaghetti"), "Spaghetti|Pasta"),
        (_t("Fries"), "Pommes|Pommes frites"), (_t("Rösti"), "Rösti|Roesti"),
        (_t("Fondue"), "Fondue"), (_t("Raclette"), "Raclette"),
        (_t("Hamburger"), "Hamburger|Burger"), (_t("Sausage"), "Bratwurst|Wurst"),
        (_t("Bread"), "Brot"), (_t("Braided bread"), "Zopf|Butterzopf"),
        (_t("Croissant"), "Gipfeli|Croissant"), (_t("Cheese"), "Käse|Kaese"),
        (_t("Chocolate"), "Schokolade"), (_t("Ice cream"), "Glace|Eis|Glacé"),
        (_t("Cake"), "Kuchen"), (_t("Carrot"), "Rüebli|Karotte|Möhre|Ruebli"),
        (_t("Potato"), "Kartoffel|Härdöpfel"), (_t("Tomato"), "Tomate"),
        (_t("Cucumber"), "Gurke"), (_t("Egg"), "Ei|Spiegelei"),
        (_t("Honey"), "Honig"), (_t("Popcorn"), "Popcorn"),
        (_t("Muesli"), "Müesli|Muesli|Müsli"), (_t("Soup"), "Suppe"),
        (_t("Salad"), "Salat"),
    ]),
    "laender": (_t("Countries"), "🌍", [
        (_t("Switzerland"), "Schweiz"), (_t("Germany"), "Deutschland"),
        (_t("Austria"), "Österreich|Oesterreich"), (_t("France"), "Frankreich"),
        (_t("Italy"), "Italien"), (_t("Spain"), "Spanien"),
        (_t("Portugal"), "Portugal"), (_t("England"), "England|Grossbritannien"),
        (_t("Ireland"), "Irland"), (_t("Netherlands"), "Niederlande|Holland"),
        (_t("Belgium"), "Belgien"), (_t("Sweden"), "Schweden"),
        (_t("Norway"), "Norwegen"), (_t("Denmark"), "Dänemark|Daenemark"),
        (_t("Finland"), "Finnland"), (_t("Iceland"), "Island"),
        (_t("Poland"), "Polen"), (_t("Greece"), "Griechenland"),
        (_t("Turkey"), "Türkei|Tuerkei"), (_t("Egypt"), "Ägypten|Aegypten"),
        (_t("Morocco"), "Marokko"), (_t("South Africa"), "Südafrika|Suedafrika"),
        (_t("Kenya"), "Kenia"), (_t("USA"), "USA|Amerika|Vereinigte Staaten"),
        (_t("Canada"), "Kanada"), (_t("Mexico"), "Mexiko"),
        (_t("Brazil"), "Brasilien"), (_t("Argentina"), "Argentinien"),
        (_t("China"), "China"), (_t("Japan"), "Japan"),
        (_t("India"), "Indien"), (_t("Australia"), "Australien"),
        (_t("New Zealand"), "Neuseeland"), (_t("Russia"), "Russland"),
        (_t("Thailand"), "Thailand"),
    ]),
    "schweiz": (_t("Swiss places & mountains"), "🏔️", [
        (_t("Zurich"), "Zürich|Zuerich"), (_t("Bern"), "Bern"),
        (_t("Basel"), "Basel"), (_t("Geneva"), "Genf"),
        (_t("Lausanne"), "Lausanne"), (_t("Lucerne"), "Luzern"),
        (_t("St. Gallen"), "St. Gallen|Sankt Gallen"), (_t("Lugano"), "Lugano"),
        (_t("Winterthur"), "Winterthur"), (_t("Chur"), "Chur"),
        (_t("Zug"), "Zug"), (_t("Schaffhausen"), "Schaffhausen"),
        (_t("Fribourg"), "Freiburg|Fribourg"), (_t("Neuchâtel"), "Neuenburg|Neuchâtel"),
        (_t("Sion"), "Sion|Sitten"), (_t("Bellinzona"), "Bellinzona"),
        (_t("Locarno"), "Locarno"), (_t("Interlaken"), "Interlaken"),
        (_t("Zermatt"), "Zermatt"), (_t("Davos"), "Davos"),
        (_t("St. Moritz"), "St. Moritz|Sankt Moritz"), (_t("Grindelwald"), "Grindelwald"),
        (_t("Appenzell"), "Appenzell"), (_t("Einsiedeln"), "Einsiedeln"),
        (_t("Matterhorn"), "Matterhorn"), (_t("Eiger"), "Eiger"),
        (_t("Jungfrau"), "Jungfrau"), (_t("Pilatus"), "Pilatus"),
        (_t("Rigi"), "Rigi"), (_t("Säntis"), "Säntis|Saentis"),
        (_t("Titlis"), "Titlis"), (_t("Gotthard"), "Gotthard"),
        (_t("Rhine Falls"), "Rheinfall"), (_t("Lake Lucerne"), "Vierwaldstättersee"),
        (_t("Lake Constance"), "Bodensee"), (_t("Lake Geneva"), "Genfersee|Lac Léman"),
    ]),
    "maerchen": (_t("Fairy tales & legends"), "🧚", [
        (_t("Little Red Riding Hood"), "Rotkäppchen|Rotkaeppchen"), (_t("Snow White"), "Schneewittchen"),
        (_t("Hansel"), "Hänsel|Haensel"), (_t("Gretel"), "Gretel"),
        (_t("Cinderella"), "Aschenputtel"), (_t("Rumpelstiltskin"), "Rumpelstilzchen"),
        (_t("Mother Hulda"), "Frau Holle"), (_t("Sleeping Beauty"), "Dornröschen|Dornroeschen"),
        (_t("Rapunzel"), "Rapunzel"), (_t("Puss in Boots"), "Der gestiefelte Kater|Gestiefelter Kater"),
        (_t("The Frog Prince"), "Der Froschkönig|Froschkönig|Froschkoenig"), (_t("Pinocchio"), "Pinocchio"),
        (_t("Heidi"), "Heidi"), (_t("William Tell"), "Wilhelm Tell|Tell"),
        (_t("Robin Hood"), "Robin Hood"), (_t("King Arthur"), "König Artus|Koenig Artus|Artus"),
        (_t("Aladdin"), "Aladin"), (_t("Sinbad"), "Sindbad|Sindbad der Seefahrer"),
        (_t("Thumbelina"), "Däumelinchen|Daeumelinchen"), (_t("The Little Mermaid"), "Die kleine Meerjungfrau|Kleine Meerjungfrau|Meerjungfrau"),
        (_t("The Big Bad Wolf"), "Der böse Wolf|Wolf|Böser Wolf"), (_t("The Seven Little Goats"), "Die sieben Geisslein|Sieben Geisslein|Geisslein"),
        (_t("Shockheaded Peter"), "Struwwelpeter"), (_t("The Witch"), "Die Hexe|Hexe"),
        (_t("The Pied Piper of Hamelin"), "Der Rattenfänger von Hameln|Rattenfänger"), (_t("The Ugly Duckling"), "Das hässliche Entlein|Hässliches Entlein|Entlein"),
        (_t("The Dwarf"), "Der Zwerg|Zwerg|Die sieben Zwerge"), (_t("The Town Musicians of Bremen"), "Die Bremer Stadtmusikanten|Stadtmusikanten"),
        (_t("Max and Moritz"), "Max und Moritz"), (_t("The Dragon"), "Der Drache|Drache"),
        (_t("The Snow Queen"), "Die Schneekönigin|Schneekönigin"), (_t("Rübezahl"), "Der Rübezahl|Rübezahl|Ruebezahl"),
        (_t("Ali Baba"), "Ali Baba"), (_t("Baron Munchausen"), "Münchhausen|Baron Münchhausen|Muenchhausen"),
        (_t("Merlin"), "Merlin"), (_t("The Giant"), "Der Riese|Riese"),
    ]),
    "gegenstaende": (_t("Things at home"), "🏠", [
        (_t("Table (furniture)"), "Tisch"), (_t("Chair"), "Stuhl"),
        (_t("Bed"), "Bett"), (_t("Sofa"), "Sofa|Couch"),
        (_t("Lamp"), "Lampe"), (_t("Fridge"), "Kühlschrank|Kuehlschrank"),
        (_t("Oven"), "Backofen|Ofen"), (_t("Washing machine"), "Waschmaschine"),
        (_t("Vacuum cleaner"), "Staubsauger"), (_t("Television"), "Fernseher|Fernsehen|TV"),
        (_t("Telephone"), "Telefon|Handy"), (_t("Clock"), "Uhr|Wecker"),
        (_t("Mirror"), "Spiegel"), (_t("Toothbrush"), "Zahnbürste|Zahnbuerste"),
        (_t("Bathtub"), "Badewanne"), (_t("Shower"), "Dusche"),
        (_t("Toilet"), "Toilette|WC|Klo"), (_t("Carpet"), "Teppich"),
        (_t("Window"), "Fenster"), (_t("Door"), "Türe|Tür|Tuer"),
        (_t("Wardrobe"), "Schrank|Kasten"), (_t("Pillow"), "Kissen|Kopfkissen"),
        (_t("Duvet"), "Bettdecke|Decke|Duvet"), (_t("Frying pan"), "Pfanne"),
        (_t("Cooking pot"), "Kochtopf|Topf"), (_t("Spoon"), "Löffel|Loeffel"),
        (_t("Fork"), "Gabel"), (_t("Knife"), "Messer"),
        (_t("Plate"), "Teller"), (_t("Cup"), "Tasse"),
        (_t("Drinking glass"), "Glas"), (_t("Scissors"), "Schere"),
        (_t("Broom"), "Besen"), (_t("Umbrella"), "Regenschirm|Schirm"),
        (_t("Book (to read)"), "Buch"), (_t("Candle"), "Kerze"),
        (_t("Iron (for clothes)"), "Bügeleisen|Buegeleisen"), (_t("Hair dryer"), "Föhn|Haartrockner|Fön"),
    ]),
    "sport": (_t("Sports"), "⚽", [
        (_t("Football"), "Fussball|Fußball"), (_t("Tennis"), "Tennis"),
        (_t("Skiing"), "Skifahren|Ski"), (_t("Snowboarding"), "Snowboard|Snowboarden"),
        (_t("Swimming"), "Schwimmen"), (_t("Cycling"), "Velofahren|Radfahren|Velo"),
        (_t("Ice hockey"), "Eishockey"), (_t("Basketball"), "Basketball"),
        (_t("Volleyball"), "Volleyball"), (_t("Handball"), "Handball"),
        (_t("Floorball"), "Unihockey|Floorball"), (_t("Golf"), "Golf"),
        (_t("Horse riding"), "Reiten"), (_t("Gymnastics"), "Turnen"),
        (_t("Athletics"), "Leichtathletik"), (_t("Climbing"), "Klettern"),
        (_t("Judo"), "Judo"), (_t("Karate"), "Karate"),
        (_t("Boxing (sport)"), "Boxen"), (_t("Table tennis"), "Tischtennis|Pingpong"),
        (_t("Badminton"), "Badminton|Federball"), (_t("Figure skating"), "Eiskunstlauf|Eislaufen"),
        (_t("Cross-country skiing"), "Langlauf"), (_t("Rowing"), "Rudern"),
        (_t("Sailing"), "Segeln"), (_t("Surfing"), "Surfen"),
        (_t("Diving"), "Tauchen"), (_t("Swiss wrestling"), "Schwingen"),
        (_t("Hornussen"), "Hornussen"), (_t("Curling"), "Curling"),
        (_t("Archery"), "Bogenschiessen|Bogenschießen"), (_t("Fencing"), "Fechten"),
        (_t("Rugby"), "Rugby"), (_t("Baseball"), "Baseball"),
        (_t("Ski jumping"), "Skispringen"), (_t("Roller skating"), "Rollschuhfahren|Inlineskaten"),
    ]),
    "personen": (_t("Famous people"), "⭐", [
        (_t("Albert Einstein"), "Albert Einstein|Einstein"), (_t("Wolfgang Amadeus Mozart"), "Wolfgang Amadeus Mozart|Mozart"),
        (_t("Leonardo da Vinci"), "Leonardo da Vinci|Leonardo|Da Vinci"), (_t("Cleopatra"), "Kleopatra|Cleopatra"),
        (_t("Napoleon"), "Napoleon|Napoleon Bonaparte"), (_t("Marie Curie"), "Marie Curie|Curie"),
        (_t("Christopher Columbus"), "Christoph Kolumbus|Kolumbus|Columbus"), (_t("Julius Caesar"), "Julius Caesar|Caesar|Cäsar"),
        (_t("Galileo Galilei"), "Galileo Galilei|Galilei|Galileo"), (_t("Ludwig van Beethoven"), "Ludwig van Beethoven|Beethoven"),
        (_t("Henri Dunant"), "Henri Dunant|Dunant"), (_t("Johanna Spyri"), "Johanna Spyri|Spyri"),
        (_t("Isaac Newton"), "Isaac Newton|Newton"), (_t("Charles Darwin"), "Charles Darwin|Darwin"),
        (_t("Florence Nightingale"), "Florence Nightingale|Nightingale"), (_t("Johannes Gutenberg"), "Johannes Gutenberg|Gutenberg"),
        (_t("Johann Sebastian Bach"), "Johann Sebastian Bach|Bach"), (_t("Michelangelo"), "Michelangelo"),
        (_t("William Shakespeare"), "William Shakespeare|Shakespeare"), (_t("Johann Wolfgang von Goethe"), "Johann Wolfgang von Goethe|Goethe"),
        (_t("Friedrich Schiller"), "Friedrich Schiller|Schiller"), (_t("Martin Luther"), "Martin Luther|Luther"),
        (_t("Charlemagne"), "Karl der Grosse|Karl der Große|Charlemagne"), (_t("Alexander the Great"), "Alexander der Grosse|Alexander der Große"),
        (_t("Marco Polo"), "Marco Polo"), (_t("Joan of Arc"), "Jeanne d'Arc|Johanna von Orléans|Jeanne d Arc"),
        (_t("Tutankhamun"), "Tutanchamun"), (_t("Abraham Lincoln"), "Abraham Lincoln|Lincoln"),
        (_t("Rembrandt"), "Rembrandt"), (_t("Vincent van Gogh"), "Vincent van Gogh|van Gogh"),
        (_t("Thomas Edison"), "Thomas Edison|Edison"), (_t("Nikola Tesla"), "Nikola Tesla|Tesla"),
        (_t("Ferdinand Magellan"), "Ferdinand Magellan|Magellan"), (_t("Mahatma Gandhi"), "Mahatma Gandhi|Gandhi"),
        (_t("Johann Heinrich Pestalozzi"), "Pestalozzi|Johann Heinrich Pestalozzi"), (_t("Albert Anker"), "Albert Anker|Anker"),
    ]),
}

CATEGORIES: dict[str, dict] = {}
LEGACY: dict[str, str] = {}          # an old German name or alias → its key (main names first)
for _key, (_title, _emoji, _items) in _RAW.items():
    _list = []
    for _name, _de in _items:
        _german = [x.strip() for x in _de.split("|")]
        _list.append({"name": _name, "aliases": _german})
        LEGACY.setdefault(_german[0], _name)
    CATEGORIES[_key] = {"title": _title, "emoji": _emoji, "chars": _list}
for _c in CATEGORIES.values():
    for _w in _c["chars"]:
        for _a in _w["aliases"][1:]:
            LEGACY.setdefault(_a, _w["name"])
KEYS = {_w["name"] for _c in CATEGORIES.values() for _w in _c["chars"]}


def legacy(name: str) -> str:
    """The key of a word from a table or history entry of before the translation (German); a key stays as it is."""
    if not isinstance(name, str) or name in KEYS:
        return name
    return LEGACY.get(name, name)

DEFAULT = "tiere"
