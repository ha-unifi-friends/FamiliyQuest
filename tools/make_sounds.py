"""Build the game sounds of «Errate den Song» (own synthesized sounds, no third-party material).

    python3 tools/make_sounds.py   → family_quest/app/web/sounds/right.mp3, wrong.mp3  (needs numpy and ffmpeg)

right: a quick rising game-show arpeggio (A4 – E5 – A5) and a ringing A-major chord that fades out.
wrong: a harsh buzzer (two slightly detuned saw/square waves around 236 Hz, the beating makes it rasp).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

R = 44100
OUT = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web" / "sounds"


def bell(f: float, dur: float, decay: float, bright: float = 1.0) -> np.ndarray:
    t = np.arange(int(R * dur)) / R
    env = np.exp(-t * decay) * np.minimum(1, t / 0.004)
    s = np.zeros_like(t)
    for k, amp in ((1, 1.0), (2, 0.45 * bright), (3, 0.22 * bright), (4.2, 0.08 * bright)):   # 4.2: a bit of metal
        for det in (-1.5, 1.5):                                                              # two voices → shimmer
            s += amp * 0.5 * np.sin(2 * np.pi * (f * k + det) * t)
    return s * env


def right() -> np.ndarray:
    total = np.zeros(int(R * 2.9))
    def put(sig, at):
        i = int(R * at)
        total[i:i + len(sig)] += sig[: len(total) - i]
    for i, f in enumerate((440.0, 659.25, 880.0)):              # the quick run up
        put(0.55 * bell(f, 0.5, 9, 1.2), i * 0.075)
    for f in (880.0, 1108.73, 1318.51, 1760.0):                 # the ringing chord
        put(0.32 * bell(f, 2.6, 1.6, 0.8), 0.225)
    return total


def wrong() -> np.ndarray:
    dur = 0.9
    t = np.arange(int(R * dur)) / R
    def saw(f):
        return 2 * ((t * f) % 1) - 1
    def sq(f):
        return np.sign(np.sin(2 * np.pi * f * t))
    s = 0.5 * saw(233) + 0.5 * saw(239.5) + 0.35 * sq(236) + 0.15 * sq(118)
    s = np.tanh(1.8 * s)                                        # soft clipping: loud and raspy
    k = int(R * 0.0004)                                         # light low-pass so it is not too shrill
    s = np.convolve(s, np.ones(k) / k, mode="same")
    env = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.04)
    return s * env


def write(name: str, sig: np.ndarray) -> None:
    sig = sig / max(1e-9, np.max(np.abs(sig))) * 0.89
    pcm = (sig * 32767).astype("<i2").tobytes()
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(R), "-ac", "1", "-i", "-",
                    "-codec:a", "libmp3lame", "-b:a", "112k", "-map_metadata", "-1", str(OUT / f"{name}.mp3")],
                   input=pcm, check=True)
    print(OUT / f"{name}.mp3")


if __name__ == "__main__":
    write("right", right())
    write("wrong", wrong())
