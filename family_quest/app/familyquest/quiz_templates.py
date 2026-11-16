"""Quiz templates for the family quiz (German content – quizzes are content, like learning packs).

Every question: (question, right answer, wrong answer, wrong answer, wrong answer). Copying a template makes an
ordinary quiz that can be changed; the answers are shuffled (community.template_questions).
Flags are emoji – most phones and tablets show them; Windows shows the two letters instead.
"""
from __future__ import annotations


# flags of all countries used in the flag quizzes (answers of the reversed quiz)
FLAGS = {
    "Schweiz": "🇨🇭", "Dänemark": "🇩🇰", "Österreich": "🇦🇹", "Japan": "🇯🇵", "Italien": "🇮🇹", "Irland": "🇮🇪", "Mexiko": "🇲🇽",
    "Ungarn": "🇭🇺", "Frankreich": "🇫🇷", "Niederlande": "🇳🇱", "Russland": "🇷🇺", "Deutschland": "🇩🇪", "Belgien": "🇧🇪",
    "Spanien": "🇪🇸", "China": "🇨🇳", "Südkorea": "🇰🇷", "Bangladesch": "🇧🇩", "Brasilien": "🇧🇷", "Portugal": "🇵🇹",
    "Argentinien": "🇦🇷", "Kolumbien": "🇨🇴", "Kanada": "🇨🇦", "USA": "🇺🇸", "Peru": "🇵🇪", "Schweden": "🇸🇪", "Finnland": "🇫🇮",
    "Norwegen": "🇳🇴", "Island": "🇮🇸", "Griechenland": "🇬🇷", "Israel": "🇮🇱", "Luxemburg": "🇱🇺", "Lettland": "🇱🇻", "Polen": "🇵🇱",
    "Indien": "🇮🇳", "Niger": "🇳🇪", "Elfenbeinküste": "🇨🇮", "Nordkorea": "🇰🇵", "Australien": "🇦🇺", "Neuseeland": "🇳🇿",
    "Grossbritannien": "🇬🇧", "Fidschi": "🇫🇯", "Türkei": "🇹🇷", "Tunesien": "🇹🇳", "Marokko": "🇲🇦", "Südafrika": "🇿🇦",
    "Jamaika": "🇯🇲", "Kenia": "🇰🇪", "Nigeria": "🇳🇬", "Uruguay": "🇺🇾", "Guatemala": "🇬🇹", "Liberia": "🇱🇷", "Malaysia": "🇲🇾",
    "Liechtenstein": "🇱🇮", "Haiti": "🇭🇹", "Andorra": "🇦🇩", "Monaco": "🇲🇨",
}
_ARTICLE = {"Schweiz": "die Schweiz", "USA": "die USA", "Türkei": "die Türkei", "Niederlande": "die Niederlande",
            "Elfenbeinküste": "die Elfenbeinküste"}


def _reverse_flags(questions: list[tuple]) -> list[tuple]:
    """«Which country has this flag?» turned round: «Which flag has Germany?» with four flags as answers."""
    return [(f"Welche Flagge hat {_ARTICLE.get(right, right)}?", FLAGS[right], *[FLAGS[w] for w in wrong])
            for _q, right, *wrong in questions]


def _caps(country_capitals: list[tuple[str, str, str, str, str]], text: str) -> list[tuple]:
    return [(text.format(c), right, *wrong) for c, right, *wrong in country_capitals]


# cantons mixed in with the capitals: neighbours and waters (every border checked on the map)
_CANTON_EXTRA = [
    ("Welcher Kanton grenzt NICHT an den Thurgau?", "Aargau", "Zürich", "St. Gallen", "Schaffhausen"),
    ("Welcher Kanton ist der einzige Schweizer Nachbar von Genf?", "Waadt", "Wallis", "Neuenburg", "Freiburg"),
    ("Welcher Kanton ist der einzige Schweizer Nachbar von Basel-Stadt?", "Basel-Landschaft", "Aargau", "Solothurn", "Jura"),
    ("Welcher Kanton grenzt an Appenzell Innerrhoden?", "Appenzell Ausserrhoden", "Thurgau", "Glarus", "Zürich"),
    ("Welcher Kanton grenzt an Uri?", "Schwyz", "Zürich", "Luzern", "Zug"),
    ("Welcher Kanton grenzt an Zug?", "Zürich", "Bern", "Uri", "Thurgau"),
    ("Welcher Kanton grenzt an Schaffhausen?", "Zürich", "Aargau", "St. Gallen", "Basel-Landschaft"),
    ("Welcher Kanton grenzt an den Jura?", "Bern", "Freiburg", "Waadt", "Aargau"),
    ("Welcher Kanton grenzt an Glarus?", "St. Gallen", "Zürich", "Luzern", "Thurgau"),
    ("Welcher Fluss bildet einen Teil der Grenze zwischen dem Thurgau und Deutschland?", "Rhein", "Thur", "Aare", "Inn"),
    ("Welcher See liegt an den Kantonen Zürich, Schwyz und St. Gallen?", "Zürichsee", "Walensee", "Bodensee", "Greifensee"),
    ("In welchem Kanton liegt der Silsersee?", "Graubünden", "Tessin", "Wallis", "Uri"),
    ("An welchem See liegt das Dorf Brienz im Kanton Bern?", "Brienzersee", "Thunersee", "Bielersee", "Sarnersee"),
    ("In welchem Kanton liegt der Sarnersee?", "Obwalden", "Nidwalden", "Luzern", "Uri"),
    ("An welchem See liegt die Stadt Lugano?", "Luganersee", "Lago Maggiore", "Comer See", "Gardasee"),
    ("An welchem See liegt die Stadt Zug?", "Zugersee", "Ägerisee", "Vierwaldstättersee", "Zürichsee"),
]

TEMPLATES: dict[str, dict] = {
    "schweizer-gewaesser": {"title": "Schweizer Gewässer", "icon": "🏞️", "questions": [
        ("Welcher ist der grösste See, der ganz in der Schweiz liegt?", "Neuenburgersee", "Vierwaldstättersee", "Zürichsee", "Thunersee"),
        ("Welcher Fluss fliesst durch Basel?", "Rhein", "Aare", "Reuss", "Limmat"),
        ("Durch welchen See fliesst die Rhone, bevor sie die Schweiz verlässt?", "Genfersee", "Bodensee", "Neuenburgersee", "Lago Maggiore"),
        ("Welcher Fluss ist der längste, der ganz in der Schweiz fliesst?", "Aare", "Reuss", "Limmat", "Thur"),
        ("Durch welche Stadt fliesst die Limmat?", "Zürich", "Bern", "Luzern", "Basel"),
        ("Welche Stadt umfliesst die Aare in einer grossen Schlaufe?", "Bern", "Zürich", "Genf", "St. Gallen"),
        ("An welchem See liegt Luzern?", "Vierwaldstättersee", "Zugersee", "Zürichsee", "Sempachersee"),
        ("Welcher See grenzt an Deutschland, Österreich und die Schweiz?", "Bodensee", "Genfersee", "Lago Maggiore", "Walensee"),
        ("In welchem Kanton entspringt der Rhein?", "Graubünden", "Wallis", "Uri", "Tessin"),
        ("In welchem Kanton entspringt die Rhone?", "Wallis", "Graubünden", "Bern", "Uri"),
        ("Welcher Fluss fliesst durch Luzern?", "Reuss", "Aare", "Emme", "Limmat"),
        ("In welchem Kanton liegen der Lago di Lugano und ein Teil des Lago Maggiore?", "Tessin", "Graubünden", "Wallis", "Uri"),
        ("Wie heisst der grosse Wasserfall bei Schaffhausen?", "Rheinfall", "Staubbachfall", "Giessbachfälle", "Reichenbachfall"),
        ("In welches Meer fliesst das Wasser des Rheins?", "Nordsee", "Mittelmeer", "Schwarzes Meer", "Ostsee"),
        ("In welches Meer fliesst das Wasser des Inn (über die Donau)?", "Schwarzes Meer", "Nordsee", "Mittelmeer", "Ostsee"),
        ("Welche Stadt liegt zwischen Thunersee und Brienzersee?", "Interlaken", "Spiez", "Brienz", "Thun"),
        ("Welcher Fluss gibt dem Kanton Thurgau seinen Namen?", "Thur", "Murg", "Sitter", "Töss"),
        ("Welcher Fluss verlässt in Genf den Genfersee?", "Rhone", "Aare", "Reuss", "Saane"),
    ]},
    "europa-geografie": {"title": "Geografie Europa", "icon": "🗺️", "questions": [
        ("Wie heisst der höchste Berg der Alpen?", "Mont Blanc", "Matterhorn", "Dufourspitze", "Eiger"),
        ("Welcher ist der längste Fluss Europas?", "Wolga", "Donau", "Rhein", "Dnepr"),
        ("Welches ist das grösste Land, das ganz in Europa liegt?", "Ukraine", "Frankreich", "Spanien", "Deutschland"),
        ("Welches ist das kleinste Land der Welt?", "Vatikanstadt", "Monaco", "San Marino", "Liechtenstein"),
        ("Welches Gebirge liegt zwischen Spanien und Frankreich?", "Pyrenäen", "Alpen", "Apenninen", "Karpaten"),
        ("Welches Meer liegt zwischen Italien und Kroatien?", "Adria", "Ägäis", "Ostsee", "Nordsee"),
        ("Durch wie viele Hauptstädte fliesst die Donau?", "4", "2", "3", "6"),
        ("Welches ist die grösste Insel im Mittelmeer?", "Sizilien", "Sardinien", "Korsika", "Zypern"),
        ("Welches Land hat die Form eines Stiefels?", "Italien", "Griechenland", "Portugal", "Kroatien"),
        ("Welche Meerenge trennt Europa und Afrika?", "Strasse von Gibraltar", "Bosporus", "Ärmelkanal", "Dardanellen"),
        ("Welcher Vulkan auf Sizilien ist der höchste aktive Vulkan Europas?", "Ätna", "Vesuv", "Stromboli", "Hekla"),
        ("An welchem Fluss liegt Paris?", "Seine", "Loire", "Rhone", "Garonne"),
        ("Welches Land der EU hat am meisten Einwohner?", "Deutschland", "Frankreich", "Italien", "Spanien"),
        ("Welches Land nennt man das «Land der tausend Seen»?", "Finnland", "Schweden", "Norwegen", "Estland"),
        ("Für welches Land sind die Fjorde berühmt?", "Norwegen", "Dänemark", "Irland", "Polen"),
        ("Welcher Kanal trennt England und Frankreich?", "Ärmelkanal", "Suezkanal", "Panamakanal", "Nord-Ostsee-Kanal"),
        ("Auf welcher Insel liegt der Geysir «Strokkur»?", "Island", "Irland", "Sizilien", "Kreta"),
    ]},
    "hauptstaedte-europa": {"title": "Hauptstädte Europa", "icon": "🏛️", "questions": _caps([
        ("der Schweiz", "Bern", "Zürich", "Genf", "Basel"),
        ("Deutschland", "Berlin", "München", "Hamburg", "Frankfurt"),
        ("Österreich", "Wien", "Salzburg", "Graz", "Innsbruck"),
        ("Frankreich", "Paris", "Lyon", "Marseille", "Nizza"),
        ("Italien", "Rom", "Mailand", "Neapel", "Venedig"),
        ("Spanien", "Madrid", "Barcelona", "Sevilla", "Valencia"),
        ("Portugal", "Lissabon", "Porto", "Faro", "Braga"),
        ("den Niederlanden", "Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"),
        ("Belgien", "Brüssel", "Antwerpen", "Gent", "Brügge"),
        ("Grossbritannien", "London", "Manchester", "Edinburgh", "Liverpool"),
        ("Irland", "Dublin", "Cork", "Belfast", "Galway"),
        ("Norwegen", "Oslo", "Bergen", "Stavanger", "Trondheim"),
        ("Schweden", "Stockholm", "Göteborg", "Malmö", "Uppsala"),
        ("Finnland", "Helsinki", "Turku", "Tampere", "Oulu"),
        ("Dänemark", "Kopenhagen", "Aarhus", "Odense", "Aalborg"),
        ("Polen", "Warschau", "Krakau", "Danzig", "Breslau"),
        ("Tschechien", "Prag", "Brünn", "Pilsen", "Ostrau"),
        ("Ungarn", "Budapest", "Debrecen", "Szeged", "Pécs"),
        ("Griechenland", "Athen", "Thessaloniki", "Patras", "Heraklion"),
        ("Kroatien", "Zagreb", "Split", "Dubrovnik", "Rijeka"),
        ("Rumänien", "Bukarest", "Cluj-Napoca", "Timișoara", "Iași"),
        ("Bulgarien", "Sofia", "Plowdiw", "Warna", "Burgas"),
        ("der Slowakei", "Bratislava", "Košice", "Žilina", "Nitra"),
        ("Slowenien", "Ljubljana", "Maribor", "Koper", "Celje"),
        ("Island", "Reykjavík", "Akureyri", "Keflavík", "Selfoss"),
        ("der Ukraine", "Kyjiw", "Lwiw", "Odessa", "Charkiw"),
        ("Liechtenstein", "Vaduz", "Schaan", "Balzers", "Triesen"),
        ("Luxemburg", "Luxemburg", "Esch an der Alzette", "Differdingen", "Düdelingen"),
    ], "Was ist die Hauptstadt von {}?")},
    "hauptstaedte-welt": {"title": "Hauptstädte der Welt", "icon": "🌍", "questions": _caps([
        ("den USA", "Washington, D.C.", "New York", "Los Angeles", "Chicago"),
        ("Kanada", "Ottawa", "Toronto", "Montreal", "Vancouver"),
        ("Australien", "Canberra", "Sydney", "Melbourne", "Brisbane"),
        ("Brasilien", "Brasília", "Rio de Janeiro", "São Paulo", "Salvador"),
        ("Argentinien", "Buenos Aires", "Córdoba", "Rosario", "Mendoza"),
        ("Mexiko", "Mexiko-Stadt", "Guadalajara", "Cancún", "Monterrey"),
        ("Japan", "Tokio", "Osaka", "Kyoto", "Yokohama"),
        ("China", "Peking", "Shanghai", "Hongkong", "Guangzhou"),
        ("Indien", "Neu-Delhi", "Mumbai", "Kalkutta", "Bangalore"),
        ("Ägypten", "Kairo", "Alexandria", "Luxor", "Gizeh"),
        ("Kenia", "Nairobi", "Mombasa", "Kisumu", "Nakuru"),
        ("Nigeria", "Abuja", "Lagos", "Kano", "Ibadan"),
        ("Marokko", "Rabat", "Casablanca", "Marrakesch", "Fès"),
        ("Russland", "Moskau", "Sankt Petersburg", "Nowosibirsk", "Kasan"),
        ("der Türkei", "Ankara", "Istanbul", "Izmir", "Antalya"),
        ("Thailand", "Bangkok", "Chiang Mai", "Phuket", "Pattaya"),
        ("Südkorea", "Seoul", "Busan", "Incheon", "Daegu"),
        ("Neuseeland", "Wellington", "Auckland", "Christchurch", "Queenstown"),
        ("Peru", "Lima", "Cusco", "Arequipa", "Trujillo"),
        ("Chile", "Santiago de Chile", "Valparaíso", "Concepción", "Antofagasta"),
        ("Kolumbien", "Bogotá", "Medellín", "Cali", "Cartagena"),
        ("Vietnam", "Hanoi", "Ho-Chi-Minh-Stadt", "Da Nang", "Hue"),
        ("Saudi-Arabien", "Riad", "Dschidda", "Mekka", "Medina"),
        ("Pakistan", "Islamabad", "Karachi", "Lahore", "Peschawar"),
        ("Kuba", "Havanna", "Santiago de Cuba", "Varadero", "Trinidad"),
    ], "Was ist die Hauptstadt von {}?")},
    "laenderflaggen": {"title": "Länderflaggen", "icon": "🚩", "t": 15, "questions": [
        ("Welches Land hat diese Flagge? 🇨🇭", "Schweiz", "Dänemark", "Österreich", "Japan"),
        ("Welches Land hat diese Flagge? 🇮🇹", "Italien", "Irland", "Mexiko", "Ungarn"),
        ("Welches Land hat diese Flagge? 🇫🇷", "Frankreich", "Niederlande", "Russland", "Italien"),
        ("Welches Land hat diese Flagge? 🇩🇪", "Deutschland", "Belgien", "Spanien", "Österreich"),
        ("Welches Land hat diese Flagge? 🇯🇵", "Japan", "China", "Südkorea", "Bangladesch"),
        ("Welches Land hat diese Flagge? 🇧🇷", "Brasilien", "Portugal", "Argentinien", "Kolumbien"),
        ("Welches Land hat diese Flagge? 🇨🇦", "Kanada", "USA", "Schweiz", "Peru"),
        ("Welches Land hat diese Flagge? 🇸🇪", "Schweden", "Finnland", "Norwegen", "Dänemark"),
        ("Welches Land hat diese Flagge? 🇳🇴", "Norwegen", "Island", "Dänemark", "Schweden"),
        ("Welches Land hat diese Flagge? 🇬🇷", "Griechenland", "Israel", "Finnland", "Argentinien"),
        ("Welches Land hat diese Flagge? 🇪🇸", "Spanien", "Portugal", "Kolumbien", "Belgien"),
        ("Welches Land hat diese Flagge? 🇳🇱", "Niederlande", "Luxemburg", "Frankreich", "Russland"),
        ("Welches Land hat diese Flagge? 🇦🇹", "Österreich", "Lettland", "Polen", "Kanada"),
        ("Welches Land hat diese Flagge? 🇮🇳", "Indien", "Irland", "Niger", "Elfenbeinküste"),
        ("Welches Land hat diese Flagge? 🇲🇽", "Mexiko", "Italien", "Irland", "Ungarn"),
        ("Welches Land hat diese Flagge? 🇰🇷", "Südkorea", "Japan", "China", "Nordkorea"),
        ("Welches Land hat diese Flagge? 🇦🇺", "Australien", "Neuseeland", "Grossbritannien", "Fidschi"),
        ("Welches Land hat diese Flagge? 🇹🇷", "Türkei", "Tunesien", "Marokko", "China"),
        ("Welches Land hat diese Flagge? 🇿🇦", "Südafrika", "Jamaika", "Kenia", "Nigeria"),
        ("Welches Land hat diese Flagge? 🇦🇷", "Argentinien", "Uruguay", "Griechenland", "Guatemala"),
        ("Welches Land hat diese Flagge? 🇬🇧", "Grossbritannien", "Australien", "USA", "Island"),
        ("Welches Land hat diese Flagge? 🇺🇸", "USA", "Liberia", "Malaysia", "Grossbritannien"),
        ("Welches Land hat diese Flagge? 🇱🇮", "Liechtenstein", "Haiti", "Andorra", "Monaco"),
        ("Welches Land hat diese Flagge? 🇵🇹", "Portugal", "Spanien", "Brasilien", "Marokko"),
    ]},
    "kulinarik-welt": {"title": "Kulinarische Spezialitäten der Welt", "icon": "🍝", "questions": [
        ("Aus welchem Land kommt die Rösti?", "Schweiz", "Österreich", "Deutschland", "Frankreich"),
        ("Aus welchem Land kommt die Pizza?", "Italien", "Griechenland", "Spanien", "USA"),
        ("Aus welchem Land kommt die Paella?", "Spanien", "Portugal", "Italien", "Mexiko"),
        ("Aus welchem Land kommt Sushi?", "Japan", "China", "Thailand", "Südkorea"),
        ("Aus welchem Land kommt das Wiener Schnitzel?", "Österreich", "Deutschland", "Schweiz", "Ungarn"),
        ("Aus welchem Land kommen Tacos?", "Mexiko", "Spanien", "Brasilien", "USA"),
        ("Aus welchem Land kommt Moussaka?", "Griechenland", "Türkei", "Italien", "Frankreich"),
        ("Aus welchem Land kommt Pad Thai?", "Thailand", "Vietnam", "Japan", "Indien"),
        ("Aus welchem Land kommt «Fish and Chips»?", "Grossbritannien", "Irland", "USA", "Australien"),
        ("Aus welchem Land kommt das Gulasch?", "Ungarn", "Österreich", "Polen", "Tschechien"),
        ("Aus welchem Land kommen Pierogi?", "Polen", "Russland", "Italien", "Griechenland"),
        ("Aus welchem Land kommt Kimchi?", "Südkorea", "Japan", "China", "Thailand"),
        ("Aus welchem Land kommen die «Pastéis de Nata»?", "Portugal", "Spanien", "Brasilien", "Frankreich"),
        ("Aus welchem Land kommt Poutine (Pommes mit Käse und Sauce)?", "Kanada", "USA", "Belgien", "Frankreich"),
        ("Aus welchem Land kommt die Feijoada (Bohneneintopf)?", "Brasilien", "Mexiko", "Spanien", "Italien"),
        ("Aus welchem Land kommt Smørrebrød?", "Dänemark", "Schweden", "Norwegen", "Niederlande"),
        ("Aus welchem Land kommt das Tiramisu?", "Italien", "Frankreich", "Österreich", "Spanien"),
        ("Aus welchem Land kommt das Baguette?", "Frankreich", "Italien", "Belgien", "Deutschland"),
        ("Aus welchem Land kommt die Currywurst?", "Deutschland", "Indien", "Österreich", "Grossbritannien"),
        ("Aus welchem Land kommt Haggis?", "Schottland", "Irland", "Wales", "Island"),
    ]},
    "schweizer-spezialitaeten": {"title": "Schweizer Spezialitäten", "icon": "🧀", "questions": [
        ("Aus welchem Kanton kommt die Engadiner Nusstorte?", "Graubünden", "Wallis", "Bern", "Tessin"),
        ("Aus welcher Stadt kommen die Läckerli?", "Basel", "Bern", "Zürich", "Luzern"),
        ("Aus welchem Kanton kommt die Kirschtorte mit dem Kantonsnamen?", "Zug", "Schwyz", "Luzern", "Aargau"),
        ("Aus welchem Kanton kommt die Rüeblitorte?", "Aargau", "Thurgau", "Solothurn", "Zürich"),
        ("Aus welchem Kanton kommt das Bündnerfleisch?", "Graubünden", "Wallis", "Uri", "Glarus"),
        ("Aus welchem Kanton kommt die Chügelipastete?", "Luzern", "Bern", "Zug", "Basel-Stadt"),
        ("Welcher Kanton wird wegen seiner vielen Apfelbäume «Mostindien» genannt?", "Thurgau", "Aargau", "St. Gallen", "Zug"),
        ("Aus welcher Stadt kommt die berühmte Kalbsbratwurst mit dem Stadtnamen?", "St. Gallen", "Bern", "Luzern", "Chur"),
        ("Aus welchem Kanton kommt der Raclette-Käse mit geschützter Herkunft (AOP)?", "Wallis", "Freiburg", "Waadt", "Bern"),
        ("Nach welchem Ort im Kanton Freiburg ist ein berühmter Hartkäse benannt?", "Gruyères", "Emmental", "Tilsit", "Sbrinz"),
        ("Aus welcher Stadt kommt das Geschnetzelte mit Rahmsauce, das ihren Namen trägt?", "Zürich", "Bern", "Basel", "Genf"),
        ("Was ist eine «Berner Platte»?", "Fleisch und Würste mit Sauerkraut und Bohnen", "Ein Käsekuchen", "Eine Fischplatte", "Ein Dessert mit Meringue"),
        ("Aus welchem Kanton kommt die Glarner Pastete?", "Glarus", "Uri", "Schwyz", "Appenzell Innerrhoden"),
        ("Was ist Birchermüesli ursprünglich?", "Eine Speise eines Schweizer Arztes", "Ein Bündner Bergkäse", "Ein Tessiner Wein", "Ein Basler Gebäck"),
    ]},
    "kantone-hauptorte": {"title": "Kantone der Schweiz", "icon": "🇨🇭", "questions": _CANTON_EXTRA + _caps([
        ("Thurgau", "Frauenfeld", "Weinfelden", "Kreuzlingen", "Arbon"),
        ("Graubünden", "Chur", "Davos", "St. Moritz", "Ilanz"),
        ("Wallis", "Sitten", "Brig", "Martigny", "Visp"),
        ("Tessin", "Bellinzona", "Lugano", "Locarno", "Mendrisio"),
        ("Waadt", "Lausanne", "Montreux", "Yverdon-les-Bains", "Vevey"),
        ("Aargau", "Aarau", "Baden", "Wettingen", "Brugg"),
        ("Basel-Landschaft", "Liestal", "Allschwil", "Reinach", "Pratteln"),
        ("Appenzell Ausserrhoden", "Herisau", "Appenzell", "Teufen", "Heiden"),
        ("Nidwalden", "Stans", "Hergiswil", "Buochs", "Beckenried"),
        ("Obwalden", "Sarnen", "Engelberg", "Alpnach", "Kerns"),
        ("Uri", "Altdorf", "Andermatt", "Erstfeld", "Flüelen"),
        ("Schwyz", "Schwyz", "Einsiedeln", "Küssnacht", "Lachen"),
        ("Jura", "Delsberg", "Pruntrut", "Saignelégier", "Moutier"),
        ("Neuenburg", "Neuenburg", "La Chaux-de-Fonds", "Le Locle", "Boudry"),
        ("Solothurn", "Solothurn", "Olten", "Grenchen", "Biberist"),
        ("Glarus", "Glarus", "Näfels", "Netstal", "Linthal"),
        ("Schaffhausen", "Schaffhausen", "Neuhausen am Rheinfall", "Stein am Rhein", "Thayngen"),
        ("St. Gallen", "St. Gallen", "Rapperswil-Jona", "Wil", "Gossau"),
        ("Zug", "Zug", "Baar", "Cham", "Steinhausen"),
        ("Bern", "Bern", "Biel", "Thun", "Köniz"),
    ], "Was ist der Hauptort des Kantons {}?")},
    "tiere": {"title": "Tierwelt", "icon": "🦒", "questions": [
        ("Welches ist das schnellste Landtier?", "Gepard", "Löwe", "Pferd", "Antilope"),
        ("Welches ist das grösste Tier der Welt?", "Blauwal", "Elefant", "Giraffe", "Walhai"),
        ("Wie viele Beine hat eine Spinne?", "8", "6", "10", "12"),
        ("Welcher Vogel kann auch rückwärts fliegen?", "Kolibri", "Adler", "Spatz", "Möwe"),
        ("Welches Säugetier kann richtig fliegen?", "Fledermaus", "Pinguin", "Strauss", "Maulwurf"),
        ("Wie heisst ein Känguru-Baby?", "Joey", "Kitz", "Fohlen", "Welpe"),
        ("Wie viele Herzen hat ein Oktopus?", "3", "1", "2", "8"),
        ("Welches Tier lebt in der Arktis am Nordpol?", "Eisbär", "Pinguin", "Kamel", "Känguru"),
        ("Welches dieser Tiere ist ein Säugetier?", "Delfin", "Hai", "Thunfisch", "Lachs"),
        ("Was frisst ein Grosser Panda fast nur?", "Bambus", "Fisch", "Honig", "Gras"),
        ("Welches Tier kann seine Hautfarbe wechseln?", "Chamäleon", "Frosch", "Schildkröte", "Igel"),
        ("Wie viele Beine hat ein Insekt?", "6", "4", "8", "10"),
        ("Welches ist der grösste Vogel der Welt?", "Strauss", "Adler", "Albatros", "Emu"),
        ("Welches Tier hat den längsten Hals?", "Giraffe", "Kamel", "Strauss", "Lama"),
        ("Wie lange ist eine Elefantenkuh ungefähr trächtig?", "22 Monate", "9 Monate", "12 Monate", "36 Monate"),
        ("Welches Tier baut Dämme aus Holz?", "Biber", "Otter", "Dachs", "Murmeltier"),
    ]},
    "weltall": {"title": "Weltall", "icon": "🚀", "questions": [
        ("Welcher Planet ist der Sonne am nächsten?", "Merkur", "Venus", "Mars", "Erde"),
        ("Welcher ist der grösste Planet unseres Sonnensystems?", "Jupiter", "Saturn", "Neptun", "Erde"),
        ("Welcher Planet wird «der rote Planet» genannt?", "Mars", "Venus", "Jupiter", "Merkur"),
        ("Wie viele Planeten hat unser Sonnensystem?", "8", "7", "9", "10"),
        ("Wer betrat als erster Mensch den Mond?", "Neil Armstrong", "Juri Gagarin", "Buzz Aldrin", "Michael Collins"),
        ("In welchem Jahr landeten Menschen zum ersten Mal auf dem Mond?", "1969", "1959", "1979", "1989"),
        ("Wer war der erste Mensch im Weltall?", "Juri Gagarin", "Neil Armstrong", "Alan Shepard", "John Glenn"),
        ("Wie heisst unsere Galaxie?", "Milchstrasse", "Andromeda", "Sombrero", "Whirlpool"),
        ("Wie lange braucht das Licht von der Sonne zur Erde ungefähr?", "8 Minuten", "8 Sekunden", "8 Stunden", "8 Tage"),
        ("Was ist die Sonne?", "Ein Stern", "Ein Planet", "Ein Mond", "Ein Komet"),
        ("Welcher Planet ist am heissesten?", "Venus", "Merkur", "Mars", "Jupiter"),
        ("Welcher Planet ist bekannt für seine grossen, hellen Ringe?", "Saturn", "Mars", "Venus", "Merkur"),
        ("Wer flog als erster Schweizer ins Weltall?", "Claude Nicollier", "Bertrand Piccard", "Auguste Piccard", "Marco Sieber"),
        ("Wie heisst der natürliche Begleiter der Erde?", "Mond", "Phobos", "Titan", "Europa"),
    ]},
    "erfindungen": {"title": "Erfindungen und Entdeckungen", "icon": "💡", "questions": [
        ("Wer erfand den Buchdruck mit beweglichen Lettern in Europa?", "Johannes Gutenberg", "Leonardo da Vinci", "Martin Luther", "Isaac Newton"),
        ("Welcher Schweizer erfand den Klettverschluss?", "George de Mestral", "Karl Elsener", "Henri Nestlé", "Daniel Peter"),
        ("Wer gründete die Firma, die das Schweizer Offiziersmesser bekannt machte?", "Karl Elsener", "George de Mestral", "Henry Dunant", "Rudolf Lindt"),
        ("Wer entdeckte das Penicillin?", "Alexander Fleming", "Louis Pasteur", "Marie Curie", "Robert Koch"),
        ("Wer flog 1903 als Erste mit einem Motorflugzeug?", "Die Gebrüder Wright", "Otto Lilienthal", "Graf Zeppelin", "Louis Blériot"),
        ("Wo erfand Tim Berners-Lee das World Wide Web?", "Am CERN in Genf", "In Silicon Valley", "An der ETH Zürich", "In London"),
        ("Wer baute 1885 eines der ersten Autos mit Benzinmotor?", "Carl Benz", "Henry Ford", "Ferdinand Porsche", "Enzo Ferrari"),
        ("Welcher Schweizer erfand 1875 die Milchschokolade?", "Daniel Peter", "Rodolphe Lindt", "Philippe Suchard", "Theodor Tobler"),
        ("Wer entwickelte die Relativitätstheorie?", "Albert Einstein", "Isaac Newton", "Galileo Galilei", "Niels Bohr"),
        ("Wer gründete das Rote Kreuz?", "Henry Dunant", "Florence Nightingale", "Albert Schweitzer", "Guillaume Henri Dufour"),
        ("Wer verbesserte die Dampfmaschine so, dass sie überall genutzt wurde?", "James Watt", "Thomas Edison", "Nikola Tesla", "George Stephenson"),
        ("Wem gelang 1876 ein Patent auf das Telefon?", "Alexander Graham Bell", "Thomas Edison", "Guglielmo Marconi", "Werner von Siemens"),
    ]},
    "schweiz": {"title": "Schweiz allgemein", "icon": "⛰️", "questions": [
        ("Wie viele Kantone hat die Schweiz?", "26", "23", "24", "28"),
        ("Wie viele Landessprachen hat die Schweiz?", "4", "3", "2", "5"),
        ("Wie heisst der höchste Berg der Schweiz?", "Dufourspitze", "Matterhorn", "Jungfrau", "Eiger"),
        ("Wie viele Mitglieder hat der Bundesrat?", "7", "5", "9", "12"),
        ("Wann ist der Schweizer Nationalfeiertag?", "1. August", "1. Mai", "12. September", "6. Januar"),
        ("Welches Jahr gilt als Gründungsjahr der Eidgenossenschaft?", "1291", "1315", "1499", "1848"),
        ("Wo soll Wilhelm Tell den Apfel vom Kopf seines Sohnes geschossen haben?", "Altdorf", "Luzern", "Schwyz", "Bern"),
        ("Wie heisst der längste Eisenbahntunnel der Welt?", "Gotthard-Basistunnel", "Lötschberg-Basistunnel", "Simplontunnel", "Eurotunnel"),
        ("In welcher Stadt hat die UNO ihren europäischen Sitz?", "Genf", "Bern", "Zürich", "Basel"),
        ("Bei welchem Dorf steht das Matterhorn?", "Zermatt", "Grindelwald", "Saas-Fee", "St. Moritz"),
        ("Wie heisst die Währung der Schweiz?", "Franken", "Euro", "Taler", "Krone"),
        ("Welcher See ist der grösste, der zum Teil in der Schweiz liegt?", "Genfersee", "Bodensee", "Neuenburgersee", "Lago Maggiore"),
    ]},
}

# cantons as pictures: the outline alone, or marked on the map of Switzerland (web/geo/ch.json, tools/build_ch_geo.py)
CANTON_NAMES = {"ZH": "Zürich", "BE": "Bern", "LU": "Luzern", "UR": "Uri", "SZ": "Schwyz", "OW": "Obwalden", "NW": "Nidwalden",
                "GL": "Glarus", "ZG": "Zug", "FR": "Freiburg", "SO": "Solothurn", "BS": "Basel-Stadt", "BL": "Basel-Landschaft",
                "SH": "Schaffhausen", "AR": "Appenzell Ausserrhoden", "AI": "Appenzell Innerrhoden", "SG": "St. Gallen",
                "GR": "Graubünden", "AG": "Aargau", "TG": "Thurgau", "TI": "Tessin", "VD": "Waadt", "VS": "Wallis",
                "NE": "Neuenburg", "GE": "Genf", "JU": "Jura"}
# wrong answers that look alike or lie close – not just any canton
_CANTON_DECOYS = {"ZH": ("Aargau", "Thurgau", "Schaffhausen"), "BE": ("Freiburg", "Waadt", "Luzern"), "LU": ("Aargau", "Bern", "Zug"),
                  "UR": ("Glarus", "Schwyz", "Obwalden"), "SZ": ("Zug", "Uri", "Glarus"), "OW": ("Nidwalden", "Uri", "Zug"),
                  "NW": ("Obwalden", "Zug", "Uri"), "GL": ("Uri", "Schwyz", "St. Gallen"), "ZG": ("Nidwalden", "Obwalden", "Schwyz"),
                  "FR": ("Waadt", "Bern", "Neuenburg"), "SO": ("Basel-Landschaft", "Aargau", "Jura"), "BS": ("Genf", "Basel-Landschaft", "Zug"),
                  "BL": ("Solothurn", "Basel-Stadt", "Jura"), "SH": ("Thurgau", "Zürich", "Basel-Stadt"),
                  "AR": ("Appenzell Innerrhoden", "St. Gallen", "Thurgau"), "AI": ("Appenzell Ausserrhoden", "Glarus", "Zug"),
                  "SG": ("Thurgau", "Graubünden", "Appenzell Ausserrhoden"), "GR": ("Wallis", "Tessin", "Bern"),
                  "AG": ("Zürich", "Solothurn", "Luzern"), "TG": ("Schaffhausen", "St. Gallen", "Zürich"), "TI": ("Graubünden", "Wallis", "Uri"),
                  "VD": ("Freiburg", "Neuenburg", "Genf"), "VS": ("Graubünden", "Tessin", "Bern"), "NE": ("Jura", "Waadt", "Freiburg"),
                  "GE": ("Basel-Stadt", "Waadt", "Neuenburg"), "JU": ("Neuenburg", "Solothurn", "Basel-Landschaft")}
TEMPLATES["kantone-umrisse"] = {"title": "Kantone erkennen (Umrisse)", "icon": "🗺️", "questions": [
    ("Welcher Kanton hat diese Form?", name, *_CANTON_DECOYS[k], {"geo": "canton", "id": k, "mode": "outline"})
    for k, name in CANTON_NAMES.items()]}
TEMPLATES["kantone-karte"] = {"title": "Kantone auf der Karte", "icon": "📍", "questions": [
    ("Welcher Kanton ist auf der Karte markiert?", name, *_CANTON_DECOYS[k], {"geo": "canton", "id": k, "mode": "map"})
    for k, name in CANTON_NAMES.items()]}
# coats of arms that look alike are the wrong answers
_ARMS_DECOYS = {"ZH": ("Luzern", "Zug", "Tessin"), "BE": ("Schaffhausen", "Uri", "Appenzell Innerrhoden"), "LU": ("Zürich", "Zug", "Tessin"),
                "UR": ("Bern", "Schaffhausen", "Basel-Stadt"), "SZ": ("Solothurn", "Freiburg", "Neuenburg"), "OW": ("Nidwalden", "Schwyz", "Basel-Landschaft"),
                "NW": ("Obwalden", "Basel-Landschaft", "Schwyz"), "GL": ("Graubünden", "Genf", "Schwyz"), "ZG": ("Luzern", "Zürich", "Freiburg"),
                "FR": ("Solothurn", "Zug", "Wallis"), "SO": ("Freiburg", "Schwyz", "Zug"), "BS": ("Basel-Landschaft", "Appenzell Innerrhoden", "Jura"),
                "BL": ("Basel-Stadt", "Jura", "Obwalden"), "SH": ("Bern", "Uri", "Appenzell Ausserrhoden"),
                "AR": ("Appenzell Innerrhoden", "Bern", "Schaffhausen"), "AI": ("Appenzell Ausserrhoden", "Bern", "Basel-Stadt"),
                "SG": ("Thurgau", "Waadt", "Aargau"), "GR": ("Glarus", "Wallis", "Genf"), "AG": ("Thurgau", "St. Gallen", "Zug"),
                "TG": ("St. Gallen", "Aargau", "Schaffhausen"), "TI": ("Luzern", "Zürich", "Zug"), "VD": ("Neuenburg", "St. Gallen", "Thurgau"),
                "VS": ("Graubünden", "Solothurn", "Jura"), "NE": ("Waadt", "Tessin", "Schwyz"), "GE": ("Graubünden", "Glarus", "Uri"),
                "JU": ("Basel-Landschaft", "Basel-Stadt", "Wallis")}
TEMPLATES["kantone-wappen"] = {"title": "Kantonswappen erkennen", "icon": "🛡️", "questions": [
    ("Welchem Kanton gehört dieses Wappen?", name, *_ARMS_DECOYS[k], {"geo": "canton", "id": k, "mode": "arms"})
    for k, name in CANTON_NAMES.items()]}

# estimation: everybody answers with a number – the closest wins (1000 / 500 / 250 points)
def _est(q, answer, lo, hi, unit="", step=None):
    return {"kind": "estimate", "q": q, "answer": answer, "min": lo, "max": hi, "unit": unit, **({"step": step} if step else {})}


TEMPLATES["schaetzfragen"] = {"title": "Schätzfragen", "icon": "🎚️", "t": 30, "questions": [
    _est("Wie hoch ist das Matterhorn?", 4478, 2000, 6000, "m"),
    _est("Wie hoch ist die Dufourspitze, der höchste Berg der Schweiz?", 4634, 2000, 6000, "m"),
    _est("Wie hoch ist der Mount Everest?", 8849, 4000, 12000, "m"),
    _est("Wie viele Kantone hat die Schweiz?", 26, 1, 50),
    _est("In welchem Jahr wurde der Bundesbrief geschrieben (Gründung der Eidgenossenschaft)?", 1291, 1000, 2000),
    _est("In welchem Jahr wurde der Schweizer Bundesstaat gegründet?", 1848, 1500, 2000),
    _est("Wie lang ist der Gotthard-Basistunnel?", 57, 10, 100, "km"),
    _est("Wie gross ist die Schweiz?", 41285, 10000, 100000, "km²", 100),
    _est("Wie lang ist der Rhein?", 1233, 200, 3000, "km"),
    _est("Wie viele Knochen hat ein erwachsener Mensch?", 206, 50, 500),
    _est("Wie viele Zähne hat ein Erwachsener mit Weisheitszähnen?", 32, 10, 60),
    _est("In welchem Jahr landeten zum ersten Mal Menschen auf dem Mond?", 1969, 1900, 2020),
    _est("Wie weit ist der Mond durchschnittlich von der Erde entfernt (in Tausend km)?", 384, 50, 1000, "Tausend km"),
    _est("Wie schnell ist der Schall in der Luft (bei 20 °C)?", 343, 50, 1000, "m/s"),
    _est("Wie viele Tage hat ein Schaltjahr?", 366, 300, 400),
    _est("In welchem Jahr fanden in St. Moritz zum ersten Mal Olympische Winterspiele statt?", 1928, 1890, 2000),
    _est("Bei wie viel Grad Celsius siedet Wasser auf Meereshöhe?", 100, 0, 200, "°C"),
    _est("Wie viele Beine hat eine Spinne?", 8, 0, 20),
]}


# map questions: everybody sets a pin – the closest (in km) wins
def _pin(place, lat, lon, m, q=None):
    return {"kind": "pin", "q": q or f"Wo liegt {place}?", "lat": lat, "lon": lon, "map": m, "label": place}


TEMPLATES["wo-liegt-schweiz"] = {"title": "Wo liegt das? (Schweiz)", "icon": "📌", "t": 25, "questions": [
    _pin("Bern", 46.948, 7.447, "ch"), _pin("Zürich", 47.377, 8.540, "ch"), _pin("Genf", 46.204, 6.143, "ch"),
    _pin("Basel", 47.560, 7.588, "ch"), _pin("Lugano", 46.004, 8.951, "ch"), _pin("Luzern", 47.050, 8.309, "ch"),
    _pin("St. Gallen", 47.424, 9.377, "ch"), _pin("Chur", 46.850, 9.531, "ch"), _pin("Sitten (Sion)", 46.233, 7.360, "ch"),
    _pin("Lausanne", 46.520, 6.633, "ch"), _pin("Schaffhausen", 47.696, 8.634, "ch"), _pin("Frauenfeld", 47.557, 8.898, "ch"),
    _pin("Altdorf", 46.880, 8.644, "ch"), _pin("Bellinzona", 46.192, 9.017, "ch"), _pin("Delémont", 47.365, 7.343, "ch"),
    _pin("Appenzell", 47.331, 9.409, "ch"), _pin("das Matterhorn", 45.976, 7.658, "ch"), _pin("der Rheinfall", 47.678, 8.615, "ch"),
    _pin("der Säntis", 47.249, 9.343, "ch"), _pin("St. Moritz", 46.498, 9.839, "ch"), _pin("Interlaken", 46.686, 7.863, "ch"),
    _pin("Einsiedeln", 47.128, 8.747, "ch"), _pin("Biel/Bienne", 47.137, 7.247, "ch"), _pin("Thun", 46.758, 7.628, "ch"),
]}
TEMPLATES["wo-liegt-europa"] = {"title": "Wo liegt das? (Europa)", "icon": "🌍", "t": 25, "questions": [
    _pin("Berlin", 52.520, 13.405, "europe"), _pin("Paris", 48.857, 2.352, "europe"), _pin("Rom", 41.903, 12.496, "europe"),
    _pin("Madrid", 40.417, -3.704, "europe"), _pin("London", 51.507, -0.128, "europe"), _pin("Wien", 48.208, 16.373, "europe"),
    _pin("Amsterdam", 52.370, 4.895, "europe"), _pin("Brüssel", 50.850, 4.352, "europe"), _pin("Lissabon", 38.722, -9.139, "europe"),
    _pin("Stockholm", 59.329, 18.069, "europe"), _pin("Oslo", 59.914, 10.752, "europe"), _pin("Kopenhagen", 55.676, 12.568, "europe"),
    _pin("Helsinki", 60.170, 24.938, "europe"), _pin("Warschau", 52.230, 21.012, "europe"), _pin("Prag", 50.076, 14.438, "europe"),
    _pin("Budapest", 47.498, 19.040, "europe"), _pin("Athen", 37.984, 23.728, "europe"), _pin("Dublin", 53.350, -6.260, "europe"),
    _pin("Reykjavík", 64.147, -21.942, "europe"), _pin("Bukarest", 44.427, 26.103, "europe"), _pin("Venedig", 45.441, 12.316, "europe"),
    _pin("Barcelona", 41.385, 2.173, "europe"), _pin("Istanbul", 41.008, 28.978, "europe"), _pin("Bern", 46.948, 7.447, "europe"),
]}

# both ways in one quiz: «Which country has this flag?» and «Which flag has Germany?» (mixed at the start of a game)
TEMPLATES["laenderflaggen"]["questions"] += _reverse_flags(TEMPLATES["laenderflaggen"]["questions"])

# ---------------------------------------------------------------- Germany, Austria, the Netherlands
TEMPLATES["deutschland-bundeslaender"] = {"title": "Deutschland: Bundesländer", "icon": "🇩🇪", "questions": [
    ("Wie viele Bundesländer hat Deutschland?", "16", "12", "15", "20"),
    ("Welche drei Bundesländer sind Stadtstaaten?", "Berlin, Hamburg, Bremen", "Berlin, Hamburg, München", "Berlin, Bremen, Köln", "Hamburg, Bremen, Frankfurt"),
] + _caps([
    ("Baden-Württemberg", "Stuttgart", "Karlsruhe", "Mannheim", "Freiburg"),
    ("Bayern", "München", "Nürnberg", "Augsburg", "Regensburg"),
    ("Brandenburg", "Potsdam", "Cottbus", "Frankfurt (Oder)", "Brandenburg an der Havel"),
    ("Hessen", "Wiesbaden", "Frankfurt am Main", "Kassel", "Darmstadt"),
    ("Mecklenburg-Vorpommern", "Schwerin", "Rostock", "Greifswald", "Stralsund"),
    ("Niedersachsen", "Hannover", "Braunschweig", "Osnabrück", "Oldenburg"),
    ("Nordrhein-Westfalen", "Düsseldorf", "Köln", "Dortmund", "Essen"),
    ("Rheinland-Pfalz", "Mainz", "Koblenz", "Trier", "Ludwigshafen"),
    ("Saarland", "Saarbrücken", "Neunkirchen", "Homburg", "Saarlouis"),
    ("Sachsen", "Dresden", "Leipzig", "Chemnitz", "Zwickau"),
    ("Sachsen-Anhalt", "Magdeburg", "Halle (Saale)", "Dessau-Roßlau", "Wittenberg"),
    ("Schleswig-Holstein", "Kiel", "Lübeck", "Flensburg", "Neumünster"),
    ("Thüringen", "Erfurt", "Jena", "Weimar", "Gera"),
], "Was ist die Landeshauptstadt von {}?")}

TEMPLATES["deutschland"] = {"title": "Deutschland allgemein", "icon": "🦅", "questions": [
    ("Wie heisst der höchste Berg Deutschlands?", "Zugspitze", "Watzmann", "Feldberg", "Brocken"),
    ("Wann ist der Tag der Deutschen Einheit?", "3. Oktober", "9. November", "1. Mai", "17. Juni"),
    ("In welchem Jahr fiel die Berliner Mauer?", "1989", "1990", "1961", "1975"),
    ("Welches Tor ist ein Wahrzeichen von Berlin?", "Brandenburger Tor", "Holstentor", "Siegestor", "Porta Nigra"),
    ("In welcher Stadt findet das Oktoberfest statt?", "München", "Köln", "Stuttgart", "Berlin"),
    ("Welcher Fluss fliesst durch Köln?", "Rhein", "Main", "Elbe", "Donau"),
    ("Welcher Fluss fliesst durch Hamburg und Dresden?", "Elbe", "Weser", "Oder", "Spree"),
    ("Wie heisst die grösste deutsche Insel?", "Rügen", "Usedom", "Sylt", "Fehmarn"),
    ("Welcher See liegt ganz in Deutschland und ist der grösste dieser Seen?", "Müritz", "Chiemsee", "Starnberger See", "Bodensee"),
    ("Welche Währung hatte Deutschland vor dem Euro?", "D-Mark", "Schilling", "Gulden", "Franken"),
    ("Wie viele Nachbarländer hat Deutschland?", "9", "7", "8", "10"),
    ("An welche zwei Meere grenzt Deutschland?", "Nordsee und Ostsee", "Nordsee und Mittelmeer", "Ostsee und Atlantik", "Nordsee und Schwarzes Meer"),
    ("Wer war der erste Bundeskanzler?", "Konrad Adenauer", "Willy Brandt", "Helmut Kohl", "Ludwig Erhard"),
]}

TEMPLATES["oesterreich-bundeslaender"] = {"title": "Österreich: Bundesländer", "icon": "🇦🇹", "questions": [
    ("Wie viele Bundesländer hat Österreich?", "9", "8", "10", "12"),
    ("Wie heisst der höchste Berg Österreichs?", "Grossglockner", "Wildspitze", "Dachstein", "Zugspitze"),
] + _caps([
    ("Niederösterreich", "St. Pölten", "Wiener Neustadt", "Krems", "Baden"),
    ("Oberösterreich", "Linz", "Wels", "Steyr", "Braunau"),
    ("Salzburg", "Salzburg", "Hallein", "Zell am See", "Bischofshofen"),
    ("Tirol", "Innsbruck", "Kufstein", "Lienz", "Kitzbühel"),
    ("Vorarlberg", "Bregenz", "Dornbirn", "Feldkirch", "Bludenz"),
    ("Kärnten", "Klagenfurt", "Villach", "Wolfsberg", "Spittal an der Drau"),
    ("Steiermark", "Graz", "Leoben", "Bruck an der Mur", "Kapfenberg"),
    ("Burgenland", "Eisenstadt", "Neusiedl am See", "Oberwart", "Mattersburg"),
], "Was ist die Landeshauptstadt von {}?")}

TEMPLATES["niederlande-provinzen"] = {"title": "Niederlande: Provinzen", "icon": "🇳🇱", "questions": [
    ("Wie viele Provinzen haben die Niederlande?", "12", "10", "11", "16"),
] + _caps([
    ("Groningen", "Groningen", "Assen", "Leeuwarden", "Emmen"),
    ("Friesland", "Leeuwarden", "Sneek", "Heerenveen", "Groningen"),
    ("Drenthe", "Assen", "Emmen", "Hoogeveen", "Meppel"),
    ("Overijssel", "Zwolle", "Enschede", "Deventer", "Almelo"),
    ("Flevoland", "Lelystad", "Almere", "Emmeloord", "Dronten"),
    ("Gelderland", "Arnheim", "Nimwegen", "Apeldoorn", "Ede"),
    ("Utrecht", "Utrecht", "Amersfoort", "Zeist", "Hilversum"),
    ("Nordholland", "Haarlem", "Amsterdam", "Alkmaar", "Zaandam"),
    ("Südholland", "Den Haag", "Rotterdam", "Leiden", "Delft"),
    ("Zeeland", "Middelburg", "Vlissingen", "Goes", "Terneuzen"),
    ("Nordbrabant", "’s-Hertogenbosch", "Eindhoven", "Tilburg", "Breda"),
    ("Limburg", "Maastricht", "Venlo", "Heerlen", "Roermond"),
], "Was ist die Hauptstadt der Provinz {}?")}

TEMPLATES["niederlande"] = {"title": "Niederlande allgemein", "icon": "🌷", "questions": [
    ("Was ist die Hauptstadt der Niederlande?", "Amsterdam", "Den Haag", "Rotterdam", "Utrecht"),
    ("In welcher Stadt sitzt die niederländische Regierung?", "Den Haag", "Amsterdam", "Rotterdam", "Utrecht"),
    ("Wie heisst der König der Niederlande (seit 2013)?", "Willem-Alexander", "Wilhelm III.", "Maximilian", "Friso"),
    ("Wann ist der Königstag?", "27. April", "30. April", "5. Mai", "1. Mai"),
    ("Welche Stadt hat den grössten Hafen Europas?", "Rotterdam", "Antwerpen", "Hamburg", "Amsterdam"),
    ("Wie heisst der grosse Damm zwischen IJsselmeer und Wattenmeer?", "Afsluitdijk", "Deltawerke", "Oosterscheldekering", "Maeslantkering"),
    ("Wie heisst der höchste Punkt im europäischen Teil der Niederlande?", "Vaalserberg", "Brocken", "Tafelberg", "Feldberg"),
    ("Welche Farbe tragen die niederländischen Sportteams?", "Orange", "Blau", "Rot", "Grün"),
    ("Wer malte «Die Nachtwache»?", "Rembrandt", "Vermeer", "Van Gogh", "Mondrian"),
    ("Welche dieser Inseln gehört zu den Niederlanden?", "Texel", "Sylt", "Föhr", "Rømø"),
    ("Welche Währung hatten die Niederlande vor dem Euro?", "Gulden", "Mark", "Franken", "Krone"),
]}

# the region of every template: the collection can be filtered (general, Switzerland, Germany …)
REGIONS = ["general", "ch", "de", "at", "nl"]
_REGION = {"ch": ["schweiz", "schweizer-gewaesser", "schweizer-spezialitaeten", "kantone-hauptorte", "kantone-umrisse", "kantone-karte",
                  "kantone-wappen", "wo-liegt-schweiz"],
           "de": ["deutschland", "deutschland-bundeslaender"], "at": ["oesterreich-bundeslaender"],
           "nl": ["niederlande", "niederlande-provinzen"]}
for _r, _ids in _REGION.items():
    for _i in _ids:
        TEMPLATES[_i]["region"] = _r
for _t in TEMPLATES.values():
    _t.setdefault("region", "general")
