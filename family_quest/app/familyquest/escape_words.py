"""Words for the language riddles of «Escape Room» (escape_riddles.py): one concept in the 9 languages of the app
(and English). Every device shows a word riddle in its own language; the answer counts in any of them.

Fields: emoji, category (animal | food | thing | nature), words per language (en de fr it es nl pl pt sv;
de-CH uses de).
"""
from __future__ import annotations

import unicodedata

LANGS = ("en", "de", "fr", "it", "es", "nl", "pl", "pt", "sv")

#        emoji  cat       en           de            fr             it            es           nl           pl            pt          sv
_RAW = [
    ("🍎", "food", "apple", "Apfel", "pomme", "mela", "manzana", "appel", "jabłko", "maçã", "äpple"),
    ("🍌", "food", "banana", "Banane", "banane", "banana", "plátano", "banaan", "banan", "banana", "banan"),
    ("🐱", "animal", "cat", "Katze", "chat", "gatto", "gato", "kat", "kot", "gato", "katt"),
    ("🐶", "animal", "dog", "Hund", "chien", "cane", "perro", "hond", "pies", "cachorro", "hund"),
    ("🐴", "animal", "horse", "Pferd", "cheval", "cavallo", "caballo", "paard", "koń", "cavalo", "häst"),
    ("🐭", "animal", "mouse", "Maus", "souris", "topo", "ratón", "muis", "mysz", "rato", "mus"),
    ("🐟", "animal", "fish", "Fisch", "poisson", "pesce", "pez", "vis", "ryba", "peixe", "fisk"),
    ("🐦", "animal", "bird", "Vogel", "oiseau", "uccello", "pájaro", "vogel", "ptak", "pássaro", "fågel"),
    ("🌳", "nature", "tree", "Baum", "arbre", "albero", "árbol", "boom", "drzewo", "árvore", "träd"),
    ("🏠", "thing", "house", "Haus", "maison", "casa", "casa", "huis", "dom", "casa", "hus"),
    ("☀️", "nature", "sun", "Sonne", "soleil", "sole", "sol", "zon", "słońce", "sol", "sol"),
    ("🌙", "nature", "moon", "Mond", "lune", "luna", "luna", "maan", "księżyc", "lua", "måne"),
    ("⭐", "nature", "star", "Stern", "étoile", "stella", "estrella", "ster", "gwiazda", "estrela", "stjärna"),
    ("📚", "thing", "book", "Buch", "livre", "libro", "libro", "boek", "książka", "livro", "bok"),
    ("⚽", "thing", "ball", "Ball", "ballon", "palla", "pelota", "bal", "piłka", "bola", "boll"),
    ("⛵", "thing", "boat", "Boot", "bateau", "barca", "barco", "boot", "łódź", "barco", "båt"),
    ("🚗", "thing", "car", "Auto", "voiture", "macchina", "coche", "auto", "samochód", "carro", "bil"),
    ("🚂", "thing", "train", "Zug", "train", "treno", "tren", "trein", "pociąg", "trem", "tåg"),
    ("🌸", "nature", "flower", "Blume", "fleur", "fiore", "flor", "bloem", "kwiat", "flor", "blomma"),
    ("🎂", "food", "cake", "Kuchen", "gâteau", "torta", "pastel", "taart", "ciasto", "bolo", "tårta"),
    ("🍞", "food", "bread", "Brot", "pain", "pane", "pan", "brood", "chleb", "pão", "bröd"),
    ("🧀", "food", "cheese", "Käse", "fromage", "formaggio", "queso", "kaas", "ser", "queijo", "ost"),
    ("🦁", "animal", "lion", "Löwe", "lion", "leone", "león", "leeuw", "lew", "leão", "lejon"),
    ("🐯", "animal", "tiger", "Tiger", "tigre", "tigre", "tigre", "tijger", "tygrys", "tigre", "tiger"),
    ("🐻", "animal", "bear", "Bär", "ours", "orso", "oso", "beer", "niedźwiedź", "urso", "björn"),
    ("🐸", "animal", "frog", "Frosch", "grenouille", "rana", "rana", "kikker", "żaba", "sapo", "groda"),
    ("🦆", "animal", "duck", "Ente", "canard", "anatra", "pato", "eend", "kaczka", "pato", "anka"),
    ("🦉", "animal", "owl", "Eule", "hibou", "gufo", "búho", "uil", "sowa", "coruja", "uggla"),
    ("🐍", "animal", "snake", "Schlange", "serpent", "serpente", "serpiente", "slang", "wąż", "cobra", "orm"),
    ("🐰", "animal", "rabbit", "Hase", "lapin", "coniglio", "conejo", "konijn", "królik", "coelho", "kanin"),
    ("🔑", "thing", "key", "Schlüssel", "clé", "chiave", "llave", "sleutel", "klucz", "chave", "nyckel"),
    ("🚪", "thing", "door", "Tür", "porte", "porta", "puerta", "deur", "drzwi", "porta", "dörr"),
    ("🏰", "thing", "castle", "Burg", "château", "castello", "castillo", "kasteel", "zamek", "castelo", "slott"),
    ("🐉", "thing", "dragon", "Drache", "dragon", "drago", "dragón", "draak", "smok", "dragão", "drake"),
    ("🚀", "thing", "rocket", "Rakete", "fusée", "razzo", "cohete", "raket", "rakieta", "foguete", "raket"),
    ("🐘", "animal", "elephant", "Elefant", "éléphant", "elefante", "elefante", "olifant", "słoń", "elefante", "elefant"),
    ("🐄", "animal", "cow", "Kuh", "vache", "mucca", "vaca", "koe", "krowa", "vaca", "ko"),
    ("🐷", "animal", "pig", "Schwein", "cochon", "maiale", "cerdo", "varken", "świnia", "porco", "gris"),
    ("🍋", "food", "lemon", "Zitrone", "citron", "limone", "limón", "citroen", "cytryna", "limão", "citron"),
    ("🐝", "animal", "bee", "Biene", "abeille", "ape", "abeja", "bij", "pszczoła", "abelha", "bi"),
    ("🦊", "animal", "fox", "Fuchs", "renard", "volpe", "zorro", "vos", "lis", "raposa", "räv"),
    ("🐑", "animal", "sheep", "Schaf", "mouton", "pecora", "oveja", "schaap", "owca", "ovelha", "får"),
    ("🎈", "thing", "balloon", "Ballon", "ballon", "palloncino", "globo", "ballon", "balon", "balão", "ballong"),
    ("🐢", "animal", "turtle", "Schildkröte", "tortue", "tartaruga", "tortuga", "schildpad", "żółw", "tartaruga", "sköldpadda"),
    ("👑", "thing", "crown", "Krone", "couronne", "corona", "corona", "kroon", "korona", "coroa", "krona"),
]

CONCEPTS = [{"emoji": r[0], "cat": r[1], "words": dict(zip(LANGS, r[2:]))} for r in _RAW]


def plain(s: str) -> str:
    """Lower case, without accents, only letters and digits – how answers are compared (ł → l, ß → ss)."""
    s = str(s or "").lower().replace("ß", "ss").replace("ł", "l").replace("æ", "ae").replace("ø", "o")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isascii() and c.isalnum())


def upper(word: str) -> str:
    """The word as shown in riddles: capital letters (accents kept)."""
    return word.upper().replace("ß", "SS")


def accepted(concept: dict) -> list[str]:
    """Every spelling that counts as the right answer (all languages, without accents)."""
    return sorted({plain(w) for w in concept["words"].values()})


def length(concept: dict) -> float:
    """The typical length of the word (the middle of all languages)."""
    ls = sorted(len(plain(w)) for w in concept["words"].values())
    return ls[len(ls) // 2]
