"""Checking typed answers – strict enough to learn, kind enough for children."""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction
from math import gcd

from ..i18n import _t

ARTICLES = ("le ", "la ", "l'", "les ", "un ", "une ", "des ", "der ", "die ", "das ", "the ", "a ", "an ", "il ", "lo ", "gli ", "el ", "los ", "las ")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", str(s)).strip().lower()
    s = s.replace("’", "'").replace("`", "'").replace("´", "'")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*'\s*", "'", s)
    return s.strip(" .!?;,")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").replace("ß", "ss")


def lev(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _strip_article(s: str) -> str:
    for a in ARTICLES:
        if s.startswith(a):
            return s[len(a):]
    return s


def check_text(given: str, answer: str, also: list[str] | None = None) -> tuple[bool, str]:
    """Returns (counts as right, note). Notes are English source text for the client."""
    g = norm(given)
    if not g:
        return False, ""
    targets = [answer] + list(also or [])
    # "le chien / la chienne" or "Haus; Gebäude" in one answer field
    for t in list(targets):
        if "/" in t or ";" in t:
            targets += [x.strip() for x in re.split(r"[/;]", t) if x.strip()]
    nt = [norm(t) for t in targets if t]
    if g in nt:
        return True, ""
    ga = strip_accents(g)
    for t in nt:
        if ga == strip_accents(t):
            return True, _t("Right – watch the accents")
    for t in nt:
        if _strip_article(t) != t and g == _strip_article(t):
            return False, _t("Don't forget the article")
        if _strip_article(g) != g and _strip_article(t) == t and _strip_article(g) == t:
            return True, ""
    for t in nt:
        if len(t) >= 6 and lev(ga, strip_accents(t), 1) <= 1:
            return True, _t("Right – small typo")
    return False, ""


def parse_number(s: str) -> float | None:
    s = str(s).strip().replace("'", "").replace("’", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def check_number(given, answer) -> bool:
    g = parse_number(given)
    return g is not None and abs(g - float(answer)) < 1e-6


def check_fraction(given, answer, reduced: bool) -> tuple[bool, str]:
    try:
        n, d = int(given[0]), int(given[1])
    except (TypeError, ValueError, IndexError):
        return False, ""
    if d == 0:
        return False, ""
    if Fraction(n, d) != Fraction(int(answer[0]), int(answer[1])):
        return False, ""
    if reduced and gcd(n, d) != 1:
        return False, _t("Correct value, but it can be simplified further")
    return True, ""
