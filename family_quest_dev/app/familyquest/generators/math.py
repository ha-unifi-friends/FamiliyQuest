"""Mathematics generators for primary school (5th grade and around)."""
from __future__ import annotations

import random
from fractions import Fraction
from math import gcd

from ..i18n import _t
from .base import Generator, ints, register

MUL = "×"
DIV = ":"


# ---------------------------------------------------------------- times tables
def _ee_skills(p: dict) -> list[str]:
    rows = ints(p, "reihen", list(range(2, 11)))
    mode = p.get("modus", "gemischt")          # mal | geteilt | gemischt
    out = []
    for r in rows:
        if mode in ("mal", "gemischt"):
            out.append(f"x{r}")
        if mode in ("geteilt", "gemischt"):
            out.append(f":{r}")
    return out


def _ee_make(skill: str, p: dict, rng: random.Random) -> dict:
    r = int(skill[1:])
    k = rng.randint(int(p.get("von", 1)), int(p.get("bis", 10)))
    if skill[0] == "x":
        a, b = (k, r) if rng.random() < 0.5 else (r, k)
        return {"instruction": _t("Calculate"), "expr": [a, MUL, b, "="], "input": "number", "answer": a * b}
    return {"instruction": _t("Calculate"), "expr": [r * k, DIV, r, "="], "input": "number", "answer": k}


register(Generator("einmaleins", _t("Times tables"), _ee_skills, _ee_make,
                   lambda s: (f"× {s[1:]}" if s[0] == "x" else f": {s[1:]}")))


# ---------------------------------------------------------------- division with remainder
def _dr_skills(p: dict) -> list[str]:
    return [f"d{d}" for d in ints(p, "teiler", list(range(2, 10)))]


def _dr_make(skill: str, p: dict, rng: random.Random) -> dict:
    d = int(skill[1:])
    q = rng.randint(1, int(p.get("max_quotient", 12)))
    r = rng.randint(1 if p.get("immer_rest", True) else 0, d - 1)
    return {"instruction": _t("Divide with remainder"), "expr": [d * q + r, DIV, d, "="], "input": "div_rest", "answer": [q, r]}


register(Generator("division_rest", _t("Division with remainder"), _dr_skills, _dr_make, lambda s: f": {s[1:]}"))


# ---------------------------------------------------------------- written methods
def _sw_skills(p: dict) -> list[str]:
    return list(p.get("arten", ["addieren", "subtrahieren", "multiplizieren", "dividieren"]))


def _sw_make(skill: str, p: dict, rng: random.Random) -> dict:
    mx = int(p.get("max", 9999))
    if skill == "addieren":
        a, b = rng.randint(mx // 10, mx), rng.randint(mx // 10, mx)
        return {"instruction": _t("Written addition"), "expr": [a, "+", b, "="], "input": "number", "answer": a + b}
    if skill == "subtrahieren":
        a, b = sorted((rng.randint(mx // 10, mx), rng.randint(mx // 10, mx)), reverse=True)
        return {"instruction": _t("Written subtraction"), "expr": [a, "−", b, "="], "input": "number", "answer": a - b}
    if skill == "multiplizieren":
        a, b = rng.randint(100, 999), rng.randint(2, int(p.get("max_faktor", 9)))
        if p.get("zweistellig") and rng.random() < 0.5:
            a, b = rng.randint(12, 99), rng.randint(12, 99)
        return {"instruction": _t("Written multiplication"), "expr": [a, MUL, b, "="], "input": "number", "answer": a * b}
    # dividieren: no remainder
    b = rng.randint(2, 9)
    q = rng.randint(100, max(101, mx // b))
    return {"instruction": _t("Written division"), "expr": [q * b, DIV, b, "="], "input": "number", "answer": q}


register(Generator("schriftlich", _t("Written arithmetic"), _sw_skills, _sw_make))


# ---------------------------------------------------------------- fractions
FRACTION_KINDS = ["kuerzen", "erweitern", "addieren_gleich", "addieren_ungleich", "subtrahieren_ungleich", "vergleichen", "von_zahl"]


def _fr_skills(p: dict) -> list[str]:
    return [k for k in p.get("arten", FRACTION_KINDS) if k in FRACTION_KINDS]


def _rand_frac(rng: random.Random, nmax: int, proper: bool = True) -> Fraction:
    d = rng.randint(2, nmax)
    n = rng.randint(1, d - 1 if proper else d * 2)
    return Fraction(n, d)


def _fr_make(skill: str, p: dict, rng: random.Random) -> dict:
    nmax = int(p.get("nenner_max", 12))
    if skill == "kuerzen":
        base = Fraction(rng.randint(1, nmax - 1), rng.randint(2, nmax))
        while base.numerator >= base.denominator or base.denominator < 2:
            base = Fraction(rng.randint(1, nmax - 1), rng.randint(2, nmax))
        k = rng.randint(2, max(2, min(9, 60 // base.denominator)))
        return {"instruction": _t("Simplify the fraction as far as possible"),
                "expr": [{"frac": [base.numerator * k, base.denominator * k]}, "="], "input": "fraction",
                "answer": [base.numerator, base.denominator], "reduced": True}
    if skill == "erweitern":
        f = _rand_frac(rng, min(nmax, 10))
        k = rng.randint(2, 6)
        return {"instruction": _t("Expand the fraction"), "expr": [{"frac": [f.numerator, f.denominator]}, "=",
                {"frac": ["?", f.denominator * k]}], "input": "number", "answer": f.numerator * k}
    if skill == "addieren_gleich":
        d = rng.randint(3, nmax)
        a, b = rng.randint(1, d - 1), rng.randint(1, d - 1)
        r = Fraction(a + b, d)
        return {"instruction": _t("Add and simplify"), "expr": [{"frac": [a, d]}, "+", {"frac": [b, d]}, "="],
                "input": "fraction", "answer": [r.numerator, r.denominator], "reduced": True}
    if skill in ("addieren_ungleich", "subtrahieren_ungleich"):
        while True:
            x, y = _rand_frac(rng, nmax), _rand_frac(rng, nmax)
            if x.denominator != y.denominator and (skill == "addieren_ungleich" or x != y):
                break
        if skill == "subtrahieren_ungleich" and x < y:
            x, y = y, x
        r = x + y if skill == "addieren_ungleich" else x - y
        op = "+" if skill == "addieren_ungleich" else "−"
        return {"instruction": _t("Calculate and simplify"),
                "expr": [{"frac": [x.numerator, x.denominator]}, op, {"frac": [y.numerator, y.denominator]}, "="],
                "input": "fraction", "answer": [r.numerator, r.denominator], "reduced": True}
    if skill == "vergleichen":
        while True:
            x, y = _rand_frac(rng, nmax), _rand_frac(rng, nmax)
            if x != y:
                break
        return {"instruction": _t("Which fraction is bigger?"), "expr": [], "input": "choice",
                "options": [f"{x.numerator}/{x.denominator}", f"{y.numerator}/{y.denominator}"],
                "answer": f"{max(x, y).numerator}/{max(x, y).denominator}"}
    # von_zahl: 3/4 von 20
    d = rng.randint(2, min(nmax, 10))
    n = rng.randint(1, d - 1)
    m = d * rng.randint(2, 10)
    return {"instruction": _t("Calculate"), "expr": [{"frac": [n, d]}, "von", m, "="], "input": "number", "answer": n * m // d}


_FR_TITLES = {"kuerzen": _t("Simplify"), "erweitern": _t("Expand"), "addieren_gleich": _t("+ same denominator"),
              "addieren_ungleich": _t("+ different denominators"), "subtrahieren_ungleich": _t("− different denominators"),
              "vergleichen": _t("Compare"), "von_zahl": _t("Fraction of a number")}
register(Generator("brueche", _t("Fractions"), _fr_skills, _fr_make, lambda s: _FR_TITLES.get(s, s)))
register(Generator("brueche_kuerzen", _t("Simplify fractions"), lambda p: ["kuerzen"], _fr_make, lambda s: _t("Simplify")))


# ---------------------------------------------------------------- decimals
DEC_KINDS = ["addieren", "subtrahieren", "mal10", "durch10", "runden", "vergleichen"]


def _dc_skills(p: dict) -> list[str]:
    return [k for k in p.get("arten", DEC_KINDS) if k in DEC_KINDS]


def _dec(rng: random.Random, places: int, mx: int = 100) -> float:
    return round(rng.randint(1, mx * 10 ** places) / 10 ** places, places)


def _fmt(x: float, places: int = 3) -> str:
    s = f"{x:.{places}f}".rstrip("0").rstrip(".")
    return s


def _dc_make(skill: str, p: dict, rng: random.Random) -> dict:
    pl = int(p.get("stellen", 2))
    if skill in ("addieren", "subtrahieren"):
        a, b = _dec(rng, rng.randint(1, pl)), _dec(rng, rng.randint(1, pl))
        if skill == "subtrahieren" and a < b:
            a, b = b, a
        r = round(a + b if skill == "addieren" else a - b, pl)
        return {"instruction": _t("Calculate"), "expr": [_fmt(a), "+" if skill == "addieren" else "−", _fmt(b), "="],
                "input": "number", "answer": r}
    if skill in ("mal10", "durch10"):
        a = _dec(rng, pl, 100)
        f = rng.choice([10, 100, 1000])
        r = round(a * f if skill == "mal10" else a / f, pl + 3)
        return {"instruction": _t("Calculate"), "expr": [_fmt(a), MUL if skill == "mal10" else DIV, f, "="],
                "input": "number", "answer": r}
    if skill == "runden":
        a = _dec(rng, 3, 100)
        to = rng.randint(0, 2)
        r = float(f"{a:.{to}f}")
        label = [_t("Round to a whole number"), _t("Round to tenths"), _t("Round to hundredths")][to]
        return {"instruction": label, "expr": [_fmt(a, 3), "≈"], "input": "number", "answer": r}
    while True:
        a, b = _dec(rng, pl, 10), _dec(rng, pl, 10)
        if a != b:
            break
    return {"instruction": _t("Which number is bigger?"), "expr": [], "input": "choice",
            "options": [_fmt(a), _fmt(b)], "answer": _fmt(max(a, b))}


_DC_TITLES = {"addieren": "+", "subtrahieren": "−", "mal10": "× 10/100/1000", "durch10": ": 10/100/1000",
              "runden": _t("Rounding"), "vergleichen": _t("Compare")}
register(Generator("dezimal", _t("Decimal numbers"), _dc_skills, _dc_make, lambda s: _DC_TITLES.get(s, s)))


def is_reduced(n: int, d: int) -> bool:
    return gcd(int(n), int(d)) == 1
