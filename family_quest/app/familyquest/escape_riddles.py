"""The riddles of «Escape Room» (escape.py): 56 riddle templates in 9 types, every one made fresh for each game from
random numbers (the server's random generator) – so the answers differ every game.

A template makes a riddle for a level (easy / medium / hard; a template supports some of them):

    {"lines": [[key, arg, …], …],    texts (English keys, translated by the app; an arg {"t": key} is translated too,
                                      an arg or value {"L": {lang: …}} is chosen by the language of the device)
     "show": [block, …],              what the riddle shows (numbers, emoji, a clock, a pyramid … – see web/escape.js)
     "input": {...},                  how it is answered (code, text, choice, cells, order, lights, slide, rings, pipes,
                                      levers)
     "sol": …, "check": kind,         the solution and how an answer is checked – never sent to the app
     "hints": [[key, arg, …], …],     up to 3 hints (shown one after the other, each costs time)
     "peek": seconds}                 memory riddles: «show» only for a moment after «Look» (the app asks the server)

check(riddle, answer) is the only judge. Language riddles (anagram, secret writing …) show the word in the
language of each device and accept the word in any language of the app.
"""
from __future__ import annotations

import itertools
import re

from .escape_words import CONCEPTS, LANGS, accepted, length, plain, upper
from .i18n import _t

TYPES = ("logic", "words", "observe", "patterns", "maths", "memory", "maps", "mechanic", "knowledge")
TYPE_NAMES = {"logic": _t("Logic & codes"), "words": _t("Words & letters"), "observe": _t("Pictures & observation"),
              "patterns": _t("Patterns & sequences"), "maths": _t("Maths"), "memory": _t("Memory"),
              "maps": _t("Maps & directions"), "mechanic": _t("Mechanical puzzles"), "knowledge": _t("Knowledge")}
TYPE_ICONS = {"logic": "🔐", "words": "🔤", "observe": "🔍", "patterns": "🔁", "maths": "➗", "memory": "🧠",
              "maps": "🧭", "mechanic": "⚙️", "knowledge": "📖"}
LEVELS = ("easy", "medium", "hard")

COLOURS = [("red", _t("red"), "#e03131"), ("yellow", _t("yellow"), "#fcc419"), ("blue", _t("blue"), "#1c7ed6"),
           ("green", _t("green"), "#2f9e44"), ("purple", _t("purple"), "#9c36b5"), ("orange", _t("orange"), "#f76707"),
           ("white", _t("white"), "#f1f3f5"), ("black", _t("black"), "#212529"), ("pink", _t("pink"), "#f783ac"),
           ("grey", _t("grey"), "#868e96"), ("brown", _t("brown"), "#8d5524")]
COLOUR = {c[0]: c for c in COLOURS}


def t(key: str) -> dict:
    return {"t": key}


def col(name: str) -> dict:
    """A colour option / argument: its name (translated) and its colour."""
    c = COLOUR[name]
    return {"t": c[1], "c": c[2]}


def per_lang(concept: dict, fn) -> dict:
    return {"L": {lg: fn(concept["words"][lg]) for lg in LANGS}}


def letters(word: str) -> str:
    return plain(word).upper()


def _concept(rng, level: str, pool=None, need_ascii=False) -> dict:
    """A concept whose word fits the level (short words easy, long words hard)."""
    pool = list(pool or CONCEPTS)
    lo, hi = {"easy": (0, 4), "medium": (4, 6), "hard": (6, 99)}[level]
    fit = [c for c in pool if lo <= length(c) <= hi] or pool
    return rng.choice(fit)


# ================================================================ logic & codes
def lock_clues(rng, level):
    n = 3 if level != "hard" else 4
    codes = ["".join(p) for p in itertools.permutations("0123456789", n)]

    def fb(secret, guess):
        right = sum(a == b for a, b in zip(secret, guess))
        return right, len(set(secret) & set(guess)) - right
    for _ in range(50):
        secret = rng.choice(codes)
        cand, clues = codes, []
        while len(cand) > 1 and len(clues) < 6:
            best = None
            for g in rng.sample(codes, 15):
                if g == secret or any(g == c[0] for c in clues):
                    continue
                f = fb(secret, g)
                left = [c for c in cand if fb(c, g) == f]
                if best is None or len(left) < len(best[2]):
                    best = (g, f, left)
            clues.append((best[0], *best[1]))
            cand = best[2]
        if len(cand) == 1 and len(clues) >= 3:
            break
    return {"lines": [[_t("The lock has a code of {0} different digits. Every line is a try:"), n],
                      [_t("✅ = right digit in the right place · 🔄 = right digit in the wrong place")]],
            "show": [{"k": "rows", "head": ["🔢", "✅", "🔄"], "v": [[g, str(a), str(b)] for g, a, b in clues]}],
            "input": {"k": "num", "max": n}, "sol": secret, "check": "digits",
            "hints": [[_t("The first digit is {0}."), secret[0]], [_t("The last digit is {0}."), secret[-1]],
                      [_t("The code starts with {0}."), secret[:2]]]}


_DD = [  # digit detective: (key, test(code, x), x choices)
    ("sum", _t("The three digits add up to {0}."), lambda c, x: sum(c) == x),
    ("first_more", _t("The first digit is {0} more than the last one."), lambda c, x: c[0] - c[2] == x),
    ("mid_big", _t("The middle digit is the biggest."), lambda c, x: c[1] > c[0] and c[1] > c[2]),
    ("last_even", _t("The last digit is even."), lambda c, x: c[2] % 2 == 0),
    ("last_odd", _t("The last digit is odd."), lambda c, x: c[2] % 2 == 1),
    ("diff", _t("All digits are different."), lambda c, x: len(set(c)) == 3),
    ("double", _t("The first digit is double the middle one."), lambda c, x: c[0] == 2 * c[1]),
    ("mid", _t("The middle digit is {0}."), lambda c, x: c[1] == x),
    ("first_small", _t("The first digit is smaller than {0}."), lambda c, x: c[0] < x),
    ("same", _t("Two digits are the same."), lambda c, x: len(set(c)) == 2),
    ("last_is", _t("The last digit is {0}."), lambda c, x: c[2] == x),
]


def digit_detective(rng, level):
    allc = list(itertools.product(range(1, 10), repeat=3))
    for _ in range(200):
        code = rng.choice(allc)
        facts = []
        for key, text, fn in _DD:
            if key in ("mid", "last_is") and level != "easy":
                continue
            x = {"sum": sum(code), "first_more": code[0] - code[2], "mid": code[1], "last_is": code[2],
                 "first_small": code[0] + rng.randint(1, 3)}.get(key)
            if key == "first_more" and x <= 0:
                continue
            if key == "first_small" and x > 9:
                continue
            if fn(code, x):
                facts.append((text, fn, x))
        rng.shuffle(facts)
        cand, used = allc, []
        for text, fn, x in facts:
            nxt = [c for c in cand if fn(c, x)]
            if len(nxt) < len(cand):
                cand, used = nxt, used + [(text, x)]
            if len(cand) == 1:
                break
        if len(cand) == 1 and 3 <= len(used) <= 5:
            s = "".join(map(str, code))
            return {"lines": [[_t("The secret number has three digits from 1 to 9.")]] + [[tx] + ([x] if "{0}" in tx else []) for tx, x in used],
                    "input": {"k": "num", "max": 3}, "sol": s, "check": "digits",
                    "hints": [[_t("The first digit is {0}."), s[0]], [_t("The last digit is {0}."), s[2]], [_t("The code starts with {0}."), s[:2]]]}
    return lock_clues(rng, "medium")


def liar_chests(rng, level):
    names = ["red", "blue", "green"]
    want = 1 if level != "hard" else 2               # how many sentences are true
    forms = ["in", "notin", "here", "nothere"]
    for _ in range(500):
        st = []
        for i in range(3):
            f = rng.choice(forms)
            x = rng.randrange(3)
            st.append((f, x if f in ("in", "notin") else i))
        good = []
        for g in range(3):
            n = sum((g == x) if f in ("in", "here") else (g != x) for f, x in st)
            if n == want:
                good.append(g)
        if len(good) == 1:
            gold = good[0]
            break
    texts = {"in": _t("The gold is in the {0} chest."), "notin": _t("The gold is not in the {0} chest."),
             "here": _t("The gold is in this chest."), "nothere": _t("The gold is not in this chest.")}
    lines = [[_t("Three chests – only one holds the gold. Each chest has a sign:")]]
    for i, (f, x) in enumerate(st):
        lines.append([_t("{0} chest: «{1}»"), col(names[i]), {"line": [texts[f]] + ([col(names[x])] if f in ("in", "notin") else [])}])
    lines.append([_t("Exactly one sign tells the truth.")] if want == 1 else [_t("Exactly one sign lies.")])
    wrong = [i for i in range(3) if i != gold]
    rng.shuffle(wrong)
    return {"lines": lines, "input": {"k": "choice", "opts": [{"v": "🧰", **col(n)} for n in names], "cols": 3},
            "sol": gold, "check": "choice",
            "hints": [[_t("Imagine the gold is in the red chest: how many signs would be true?")],
                      [_t("The gold is not in the {0} chest."), col(names[wrong[0]])],
                      [_t("The gold is not in the {0} chest."), col(names[wrong[1]])]]}


ANIMALS = ["🐱", "🐶", "🐭", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐧", "🐔", "🦉", "🐢"]


def seat_order(rng, level):
    n = 3 if level == "medium" else 4 if level == "hard" else 3
    who = rng.sample(ANIMALS, n)
    perms = list(itertools.permutations(range(n)))
    for _ in range(300):
        order = list(rng.choice(perms))                       # order[place] = animal index
        pos = {a: i for i, a in enumerate(order)}
        facts = []
        for a, b in itertools.permutations(range(n), 2):
            if pos[a] + 1 == pos[b]:
                facts.append((_t("{0} sits directly left of {1}."), (a, b), lambda p, a=a, b=b: p[a] + 1 == p[b]))
            if pos[a] < pos[b]:
                facts.append((_t("{0} sits somewhere left of {1}."), (a, b), lambda p, a=a, b=b: p[a] < p[b]))
            if abs(pos[a] - pos[b]) != 1 and a < b:
                facts.append((_t("{0} does not sit next to {1}."), (a, b), lambda p, a=a, b=b: abs(p[a] - p[b]) != 1))
        for a in range(n):
            if pos[a] in (0, n - 1):
                facts.append((_t("{0} sits at one end."), (a,), lambda p, a=a: p[a] in (0, n - 1)))
            else:
                facts.append((_t("{0} does not sit at an end."), (a,), lambda p, a=a: p[a] not in (0, n - 1)))
        rng.shuffle(facts)
        cand = [dict((a, i) for i, a in enumerate(pm)) for pm in perms]
        used = []
        for text, args, fn in facts:
            nxt = [p for p in cand if fn(p)]
            if len(nxt) < len(cand):
                cand, used = nxt, used + [(text, args)]
            if len(cand) == 1:
                break
        if len(cand) == 1 and len(used) <= n + 1:
            break
    lines = [[_t("The animals sit on one bench. Tap them from left to right!")]]
    lines += [[text] + [who[a] for a in args] for text, args in used]
    return {"lines": lines, "input": {"k": "order", "opts": [{"v": w} for w in who], "len": n},
            "sol": order, "check": "seq",
            "hints": [[_t("Place {0} from the left: {1}"), 1, who[order[0]]], [_t("Place {0} from the left: {1}"), n, who[order[-1]]],
                      [_t("Place {0} from the left: {1}"), 2, who[order[1]]]]}


def heaviest(rng, level):
    n = {"easy": 3, "medium": 4, "hard": 5}[level]
    who = rng.sample(ANIMALS, n)
    rank = list(range(n))
    rng.shuffle(rank)                                         # rank[i]: weight order (bigger = heavier)
    light = rng.random() < 0.3 and level != "easy"
    target = (min if light else max)(range(n), key=lambda i: rank[i])
    comps = []
    for x in range(n):
        if x == target:
            continue
        if light:          # x is heavier than somebody
            ys = [y for y in range(n) if rank[y] < rank[x]]
        else:
            ys = [y for y in range(n) if rank[y] > rank[x]]
        y = rng.choice(ys)
        comps.append((y, x) if not light else (x, y))         # (heavier, lighter)
    rng.shuffle(comps)
    others = [i for i in range(n) if i != target]
    rng.shuffle(others)
    return {"lines": [[_t("The scales show:")]] + [[_t("{0} is heavier than {1}."), who[a], who[b]] for a, b in comps]
            + [[_t("Which animal is the lightest?")] if light else [_t("Which animal is the heaviest?")]],
            "input": {"k": "choice", "opts": [{"v": w} for w in who], "cols": min(n, 5)}, "sol": target, "check": "choice",
            "hints": [[_t("It is not {0}."), who[o]] for o in others[:3]]}


def _sudoku_solutions(g, limit=2):
    out = []

    def ok(i, v):
        r, c = divmod(i, 4)
        if any(g[r * 4 + k] == v for k in range(4)) or any(g[k * 4 + c] == v for k in range(4)):
            return False
        br, bc = r // 2 * 2, c // 2 * 2
        return all(g[(br + a) * 4 + bc + b] != v for a in range(2) for b in range(2))

    def go():
        if len(out) >= limit:
            return
        try:
            i = g.index(0)
        except ValueError:
            out.append(list(g))
            return
        for v in range(1, 5):
            if ok(i, v):
                g[i] = v
                go()
                g[i] = 0
    go()
    return out


def mini_sudoku(rng, level):
    base = [[1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 1]]
    digits = [1, 2, 3, 4]
    rng.shuffle(digits)
    rows = [0, 1] if rng.random() < .5 else [1, 0]
    rows += [2, 3] if rng.random() < .5 else [3, 2]
    if rng.random() < .5:
        rows = rows[2:] + rows[:2]
    grid = [[digits[base[r][c] - 1] for c in range(4)] for r in rows]
    if rng.random() < .5:
        grid = [list(x) for x in zip(*grid)]
    full = [v for row in grid for v in row]
    g = list(full)
    keep = 7 if level == "medium" else 5
    cells = list(range(16))
    rng.shuffle(cells)
    for i in cells:
        if sum(1 for v in g if v) <= keep:
            break
        v, g[i] = g[i], 0
        if len(_sudoku_solutions(list(g))) != 1:
            g[i] = v
    empty = [i for i in range(16) if not g[i]]
    a, b = sorted(rng.sample(empty, 2))
    view = [str(v) if v else "" for v in g]
    view[a], view[b] = "⭐", "🌙"
    sol = f"{full[a]}{full[b]}"
    return {"lines": [[_t("Every row, every column and every 2×2 box has the numbers 1 to 4 once.")],
                      [_t("The code: the number on the ⭐, then the number on the 🌙.")]],
            "show": [{"k": "grid", "n": 4, "box": 2, "v": view}], "input": {"k": "num", "max": 2}, "sol": sol, "check": "digits",
            "hints": [[_t("Start with a row or column where only one number is missing.")], [_t("The ⭐ is {0}."), sol[0]],
                      [_t("The 🌙 is {0}."), sol[1]]]}


# ================================================================ words & letters (in the language of each device)
def _word_hints(c, more=None):
    return ([more] if more else []) + [[_t("It looks like this: {0}"), c["emoji"]],
                                       [_t("It starts with {0}."), per_lang(c, lambda w: upper(w)[0])]]


def anagram(rng, level):
    c = _concept(rng, level)

    def mix(w):
        w = upper(w)
        if len(set(w)) < 2:
            return w
        for _ in range(30):
            x = list(w)
            rng.shuffle(x)
            if "".join(x) != w:
                return " ".join(x)
        return " ".join(reversed(w))
    return {"lines": [[_t("The letters got mixed up! Which word is it?")]], "show": [{"k": "big", "v": per_lang(c, mix)}],
            "input": {"k": "text"}, "sol": accepted(c), "check": "word",
            "hints": [[_t("It looks like this: {0}"), c["emoji"]], [_t("It starts with {0}."), per_lang(c, lambda w: upper(w)[0])],
                      [_t("It ends with {0}."), per_lang(c, lambda w: upper(w)[-1])]]}


def _shift(w, k):
    return "".join(chr((ord(ch) - 65 + k) % 26 + 65) for ch in letters(w))


def caesar(rng, level):
    c = _concept(rng, "medium" if level == "medium" else "hard")
    k = rng.randint(1, 3) if level == "medium" else rng.randint(2, 5)
    lines = [[_t("A secret message! Every letter was moved forward in the alphabet.")]]
    if level == "medium":
        lines.append([_t("The key: A → {0}, B → {1}"), chr(65 + k), chr(66 + k)])
    return {"lines": lines + [[_t("(Letters without accents.)")]], "show": [{"k": "big", "v": per_lang(c, lambda w: " ".join(_shift(w, k)))},
                                                                            {"k": "abc"}],
            "input": {"k": "text"}, "sol": accepted(c), "check": "word",
            "hints": [[_t("Every letter was moved {0} places."), k], [_t("It looks like this: {0}"), c["emoji"]],
                      [_t("It starts with {0}."), per_lang(c, lambda w: letters(w)[0])]]}


RUNES = ["☽", "☀", "★", "♠", "♣", "♥", "♦", "☂", "☁", "⚑", "♫", "✿", "❄", "⚓", "☘", "✈", "⌂", "♞", "☯", "⚡", "✂", "☎", "✉", "♜", "☕", "⚙"]


def rune_alphabet(rng, level):
    c = _concept(rng, level)
    sym = list(RUNES)
    rng.shuffle(sym)
    code = {chr(65 + i): sym[i] for i in range(26)}

    def key(w):
        ls = sorted(set(letters(w)))
        extra = [x for x in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if x not in ls]
        rng.shuffle(extra)
        ls = sorted(ls + extra[:3])
        return [[code[x], x] for x in ls]
    return {"lines": [[_t("An old rune alphabet! Use the key to read the word.")], [_t("(Letters without accents.)")]],
            "show": [{"k": "big", "v": per_lang(c, lambda w: " ".join(code[x] for x in letters(w)))},
                     {"k": "key", "v": per_lang(c, key)}],
            "input": {"k": "text"}, "sol": accepted(c), "check": "word", "hints": _word_hints(c)}


def missing_letters(rng, level):
    c = _concept(rng, "easy" if level == "easy" else "medium")

    def gaps(w):
        w = upper(w)
        idx = list(range(len(w)))
        rng.shuffle(idx)
        hide = set(idx[:max(1, len(w) * (2 if level == "easy" else 3) // 5)])
        if len(hide) >= len(w):
            hide = set(idx[:len(w) - 1])
        return " ".join("_" if i in hide else ch for i, ch in enumerate(w))
    lines = [[_t("The sign is worn out – some letters are missing. Which word is it?")]]
    if level == "easy":
        lines.append([_t("It looks like this: {0}"), c["emoji"]])
    return {"lines": lines, "show": [{"k": "big", "v": per_lang(c, gaps)}], "input": {"k": "text"},
            "sol": accepted(c), "check": "word",
            "hints": ([] if level == "easy" else [[_t("It looks like this: {0}"), c["emoji"]]])
            + [[_t("It starts with {0}."), per_lang(c, lambda w: upper(w)[0])], [_t("It ends with {0}."), per_lang(c, lambda w: upper(w)[-1])]]}


def mirror_word(rng, level):
    c = _concept(rng, rng.choice(["easy", "medium"]))
    return {"lines": [[_t("Somebody wrote this backwards. Read it from right to left!")]],
            "show": [{"k": "big", "v": per_lang(c, lambda w: upper(w)[::-1])}], "input": {"k": "text"},
            "sol": accepted(c), "check": "word", "hints": _word_hints(c)}


def word_search(rng, level):
    n = 6 if level == "medium" else 7
    animals = [x for x in CONCEPTS if x["cat"] == "animal" and all(len(upper(w)) <= n for w in x["words"].values())]
    c = rng.choice(animals)
    rows_of = {}

    def grid(w):
        w = upper(w)
        for _ in range(100):
            g = [rng.choice("ABCDEFGHIJKLMNOPRSTUVZ") for _ in range(n * n)]
            d = rng.choice([(0, 1), (1, 0)] + ([(0, -1), (1, 1)] if level == "hard" else []))
            r0, c0 = rng.randrange(n), rng.randrange(n)
            cells = [(r0 + d[0] * i, c0 + d[1] * i) for i in range(len(w))]
            if all(0 <= r < n and 0 <= q < n for r, q in cells):
                for (r, q), ch in zip(cells, w):
                    g[r * n + q] = ch
                rows_of[w] = cells[0]
                return g
        return list(w.ljust(n * n, "A"))[:n * n]
    g = per_lang(c, grid)
    return {"lines": [[_t("An animal is hidden in the letters (in a straight line). Which one?")]],
            "show": [{"k": "letters", "n": n, "v": g}], "input": {"k": "text"}, "sol": accepted(c), "check": "word",
            "hints": [[_t("Look along the rows and the columns – also backwards and diagonally.") if level == "hard" else _t("Look along the rows and the columns.")],
                      [_t("It looks like this: {0}"), c["emoji"]], [_t("It starts with {0}."), per_lang(c, lambda w: upper(w)[0])]]}


def letter_numbers(rng, level):
    c = _concept(rng, level if level != "easy" else "medium")
    return {"lines": [[_t("A = 1, B = 2, C = 3 … Which word do the numbers spell?")], [_t("(Letters without accents.)")]],
            "show": [{"k": "big", "v": per_lang(c, lambda w: " - ".join(str(ord(ch) - 64) for ch in letters(w)))}, {"k": "abc", "num": True}],
            "input": {"k": "text"}, "sol": accepted(c), "check": "word", "hints": _word_hints(c)}


CATS = {"animal": _t("It is an animal."), "food": _t("It is something to eat."), "thing": _t("It is a thing."), "nature": _t("It is in nature.")}


def vowel_thief(rng, level):
    c = _concept(rng, "medium")

    def cons(w):
        w = upper(w)
        k = "".join(ch for ch in w if plain(ch) not in ("a", "e", "i", "o", "u", "y"))
        return " ".join(k) or w[0]
    return {"lines": [[_t("The vowel thief stole all the vowels (A E I O U Y)! Which word was it?")]],
            "show": [{"k": "big", "v": per_lang(c, cons)}], "input": {"k": "text"}, "sol": accepted(c), "check": "word",
            "hints": [[CATS[c["cat"]]], [_t("It looks like this: {0}"), c["emoji"]], [_t("It starts with {0}."), per_lang(c, lambda w: upper(w)[0])]]}


# ================================================================ pictures & observation
BUGS = [["🐞", "🐝", "🦋", "🐛"], ["🍄", "🌸", "🌼", "🍀"], ["🐟", "🐠", "🐡", "🦀"], ["⭐", "🌙", "☁️", "⚡"], ["🍎", "🍐", "🍊", "🍋"]]


def count_objects(rng, level):
    kinds = rng.choice(BUGS)
    n = 30 if level == "easy" else 36
    cells = [rng.choice(kinds) if rng.random() < 0.8 else "" for _ in range(n)]
    a = rng.choice(kinds)
    if level == "easy":
        ask, lines = [a], [[_t("How many {0} can you see?"), a]]
    else:
        b = rng.choice([k for k in kinds if k != a])
        ask, lines = [a, b], [[_t("How many {0} and {1} are there together?"), a, b]]
    sol = sum(1 for x in cells if x in ask)
    first = sum(1 for x in cells[:6] if x in ask)
    return {"lines": lines, "show": [{"k": "emo", "cols": 6, "v": cells}], "input": {"k": "num", "max": 2}, "sol": str(sol), "check": "int",
            "hints": [[_t("Count row by row – the first row has {0}."), first], [_t("It is more than {0}."), max(0, sol - 3 - rng.randint(0, 2))],
                      [_t("It is less than {0}."), sol + 1 + rng.randint(0, 2)]]}


PAIRS = [("😀", "😃"), ("🐟", "🐠"), ("🌕", "🌝"), ("🍏", "🍎"), ("🌲", "🌳"), ("🐌", "🐚"), ("🔵", "🟣"), ("🍪", "🥯"), ("🐑", "🐏"), ("🕐", "🕑")]


def odd_one(rng, level):
    cols = 5 if level == "easy" else 6
    a, b = rng.choice(PAIRS)
    if rng.random() < .5:
        a, b = b, a
    n = cols * cols
    i = rng.randrange(n)
    cells = [b if k == i else a for k in range(n)]
    r, c = divmod(i, cols)
    return {"lines": [[_t("One of them is different. Tap it!")]], "input": {"k": "cells", "cols": cols, "v": cells},
            "sol": i, "check": "choice",
            "hints": [[_t("It is in row {0}."), r + 1], [_t("It is in column {0}."), c + 1], [_t("It looks like this: {0}"), b]]}


SCENE = ["🌳", "🏠", "🐶", "🐱", "🚗", "🌼", "⭐", "🍎", "🎈", "🐦", "☀️", "🌙", "🐟", "🍄", "⚽", "🎁"]


def two_pictures(rng, level):
    cols = 4 if level == "medium" else 5
    k = 3 if level == "medium" else 4
    left = [rng.choice(SCENE) for _ in range(cols * cols)]
    right = list(left)
    diff = sorted(rng.sample(range(cols * cols), k))
    for i in diff:
        right[i] = rng.choice([x for x in SCENE if x != left[i]])
    rows = sorted({i // cols + 1 for i in diff})
    return {"lines": [[_t("The right picture has {0} differences. Tap them in the right picture!"), k]],
            "show": [{"k": "emo", "cols": cols, "v": left, "label": t(_t("Left picture"))}],
            "input": {"k": "cells", "cols": cols, "v": right, "multi": k, "label": t(_t("Right picture"))}, "sol": diff, "check": "set",
            "hints": [[_t("There is a difference in row {0}."), rows[0]], [_t("There is a difference in row {0}."), rows[-1]],
                      [_t("Compare field by field, row by row.")]]}


def clock_read(rng, level):
    h = rng.randint(1, 12)
    m = rng.choice([0, 30]) if level == "easy" else rng.choice(range(0, 60, 5))
    lines = [[_t("The clock stopped. What time does it show? Type it with 4 digits, e.g. 0730.")]]
    sh, sm = h, m
    if level != "easy":
        fast = rng.choice([10, 15, 20, 30])
        tot = (h * 60 + m - fast) % 720
        sh, sm = tot // 60 or 12, tot % 60
        lines = [[_t("This clock is {0} minutes fast. What is the real time? Type it with 4 digits, e.g. 0730."), fast]]
    sol = f"{sh:02d}{sm:02d}"
    return {"lines": lines, "show": [{"k": "clock", "h": h, "m": m}], "input": {"k": "num", "max": 4}, "sol": sol, "check": "time",
            "hints": [[_t("The short hand shows the hours, the long hand the minutes.")], [_t("The hour is {0}."), sh],
                      [_t("The minutes are {0}."), sm]]}


def shelf_book(rng, level):
    names = ["red", "blue", "green", "yellow"]
    n = 8 if level == "easy" else 10
    books = [rng.choice(names) for _ in range(n)]
    want = rng.choice(names)
    if books.count(want) < 2:
        for i in rng.sample(range(n), 2):
            books[i] = want
    side = rng.choice(["left", "right"])
    if level == "easy":
        idx = [i for i, b in enumerate(books) if b == want]
        text = _t("Count the {0} books from the left: the key is in number {1}.") if side == "left" else _t("Count the {0} books from the right: the key is in number {1}.")
    else:
        idx = [i for i, b in enumerate(books) if b != want]
        text = _t("Count the books that are NOT {0} from the left: the key is in number {1}.") if side == "left" else _t("Count the books that are NOT {0} from the right: the key is in number {1}.")
    if side == "right":
        idx = idx[::-1]
    k = rng.randrange(min(len(idx), 4))
    return {"lines": [[text, col(want), k + 1], [_t("Tap the book with the key!")]],
            "input": {"k": "choice", "opts": [{"v": "📕", **col(b)} for b in books], "cols": n, "books": True},
            "sol": idx[k], "check": "choice",
            "hints": [[_t("Start on the left.") if side == "left" else _t("Start on the right.")], [_t("Skip every book that does not count.")],
                      [_t("It is book number {0} from the left."), idx[k] + 1]]}


def candle_code(rng, level):
    kinds = rng.sample([("red", "🔴"), ("yellow", "🟡"), ("blue", "🔵"), ("green", "🟢"), ("purple", "🟣")], 3)
    counts = [rng.randint(2, 9) for _ in kinds]
    cells = [e for (_, e), c in zip(kinds, counts) for _ in range(c)]
    cells += [""] * (30 - len(cells))
    rng.shuffle(cells)
    sol = "".join(map(str, counts))
    return {"lines": [[_t("Candles in three colours. The code: how many {0}, then {1}, then {2}?"), kinds[0][1], kinds[1][1], kinds[2][1]]],
            "show": [{"k": "emo", "cols": 6, "v": cells}], "input": {"k": "num", "max": 3}, "sol": sol, "check": "digits",
            "hints": [[_t("There are {0} × {1}."), counts[0], kinds[0][1]], [_t("There are {0} × {1}."), counts[1], kinds[1][1]],
                      [_t("There are {0} × {1}."), counts[2], kinds[2][1]]]}


def mirror_pick(rng, level):
    row = rng.sample(SCENE, 4 if level != "hard" else 5)
    good = row[::-1]
    opts = [good, list(row)]
    while len(opts) < 4:
        x = list(good)
        i = rng.randrange(len(x) - 1)
        x[i], x[i + 1] = x[i + 1], x[i]
        if x not in opts:
            opts.append(x)
    order = list(range(4))
    rng.shuffle(order)
    return {"lines": [[_t("Which row do you see in the mirror?")]], "show": [{"k": "emo", "cols": len(row), "v": row}, {"k": "mirror"}],
            "input": {"k": "choice", "opts": [{"v": " ".join(opts[i])} for i in order], "cols": 1}, "sol": order.index(0), "check": "choice",
            "hints": [[_t("In a mirror, left and right swap.")], [_t("The first one comes last.")],
                      [_t("The row starts with {0}."), good[0]]]}


# ================================================================ patterns & sequences
def number_row(rng, level):
    for _ in range(50):
        if level == "easy":
            kind = rng.choice(["add", "add", "sub", "double"])
        elif level == "medium":
            kind = rng.choice(["alt", "grow", "squares", "add"])
        else:
            kind = rng.choice(["fib", "x2p1", "x3m1", "sqp1", "grow2"])
        a = rng.randint(1, 9)
        k = rng.randint(2, 6)
        if kind == "add":
            s = [a + k * i for i in range(6)]
            hint = [_t("Each number is {0} more than the one before."), k]
        elif kind == "sub":
            s = [a + 5 * k - k * i for i in range(6)]
            hint = [_t("Each number is {0} less than the one before."), k]
        elif kind == "double":
            s = [rng.randint(1, 3) * 2 ** i for i in range(6)]
            hint = [_t("Each number is double the one before.")]
        elif kind == "alt":
            b = rng.choice([x for x in range(1, 7) if x != k])
            s = [a]
            for i in range(5):
                s.append(s[-1] + (k if i % 2 == 0 else b))
            hint = [_t("Add {0}, then {1}, then {0} again …"), k, b]
        elif kind == "grow":
            s = [a]
            for i in range(5):
                s.append(s[-1] + i + 1)
            hint = [_t("Add 1, then 2, then 3 …")]
        elif kind == "grow2":
            s = [a]
            for i in range(5):
                s.append(s[-1] + 2 * i + 1)
            hint = [_t("Add 1, then 3, then 5 …")]
        elif kind == "squares":
            o = rng.randint(1, 3)
            s = [(o + i) ** 2 for i in range(6)]
            hint = [_t("These are square numbers: 1×1, 2×2, 3×3 …")]
        elif kind == "sqp1":
            o = rng.randint(1, 3)
            s = [(o + i) ** 2 + 1 for i in range(6)]
            hint = [_t("Square numbers (1×1, 2×2 …) plus 1.")]
        elif kind == "fib":
            s = [a, rng.randint(1, 9)]
            while len(s) < 6:
                s.append(s[-1] + s[-2])
            hint = [_t("Each number is the sum of the two before.")]
        elif kind == "x2p1":
            s = [a]
            for _ in range(5):
                s.append(s[-1] * 2 + 1)
            hint = [_t("Double the number and add 1.")]
        else:
            s = [rng.randint(1, 3)]
            for _ in range(5):
                s.append(s[-1] * 3 - 1)
            hint = [_t("Triple the number and take away 1.")]
        if 0 < s[-1] < 1000:
            break
    return {"lines": [[_t("Which number comes next?")]], "show": [{"k": "seq", "v": [str(x) for x in s[:5]] + ["?"]}],
            "input": {"k": "num", "max": 4}, "sol": str(s[5]), "check": "int",
            "hints": [[_t("Look at how the numbers change from one to the next.")], hint, [_t("The answer is between {0} and {1}."), s[5] - rng.randint(1, 4), s[5] + rng.randint(1, 4)]]}


BEADS = ["🔴", "🟡", "🔵", "🟢", "🟣", "🟠", "⚪", "🟤"]


def necklace(rng, level):
    u = rng.randint(2, 3) if level == "easy" else 4
    unit = rng.sample(BEADS, u if level == "easy" else 3)
    if level != "easy":
        unit = unit + [unit[rng.randrange(3)]]
        rng.shuffle(unit)
    seq = [unit[i % len(unit)] for i in range(len(unit) * 3)]
    miss = len(seq) - 1 if level == "easy" else rng.randrange(len(unit), len(seq) - 1)
    ans = seq[miss]
    show = [("?" if i == miss else x) for i, x in enumerate(seq)]
    opts = list(dict.fromkeys([ans] + rng.sample(BEADS, 6)))[:4]
    rng.shuffle(opts)
    return {"lines": [[_t("Which bead belongs where the «?» is?")]], "show": [{"k": "seq", "v": show, "plain": True}],
            "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(ans), "check": "choice",
            "hints": [[_t("The pattern repeats every {0} beads."), len(unit)], [_t("Look at the bead {0} places before the «?»."), len(unit)],
                      [_t("It is {0}."), ans]]}


TILES = {"🔴": ("circle", "red"), "🟢": ("circle", "green"), "🔵": ("circle", "blue"), "🟥": ("square", "red"), "🟩": ("square", "green"),
         "🟦": ("square", "blue"), "❤️": ("heart", "red"), "💚": ("heart", "green"), "💙": ("heart", "blue")}


def latin_tiles(rng, level):
    if level == "medium":
        items = rng.sample(["🍎", "🍐", "🍊", "🍇", "🍓", "🥝"], 4)
        base = [[(r + c) % 4 for c in range(4)] for r in range(4)]
        rng.shuffle(base)
        cols = list(range(4))
        rng.shuffle(cols)
        cells = [items[base[r][c]] for r in range(4) for c in cols]
        n = 4
        miss = rng.randrange(16)
        ans = cells[miss]
        opts = list(items)
        hint3 = [_t("Each fruit is once in every row and every column.")]
    else:
        shapes, colours = ["circle", "square", "heart"], ["red", "green", "blue"]
        by = {v: k for k, v in TILES.items()}
        a = rng.sample(range(3), 3)
        b = rng.sample(range(3), 3)
        cells = [by[(shapes[a[(r + c) % 3]], colours[b[(r + 2 * c) % 3]])] for r in range(3) for c in range(3)]
        n = 3
        miss = rng.randrange(9)
        ans = cells[miss]
        sh, co = TILES[ans]
        opts = list(dict.fromkeys([ans, by[(sh, rng.choice([x for x in colours if x != co]))], by[(rng.choice([x for x in shapes if x != sh]), co)]]
                                  + rng.sample(list(TILES), 9)))[:4]
        hint3 = [_t("Every shape and every colour is once in every row and every column.")]
    rng.shuffle(opts)
    show = ["?" if i == miss else x for i, x in enumerate(cells)]
    r, c = divmod(miss, n)
    return {"lines": [[_t("Which tile belongs where the «?» is?")]], "show": [{"k": "emo", "cols": n, "v": show, "tiles": True}],
            "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(ans), "check": "choice",
            "hints": [hint3, [_t("Look at row {0}: what is missing there?"), r + 1], [_t("Look at column {0}: what is missing there?"), c + 1]]}


def growing_towers(rng, level):
    if level == "easy":
        a, k = rng.randint(1, 3), rng.randint(1, 3)
        s = [a + k * i for i in range(5)]
        hint = [_t("Each tower has {0} more blocks."), k]
    else:
        kind = rng.choice(["tri", "sq", "double"])
        if kind == "tri":
            s = [i * (i + 1) // 2 for i in range(1, 6)]
            hint = [_t("Add 1, then 2, then 3 …")]
        elif kind == "sq":
            s = [i * i for i in range(1, 6)]
            hint = [_t("These are square numbers: 1×1, 2×2, 3×3 …")]
        else:
            s = [2 ** i for i in range(5)]
            hint = [_t("Each number is double the one before.")]
    return {"lines": [[_t("How many blocks does the next tower have?")]], "show": [{"k": "towers", "v": s[:4]}],
            "input": {"k": "num", "max": 3}, "sol": str(s[4]), "check": "int",
            "hints": [[_t("Count the blocks of each tower: {0}"), ", ".join(map(str, s[:4]))], hint, [_t("It is more than {0}."), s[3]]]}


def letter_row(rng, level):
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for _ in range(50):
        kind = rng.choice(["step", "step"] if level == "medium" else ["back", "grow", "zigzag"])
        if kind == "step":
            k, a = rng.randint(2, 3), rng.randint(0, 8)
            idx = [a + k * i for i in range(6)]
            hint = [_t("Skip {0} letters each time."), k - 1]
        elif kind == "back":
            a = rng.randint(14, 25)
            k = rng.randint(2, 3)
            idx = [a - k * i for i in range(6)]
            hint = [_t("The letters go backwards through the alphabet.")]
        elif kind == "grow":
            a = rng.randint(0, 6)
            idx = [a]
            for i in range(5):
                idx.append(idx[-1] + i + 1)
            hint = [_t("Skip 0, then 1, then 2 letters …")]
        else:
            idx = []
            for i in range(6):
                idx.append(i // 2 if i % 2 == 0 else 25 - i // 2)
            hint = [_t("One from the front of the alphabet, one from the back …")]
        if all(0 <= i < 26 for i in idx):
            break
    ans = abc[idx[5]]
    opts = list(dict.fromkeys([ans, abc[(idx[5] + 1) % 26], abc[(idx[5] - 1) % 26], abc[(idx[5] + 2) % 26]]))
    rng.shuffle(opts)
    return {"lines": [[_t("Which letter comes next?")]], "show": [{"k": "seq", "v": [abc[i] for i in idx[:5]] + ["?"]}, {"k": "abc"}],
            "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(ans), "check": "choice",
            "hints": [[_t("Write down the alphabet and mark the letters.")], hint, [_t("It is not {0}."), next(o for o in opts if o != ans)]]}


def clock_steps(rng, level):
    step = rng.choice([30, 45, 75, 90]) if level == "medium" else rng.choice([105, 140, 155, 200])
    start = rng.randint(1, 8) * 60 + rng.choice([0, 15, 30, 45])
    times = [start + step * i for i in range(5)]
    fmt = [f"{(x // 60 - 1) % 12 + 1}:{x % 60:02d}" for x in times]
    ans = times[4] % 720
    sol = f"{(ans // 60) or 12:02d}{ans % 60:02d}"
    return {"lines": [[_t("The cuckoo clock calls at these times. When does it call next? Type it with 4 digits, e.g. 0730.")]],
            "show": [{"k": "seq", "v": fmt[:4] + ["?"]}], "input": {"k": "num", "max": 4}, "sol": sol, "check": "time",
            "hints": [[_t("How many minutes are between two calls?")], [_t("Every {0} minutes."), step], [_t("The hour is {0}."), (ans // 60) or 12]]}


ARROWS = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]


def turning_arrows(rng, level):
    step = rng.choice([2, 6]) if level == "easy" else rng.choice([1, 3, 5, 7])
    a = rng.randrange(8)
    s = [ARROWS[(a + step * i) % 8] for i in range(5)]
    ans = s[4]
    opts = list(dict.fromkeys([ans] + rng.sample(ARROWS, 8)))[:4]
    rng.shuffle(opts)
    return {"lines": [[_t("The arrow turns the same way each time. Where does it point next?")]], "show": [{"k": "seq", "v": s[:4] + ["?"], "plain": True}],
            "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(ans), "check": "choice",
            "hints": [[_t("Watch how far it turns from one arrow to the next.")],
                      [_t("It turns clockwise.") if step < 4 else _t("It turns anticlockwise.")], [_t("It is {0}."), ans]]}


# ================================================================ maths
FRUITS = ["🍎", "🍌", "🍇", "🍓", "🍊", "🥝"]


def fruit_sums(rng, level):
    f = rng.sample(FRUITS, 3)
    v = [rng.randint(2, 9) for _ in range(3)]
    if level == "easy":
        eq = [(f[0] + " + " + f[0], 2 * v[0])]
        q, ans = f[0] + " + 3", v[0] + 3
    elif level == "medium":
        eq = [(f[0] + " + " + f[0], 2 * v[0]), (f[0] + " + " + f[1], v[0] + v[1])]
        q, ans = f[1] + " + " + f[1] + " + " + f[0], 2 * v[1] + v[0]
    else:
        eq = [(f[0] + " + " + f[0] + " + " + f[0], 3 * v[0]), (f[0] + " + " + f[1] + " + " + f[1], v[0] + 2 * v[1]),
              (f[1] + " + " + f[2], v[1] + v[2])]
        q, ans = f[2] + " + " + f[0] + " × " + f[1], v[2] + v[0] * v[1]
    return {"lines": [[_t("Every fruit stands for a number. Work out the last line!")]],
            "show": [{"k": "eqs", "v": [[a, str(b)] for a, b in eq] + [[q, "?"]]}], "input": {"k": "num", "max": 3}, "sol": str(ans), "check": "int",
            "hints": [[_t("{0} = {1}"), f[0], v[0]], [_t("{0} = {1}"), f[1], v[1]],
                      [_t("{0} = {1}"), f[2], v[2]] if level == "hard" else [_t("Multiply before you add.")]]}


def purse(rng, level):
    coins = sorted((rng.choice([1, 2, 5, 10] if level == "easy" else [1, 2, 5, 10, 20]) for _ in range(rng.randint(4, 6))), reverse=True)
    tot = sum(coins)
    if level == "easy":
        lines, ans = [[_t("How many coins of money are in the purse altogether?")]], tot
    else:
        price = rng.randint(3, tot - 1)
        lines, ans = [[_t("You buy a magic map for {0}. How much money is left?"), price]], tot - price
    return {"lines": lines, "show": [{"k": "coins", "v": coins}], "input": {"k": "num", "max": 3}, "sol": str(ans), "check": "int",
            "hints": [[_t("Start with the big coins.")], [_t("Altogether there are {0}."), tot], [_t("It is more than {0}."), max(0, ans - 3)]]}


def magic_square(rng, level):
    lo = [[2, 7, 6], [9, 5, 1], [4, 3, 8]]
    for _ in range(rng.randrange(4)):
        lo = [list(x) for x in zip(*lo[::-1])]
    if rng.random() < .5:
        lo = [r[::-1] for r in lo]
    k = rng.randint(1, 3) if level == "medium" else rng.randint(2, 5)
    o = rng.randint(0, 10)
    g = [o + k * v for r in lo for v in r]
    total = sum(g[:3])
    hide = rng.sample(range(9), 4 if level == "medium" else 5)
    star = rng.choice(hide)
    view = ["⭐" if i == star else ("" if i in hide else str(v)) for i, v in enumerate(g)]
    return {"lines": [[_t("Every row, column and diagonal adds up to the same number. Which number belongs on the ⭐?")]],
            "show": [{"k": "grid", "n": 3, "v": view}], "input": {"k": "num", "max": 3}, "sol": str(g[star]), "check": "int",
            "hints": [[_t("Find a full line first and add it up.")], [_t("Every line adds up to {0}."), total],
                      [_t("It is more than {0}."), g[star] - rng.randint(1, 4)]]}


STORIES = {
    "easy": [
        (_t("The wizard has {0} potions. He drinks {1} and brews {2} new ones. How many potions does he have now?"),
         lambda r: (lambda a, b, c: ((a, b, c), a - b + c))(r.randint(6, 15), r.randint(1, 5), r.randint(1, 6))),
        (_t("A squirrel hides {0} nuts in the morning and {1} nuts in the evening. How many nuts did it hide?"),
         lambda r: (lambda a, b: ((a, b), a + b))(r.randint(5, 25), r.randint(5, 25))),
        (_t("There are {0} penguins on the ice. {1} jump into the water. How many are still on the ice?"),
         lambda r: (lambda a, b: ((a, b), a - b))(r.randint(10, 30), r.randint(2, 9))),
    ],
    "medium": [
        (_t("{0} pirates share {1} gold coins fairly. How many coins does each pirate get?"),
         lambda r: (lambda a, b: ((a, a * b), b))(r.randint(2, 6), r.randint(3, 9))),
        (_t("A dragon has {0} heads. How many heads do {1} dragons have?"),
         lambda r: (lambda a, b: ((a, b), a * b))(r.randint(2, 4), r.randint(3, 8))),
        (_t("The train has {0} carriages with {1} seats each. How many seats are there?"),
         lambda r: (lambda a, b: ((a, b), a * b))(r.randint(3, 8), r.randint(4, 12))),
        (_t("A robot walks {0} steps every minute. How many steps does it walk in {1} minutes?"),
         lambda r: (lambda a, b: ((a, b), a * b))(r.randint(4, 12), r.randint(3, 9))),
    ],
}


def story_sums(rng, level):
    text, fn = rng.choice(STORIES["easy" if level == "easy" else "medium"])
    args, ans = fn(rng)
    return {"lines": [[text, *args]], "input": {"k": "num", "max": 3}, "sol": str(ans), "check": "int",
            "hints": [[_t("Draw it on paper or use your fingers.")], [_t("It is more than {0}."), max(0, ans - rng.randint(2, 5))],
                      [_t("It is less than {0}."), ans + rng.randint(2, 5)]]}


def pyramid(rng, level):
    n = 3 if level == "medium" else 4
    bottom = [rng.randint(1, 9) for _ in range(n)]
    rows = [bottom]
    while len(rows[-1]) > 1:
        r = rows[-1]
        rows.append([r[i] + r[i + 1] for i in range(len(r) - 1)])
    rows = rows[::-1]                                          # top first
    view = [[str(v) for v in r] for r in rows]
    if level == "medium":
        view[0][0] = "⭐"
        for i in range(len(view[1])):
            view[1][i] = ""
        ans = rows[0][0]
        lines = [[_t("Each stone is the sum of the two stones below it. Which number is on the ⭐?")]]
    else:
        i = rng.randrange(n)
        view[-1][i] = "⭐"
        for r in range(1, n - 1):
            view[r] = ["" for _ in view[r]]
        ans = bottom[i]
        lines = [[_t("Each stone is the sum of the two stones below it. Which number is on the ⭐?")]]
    return {"lines": lines, "show": [{"k": "pyr", "v": view}], "input": {"k": "num", "max": 3}, "sol": str(ans), "check": "int",
            "hints": [[_t("Fill the stones one by one, from the bottom up.")], [_t("The second row from the top: {0}"), " · ".join(map(str, rows[1]))],
                      [_t("It is more than {0}."), max(0, ans - 2)]]}


def dice_sum(rng, level):
    d = [rng.randint(1, 6) for _ in range(3 if level == "easy" else 4)]
    if level == "easy":
        lines, ans = [[_t("How many dots are on the dice together?")]], sum(d)
        hints = [[_t("Count the dots die by die.")], [_t("The first two dice have {0}."), d[0] + d[1]], [_t("It is more than {0}."), sum(d) - 2]]
    else:
        lines, ans = [[_t("On a die, opposite sides always add up to 7. How many dots are on the bottom sides together?")]], 7 * len(d) - sum(d)
        hints = [[_t("Below a {0} is a {1}."), d[0], 7 - d[0]], [_t("All sides together (top + bottom) make {0}."), 7 * len(d)],
                 [_t("The top sides have {0}."), sum(d)]]
    return {"lines": lines, "show": [{"k": "dice", "v": d}], "input": {"k": "num", "max": 2}, "sol": str(ans), "check": "int", "hints": hints}


def number_machine(rng, level):
    a = rng.randint(1, 2) if level == "medium" else rng.randint(2, 4)
    b = rng.randint(1, 9) if level == "medium" else rng.randint(-5, 9)
    xs = rng.sample(range(1, 11), 4)
    f = lambda x: a * x + b  # noqa: E731
    while any(f(x) < 0 for x in xs):
        b += 1
    pairs = [[str(x), str(f(x))] for x in xs[:3]]
    q = xs[3]
    rule = [_t("The machine does: × {0}, then + {1}."), a, b] if b >= 0 else [_t("The machine does: × {0}, then − {1}."), a, -b]
    return {"lines": [[_t("A number machine! What comes out when {0} goes in?"), q]],
            "show": [{"k": "rows", "head": ["➡️", "⚙️", "⬅️"], "v": [[x, "→", y] for x, y in pairs] + [[str(q), "→", "?"]]}],
            "input": {"k": "num", "max": 3}, "sol": str(f(q)), "check": "int",
            "hints": [[_t("Compare what goes in with what comes out.")], [_t("It multiplies by {0}."), a], rule]}


# ================================================================ memory (shown only for a moment)
GEMS = ["red", "yellow", "blue", "green", "purple", "orange"]


def glowing_crystals(rng, level):
    n = {"easy": 4, "medium": 5, "hard": 7}[level]
    seq = [rng.randrange(6) for _ in range(n)]
    return {"lines": [[_t("The crystals glow one after the other. Tap «Peek», remember the colours and tap them in the same order!")]],
            "show": [{"k": "gems", "v": [col(GEMS[i]) for i in seq]}], "peek": {"easy": 6, "medium": 6, "hard": 7}[level],
            "input": {"k": "order", "opts": [col(g) for g in GEMS], "len": n, "gems": True, "repeat": True}, "sol": seq, "check": "seq",
            "hints": [[_t("The first one is {0}."), col(GEMS[seq[0]])], [_t("The last one is {0}."), col(GEMS[seq[-1]])],
                      [_t("The second one is {0}."), col(GEMS[seq[1]])]]}


TRAY = ["🔑", "🕯️", "🧦", "🍪", "🪶", "🎲", "🧸", "📎", "🥄", "🔔", "🧩", "🪀", "🍬", "🧲", "🕶️", "🧤", "🪁", "🎺"]


def magic_tray(rng, level):
    n = 6 if level == "medium" else 9
    items = rng.sample(TRAY, n + 1)
    tray, missing = items[:n], items[n]
    opts = rng.sample(tray, 3) + [missing]
    rng.shuffle(opts)
    return {"lines": [[_t("Tap «Peek» and remember everything on the magic tray. Which of these was NOT on the tray?")]],
            "show": [{"k": "emo", "cols": 3, "v": tray}], "peek": 6 if level == "medium" else 8,
            "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(missing), "check": "choice",
            "hints": [[_t("It is not {0}."), o] for o in opts if o != missing][:3]}


def where_key(rng, level):
    cols = 3 if level == "easy" else 4
    items = rng.sample(TRAY, cols * cols)
    i = rng.randrange(cols * cols)
    r, c = divmod(i, cols)
    return {"lines": [[_t("Tap «Peek» and remember where everything is. Then tap the field where the {0} was!"), items[i]]],
            "show": [{"k": "emo", "cols": cols, "v": items}], "peek": 5 if level == "easy" else 7,
            "input": {"k": "cells", "cols": cols, "v": ["❔"] * (cols * cols)}, "sol": i, "check": "choice",
            "hints": [[_t("It is in row {0}."), r + 1], [_t("It is in column {0}."), c + 1], [_t("Peek again – it costs nothing.")]]}


def flash_digits(rng, level):
    n = 5 if level == "medium" else 7
    s = "".join(str(rng.randrange(10)) for _ in range(n))
    return {"lines": [[_t("Tap «Peek»: the numbers flash for a moment. Type them in the same order!")]],
            "show": [{"k": "big", "v": " ".join(s)}], "peek": 4 if level == "medium" else 5,
            "input": {"k": "num", "max": n}, "sol": s, "check": "digits",
            "hints": [[_t("The code starts with {0}."), s[:2]], [_t("The last digit is {0}."), s[-1]], [_t("Split it into small groups.")]]}


FLOCK = ["🦉", "🦇", "🐦", "🦋", "🐝"]


def flock_count(rng, level):
    kinds = rng.sample(FLOCK, 3)
    cells = [rng.choice(kinds) for _ in range(rng.randint(10, 14) if level == "easy" else rng.randint(16, 20))]
    a = rng.choice(kinds)
    ans = cells.count(a)
    cells += [""] * (20 - len(cells))
    rng.shuffle(cells)
    return {"lines": [[_t("Tap «Peek»: something flies past the window! How many {0} were there?"), a]],
            "show": [{"k": "emo", "cols": 5, "v": cells}], "peek": 6 if level == "easy" else 5,
            "input": {"k": "num", "max": 2}, "sol": str(ans), "check": "int",
            "hints": [[_t("Peek again and count only the {0}."), a], [_t("It is more than {0}."), max(0, ans - 2)], [_t("It is less than {0}."), ans + 2]]}


# ================================================================ maps & directions
LANDMARKS = ["🌴", "🪨", "🏝️", "⛺", "🌋", "🐊", "🌵", "🏚️", "🗿", "⛲", "🍄", "🌲"]
DIRS = {"N": (-1, 0, "⬆️"), "S": (1, 0, "⬇️"), "E": (0, 1, "➡️"), "W": (0, -1, "⬅️")}


def treasure_walk(rng, level):
    n = 5
    for _ in range(200):
        start = rng.randrange(n * n)
        r, c = divmod(start, n)
        steps = []
        for _ in range(2 if level == "easy" else 4):
            d = rng.choice("NSEW")
            k = rng.randint(1, 3)
            dr, dc, _a = DIRS[d]
            if 0 <= r + dr * k < n and 0 <= c + dc * k < n and (not steps or steps[-1][0] != d):
                r, c = r + dr * k, c + dc * k
                steps.append((d, k))
        end = r * n + c
        if len(steps) >= (2 if level == "easy" else 3) and end != start:
            break
    cells = ["" for _ in range(n * n)]
    for i in rng.sample([x for x in range(n * n) if x != start], 8):
        cells[i] = rng.choice(LANDMARKS)
    cells[start] = "🧍"
    return {"lines": [[_t("Start at 🧍 and follow the arrows (one arrow = one field). Tap the field where the treasure is!")]],
            "show": [{"k": "seq", "v": [DIRS[d][2] + " " + str(k) for d, k in steps], "plain": True}],
            "input": {"k": "cells", "cols": n, "v": cells, "map": True}, "sol": end, "check": "choice",
            "hints": [[_t("Move with your finger, field by field.")], [_t("It is in row {0}."), end // n + 1], [_t("It is in column {0}."), end % n + 1]]}


COMPASS = [("N", _t("North")), ("E", _t("East")), ("S", _t("South")), ("W", _t("West"))]


def compass_turns(rng, level):
    a = rng.randrange(4)
    right, left = rng.randint(1, 3), rng.randint(0, 2 if level == "easy" else 3)
    back = level != "easy" and rng.random() < .6
    end = (a + right - left + (2 if back else 0)) % 4
    lines = [[_t("You look to the {0}. You make {1} quarter turns to the right and {2} quarter turns to the left."), t(COMPASS[a][1]), right, left]]
    if back:
        lines.append([_t("Then you turn around once.")])
    lines.append([_t("Where do you look now?")])
    return {"lines": lines, "show": [{"k": "compass"}], "input": {"k": "choice", "opts": [{"v": k, "t": n} for k, n in COMPASS], "cols": 4},
            "sol": end, "check": "choice",
            "hints": [[_t("Stand up and try it!")], [_t("A right turn and a left turn cancel each other.")],
                      [_t("It is not {0}."), t(COMPASS[(end + 1) % 4][1])]]}


PRIZES = ["🍰", "🎁", "🪙", "🧸", "🍭", "📯"]


def ladder(rng, level):
    n = 4 if level == "medium" else 5
    m = rng.randint(5, 7) if level == "medium" else rng.randint(8, 11)
    rungs = []
    for y in range(m):
        i = rng.randrange(n - 1)
        if rungs and rungs[-1][1] in (i - 1, i, i + 1) and rng.random() < .5:
            i = (i + 2) % (n - 1)
        rungs.append([y, i])
    top = rng.sample(ANIMALS, n)
    bottom = rng.sample(PRIZES, n)
    who = rng.randrange(n)
    x = who
    for _y, i in rungs:
        if x == i:
            x = i + 1
        elif x == i + 1:
            x = i
    mid = who
    for _y, i in rungs[:len(rungs) // 2]:
        mid = i + 1 if mid == i else i if mid == i + 1 else mid
    return {"lines": [[_t("{0} walks down its line. At every bridge it must cross over. Which prize does it reach?"), top[who]]],
            "show": [{"k": "ladder", "n": n, "rungs": rungs, "rows": m, "top": top, "bottom": bottom}],
            "input": {"k": "choice", "opts": [{"v": b} for b in bottom], "cols": n}, "sol": x, "check": "choice",
            "hints": [[_t("Follow the line with your finger – never skip a bridge.")], [_t("Halfway down it is on line {0}."), mid + 1],
                      [_t("It is not {0}."), bottom[(x + 1) % n]]]}


def robot(rng, level):
    n = 5
    heads = ["N", "E", "S", "W"]
    for _ in range(300):
        r, c = rng.randrange(n), rng.randrange(n)
        start = r * n + c
        h = rng.randrange(4)
        prog, ok = [], True
        for _ in range(4 if level == "medium" else 6):
            if prog and prog[-1][0] == "F" or rng.random() < .4:
                turn = rng.choice(["L", "R"])
                h = (h + (1 if turn == "R" else -1)) % 4
                prog.append((turn, 0))
            else:
                k = rng.randint(1, 3)
                dr, dc, _a = DIRS[heads[h]]
                if not (0 <= r + dr * k < n and 0 <= c + dc * k < n):
                    ok = False
                    break
                r, c = r + dr * k, c + dc * k
                prog.append(("F", k))
        if ok and r * n + c != start and sum(1 for p in prog if p[0] == "F") >= 2:
            break
    cells = [""] * (n * n)
    cells[start] = "🤖"
    sym = {"F": "⏫", "L": "↩️", "R": "↪️"}
    return {"lines": [[_t("The robot looks up (⬆️). ⏫ = forward, ↩️ = turn left, ↪️ = turn right. Tap the field where it stops!")]],
            "show": [{"k": "seq", "v": [sym[a] + (" " + str(k) if a == "F" else "") for a, k in prog], "plain": True}],
            "input": {"k": "cells", "cols": n, "v": cells, "map": True}, "sol": r * n + c, "check": "choice",
            "hints": [[_t("Turning does not move the robot – it only changes where it looks.")], [_t("It is in row {0}."), r + 1],
                      [_t("It is in column {0}."), c + 1]]}


# ================================================================ mechanical puzzles (played on the device, checked here)
def _press(on, n, i):
    r, c = divmod(i, n)
    for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= r + dr < n and 0 <= c + dc < n:
            on[(r + dr) * n + c + dc] ^= 1


def lights_out(rng, level):
    n = 3 if level != "hard" else 4
    k = {"easy": 2, "medium": 4, "hard": 5}[level]
    presses = rng.sample(range(n * n), k)
    on = [0] * (n * n)
    for i in presses:
        _press(on, n, i)
    first = [divmod(i, n) for i in presses]
    return {"lines": [[_t("Make all rune lamps go dark! Tapping a lamp switches it and its neighbours (up, down, left, right).")]],
            "input": {"k": "lights", "n": n, "on": on}, "sol": presses, "check": "lights",
            "hints": [[_t("Tap the lamp in row {0}, column {1}."), first[0][0] + 1, first[0][1] + 1],
                      [_t("Tap the lamp in row {0}, column {1}."), first[1][0] + 1, first[1][1] + 1],
                      [_t("Tapping a lamp twice changes nothing.")]]}


def sliding(rng, level):
    n = 3
    tiles = list(range(1, n * n)) + [0]
    moves = 12 if level == "medium" else 30
    last = None
    path = []
    for _ in range(moves):
        b = tiles.index(0)
        r, c = divmod(b, n)
        opts = [(r + dr) * n + c + dc for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= r + dr < n and 0 <= c + dc < n]
        opts = [o for o in opts if tiles[o] != last] or opts
        o = rng.choice(opts)
        last = tiles[o]
        path.append(tiles[o])
        tiles[b], tiles[o] = tiles[o], 0
    if tiles == list(range(1, n * n)) + [0]:
        b = tiles.index(0)
        tiles[b], tiles[b - 1] = tiles[b - 1], 0
        path.append(tiles[b])
    back = path[::-1]
    return {"lines": [[_t("Slide the tiles into the order 1 to 8 – the empty field at the bottom right. Tap a tile next to the gap.")]],
            "input": {"k": "slide", "n": n, "v": tiles}, "sol": back, "check": "slide",
            "hints": [[_t("First move the tile {0}."), back[0]], [_t("Then move the tile {0}."), back[1]],
                      [_t("Bring the top row in order first, then the rest.")]]}


RING_SYM = ["🌙", "⭐", "☀️", "☁️", "⚡", "❄️"]


def rings(rng, level):
    n = 3 if level == "medium" else 4
    rs = [rng.sample(RING_SYM, 6) for _ in range(n)]
    for _ in range(50):
        p = [rng.randrange(6) for _ in range(n)]
        off = [(p[i] + (p[i - 1] if i else 0)) % 6 for i in range(n)]
        if any(off):
            break
    target = [rs[i][off[i]] for i in range(n)]
    return {"lines": [[_t("Turn the rings until the top row shows: {0}"), " ".join(target)],
                      [_t("Careful: each button turns its ring – and the ring below it too!")]],
            "input": {"k": "rings", "rings": rs}, "sol": [i for i in range(n) for _ in range(p[i])], "check": "rings", "target": target,
            "hints": [[_t("Start with the top ring, then go down.")], [_t("Press button {0} {1} times."), 1, p[0]],
                      [_t("Press button {0} {1} times."), 2, p[1]]]}


OPEN = {"I": (0, 2), "L": (0, 1), "T": (0, 1, 2)}           # openings at rotation 0: 0 up, 1 right, 2 down, 3 left


def _openings(kind, rot):
    return {(d + rot) % 4 for d in OPEN[kind]}


def _pipe_flows(n, tiles, src, dst):
    start = src * n
    if 3 not in _openings(*tiles[start]):
        return False
    seen, todo = {start}, [start]
    while todo:
        i = todo.pop()
        r, c = divmod(i, n)
        op = _openings(*tiles[i])
        if i == dst * n + n - 1 and 1 in op:
            return True
        for d, (dr, dc) in enumerate(((-1, 0), (0, 1), (1, 0), (0, -1))):
            if d in op and 0 <= r + dr < n and 0 <= c + dc < n:
                j = (r + dr) * n + c + dc
                if (d + 2) % 4 in _openings(*tiles[j]) and j not in seen:
                    seen.add(j)
                    todo.append(j)
    return False


def pipes(rng, level):
    n = 4 if level == "medium" else 5
    for _ in range(200):
        src, dst = rng.randrange(n), rng.randrange(n)
        path, seen = [(src, 0)], {(src, 0)}
        ok = False
        for _ in range(60):
            r, c = path[-1]
            if c == n - 1 and r == dst:
                ok = True
                break
            nb = [(r + dr, c + dc) for dr, dc in ((-1, 0), (1, 0), (0, 1), (0, 1), (0, -1)) if 0 <= r + dr < n and 0 <= c + dc < n and (r + dr, c + dc) not in seen]
            if not nb:
                break
            p = rng.choice(nb)
            path.append(p)
            seen.add(p)
        if ok and len(path) >= n + 1:
            break
    dirs = {(-1, 0): 0, (0, 1): 1, (1, 0): 2, (0, -1): 3}
    tiles = [[rng.choice("ILT"), 0] for _ in range(n * n)]
    for k, (r, c) in enumerate(path):
        a = 3 if k == 0 else dirs[(path[k - 1][0] - r, path[k - 1][1] - c)]
        b = 1 if k == len(path) - 1 else dirs[(path[k + 1][0] - r, path[k + 1][1] - c)]
        need = {a, b}
        for kind in ("I", "L"):
            for rot in range(4):
                if _openings(kind, rot) == need:
                    tiles[r * n + c] = [kind, rot]
    good = [tl[1] for tl in tiles]
    for tl in tiles:
        tl[1] = rng.randrange(4)
    if _pipe_flows(n, tiles, src, dst):
        tiles[path[0][0] * n][1] = (tiles[path[0][0] * n][1] + 1) % 4
    hint = path[len(path) // 2]
    return {"lines": [[_t("Turn the pipes (tap them) so that the water flows from 💧 on the left to 🪣 on the right.")]],
            "input": {"k": "pipes", "n": n, "v": tiles, "src": src, "dst": dst}, "sol": good, "check": "pipes",
            "hints": [[_t("The water must flow through row {0}, column {1}."), path[1][0] + 1, path[1][1] + 1],
                      [_t("The water must flow through row {0}, column {1}."), hint[0] + 1, hint[1] + 1],
                      [_t("Not every pipe is needed.")]]}


def levers(rng, level):
    n = 4 if level == "easy" else 5
    for _ in range(100):
        lv = [sorted(rng.sample(range(n), rng.randint(1, 2 if level == "easy" else 3))) for _ in range(n)]
        sol = [i for i in range(n) if rng.random() < .5] or [0]
        on = [1] * n
        for i in sol:
            for j in lv[i]:
                on[j] ^= 1
        if 0 in on:
            break
    rest = [i for i in range(n) if i not in sol]
    return {"lines": [[_t("Pull levers until all lamps shine. Each lever switches the lamps it is connected to.")]],
            "input": {"k": "levers", "lamps": n, "on": on, "levers": lv}, "sol": sol, "check": "levers",
            "hints": [[_t("Lever {0} must be pulled."), sol[0] + 1],
                      [_t("Lever {0} must stay."), rest[0] + 1] if rest else [_t("Pulling a lever twice changes nothing.")],
                      [_t("Lever {0} must be pulled."), sol[-1] + 1] if len(sol) > 1 else [_t("Pulling a lever twice changes nothing.")]]}


def gears(rng, level):
    if level != "hard":
        n = rng.randint(4, 6) if level == "easy" else rng.randint(7, 9)
        k = n if level == "easy" else rng.randint(3, n)
        cw = k % 2 == 1
        return {"lines": [[_t("The first gear turns clockwise ↻. Which way does gear number {0} turn?"), k]],
                "show": [{"k": "gears", "n": n, "mark": k}],
                "input": {"k": "choice", "opts": [{"v": "↻", "t": _t("clockwise")}, {"v": "↺", "t": _t("anticlockwise")}], "cols": 2},
                "sol": 0 if cw else 1, "check": "choice",
                "hints": [[_t("Two gears that touch always turn in opposite directions.")], [_t("Gear 2 turns anticlockwise ↺.")],
                          [_t("All odd gears (1, 3, 5 …) turn the same way.")]]}
    a = rng.choice([10, 12, 20, 24, 30, 36])
    b = rng.choice([x for x in (6, 8, 10, 12, 15) if a % x == 0 and x != a] or [a // 2])
    turns = rng.randint(2, 5)
    ans = a * turns // b
    return {"lines": [[_t("Gear A has {0} teeth, gear B has {1} teeth. When A turns {2} times, how many times does B turn?"), a, b, turns]],
            "show": [{"k": "gears", "n": 2, "labels": ["A", "B"]}], "input": {"k": "num", "max": 3}, "sol": str(ans), "check": "int",
            "hints": [[_t("Count the teeth that pass by.")], [_t("A turns once: {0} teeth pass."), a], [_t("B needs {0} teeth for one turn."), b]]}


# ================================================================ knowledge (for children)
LEGS = [("🐔", 2), ("🦆", 2), ("🐦", 2), ("🐶", 4), ("🐱", 4), ("🐴", 4), ("🐘", 4), ("🕷️", 8), ("🐜", 6), ("🐝", 6), ("🐍", 0), ("🐟", 0)]


def legs_count(rng, level):
    animals = [rng.choice(LEGS) for _ in range(3 if level == "easy" else 5)]
    ans = sum(x[1] for x in animals)
    return {"lines": [[_t("How many legs do these animals have together?")]], "show": [{"k": "emo", "cols": len(animals), "v": [a for a, _ in animals]}],
            "input": {"k": "num", "max": 2}, "sol": str(ans), "check": "int",
            "hints": [[_t("Insects have 6 legs, spiders 8, birds 2.")], [_t("A {0} has {1} legs."), animals[0][0], animals[0][1]],
                      [_t("It is more than {0}."), max(0, ans - 3)]]}


MIXES = [("red", "yellow", "orange"), ("blue", "yellow", "green"), ("red", "blue", "purple"), ("red", "white", "pink"),
         ("black", "white", "grey")]


def colour_mix(rng, level):
    a, b, res = rng.choice(MIXES)
    if level == "easy":
        opts = [res] + rng.sample([c for c in ("orange", "green", "purple", "pink", "grey", "brown") if c != res], 3)
        rng.shuffle(opts)
        return {"lines": [[_t("The witch mixes {0} and {1} paint. Which colour does she get?"), col(a), col(b)]],
                "input": {"k": "choice", "opts": [{"v": "🧪", **col(o)} for o in opts], "cols": 2}, "sol": opts.index(res), "check": "choice",
                "hints": [[_t("Think of your paint box!")], [_t("It is not {0}."), col(next(o for o in opts if o != res))],
                          [_t("It is not {0}."), col([o for o in opts if o != res][1])]]}
    pairs = [(a, b)] + [(x, y) for x, y, r in MIXES if r != res]
    pairs = [pairs[0]] + rng.sample(pairs[1:], 3)
    rng.shuffle(pairs)
    return {"lines": [[_t("Which two colours of paint make {0}?"), col(res)]],
            "input": {"k": "choice", "opts": [{"v": "🎨", "pair": [col(x), col(y)]} for x, y in pairs], "cols": 2},
            "sol": pairs.index((a, b)), "check": "choice",
            "hints": [[_t("Think of your paint box!")], [_t("One of them is {0}."), col(a)], [_t("One of them is {0}."), col(b)]]}


PLANETS = [("☿", _t("Mercury")), ("♀", _t("Venus")), ("🌍", _t("Earth")), ("♂", _t("Mars")), ("♃", _t("Jupiter")), ("🪐", _t("Saturn")),
           ("⛢", _t("Uranus")), ("♆", _t("Neptune"))]


def planets(rng, level):
    if level == "easy":
        q, ans = rng.choice([([_t("On which planet do we live?")], 2), ([_t("Which planet has big, bright rings?")], 5),
                             ([_t("Which planet is the biggest?")], 4), ([_t("Which planet is called the red planet?")], 3)])
    else:
        k = rng.randrange(8)
        q, ans = [_t("Which planet is number {0} from the sun?"), k + 1], k
    opts = [ans] + rng.sample([i for i in range(8) if i != ans], 3)
    rng.shuffle(opts)
    return {"lines": [q], "input": {"k": "choice", "opts": [{"v": PLANETS[i][0], "t": PLANETS[i][1]} for i in opts], "cols": 2},
            "sol": opts.index(ans), "check": "choice",
            "hints": [[_t("From the sun: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune.")],
                      [_t("It is not {0}."), t(PLANETS[next(o for o in opts if o != ans)][1])],
                      [_t("It is not {0}."), t(PLANETS[[o for o in opts if o != ans][1]][1])]]}


EGGS = ["🐔", "🦆", "🐢", "🐍", "🐸", "🐟", "🐊", "🦉", "🐧"]
MILK = ["🐶", "🐱", "🐴", "🐄", "🐷", "🐘", "🦁", "🐰", "🐭", "🐻"]


def egg_layers(rng, level):
    if level == "easy":
        ans, others, q = rng.choice(EGGS), rng.sample(MILK, 3), [_t("Which animal lays eggs?")]
    else:
        ans, others, q = rng.choice(MILK), rng.sample(EGGS, 3), [_t("Which animal does NOT lay eggs?")]
    opts = others + [ans]
    rng.shuffle(opts)
    return {"lines": [q], "input": {"k": "choice", "opts": [{"v": o} for o in opts], "cols": 4}, "sol": opts.index(ans), "check": "choice",
            "hints": [[_t("Birds, fish, frogs, snakes and turtles lay eggs.")], [_t("It is not {0}."), others[0]], [_t("It is not {0}."), others[1]]]}


MONTHS = [_t("January"), _t("February"), _t("March"), _t("April"), _t("May"), _t("June"), _t("July"), _t("August"), _t("September"),
          _t("October"), _t("November"), _t("December")]
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
WEEKDAYS = [_t("Monday"), _t("Tuesday"), _t("Wednesday"), _t("Thursday"), _t("Friday"), _t("Saturday"), _t("Sunday")]


def calendar(rng, level):
    if level == "easy":
        m, k = rng.randrange(12), rng.randint(2, 5)
        ans = (m + k) % 12
        opts = list(dict.fromkeys([ans, (ans + 1) % 12, (ans - 1) % 12, (ans + 2) % 12]))
        rng.shuffle(opts)
        return {"lines": [[_t("Which month comes {0} months after {1}?"), k, t(MONTHS[m])]],
                "input": {"k": "choice", "opts": [{"v": "📅", "t": MONTHS[i]} for i in opts], "cols": 2}, "sol": opts.index(ans), "check": "choice",
                "hints": [[_t("Count the months on your fingers.")], [_t("The month after {0} is {1}."), t(MONTHS[m]), t(MONTHS[(m + 1) % 12])],
                          [_t("It is not {0}."), t(MONTHS[next(o for o in opts if o != ans)])]]}
    if rng.random() < .5:
        m = rng.randrange(12)
        return {"lines": [[_t("How many days does {0} have (not in a leap year)?"), t(MONTHS[m])]], "input": {"k": "num", "max": 2},
                "sol": str(DAYS[m]), "check": "int",
                "hints": [[_t("Count on your knuckles: a knuckle is a long month (31 days).")], [_t("Only one month has fewer than 30 days.")],
                          [_t("It is more than {0}."), DAYS[m] - 2]]}
    d, k = rng.randrange(7), rng.randint(3, 12)
    ans = (d + k) % 7
    return {"lines": [[_t("Today is {0}. Which day is it in {1} days?"), t(WEEKDAYS[d]), k]],
            "input": {"k": "choice", "opts": [{"v": "📆", "t": w} for w in WEEKDAYS], "cols": 2}, "sol": ans, "check": "choice",
            "hints": [[_t("A week has 7 days – after 7 days it is the same day again.")], [_t("In 7 days it is {0} again."), t(WEEKDAYS[d])],
                      [_t("It is not {0}."), t(WEEKDAYS[(ans + 1) % 7])]]}


def shape_corners(rng, level):
    pool = [3, 4, 0, 5, 6] if level != "easy" else [3, 4, 0]
    s = [rng.choice(pool) for _ in range(3 if level == "easy" else 5)]
    ans = sum(s)
    return {"lines": [[_t("How many corners do all these shapes have together?")]], "show": [{"k": "shapes", "v": s}],
            "input": {"k": "num", "max": 2}, "sol": str(ans), "check": "int",
            "hints": [[_t("A circle has no corners.")], [_t("A triangle has 3 corners, a square 4.")], [_t("It is more than {0}."), max(0, ans - 3)]]}


# ================================================================ the templates
#   id: (type, levels, name, generator)
TEMPLATES = {
    "lock_clues": ("logic", ("medium", "hard"), _t("The clue lock"), lock_clues),
    "digit_detective": ("logic", ("easy", "medium"), _t("Number detective"), digit_detective),
    "liar_chests": ("logic", ("medium", "hard"), _t("Three chests"), liar_chests),
    "seat_order": ("logic", ("medium", "hard"), _t("The animal bench"), seat_order),
    "heaviest": ("logic", ("easy", "medium", "hard"), _t("The big scales"), heaviest),
    "mini_sudoku": ("logic", ("medium", "hard"), _t("The number square"), mini_sudoku),
    "anagram": ("words", ("easy", "medium", "hard"), _t("Mixed-up letters"), anagram),
    "caesar": ("words", ("medium", "hard"), _t("Secret writing"), caesar),
    "rune_alphabet": ("words", ("medium", "hard"), _t("Rune alphabet"), rune_alphabet),
    "missing_letters": ("words", ("easy", "medium"), _t("The worn-out sign"), missing_letters),
    "mirror_word": ("words", ("easy",), _t("Mirror writing"), mirror_word),
    "word_search": ("words", ("medium", "hard"), _t("Hidden animal"), word_search),
    "letter_numbers": ("words", ("medium", "hard"), _t("Letters as numbers"), letter_numbers),
    "vowel_thief": ("words", ("hard",), _t("The vowel thief"), vowel_thief),
    "count_objects": ("observe", ("easy", "medium"), _t("Count carefully"), count_objects),
    "odd_one": ("observe", ("easy", "medium"), _t("The odd one"), odd_one),
    "two_pictures": ("observe", ("medium", "hard"), _t("Two pictures"), two_pictures),
    "clock_read": ("observe", ("easy", "medium"), _t("The stopped clock"), clock_read),
    "shelf_book": ("observe", ("easy", "medium"), _t("The book shelf"), shelf_book),
    "candle_code": ("observe", ("medium",), _t("Coloured candles"), candle_code),
    "mirror_pick": ("observe", ("medium", "hard"), _t("The magic mirror"), mirror_pick),
    "number_row": ("patterns", ("easy", "medium", "hard"), _t("Number row"), number_row),
    "necklace": ("patterns", ("easy", "medium"), _t("The bead necklace"), necklace),
    "latin_tiles": ("patterns", ("medium", "hard"), _t("The tile floor"), latin_tiles),
    "growing_towers": ("patterns", ("easy", "medium"), _t("Growing towers"), growing_towers),
    "letter_row": ("patterns", ("medium", "hard"), _t("Letter row"), letter_row),
    "clock_steps": ("patterns", ("medium", "hard"), _t("The cuckoo clock"), clock_steps),
    "turning_arrows": ("patterns", ("easy", "medium"), _t("Turning arrows"), turning_arrows),
    "fruit_sums": ("maths", ("easy", "medium", "hard"), _t("Fruit sums"), fruit_sums),
    "purse": ("maths", ("easy", "medium"), _t("The coin purse"), purse),
    "magic_square": ("maths", ("medium", "hard"), _t("The magic square"), magic_square),
    "story_sums": ("maths", ("easy", "medium"), _t("Story sums"), story_sums),
    "pyramid": ("maths", ("medium", "hard"), _t("Number pyramid"), pyramid),
    "dice_sum": ("maths", ("easy", "medium"), _t("The dice tower"), dice_sum),
    "number_machine": ("maths", ("medium", "hard"), _t("The number machine"), number_machine),
    "glowing_crystals": ("memory", ("easy", "medium", "hard"), _t("Glowing crystals"), glowing_crystals),
    "magic_tray": ("memory", ("medium", "hard"), _t("The magic tray"), magic_tray),
    "where_key": ("memory", ("easy", "medium"), _t("Where was it?"), where_key),
    "flash_digits": ("memory", ("medium", "hard"), _t("Flashing numbers"), flash_digits),
    "flock_count": ("memory", ("easy", "medium"), _t("Past the window"), flock_count),
    "treasure_walk": ("maps", ("easy", "medium"), _t("The treasure map"), treasure_walk),
    "compass_turns": ("maps", ("easy", "medium"), _t("The compass"), compass_turns),
    "ladder": ("maps", ("medium", "hard"), _t("Bridges and paths"), ladder),
    "robot": ("maps", ("medium", "hard"), _t("The robot program"), robot),
    "lights_out": ("mechanic", ("easy", "medium", "hard"), _t("Rune lamps"), lights_out),
    "sliding": ("mechanic", ("medium", "hard"), _t("Sliding tiles"), sliding),
    "rings": ("mechanic", ("medium", "hard"), _t("Turning rings"), rings),
    "pipes": ("mechanic", ("medium", "hard"), _t("Water pipes"), pipes),
    "levers": ("mechanic", ("easy", "medium"), _t("The lever board"), levers),
    "gears": ("mechanic", ("easy", "medium", "hard"), _t("Gear chain"), gears),
    "legs_count": ("knowledge", ("easy", "medium"), _t("Counting legs"), legs_count),
    "colour_mix": ("knowledge", ("easy", "medium"), _t("Mixing paint"), colour_mix),
    "planets": ("knowledge", ("easy", "medium"), _t("The planets"), planets),
    "egg_layers": ("knowledge", ("easy", "medium"), _t("Eggs or not?"), egg_layers),
    "calendar": ("knowledge", ("easy", "medium"), _t("The calendar"), calendar),
    "shape_corners": ("knowledge", ("easy", "medium"), _t("Corners"), shape_corners),
}


def nearest_level(tid: str, level: str) -> str:
    lv = TEMPLATES[tid][1]
    if level in lv:
        return level
    i = LEVELS.index(level)
    return min(lv, key=lambda x: abs(LEVELS.index(x) - i))


def make(tid: str, rng, level: str) -> dict:
    """A fresh riddle of this template for this level (the nearest level the template has)."""
    typ, _levels, name, gen = TEMPLATES[tid]
    lv = nearest_level(tid, level)
    r = gen(rng, lv)
    r.update(tpl=tid, type=typ, level=lv, name=name)
    r["hints"] = list(r.get("hints") or [])[:3]
    return r


# ================================================================ checking an answer
def _ints(x, limit=400) -> list[int] | None:
    if not isinstance(x, list) or len(x) > limit:
        return None
    try:
        return [int(v) for v in x]
    except (TypeError, ValueError):
        return None


def check(r: dict, answer) -> bool:
    kind, sol = r["check"], r.get("sol")
    if isinstance(answer, bool) or (kind in ("digits", "int", "time", "word", "choice") and not isinstance(answer, (str, int))):
        return False
    try:
        if kind == "digits":
            return re.sub(r"\D", "", str(answer)) == sol
        if kind == "int":
            s = re.sub(r"[^\d-]", "", str(answer))
            return bool(s) and s not in ("-",) and int(s) == int(sol)
        if kind == "time":
            s = re.sub(r"\D", "", str(answer))
            if len(s) not in (3, 4):
                return False
            hh, mm = int(s[:-2]), int(s[-2:])
            return mm == int(sol[2:]) and hh % 12 == int(sol[:2]) % 12 and hh <= 24
        if kind == "word":
            return plain(answer) in sol
        if kind == "choice":
            return not isinstance(answer, bool) and int(answer) == sol
        if kind == "seq":
            return _ints(answer) == list(sol)
        if kind == "set":
            a = _ints(answer)
            return a is not None and sorted(set(a)) == sorted(sol) and len(a) == len(set(a))
        inp = r["input"]
        moves = _ints(answer)
        if moves is None:
            return False
        if kind == "lights":
            n, on = inp["n"], list(inp["on"])
            for i in moves:
                if not 0 <= i < n * n:
                    return False
                _press(on, n, i)
            return not any(on)
        if kind == "slide":
            n, tl = inp["n"], list(inp["v"])
            for v in moves:
                if v not in tl or v == 0:
                    return False
                i, b = tl.index(v), tl.index(0)
                if abs(i // n - b // n) + abs(i % n - b % n) != 1:
                    return False
                tl[i], tl[b] = 0, v
            return tl == list(range(1, n * n)) + [0]
        if kind == "rings":
            rs = inp["rings"]
            p = [0] * len(rs)
            for b in moves:
                if not 0 <= b < len(rs):
                    return False
                p[b] += 1
            return all(rs[i][(p[i] + (p[i - 1] if i else 0)) % 6] == r["target"][i] for i in range(len(rs)))
        if kind == "pipes":
            n = inp["n"]
            if len(moves) != n * n:
                return False
            tiles = [[k, rot % 4] for (k, _), rot in zip(inp["v"], moves)]
            return _pipe_flows(n, tiles, inp["src"], inp["dst"])
        if kind == "levers":
            on = list(inp["on"])
            if len(set(moves)) != len(moves):
                return False
            for i in moves:
                if not 0 <= i < len(inp["levers"]):
                    return False
                for j in inp["levers"][i]:
                    on[j] ^= 1
            return all(on)
    except (TypeError, ValueError, KeyError, IndexError):
        return False
    return False


def public(r: dict, show: bool) -> dict:
    """What the app gets of a riddle: never the solution; a memory riddle's picture only while it is shown."""
    out = {"tpl": r["tpl"], "type": r["type"], "level": r["level"], "name": r["name"], "lines": r["lines"],
           "input": r["input"], "peek": r.get("peek")}
    if r.get("target"):
        out["target"] = r["target"]
    out["show"] = (r.get("show") or []) if (not r.get("peek") or show) else []
    return out
