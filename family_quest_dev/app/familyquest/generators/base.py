"""Generators: a rule instead of a list. Each makes endless tasks for a set of sub-skills.

A task is a dict:
    instruction  English text, translated by the client
    expr         list of tokens: str | int | {"frac": [n, d]} | {"blank": True}
    input        number | fraction | div_rest | choice
    answer       number | [n, d] | [q, r] | str
    options      for input=choice
    reduced      fraction must be fully reduced
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

GENERATORS: dict[str, "Generator"] = {}


@dataclass
class Generator:
    name: str
    title: str                                        # English, shown in the parent UI
    skills: Callable[[dict], list[str]]
    make: Callable[[str, dict, random.Random], dict]
    skill_title: Callable[[str], str] = lambda s: s


def register(g: Generator) -> Generator:
    GENERATORS[g.name] = g
    return g


def get(name: str) -> Generator:
    if name not in GENERATORS:
        raise KeyError(f"unknown generator '{name}'")
    return GENERATORS[name]


def ints(params: dict, key: str, default: list[int]) -> list[int]:
    v = params.get(key, default)
    if isinstance(v, int):
        return [v]
    if isinstance(v, str) and "-" in v:                # "6-9"
        a, b = v.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in v]
