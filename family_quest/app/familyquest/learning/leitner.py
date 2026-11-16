"""Spaced repetition with five Leitner boxes.

box 0 = never seen. Right → one box up, wrong → back to box 1 (due again today),
"almost" (flash card self-check) → box stays, due tomorrow.
Box 1 is due daily, box 5 every 16 days. A finer algorithm (e.g. FSRS) can replace
`next_state` later without touching the packs.
"""
from __future__ import annotations

from datetime import date, timedelta

INTERVALS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = 5


def next_state(box: int, result: str, today: date) -> tuple[int, str]:
    if result == "correct":
        nb = min(MAX_BOX, box + 1)
        return nb, (today + timedelta(days=INTERVALS[nb])).isoformat()
    if result == "almost":
        nb = max(1, box)
        return nb, (today + timedelta(days=1)).isoformat()
    return 1, today.isoformat()


def stars(boxes: list[int]) -> int:
    """0–5 stars for a unit: the mean box of all its items (unseen = 0), rounded down.

    A unit only climbs when its cards actually sit, not because lessons were done.
    """
    if not boxes:
        return 0
    return min(5, int(sum(boxes) / len(boxes) + 1e-9))
