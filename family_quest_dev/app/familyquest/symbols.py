"""Picture PIN for children: 4 symbols in a fixed order, chosen from a set of 12 symbols (3 × 4 grid).

12 × 11 × 10 × 9 = 11 880 possible PINs – more than a 4-digit PIN (10 000), but easy to keep track of for children.

The set of 12 belongs to the profile and is not secret (every login shows exactly this set, in a new random
order) – so comparing several login screens tells nothing about which 4 symbols are the PIN.
The PIN itself is stored like a digit PIN: as a hash of "sym:<id>,<id>,<id>,<id>".
"""
from __future__ import annotations

import json
import re

from .settings import WEB_DIR
from .i18n import _t

GRID = 12
LENGTH = 4


def _load() -> dict[str, str]:
    text = (WEB_DIR / "shared" / "symbols.js").read_text(encoding="utf-8")
    body = text[text.index("{"):text.rindex("}") + 1]
    return json.loads(body)


SYMBOLS: dict[str, str] = _load()


def check_set(symbol_set: list) -> list[str]:
    ids = [str(x) for x in symbol_set or []]
    if len(ids) != GRID or len(set(ids)) != GRID or any(i not in SYMBOLS for i in ids):
        raise ValueError(_t("Choose a set of {0} different symbols").replace("{0}", str(GRID)))
    return ids


def secret(symbols: list, symbol_set: list[str]) -> str:
    """The string that is hashed: "sym:ball,cat,dog,bike" (validated)."""
    ids = [str(x) for x in symbols or []]
    if len(ids) != LENGTH or len(set(ids)) != LENGTH or any(i not in symbol_set for i in ids):
        raise ValueError(_t("Choose {0} different symbols").replace("{0}", str(LENGTH)))
    return "sym:" + ",".join(ids)


def is_symbol_pin(pin: str | None) -> bool:
    return bool(pin) and bool(re.fullmatch(r"sym:[a-z]+(,[a-z]+){3}", pin or ""))
