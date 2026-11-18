"""The words of «Zeichnen & Raten» (zeichnen.py): simple, kid-friendly words that can be drawn.

Every word is an English source text (_t – translated in web/i18n/<lang>.json, so the translation editor shows it too);
the game shows it in each player's language (gamewords.py). The second part is the German entry "Wort|alias|alias" of
before the translation: running tables and history entries with German words keep working (`legacy`), and these
German names count as right guesses for German speaking players (zeichnen.Table.guess). The keys of the categories are
the ones of «Wer bin ich?» (whoami_data.py) where they make sense for drawing, plus «gemischt».
"""
from __future__ import annotations

from .i18n import _t

_RAW = {
    "tiere": (_t("Animals"), "🐾", [
        (_t("Elephant"), "Elefant"), (_t("Giraffe"), "Giraffe"),
        (_t("Lion"), "Löwe"), (_t("Tiger"), "Tiger"),
        (_t("Zebra"), "Zebra"), (_t("Crocodile"), "Krokodil"),
        (_t("Penguin"), "Pinguin"), (_t("Polar bear"), "Eisbär"),
        (_t("Kangaroo"), "Känguru|Kaenguruh"), (_t("Monkey"), "Affe"),
        (_t("Dog"), "Hund"), (_t("Cat"), "Katze"),
        (_t("Horse"), "Pferd"), (_t("Cow"), "Kuh"),
        (_t("Pig"), "Schwein"), (_t("Sheep"), "Schaf"),
        (_t("Goat"), "Ziege|Geiss"), (_t("Chicken"), "Huhn|Henne"),
        (_t("Rabbit"), "Hase|Kaninchen"), (_t("Fox"), "Fuchs"),
        (_t("Bear"), "Bär"), (_t("Hedgehog"), "Igel"),
        (_t("Owl"), "Eule"), (_t("Dolphin"), "Delfin|Delphin"),
        (_t("Shark"), "Hai|Haifisch"), (_t("Whale"), "Wal"),
        (_t("Turtle"), "Schildkröte"), (_t("Snake"), "Schlange"),
        (_t("Frog"), "Frosch"), (_t("Butterfly"), "Schmetterling"),
        (_t("Bee"), "Biene"), (_t("Ladybird"), "Marienkäfer"),
        (_t("Snail"), "Schnecke"), (_t("Camel"), "Kamel"),
        (_t("Mouse"), "Maus"), (_t("Fish"), "Fisch"),
        (_t("Bird"), "Vogel"), (_t("Duck"), "Ente"),
        (_t("Spider"), "Spinne"), (_t("Crab"), "Krebs"),
        (_t("Jellyfish"), "Qualle"), (_t("Caterpillar"), "Raupe"),
        (_t("Deer"), "Hirsch"), (_t("Hippo"), "Nilpferd|Flusspferd"),
    ]),
    "berufe": (_t("Jobs"), "👩‍🚒", [
        (_t("Firefighter"), "Feuerwehrmann|Feuerwehrfrau|Feuerwehr"), (_t("Police officer"), "Polizist|Polizistin|Polizei"),
        (_t("Doctor"), "Arzt|Ärztin|Doktor"), (_t("Teacher"), "Lehrer|Lehrerin"),
        (_t("Cook"), "Koch|Köchin"), (_t("Baker"), "Bäcker|Bäckerin"),
        (_t("Farmer"), "Bauer|Bäuerin|Landwirt"), (_t("Pilot"), "Pilot|Pilotin"),
        (_t("Astronaut"), "Astronaut|Astronautin"), (_t("Dentist"), "Zahnarzt|Zahnärztin"),
        (_t("Vet"), "Tierarzt|Tierärztin"), (_t("Mail carrier"), "Pöstler|Briefträger|Postbote"),
        (_t("Hairdresser (job)"), "Coiffeur|Friseur|Coiffeuse"), (_t("Gardener"), "Gärtner|Gärtnerin"),
        (_t("Carpenter"), "Schreiner|Tischler"), (_t("Painter"), "Maler|Malerin"),
        (_t("Musician"), "Musiker|Musikerin"), (_t("Mechanic"), "Mechaniker|Mechanikerin"),
        (_t("Captain"), "Kapitän|Kapitänin"), (_t("Train driver"), "Lokführer|Lokführerin"),
        (_t("Bus driver"), "Busfahrer|Buschauffeur|Busfahrerin"), (_t("Salesperson"), "Verkäufer|Verkäuferin"),
        (_t("Construction worker"), "Bauarbeiter|Bauarbeiterin"), (_t("Forest ranger"), "Förster|Försterin"),
        (_t("Photographer"), "Fotograf|Fotografin"), (_t("Magician"), "Zauberer|Zauberin"),
        (_t("Clown"), "Clown"), (_t("Dancer"), "Tänzer|Tänzerin"),
        (_t("Butcher"), "Metzger|Metzgerin"), (_t("Electrician"), "Elektriker|Elektrikerin"),
        (_t("Diver"), "Taucher|Taucherin"), (_t("Pirate"), "Pirat|Piratin"),
        (_t("Knight"), "Ritter"), (_t("King"), "König|Königin"),
        (_t("Princess"), "Prinzessin|Prinz"), (_t("Detective"), "Detektiv|Detektivin"),
        (_t("Singer"), "Sänger|Sängerin"), (_t("Fisherman"), "Fischer|Fischerin"),
        (_t("Beekeeper"), "Imker|Imkerin"), (_t("Chimney sweep"), "Kaminfeger|Schornsteinfeger"),
    ]),
    "essen": (_t("Food & fruit"), "🍎", [
        (_t("Apple"), "Apfel"), (_t("Banana"), "Banane"),
        (_t("Strawberry"), "Erdbeere"), (_t("Cherry"), "Kirsche"),
        (_t("Pear"), "Birne"), (_t("Orange (fruit)"), "Orange|Apfelsine"),
        (_t("Lemon"), "Zitrone"), (_t("Pineapple"), "Ananas"),
        (_t("Watermelon"), "Wassermelone|Melone"), (_t("Grapes"), "Traube|Trauben"),
        (_t("Pizza"), "Pizza"), (_t("Spaghetti"), "Spaghetti|Pasta|Nudeln"),
        (_t("Fries"), "Pommes|Pommes frites"), (_t("Hamburger"), "Hamburger|Burger"),
        (_t("Sausage"), "Wurst|Bratwurst"), (_t("Bread"), "Brot"),
        (_t("Croissant"), "Gipfeli|Croissant"), (_t("Cheese"), "Käse"),
        (_t("Chocolate"), "Schokolade"), (_t("Ice cream"), "Glace|Eis|Glacé"),
        (_t("Cake"), "Kuchen"), (_t("Layer cake"), "Torte"),
        (_t("Carrot"), "Rüebli|Karotte|Möhre"), (_t("Potato"), "Kartoffel"),
        (_t("Tomato"), "Tomate"), (_t("Cucumber"), "Gurke"),
        (_t("Egg"), "Ei|Spiegelei"), (_t("Honey"), "Honig"),
        (_t("Popcorn"), "Popcorn"), (_t("Soup"), "Suppe"),
        (_t("Salad"), "Salat"), (_t("Pretzel"), "Brezel|Bretzel"),
        (_t("Sandwich"), "Sandwich"), (_t("Lollipop"), "Lollipop|Lutscher"),
        (_t("Donut"), "Donut|Krapfen"), (_t("Mushroom"), "Pilz"),
        (_t("Onion"), "Zwiebel"), (_t("Bell pepper"), "Paprika|Peperoni"),
        (_t("Corn"), "Mais|Maiskolben"), (_t("Muffin"), "Muffin|Cupcake"),
        (_t("Coconut"), "Kokosnuss"), (_t("Hot dog"), "Hotdog"),
    ]),
    "gegenstaende": (_t("Things at home"), "🏠", [
        (_t("Table (furniture)"), "Tisch"), (_t("Chair"), "Stuhl"),
        (_t("Bed"), "Bett"), (_t("Sofa"), "Sofa|Couch"),
        (_t("Lamp"), "Lampe"), (_t("Fridge"), "Kühlschrank"),
        (_t("Oven"), "Backofen|Ofen"), (_t("Washing machine"), "Waschmaschine"),
        (_t("Vacuum cleaner"), "Staubsauger"), (_t("Television"), "Fernseher|TV"),
        (_t("Telephone"), "Telefon|Handy"), (_t("Clock"), "Uhr|Wecker"),
        (_t("Mirror"), "Spiegel"), (_t("Toothbrush"), "Zahnbürste"),
        (_t("Bathtub"), "Badewanne"), (_t("Shower"), "Dusche"),
        (_t("Toilet"), "Toilette|WC|Klo"), (_t("Carpet"), "Teppich"),
        (_t("Window"), "Fenster"), (_t("Door"), "Türe|Tür"),
        (_t("Wardrobe"), "Schrank|Kasten"), (_t("Pillow"), "Kissen|Kopfkissen"),
        (_t("Frying pan"), "Pfanne"), (_t("Cooking pot"), "Kochtopf|Topf"),
        (_t("Spoon"), "Löffel"), (_t("Fork"), "Gabel"),
        (_t("Knife"), "Messer"), (_t("Plate"), "Teller"),
        (_t("Cup"), "Tasse"), (_t("Drinking glass"), "Glas"),
        (_t("Scissors"), "Schere"), (_t("Broom"), "Besen"),
        (_t("Umbrella"), "Regenschirm|Schirm"), (_t("Book (to read)"), "Buch"),
        (_t("Candle"), "Kerze"), (_t("Iron (for clothes)"), "Bügeleisen"),
        (_t("Hair dryer"), "Föhn|Haartrockner|Fön"), (_t("Key"), "Schlüssel"),
        (_t("Stairs"), "Treppe"), (_t("Painting"), "Bild|Gemälde"),
        (_t("Curtain"), "Vorhang"), (_t("Flowerpot"), "Blumentopf"),
    ]),
    "sport": (_t("Sports"), "⚽", [
        (_t("Football"), "Fussball|Fußball"), (_t("Tennis"), "Tennis"),
        (_t("Skiing"), "Skifahren|Ski"), (_t("Snowboarding"), "Snowboard|Snowboarden"),
        (_t("Swimming"), "Schwimmen"), (_t("Cycling"), "Velofahren|Radfahren|Velo|Fahrrad"),
        (_t("Ice hockey"), "Eishockey"), (_t("Basketball"), "Basketball"),
        (_t("Volleyball"), "Volleyball"), (_t("Handball"), "Handball"),
        (_t("Golf"), "Golf"), (_t("Horse riding"), "Reiten"),
        (_t("Gymnastics"), "Turnen"), (_t("Climbing"), "Klettern"),
        (_t("Judo"), "Judo"), (_t("Karate"), "Karate"),
        (_t("Boxing (sport)"), "Boxen"), (_t("Table tennis"), "Tischtennis|Pingpong"),
        (_t("Badminton"), "Badminton|Federball"), (_t("Ice skating"), "Eislaufen|Eiskunstlauf|Schlittschuh"),
        (_t("Cross-country skiing"), "Langlauf"), (_t("Rowing"), "Rudern"),
        (_t("Sailing"), "Segeln"), (_t("Surfing"), "Surfen"),
        (_t("Diving"), "Tauchen"), (_t("Swiss wrestling"), "Schwingen"),
        (_t("Curling"), "Curling"), (_t("Archery"), "Bogenschiessen|Bogenschießen"),
        (_t("Fencing"), "Fechten"), (_t("Rugby"), "Rugby"),
        (_t("Baseball"), "Baseball"), (_t("Ski jumping"), "Skispringen"),
        (_t("Inline skating"), "Inlineskaten|Rollschuhfahren"), (_t("Skateboard"), "Skateboard|Skateboarden"),
        (_t("Canoe"), "Kanu|Kanufahren|Paddeln"), (_t("Bowling"), "Bowling|Kegeln"),
        (_t("Jump rope"), "Seilspringen|Seilhüpfen"), (_t("Trampoline"), "Trampolin"),
        (_t("Hiking"), "Wandern"), (_t("Jogging"), "Joggen|Laufen|Rennen"),
        (_t("Yoga"), "Yoga"),
    ]),
    "gemischt": (_t("Mixed"), "🎲", [
        (_t("House"), "Haus"), (_t("Tree"), "Baum"),
        (_t("Sun (in the sky)"), "Sonne"), (_t("Moon"), "Mond"),
        (_t("Star"), "Stern"), (_t("Cloud"), "Wolke"),
        (_t("Rainbow"), "Regenbogen"), (_t("Flower"), "Blume"),
        (_t("Car"), "Auto"), (_t("Train"), "Zug|Eisenbahn"),
        (_t("Airplane"), "Flugzeug"), (_t("Ship"), "Schiff|Boot"),
        (_t("Rocket"), "Rakete"), (_t("Balloon"), "Ballon|Luftballon"),
        (_t("Kite"), "Drachen"), (_t("Snowman"), "Schneemann"),
        (_t("Castle (fortress)"), "Burg|Schloss"), (_t("Crown"), "Krone"),
        (_t("Heart"), "Herz"), (_t("Glasses"), "Brille"),
        (_t("Hat"), "Hut"), (_t("Shoe"), "Schuh"),
        (_t("Sock"), "Socke"), (_t("Trousers"), "Hose"),
        (_t("Present (gift)"), "Geschenk"), (_t("Cake"), "Kuchen"),
        (_t("Ball"), "Ball"), (_t("Mountain"), "Berg"),
        (_t("Island"), "Insel"), (_t("Tent"), "Zelt"),
        (_t("Ladder"), "Leiter"), (_t("Bicycle"), "Fahrrad|Velo"),
        (_t("Guitar"), "Gitarre"), (_t("Drum"), "Trommel"),
        (_t("Bell"), "Glocke"), (_t("Treasure chest"), "Schatztruhe|Schatz"),
        (_t("Robot"), "Roboter"), (_t("Ghost"), "Gespenst|Geist"),
        (_t("Witch"), "Hexe"), (_t("Dragon"), "Drache"),
        (_t("Unicorn"), "Einhorn"), (_t("Cactus"), "Kaktus"),
        (_t("Mushroom"), "Pilz"), (_t("Lightning"), "Blitz"),
        (_t("Rain"), "Regen"), (_t("Snowflake"), "Schneeflocke"),
        (_t("Volcano"), "Vulkan"), (_t("Lighthouse"), "Leuchtturm"),
        (_t("Bridge"), "Brücke"), (_t("Anchor"), "Anker"),
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
    CATEGORIES[_key] = {"title": _title, "emoji": _emoji, "words": _list}
for _c in CATEGORIES.values():
    for _w in _c["words"]:
        for _a in _w["aliases"][1:]:
            LEGACY.setdefault(_a, _w["name"])
KEYS = {_w["name"] for _c in CATEGORIES.values() for _w in _c["words"]}


def legacy(name: str) -> str:
    """The key of a word from a table or history entry of before the translation (German); a key stays as it is."""
    if not isinstance(name, str) or name in KEYS:
        return name
    return LEGACY.get(name, name)

DEFAULT = "gemischt"
