import random
from fractions import Fraction
from math import gcd

import pytest

from familyquest import generators
from familyquest.learning import grading


@pytest.mark.parametrize("name,params", [
    ("einmaleins", {"reihen": "6-9"}),
    ("division_rest", {"teiler": "3-9"}),
    ("schriftlich", {}),
    ("brueche", {"nenner_max": 12}),
    ("dezimal", {"stellen": 2}),
])
def test_generators_make_valid_tasks(name, params):
    g = generators.get(name)
    rng = random.Random(4)
    skills = g.skills(params)
    assert skills
    for _ in range(300):
        s = rng.choice(skills)
        t = g.make(s, params, rng)
        assert t["input"] in ("number", "fraction", "div_rest", "choice")
        assert t["instruction"]
        if t["input"] == "fraction":
            n, d = t["answer"]
            assert d > 0
            if t.get("reduced"):
                assert gcd(n, d) == 1
        if t["input"] == "choice":
            assert t["answer"] in t["options"]


def test_times_tables_answers():
    g = generators.get("einmaleins")
    rng = random.Random(1)
    for _ in range(100):
        t = g.make("x7", {}, rng)
        a, _, b, _ = t["expr"]
        assert t["answer"] == a * b
        t = g.make(":8", {}, rng)
        a, _, b, _ = t["expr"]
        assert t["answer"] * b == a


def test_division_remainder():
    rng = random.Random(2)
    for _ in range(100):
        t = generators.get("division_rest").make("d7", {}, rng)
        a, _, b, _ = t["expr"]
        q, r = t["answer"]
        assert q * b + r == a and 0 < r < b


def test_fraction_simplify_and_sum():
    rng = random.Random(3)
    g = generators.get("brueche")
    for _ in range(100):
        t = g.make("kuerzen", {"nenner_max": 12}, rng)
        f = t["expr"][0]["frac"]
        assert Fraction(*f) == Fraction(*t["answer"])
        t = g.make("addieren_ungleich", {"nenner_max": 12}, rng)
        x, y = t["expr"][0]["frac"], t["expr"][2]["frac"]
        assert Fraction(*x) + Fraction(*y) == Fraction(*t["answer"])


def test_grading_text():
    assert grading.check_text("la maison", "la maison")[0]
    assert grading.check_text("  La Maison ", "la maison")[0]
    ok, note = grading.check_text("la fenetre", "la fenêtre")
    assert ok and "accents" in note
    ok, note = grading.check_text("maison", "la maison")
    assert not ok and "article" in note
    assert grading.check_text("l'escalier", "l’escalier")[0]
    assert grading.check_text("la soeur", "la sœur", ["la soeur"])[0]
    assert not grading.check_text("le chat", "le chien")[0]
    assert grading.check_text("la cuisinne", "la cuisine")[0]            # small typo in a long word


def test_grading_numbers_and_fractions():
    assert grading.check_number("3,5", 3.5)
    assert grading.check_number("1'200", 1200)
    assert not grading.check_number("abc", 1)
    assert grading.check_fraction([3, 4], [3, 4], True)[0]
    ok, note = grading.check_fraction([6, 8], [3, 4], True)
    assert not ok and note
    assert grading.check_fraction([6, 8], [3, 4], False)[0]
