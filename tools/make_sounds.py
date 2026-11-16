"""Build the game sounds of «Errate den Song» (own synthesized sounds, no third-party material).

    python3 tools/make_sounds.py   → family_quest/app/web/sounds/right.mp3, wrong.mp3, fart.mp3  (needs numpy and ffmpeg)

right: a quick rising game-show arpeggio (A4 – E5 – A5) and a ringing A-major chord that fades out.
wrong: a harsh buzzer (two slightly detuned saw/square waves around 236 Hz, the beating makes it rasp).
fart: the whoopee cushion of the shop (pranks.py) – a low, wobbling, raspy buzz that sinks and sputters out.
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


def fart() -> np.ndarray:
    rng = np.random.default_rng(7)
    dur = 1.5
    n = int(R * dur)
    t = np.arange(n) / R
    # pitch: starts around 110 Hz, wobbles, sinks to ~60 Hz
    wob = np.interp(t, np.linspace(0, dur, 40), rng.normal(0, 1, 40))
    f = 110 * np.exp(-0.45 * t) + 12 * wob + 6 * np.sin(2 * np.pi * 7 * t)
    ph = 2 * np.pi * np.cumsum(f) / R
    # pulses (the flapping): a narrow pulse train is raspier than a sine
    s = np.maximum(0, np.sin(ph)) ** 3 - 0.35
    s += 0.25 * rng.normal(0, 1, n) * (np.sin(ph) > 0.6)       # a little air
    k = int(R * 0.0012)
    s = np.convolve(s, np.ones(k) / k, mode="same")             # muffled, like through a cushion
    # loudness: a few bursts, the last one sputters out
    burst = np.interp(t, [0, .03, .35, .42, .5, 1.0, 1.08, 1.2, 1.32, 1.38, 1.5], [0, 1, .9, .35, .95, .75, .3, .6, .15, .35, 0])
    flutter = 1 + 0.25 * np.sin(2 * np.pi * 23 * t)
    return np.tanh(2.2 * s) * burst * flutter


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
    write("fart", fart())
