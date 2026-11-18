"""«Traffic Cadet» (Verkehrskadett) – a live game: everybody regulates the traffic lights of their own map.

Everybody plays on their own device (family table, guests via QR code) or alone (optionally with practice bots) – the
tables live in the `card_game` table with kind "verkehr" (lobby, join, summary, may_lead from cardgames.CardGames,
like «Jump»).

Worlds (rule `worlds`: 1–5): every world is a street layout of its own, each more complex than the one before –
a simple crossing (only straight on), a T-junction with a left-turn lane, a 4-way crossing with left-turn lanes, two
connected crossings (the road between them can fill up), a roundabout (the drivers yield to the ring, the player has a
stop/go light at every entry). A world lasts INTRO + PLAY seconds; everybody still in the race moves on to the next
world together (a short intro first); who is out stays out and watches the live stats.

Fair for everybody: the layouts and the stream of cars come from the server (`world()` – from the table's seed, the
same for all), the cars drive by simple deterministic rules in integer steps (`step()`; the same function runs in
web/verkehr.js): stop at red (and at amber when they still can), go at green, keep a gap, turn as their route says.
Two cars of crossing / merging routes inside the same conflict area at the same time crash (💥 – an accident, both
block the way for BLOCK ticks, the others wait). Waiting makes the drivers annoyed (😐 → 😠) and then angry (😡); an
ambulance gets angry much sooner. Out: too many accidents or angry drivers (by difficulty, counted over all worlds).

The player switches light groups (a tap: green → amber → red, red → green at once). The app simulates its own map
locally from the server's world data and its own switch events (game ticks) and reports the events; the server
re-simulates every map with the same step function a moment later (LAG) – its result is what counts (accidents,
angry drivers, cars passed). Events for a tick the server simulated already are rejected (the app then rebuilds
its map from the server's snapshot).

Points: every car through (bus 2, ambulance 3) minus 5 per accident and 2 per angry driver. Places: who is still in
by points, those out after them (who lasted longer first). End: after the last world, or when no person is left, or at
a family table when one is left standing. Who leads may end the game early (ranked as it stands, no coins).
Coins (setting `game_rules`/`game_rewards["verkehr"]`): places 1–3, only people of the family at a family table with at
least two of them – never alone; paid once (flag `paid`, a unique ledger `ref` per player); the «No. 1» hat.
Bots (easy / normal / hard) run the same simulation on the server and switch phases of compatible groups by demand,
with a clearance pause – and the easier they are, the more often they forget it (crash risk) or wait too long.
"""
from __future__ import annotations

import json
import math
import random
import time
from functools import lru_cache

from .cardgames import BOTS, CardGames
from .community import CommunityError
from .pairhunt import places, rewards_of as _rewards_of
from .running import win_reason

KIND = "verkehr"
TITLE = "Traffic Cadet"
EMOJI = "🚦"
MAX_PLAYERS = 6
LEVELS = ("easy", "normal", "hard")
DEFAULTS = {"bots": 0, "level": "normal", "difficulty": "normal", "worlds": 3}

# ---------------------------------------------------------------- the simulation (the same numbers in web/verkehr.js)
HZ = 10                      # ticks per second
INTRO = 5                    # seconds of intro per world (no cars arrive yet – the lights can be set)
PLAY = 90                    # seconds of traffic per world
WT = (INTRO + PLAY) * HZ     # ticks per world
COUNTDOWN = 3.0              # seconds from the start to game time 0
KLEN = (18, 30, 10, 20)      # length: car, bus, bike, ambulance
KV = (4, 3, 2, 5)            # speed (units per tick)
KPTS = (1, 2, 1, 3)          # points when through
GAP = 6                      # the gap they keep
AMBER = 15                   # ticks of amber (green → red)
BLOCK = 40                   # a crash blocks the way this long (ticks)
AMB_MOOD = (30, 60)          # the ambulance: annoyed / angry after this many ticks of waiting
DIFF = {"easy": {"rate": 0.75, "annoy": 120, "angry": 240, "acc": 5, "ang": 15},
        "normal": {"rate": 1.0, "annoy": 100, "angry": 200, "acc": 3, "ang": 10},
        "hard": {"rate": 1.3, "annoy": 70, "angry": 140, "acc": 3, "ang": 8}}
PEN_ACC = 5                  # points off per accident …
PEN_ANG = 2                  # … and per angry driver
LAG = 15                     # the server simulates the apps' maps this many ticks behind the clock
STALE = 15.0                 # a silent app for this long: out
KEEP_EV = 4000               # switch events per world and player (at most)

# geometry of the maps (units; a lane is 20 wide, a car 10)
LANE = 20
CR = 12                      # two routes closer than this: a conflict area
ARMS = ((0, -1), (1, 0), (0, 1), (-1, 0))         # N E S W – pointing away from the centre
ARROW_IN = ("↓", "←", "↑", "→")                    # the driving direction of the traffic coming from that arm
TURN = {"S": 2, "R": 3, "L": 1}                    # the arm a movement leaves by (relative to the arm it comes from)


def mulberry32(seed: int):
    """A small random generator (the same as in jump.py)."""
    a = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((a ^ (a >> 15)) * (a | 1)) & 0xFFFFFFFF
        t = (((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt


def _right(d):
    return (-d[1], d[0])


def _bezier(p0, d0, p3, d3, n=24, f=0.55):
    dist = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    straight = abs(d0[0] * d3[0] + d0[1] * d3[1]) > 0.99
    c = dist / 3 if straight else f * max(abs(p3[0] - p0[0]), abs(p3[1] - p0[1]))
    p1 = (p0[0] + d0[0] * c, p0[1] + d0[1] * c)
    p2 = (p3[0] - d3[0] * c, p3[1] - d3[1] * c)
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, cc, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + cc * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + cc * p2[1] + d * p3[1]))
    return out


def _arc(c, r, a0, a1, n=None):
    n = n or max(4, int(abs(a1 - a0) / 6))
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


class _Map:
    """Builds a layout: links (lanes as polylines), paths (routes through the links), stops with light groups."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.links: list[list] = []
        self.paths: list[dict] = []
        self.boxes: list = []
        self.ring = None
        self.heads: dict[int, list] = {}            # group → light heads [x, y]
        self.labels: dict[int, set] = {}

    def link(self, pts) -> int:
        self.links.append([(round(x, 1), round(y, 1)) for x, y in pts])
        return len(self.links) - 1

    def border(self, p, u):
        """From p along u to the edge of the map."""
        tx = ((self.w if u[0] > 0 else 0) - p[0]) / u[0] if u[0] else 1e9
        ty = ((self.h if u[1] > 0 else 0) - p[1]) / u[1] if u[1] else 1e9
        t = min(tx, ty)
        return (p[0] + u[0] * t, p[1] + u[1] * t)


def _crossings(m: _Map, juncs: list[dict], joins: dict) -> None:
    """Junctions: {"c": (x, y), "arms": {arm: [lane {"mv": "SLR", "g": group}, …] (inbound, innermost first)}}.
    joins: {(j, arm): (j2, arm2)} – the road between two junctions (one lane each way)."""
    inl, outl, conn = {}, {}, {}
    for j, J in enumerate(juncs):
        c, arms = J["c"], J["arms"]
        B = LANE * max(1, max(len(v) for v in arms.values()))
        J["B"] = B
        m.boxes.append([c[0] - B, c[1] - B, c[0] + B, c[1] + B])
    pt_in = lambda j, a, k: (juncs[j]["c"][0] + ARMS[a][0] * juncs[j]["B"] + _right((-ARMS[a][0], -ARMS[a][1]))[0] * (10 + LANE * k),
                             juncs[j]["c"][1] + ARMS[a][1] * juncs[j]["B"] + _right((-ARMS[a][0], -ARMS[a][1]))[1] * (10 + LANE * k))
    pt_out = lambda j, b: (juncs[j]["c"][0] + ARMS[b][0] * juncs[j]["B"] + _right(ARMS[b])[0] * 10,
                           juncs[j]["c"][1] + ARMS[b][1] * juncs[j]["B"] + _right(ARMS[b])[1] * 10)
    for j, J in enumerate(juncs):
        for a, lanes in J["arms"].items():
            for k, lane in enumerate(lanes):
                if (j, a) in joins:
                    continue
                p = pt_in(j, a, k)
                inl[(j, a, k)] = m.link([m.border(p, ARMS[a]), p])
            if (j, a) not in joins:
                p = pt_out(j, a)
                outl[(j, a)] = m.link([p, m.border(p, ARMS[a])])
    for (j, a), (j2, a2) in joins.items():          # the road between: my outbound lane = the other's inbound lane 0
        outl[(j, a)] = inl[(j2, a2, 0)] = m.link([pt_out(j, a), pt_in(j2, a2, 0)])
    for j, J in enumerate(juncs):
        for a, lanes in J["arms"].items():
            for k, lane in enumerate(lanes):
                for mv in lane["mv"]:
                    b = (a + TURN[mv]) % 4
                    if b not in J["arms"]:
                        continue
                    d0 = (-ARMS[a][0], -ARMS[a][1])
                    conn[(j, a, k, mv)] = m.link(_bezier(pt_in(j, a, k), d0, pt_out(j, b), ARMS[b]))
    # light heads: beside the road at the stop line, staggered back along the arm when an arm has several groups
    for j, J in enumerate(juncs):
        for a, lanes in J["arms"].items():
            d0 = (-ARMS[a][0], -ARMS[a][1])
            r = _right(d0)
            seen = []
            for k in reversed(range(len(lanes))):
                g = lanes[k]["g"]
                m.labels.setdefault(g, set()).add(ARROW_IN[a])
                m.left = getattr(m, "left", {})
                m.left[g] = m.left.get(g, True) and lanes[k]["mv"] == "L"
                if g in seen:
                    continue
                seen.append(g)
                back = J["B"] + 26 + 56 * (len(seen) - 1)
                off = LANE * len(lanes) + 26
                c = J["c"]
                m.heads.setdefault(g, []).append([round(c[0] + ARMS[a][0] * back + r[0] * off, 1), round(c[1] + ARMS[a][1] * back + r[1] * off, 1)])

    def walk(j, a, k, links, stops):
        lane = juncs[j]["arms"][a][k]
        stops = stops + [(len(links), lane["g"])]
        links = links + [inl[(j, a, k)]]
        for mv in lane["mv"]:
            b = (a + TURN[mv]) % 4
            if (j, a, k, mv) not in conn:
                continue
            l2 = links + [conn[(j, a, k, mv)], outl[(j, b)]]
            if (j, b) in joins:
                j2, a2 = joins[(j, b)]
                walk(j2, a2, 0, l2[:-1], stops)
            else:
                m.paths.append({"links": l2, "stops": stops, "mv": mv})
    for j, J in enumerate(juncs):
        for a, lanes in J["arms"].items():
            if (j, a) in joins:
                continue
            for k in range(len(lanes)):
                walk(j, a, k, [], [])


def _roundabout(m: _Map) -> None:
    c, R, E, dl = (m.w / 2, m.h / 2), 56, 100, 30
    m.ring = [c[0], c[1], R]
    theta = {0: -90, 3: -180, 2: -270, 1: -360}      # N W S E – the ring runs counter-clockwise (θ falling)
    order = [0, 3, 2, 1]
    nxt = {order[i]: order[(i + 1) % 4] for i in range(4)}
    prv = {v: k for k, v in nxt.items()}
    ring_pt = lambda th: (c[0] + R * math.cos(math.radians(th)), c[1] + R * math.sin(math.radians(th)))
    tang = lambda th: (math.sin(math.radians(th)), -math.cos(math.radians(th)))
    ra, rb, cin, cout, inl, outl = {}, {}, {}, {}, {}, {}
    for a in order:
        th = theta[a]
        ra[a] = m.link(_arc(c, R, th + dl, th - dl))
        th2 = theta[nxt[a]]
        while th2 >= th:
            th2 -= 360
        rb[a] = m.link(_arc(c, R, th - dl, th2 + dl))
        d0 = (-ARMS[a][0], -ARMS[a][1])
        r = _right(d0)
        p_in = (c[0] + ARMS[a][0] * E + r[0] * 10, c[1] + ARMS[a][1] * E + r[1] * 10)
        inl[a] = m.link([m.border(p_in, ARMS[a]), p_in])
        cin[a] = m.link(_bezier(p_in, d0, ring_pt(th - dl), tang(th - dl), 16, 0.4))
        ro = _right(ARMS[a])
        p_out = (c[0] + ARMS[a][0] * E + ro[0] * 10, c[1] + ARMS[a][1] * E + ro[1] * 10)
        cout[a] = m.link(_bezier(ring_pt(th + dl), tang(th + dl), p_out, ARMS[a], 16, 0.4))
        outl[a] = m.link([p_out, m.border(p_out, ARMS[a])])
        m.heads[a] = [[round(c[0] + ARMS[a][0] * (E + 24) + r[0] * 46, 1), round(c[1] + ARMS[a][1] * (E + 24) + r[1] * 46, 1)]]
        m.labels[a] = {ARROW_IN[a]}
    m.yields = {}
    for a in order:
        # before entering: no car on the ring piece passing this arm, none coming on the pieces before (unless it
        # leaves here), none just after the merge, nobody entering yet
        m.yields[a] = [[ra[a], 0, 9999, -1], [rb[prv[a]], 0, 9999, ra[a]], [ra[prv[a]], 30, 9999, ra[a]], [rb[a], 0, 9999, -1],
                       [cin[a], 0, 9999, -1], [cin[prv[a]], 0, 9999, ra[a]]]
        links, b = [inl[a], cin[a], rb[a]], nxt[a]
        for mv in "RSL":
            m.paths.append({"links": links + [cout[b], outl[b]], "stops": [(0, a)], "mv": mv, "yield": a})
            links = links + [ra[b], rb[b]]
            b = nxt[b]


LAYOUTS = (
    ("Simple crossing", "cross"),
    ("T-junction", "tee"),
    ("Crossing with turning lanes", "turns"),
    ("Two crossings", "double"),
    ("Roundabout", "round"),
)
RATES = (0.5, 0.5, 0.55, 0.6, 0.7)                 # cars per second per world (before difficulty)


@lru_cache(maxsize=8)
def layout(n: int) -> dict:
    """The layout of world n (0–4) with its conflict areas – the same for everybody (no randomness)."""
    kind = LAYOUTS[n][1]
    m = _Map(400, 620 if kind == "double" else 560)      # portrait – like the phone
    m.yields = {}
    if kind == "cross":
        _crossings(m, [{"c": (200, 280), "arms": {0: [{"mv": "S", "g": 0}], 2: [{"mv": "S", "g": 0}],
                                                  1: [{"mv": "S", "g": 1}], 3: [{"mv": "S", "g": 1}]}}], {})
    elif kind == "tee":
        _crossings(m, [{"c": (200, 230), "arms": {3: [{"mv": "SR", "g": 0}], 1: [{"mv": "L", "g": 2}, {"mv": "S", "g": 0}],
                                                  2: [{"mv": "LR", "g": 1}]}}], {})
    elif kind == "turns":
        _crossings(m, [{"c": (200, 280), "arms": {a: [{"mv": "L", "g": 1 if a % 2 == 0 else 3}, {"mv": "SR", "g": 0 if a % 2 == 0 else 2}]
                                                  for a in range(4)}}], {})
    elif kind == "double":
        _crossings(m, [{"c": (200, 170), "arms": {0: [{"mv": "S", "g": 0}], 2: [{"mv": "S", "g": 0}], 1: [{"mv": "SR", "g": 1}], 3: [{"mv": "SR", "g": 1}]}},
                       {"c": (200, 450), "arms": {0: [{"mv": "S", "g": 2}], 2: [{"mv": "S", "g": 2}], 1: [{"mv": "SR", "g": 3}], 3: [{"mv": "SR", "g": 3}]}}],
                   {(0, 2): (1, 0), (1, 0): (0, 2)})
    else:
        _roundabout(m)
    # integer lengths of the links, positions along the paths
    geo = [sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) for pts in m.links]
    llen = [max(1, int(g + 0.5)) for g in geo]
    yi_of = {}
    yields = []
    for g, ys in sorted(m.yields.items()):
        yi_of[g] = len(yields)
        yields.append(ys)
    paths = []
    for p in m.paths:
        cum = [0]
        for lk in p["links"]:
            cum.append(cum[-1] + llen[lk])
        stops = [[cum[i + 1] - 4, g, yi_of[p["yield"]] if "yield" in p else -1] for i, g in p["stops"]]
        paths.append({"links": p["links"], "cum": cum, "len": cum[-1], "stops": stops, "mv": p["mv"]})
    entries = []
    for p in paths:
        if p["links"][0] not in entries:
            entries.append(p["links"][0])
        p["entry"] = entries.index(p["links"][0])
    ngroups = len(m.heads)
    lay = {"name": LAYOUTS[n][0], "w": m.w, "h": m.h, "links": [{"pts": [c for xy in pts for c in xy], "len": llen[i]} for i, pts in enumerate(m.links)],
           "paths": paths, "entries": entries, "yields": yields, "boxes": m.boxes, "ring": m.ring,
           "groups": [{"label": "".join(sorted(m.labels[g], key=ARROW_IN.index)) + ("↶" if getattr(m, "left", {}).get(g) else ""),
                       "heads": m.heads[g]} for g in range(ngroups)]}
    lay["conf"] = _conflicts(m, lay, geo)
    lay["phases"] = _phases(lay, kind == "round")
    return lay


def _point(m: _Map, lk: int, local: float, L: int, geo: float):
    """The point at this position (integer units) of a link – scaled to its real length."""
    pts = m.links[lk]
    d = max(0.0, min(geo, local * geo / L))
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if d <= seg or b is pts[-1]:
            f = 0 if seg == 0 else min(1, d / seg)
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        d -= seg
    return pts[-1]


def _conflicts(m: _Map, lay: dict, geo: list) -> list[list[int]]:
    """Where two routes come closer than CR (off the links they share): [path i, from, to, path j, from, to] –
    crossings and merges; a fork (two routes leaving a shared link) is no conflict (they keep their gap)."""
    llen = [lk["len"] for lk in lay["links"]]
    samples = []
    for p in lay["paths"]:
        pts = []
        for i, lk in enumerate(p["links"]):
            for s in range(0, llen[lk], 2):
                pts.append((p["cum"][i] + s, lk, _point(m, lk, s, llen[lk], geo[lk])))
        samples.append(pts)
    out = []
    P = lay["paths"]
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            shared = set(P[i]["links"]) & set(P[j]["links"])
            if P[i]["links"][0] == P[j]["links"][0] and len(shared) == len(P[i]["links"]) == len(P[j]["links"]):
                continue
            sj = [s for s in samples[j] if s[1] not in shared]
            grid = {}
            for s, lk, (x, y) in sj:
                grid.setdefault((int(x // CR), int(y // CR)), []).append((s, x, y))
            hits = []
            for s, lk, (x, y) in samples[i]:
                if lk in shared:
                    continue
                gx, gy = int(x // CR), int(y // CR)
                best = None
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for s2, x2, y2 in grid.get((gx + dx, gy + dy), ()):
                            dd = math.hypot(x2 - x, y2 - y)
                            if dd < CR and (best is None or dd < best[0]):
                                best = (dd, s2)
                if best:
                    hits.append((s, best[1]))
            clusters = []
            for s, s2 in hits:
                if clusters and s - clusters[-1][-1][0] <= 4:
                    clusters[-1].append((s, s2))
                else:
                    clusters.append([(s, s2)])
            ends_i = {P[i]["cum"][P[i]["links"].index(lk) + 1] for lk in shared}
            ends_j = {P[j]["cum"][P[j]["links"].index(lk) + 1] for lk in shared}
            for cl in clusters:
                a, b = cl[0][0], cl[-1][0] + 2
                c, d = min(x[1] for x in cl), max(x[1] for x in cl) + 2
                if any(abs(a - e) <= 3 for e in ends_i) and any(abs(c - e) <= 3 for e in ends_j):
                    continue                                    # a fork: no conflict
                out.append([i, a, b, j, c, d])
    return out


def _group_at(p: dict, pos: int) -> int:
    """The light group a route is under at this position (its last stop before it) – -1: none."""
    g = -1
    for sp, gg, _ in p["stops"]:
        if sp <= pos + 2 and gg >= 0:
            g = gg
    return g


def _phases(lay: dict, free: bool) -> list[list[int]]:
    """Sets of light groups without conflicts between them (the bots switch these) – at a roundabout all at once
    (the drivers yield)."""
    n = len(lay["groups"])
    if free:
        return [list(range(n))]
    bad = set()
    P = lay["paths"]
    for i, a, b, j, c, d in lay["conf"]:
        gi, gj = _group_at(P[i], a), _group_at(P[j], c)
        if gi >= 0 and gj >= 0:
            bad.add((gi, gj))
            bad.add((gj, gi))
    out = []
    for mask in range(1, 1 << n):                          # the largest sets of groups that do not conflict
        ph = [g for g in range(n) if mask >> g & 1]
        if any((a, b) in bad for a in ph for b in ph):
            continue
        if any(h not in ph and all((h, x) not in bad for x in ph) for h in range(n)):
            continue
        out.append(ph)
    return out


def group_conflicts(lay: dict) -> set:
    """(g1, g2) pairs whose routes cross or merge (also the same group – a design error)."""
    out = set()
    P = lay["paths"]
    for i, a, b, j, c, d in lay["conf"]:
        gi, gj = _group_at(P[i], a), _group_at(P[j], c)
        if gi >= 0 and gj >= 0:
            out.add((min(gi, gj), max(gi, gj)))
    return out


def arrivals(n: int, seed: int, difficulty: str) -> list[list[int]]:
    """The cars of world n: [tick, path, kind] – from the table's seed, the same for everybody."""
    lay = layout(n)
    rnd = mulberry32((seed + (n + 1) * 7919) & 0xFFFFFFFF)
    rate0 = RATES[n] * DIFF.get(difficulty, DIFF["normal"])["rate"]
    weights = []
    for i, p in enumerate(lay["paths"]):
        w = {"S": 0.6, "R": 0.25, "L": 0.25}[p["mv"]]
        weights.append(w)
    tot = sum(weights)
    out = []
    t = INTRO * HZ
    last_amb = -9999
    end = WT - 3 * HZ
    while True:
        rate = rate0 * (0.7 + 0.6 * (t - INTRO * HZ) / (PLAY * HZ))
        t += max(1, int(HZ * (0.3 + 1.4 * rnd()) / rate))
        if t >= end:
            break
        x = rnd() * tot
        p = 0
        while p < len(weights) - 1 and x >= weights[p]:
            x -= weights[p]
            p += 1
        r = rnd()
        kind = 0
        if r < 0.03 and t - last_amb > 30 * HZ:
            kind, last_amb = 3, t
        elif r < 0.13:
            kind = 1
        elif r < 0.23:
            kind = 2
        out.append([t, p, kind])
    return out


@lru_cache(maxsize=64)
def _world(n: int, seed: int, difficulty: str) -> str:
    return json.dumps({**{k: v for k, v in layout(n).items()}, "n": n, "arrivals": arrivals(n, seed, difficulty)})


def world(n: int, seed: int, difficulty: str) -> dict:
    """World n of a game: the layout and its cars (a fresh copy)."""
    return json.loads(_world(n, seed, difficulty))


class Prep:
    """What the step function needs of a world, precomputed (the same in the app)."""

    def __init__(self, w: dict):
        self.w = w
        self.paths = w["paths"]
        self.lidx = [{lk: i for i, lk in enumerate(p["links"])} for p in self.paths]
        n = len(self.paths)
        self.shares = [[bool(set(self.paths[i]["links"]) & set(self.paths[j]["links"])) for j in range(n)] for i in range(n)]
        self.cbp = [[] for _ in range(n)]
        for i, a, b, j, c, d in w["conf"]:
            self.cbp[i].append((a, b, j, c, d))
            self.cbp[j].append((c, d, i, a, b))


def new_state(w: dict, la: int, lg: int) -> dict:
    """A fresh map: all lights red, no cars; la / lg: accidents / angry drivers left until out."""
    return {"k": 0, "nid": 1, "ai": 0, "ei": 0, "cars": [], "pend": [[] for _ in w["entries"]],
            "lights": [[0, 0] for _ in w["groups"]], "acc": 0, "ann": 0, "ang": 0, "pas": 0, "pts": 0,
            "la": la, "lg": lg, "out": None, "crash": []}


# a car: [id, path, pos (front), kind, wait, mood, wreck (ticks left, 0: none), moved]
def _cur(prep: Prep, c) -> int:
    """The index of the link the car's front is on."""
    cum = prep.paths[c[1]]["cum"]
    k = 0
    while k + 2 < len(cum) and cum[k + 1] <= c[2]:
        k += 1
    return k


def _mood(S: dict, kind: int, wait: int, mood: int, thr) -> int:
    """Waiting makes them annoyed (😐 at half the time, then 😠) and angry (😡) – each counted once."""
    a, g = AMB_MOOD if kind == 3 else thr
    lvl = 3 if wait >= g else 2 if wait >= a else 1 if wait * 2 >= a else 0
    if lvl <= mood:
        return mood
    if lvl >= 2 > mood:
        S["ann"] += 1
    if lvl >= 3 > mood:
        S["ang"] += 1
    return lvl


def step(prep: Prep, S: dict, events: list, thr: tuple[int, int]) -> None:
    """One tick of a map (integer arithmetic only – the same in web/verkehr.js, vkStep)."""
    if S["out"] is not None:
        return
    W, P = prep.w, prep.paths
    k1 = S["k"] + 1
    lights = S["lights"]
    for L in lights:                                       # amber runs out
        if L[0] == 2:
            L[1] -= 1
            if L[1] <= 0:
                L[0], L[1] = 0, 0
    ev = events
    while S["ei"] < len(ev) and ev[S["ei"]][0] <= k1:     # the switches of the player
        _, g, want = ev[S["ei"]]
        S["ei"] += 1
        if 0 <= g < len(lights):
            if want:
                lights[g] = [1, 0]
            elif lights[g][0] == 1:
                lights[g] = [2, AMBER]
    arr = W["arrivals"]
    while S["ai"] < len(arr) and arr[S["ai"]][0] <= k1:   # cars arrive (they queue off the map when there is no room)
        _, p, kind = arr[S["ai"]]
        S["ai"] += 1
        S["pend"][P[p]["entry"]].append([p, kind, 0, 0])
    cars = S["cars"]
    for e, q in enumerate(S["pend"]):
        if q and all(not (P[c[1]]["entry"] == e and c[2] - KLEN[c[3]] < GAP) for c in cars):
            p, kind, wait, mood = q.pop(0)
            cars.append([S["nid"], p, 0, kind, wait, mood, 0, 1])
            S["nid"] += 1
    # moving: everybody from the positions before the tick
    cur = [_cur(prep, c) for c in cars]
    wrecks = [c for c in cars if c[6] > 0]
    new = []
    for ia, A in enumerate(cars):
        pos = A[2]
        if A[6] > 0:
            new.append(pos)
            continue
        pa, kind = A[1], A[3]
        p = P[pa]
        v = KV[kind]
        lim = pos + v
        for sp, g, yi in p["stops"]:
            if pos <= sp:
                stl = lights[g][0] if g >= 0 else 1
                if stl == 0 or (stl == 2 and not (A[7] and 0 < sp - pos <= 2 * v)):
                    lim = min(lim, sp)
                elif yi >= 0 and lim > sp:                 # the yield line of a roundabout: is the ring free?
                    for lk, a, b, need in W["yields"][yi]:
                        for ib, B in enumerate(cars):
                            if P[B[1]]["links"][cur[ib]] == lk and (need < 0 or need in prep.lidx[B[1]]):
                                f = B[2] - P[B[1]]["cum"][cur[ib]]
                                if a <= f <= b:
                                    lim = min(lim, sp)
        ka = cur[ia]
        lidx = prep.lidx[pa]
        sh = prep.shares[pa]
        for ib, B in enumerate(cars):
            if ib == ia or not sh[B[1]]:
                continue
            pb = P[B[1]]
            lb = pb["links"][cur[ib]]
            x = lidx.get(lb)
            if x is not None and x >= ka:
                front = p["cum"][x] + B[2] - pb["cum"][cur[ib]]
                if front > pos:
                    lim = min(lim, front - KLEN[B[3]] - GAP)
            else:
                rear = B[2] - KLEN[B[3]]
                kr = 0
                while kr + 2 < len(pb["cum"]) and pb["cum"][kr + 1] <= rear:
                    kr += 1
                x = lidx.get(pb["links"][kr])
                if x is not None and x >= ka:
                    r = p["cum"][x] + rear - pb["cum"][kr]
                    if r + KLEN[B[3]] > pos:
                        lim = min(lim, r - GAP)
        if wrecks:                                         # nobody drives into a crash
            for a, b, q, c, d in prep.cbp[pa]:
                if pos < a:
                    for Wc in wrecks:
                        if Wc[1] == q and Wc[2] > c and Wc[2] - KLEN[Wc[3]] < d:
                            lim = min(lim, a - 2)
        new.append(max(pos, lim))
    for c, n in zip(cars, new):
        c[7] = 1 if n > c[2] else 0
        c[2] = n
    # crashes: two cars of crossing / merging routes in their conflict areas at the same time
    if cars:
        cur = [_cur(prep, c) for c in cars]
        by = {}
        for i, c in enumerate(cars):
            by.setdefault(c[1], []).append(i)
        fresh = set()
        old = {i for i, c in enumerate(cars) if c[6] > 0}
        for i, a, b, j, c, d in W["conf"]:
            if i not in by or j not in by:
                continue
            for x in by[i]:
                A = cars[x]
                if x in old or not (A[2] > a and A[2] - KLEN[A[3]] < b):
                    continue
                for y in by[j]:
                    B = cars[y]
                    if y in old or not (B[2] > c and B[2] - KLEN[B[3]] < d):
                        continue
                    if P[B[1]]["links"][cur[y]] in prep.lidx[A[1]] or P[A[1]]["links"][cur[x]] in prep.lidx[B[1]]:
                        continue                           # one follows the other
                    if x not in fresh and y not in fresh:
                        S["acc"] += 1
                        S["crash"].append([k1, A[0], B[0]])
                    for z in (x, y):
                        if z not in fresh:
                            fresh.add(z)
                            cars[z][6] = BLOCK + 1
        del S["crash"][:-6]
    # waiting, moods, through, towed away
    keep = []
    for c in cars:
        if c[6] > 0:
            c[6] -= 1
            if c[6] > 0:
                keep.append(c)
            continue
        if not c[7]:
            c[4] += 1
            c[5] = _mood(S, c[3], c[4], c[5], thr)
        if c[2] - KLEN[c[3]] >= P[c[1]]["len"]:
            S["pas"] += 1
            S["pts"] += KPTS[c[3]]
            continue
        keep.append(c)
    S["cars"] = keep
    for q in S["pend"]:
        for c in q:
            c[2] += 1
            c[3] = _mood(S, c[1], c[2], c[3], thr)
    S["k"] = k1
    if S["acc"] >= S["la"] or S["ang"] >= S["lg"]:
        S["out"] = k1


def thresholds(difficulty: str) -> tuple[int, int]:
    d = DIFF.get(difficulty, DIFF["normal"])
    return d["annoy"], d["angry"]


# ---------------------------------------------------------------- the bots
BOT = {"easy": {"think": 8, "min": 50, "max": 230, "clear": 25, "slip": 0.35},
       "normal": {"think": 5, "min": 40, "max": 160, "clear": 25, "slip": 0.07},
       "hard": {"think": 3, "min": 35, "max": 120, "clear": 22, "slip": 0.015}}


def _demand(prep: Prep, S: dict) -> list[float]:
    """Per light group: the cars waiting for it (more for the ones waiting long, much more for an ambulance)."""
    P = prep.paths
    dem = [0.0] * len(S["lights"])
    for c in S["cars"]:
        if c[6]:
            continue
        for sp, g, _ in P[c[1]]["stops"]:
            if c[2] <= sp and g >= 0:
                if sp - c[2] <= 160:
                    dem[g] += (1 + c[4] / 40) * (4 if c[3] == 3 else 1)
                break
    for q in S["pend"]:
        for p, kind, wait, _ in q:
            dem[P[p]["stops"][0][1]] += 1 + wait / 40
    return dem


def _box_clear(prep: Prep, S: dict) -> bool:
    """No moving car inside a conflict area (the crossing is empty)."""
    for c in S["cars"]:
        if c[6]:
            continue
        for a, b, *_ in prep.cbp[c[1]]:
            if c[2] > a and c[2] - KLEN[c[3]] < b:
                return False
    return True


def bot_think(prep: Prep, S: dict, b: dict, events: list, level: str, rng: random.Random) -> None:
    """A bot at tick S["k"]: green for the phase with the most waiting cars, switched with a clearance pause (amber
    plus a moment) – sometimes it forgets the pause or stays too long."""
    cfg = BOT.get(level, BOT["normal"])
    k = S["k"]
    if k % cfg["think"]:
        return
    phases = prep.w["phases"]
    t1 = k + 1
    if b.get("go") is not None:
        if k >= b["go"] and (b.get("slip") or _box_clear(prep, S)):
            for g in phases[b["next"]]:
                events.append([t1, g, 1])
            b.update(ph=b["next"], since=k, go=None)
        return
    if k < INTRO * HZ - 10:
        return
    dem = _demand(prep, S)
    pd = [sum(dem[g] for g in ph) for ph in phases]
    if b.get("ph") is None:
        best = max(range(len(phases)), key=lambda i: pd[i])
        for g in phases[best]:
            events.append([t1, g, 1])
        b.update(ph=best, since=k, go=None)
        return
    if len(phases) == 1:
        return
    ph = b["ph"]
    others = [i for i in range(len(phases)) if i != ph]
    best = max(others, key=lambda i: pd[i])
    g_time = k - b["since"]
    if pd[best] <= 0 or g_time < cfg["min"]:
        return
    if pd[ph] < 0.5 or g_time >= cfg["max"] or pd[best] > 3 * pd[ph] + 4:
        for g in phases[ph]:
            if g not in phases[best]:
                events.append([t1, g, 0])
        slip = rng.random() < cfg["slip"]
        b.update(go=k + (rng.randint(0, 3) if slip else cfg["clear"]), next=best, slip=slip)


# ================================================================ one table (pure logic on a dict)
class Table:
    def __init__(self, st: dict, rng: random.Random | None = None, now=time.time):
        self.st = st
        self.rng = rng or random.Random()
        self.now = now
        self._prep = {}

    def order(self) -> list[str]:
        return [p["id"] for p in self.st["players"]]

    def seat_of(self, pid: str) -> dict | None:
        return next((p for p in self.st["players"] if p["id"] == pid), None)

    def nworlds(self) -> int:
        return int(self.st["rules"].get("worlds", 3))

    def diff(self) -> str:
        d = self.st["rules"].get("difficulty", "normal")
        return d if d in DIFF else "normal"

    def gt(self) -> float:
        return self.now() - self.st["t0"]

    def gtick(self) -> int:
        return int(math.floor(self.gt() * HZ))

    def total(self) -> int:
        return self.nworlds() * WT

    def prep(self, n: int) -> Prep:
        if n not in self._prep:
            self._prep[n] = Prep(world(n, self.st["seed"], self.diff()))
        return self._prep[n]

    def setup(self, seed: int | None = None) -> None:
        ids = self.order()
        if not 1 <= len(ids) <= MAX_PLAYERS:
            raise CommunityError("The table is full")
        self.st.update(phase="play", seed=seed if seed is not None else self.rng.randrange(1, 2 ** 31), t0=self.now() + COUNTDOWN,
                       ranking=None, places=None, complete=False, end_t=None)
        d = DIFF[self.diff()]
        self.st["run"] = {pid: {"w": 0, "tot": {"acc": 0, "ann": 0, "ang": 0, "pas": 0, "pts": 0}, "evs": {}, "out": None,
                                "seen": self.now(), "sim": None, "bot": {}} for pid in ids}
        for pid in ids:
            self.st["run"][pid]["sim"] = new_state(self.prep(0).w, d["acc"], d["ang"])

    # ---------- the maps on the server
    def stats(self, pid: str) -> dict:
        r = self.st["run"][pid]
        s = r["sim"] or {}
        out = {k: r["tot"][k] + (s.get(k, 0) if r["w"] < self.nworlds() else 0) for k in ("acc", "ann", "ang", "pas", "pts")}
        out["score"] = out["pts"] - PEN_ACC * out["acc"] - PEN_ANG * out["ang"]
        return out

    def advance(self, pid: str, target: int) -> None:
        """The map of this player on to the global tick target (bots think while it runs)."""
        r = self.st["run"][pid]
        seat = self.seat_of(pid)
        bot = seat.get("bot")
        thr = thresholds(self.diff())
        target = min(target, self.total())
        while r["out"] is None and r["w"] < self.nworlds():
            w = r["w"]
            S = r["sim"]
            end = (w + 1) * WT
            prep = self.prep(w)
            ev = r["evs"].setdefault(str(w), [])
            stop = min(target, end) - w * WT
            while S["k"] < stop and S["out"] is None:
                if bot:
                    bot_think(prep, S, r["bot"], ev, seat.get("level", "normal"), self.rng)
                    del ev[:-KEEP_EV]
                    S["ei"] = min(S["ei"], len(ev))
                step(prep, S, ev, thr)
            if S["out"] is not None:
                r["out"] = w * WT + S["out"]
                return
            if S["k"] >= WT:                               # the world is over: on to the next one
                for k in r["tot"]:
                    r["tot"][k] += S[k]
                r["w"] = w + 1
                r["evs"].pop(str(w), None)
                r["bot"] = {}
                if r["w"] < self.nworlds():
                    t = r["tot"]
                    d = DIFF[self.diff()]
                    r["sim"] = new_state(self.prep(r["w"]).w, d["acc"] - t["acc"], d["ang"] - t["ang"])
                continue
            return

    def alive(self) -> list[str]:
        return [p for p in self.order() if self.st["run"][p]["out"] is None]

    # ---------- what an app reports
    def report(self, pid: str, t=None, events=()) -> list:
        """The app reports its switches [global tick, group, 1 green / 0 red] – answers the rejected ones."""
        if self.st.get("phase") != "play":
            raise CommunityError("The game is not running")
        r = self.st["run"].get(pid)
        p = self.seat_of(pid)
        if r is None or not p or p.get("bot"):
            raise CommunityError("You are not at this table")
        r["seen"] = self.now()
        rej = []
        now = self.gtick()
        self.advance(pid, now - LAG)
        for e in list(events)[:40]:
            try:
                gk, g, want = int(e[0]), int(e[1]), 1 if int(e[2]) else 0
            except (TypeError, ValueError, IndexError):
                continue
            w, k = divmod(gk, WT)
            ok = r["out"] is None and r["w"] <= w < self.nworlds() and gk <= now + HZ and 0 <= g < len(self.prep(w).w["groups"])
            ev = r["evs"].setdefault(str(w), []) if ok else []
            if ok and w == r["w"] and k <= r["sim"]["k"]:
                ok = False                                 # the server is past that moment already
            if ok and ev and k < ev[-1][0]:
                ok = False
            if ok and len(ev) < KEEP_EV:
                ev.append([k, g, want])
            else:
                rej.append([gk, g, want])
        self._maybe_end()
        return rej

    # ---------- the clock: maps, bots, silent apps, the end
    def tick(self) -> bool:
        if self.st.get("phase") != "play":
            return False
        before = json.dumps([[r["w"], r["out"], r["sim"] and r["sim"]["k"]] for r in self.st["run"].values()])
        now = self.gtick()
        for p in self.st["players"]:
            r = self.st["run"][p["id"]]
            if r["out"] is not None:
                continue
            if p.get("bot"):
                self.advance(p["id"], now)
            else:
                self.advance(p["id"], now - LAG)
                if now > 0 and r["out"] is None and self.now() - r.get("seen", 0) > STALE:   # the app is gone: out
                    s = r["sim"]
                    r["out"] = r["w"] * WT + (s["k"] if s else 0)
                    r["left"] = True
        self._maybe_end()
        return self.st.get("phase") != "play" or json.dumps([[r["w"], r["out"], r["sim"] and r["sim"]["k"]] for r in self.st["run"].values()]) != before

    def _maybe_end(self) -> None:
        if self.st.get("phase") != "play":
            return
        run = self.st["run"]
        people = [p["id"] for p in self.st["players"] if not p.get("bot")]
        alive = self.alive()
        done = all(run[p]["w"] >= self.nworlds() for p in alive)
        end = done or not any(p in alive for p in people)
        if not self.st.get("solo") and len(self.order()) >= 2 and len(alive) <= 1:
            end = True                                     # the last one standing
        if end:
            self.st["complete"] = True
            self._finish()

    def _finish(self) -> None:
        order, run = self.order(), self.st["run"]
        self.st["scores"] = {p: self.stats(p) for p in order}
        tot = self.total() + 1
        rank = {p: (tot if run[p]["out"] is None else run[p]["out"], self.st["scores"][p]["score"]) for p in order}   # higher: better
        self.st["places"] = places(order, rank)
        self.st["ranking"] = sorted(order, key=lambda p: (self.st["places"][p], order.index(p)))
        self.st["end_t"] = round(max(0.0, self.gt()), 3)
        for p in order:                                    # the maps are not needed any more
            run[p]["evs"] = {}
            if run[p]["sim"]:
                run[p]["sim"]["cars"], run[p]["sim"]["pend"] = [], []
        self.st.update(phase="done", finished=self.now())

    def end(self) -> None:
        """Who leads ends the game: ranked as it stands (no coins – see coins_for)."""
        if self.st.get("phase") == "play":
            self._finish()


# ================================================================ the games in the database (table card_game, kind "verkehr")
def rewards_of(db) -> list[int]:
    return _rewards_of(db, KIND)


class Verkehr(CardGames):
    """The family table / own tables – the same rows and lobby as the card games (summary, may_lead)."""

    def __init__(self, db, add_history=None, rewards=None, now=time.time, rng: random.Random | None = None):
        super().__init__(db, add_history)
        self.rewards = rewards
        self.now = now
        self.rng = rng

    def table(self, st: dict) -> Table:
        return Table(st, self.rng, now=lambda: self.now())

    def default_rules(self, kind: str = KIND) -> dict:
        return self.clean_rules(kind, {**DEFAULTS, **(self.db.get_setting(f"game_rules.{KIND}") or {})})

    def rules_info(self) -> dict:
        return {**self.default_rules(), "rewards": rewards_of(self.db), "max_players": MAX_PLAYERS,
                "limits": {k: {"acc": v["acc"], "ang": v["ang"]} for k, v in DIFF.items()},
                "worlds_names": [n for n, _ in LAYOUTS]}

    def clean_rules(self, kind: str, r: dict) -> dict:
        out = {}
        for k, v in DEFAULTS.items():
            x = (r or {}).get(k, v)
            if isinstance(v, int):
                try:
                    out[k] = int(x)
                except (TypeError, ValueError):
                    out[k] = v
            else:
                out[k] = str(x)
        out["bots"] = max(0, min(MAX_PLAYERS - 1, out["bots"]))
        out["level"] = out["level"] if out["level"] in LEVELS else "normal"
        out["difficulty"] = out["difficulty"] if out["difficulty"] in DIFF else "normal"
        out["worlds"] = max(1, min(len(LAYOUTS), out["worlds"]))
        return out

    def _person(self, pid: int) -> dict:
        out = super()._person(pid)
        p = self.db.q1("SELECT role FROM profile WHERE id=?", pid)
        if p and p["role"] == "guest":
            out["guest"] = True
        return out

    def best(self, pid) -> int:
        return int((self.db.get_setting("verkehr_best") or {}).get(str(pid), 0) or 0)

    def _save(self, row, st: dict) -> None:
        status = {"lobby": "lobby", "done": "done"}.get(st["phase"], "running")
        self.db.x("UPDATE card_game SET state=?, status=?, finished_at=CASE WHEN ?='done' THEN datetime('now','localtime') ELSE finished_at END WHERE id=?",
                  json.dumps(st), status, status, row["id"])
        if status != "done" or st.get("paid") or st.get("places") is None:
            return
        coins = self.coins_for(st)
        st["paid"], st["coins"] = True, coins
        best = dict(self.db.get_setting("verkehr_best") or {})
        records = {}
        scores = st.get("scores") or {}
        for p in st["players"]:
            if p.get("bot") or p.get("guest"):
                continue
            sc = int((scores.get(p["id"]) or {}).get("score", 0))
            if sc > int(best.get(p["id"], 0) or 0):
                best[p["id"]] = sc
                records[p["id"]] = True
        if records:
            self.db.set_setting("verkehr_best", best)
        st["records"] = records
        self.db.x("UPDATE card_game SET state=? WHERE id=?", json.dumps(st), row["id"])
        for pid, amount in coins.items():
            ref = f"{KIND}:{row['id']}:{pid}"
            if self.rewards and not self.db.q1("SELECT id FROM ledger WHERE ref=?", ref):
                try:
                    self.rewards.book(int(pid), "coins", amount, "game_win", win_reason(KIND, st['places'][pid]), ref=ref)
                except Exception:  # noqa: BLE001
                    pass
        if len(st["players"]) >= 2:
            self._champion(st, [p for p, n in (st.get("places") or {}).items() if n == 1])
        if self.add_history:
            for p in st["players"]:
                if p.get("bot") or p.get("guest"):
                    continue
                sc = scores.get(p["id"]) or {}
                try:
                    self.add_history(int(p["id"]), KIND, {
                        "place": st["places"].get(p["id"]), "players": len(st["players"]), "score": sc.get("score", 0),
                        "passed": sc.get("pas", 0), "accidents": sc.get("acc", 0), "angry": sc.get("ang", 0),
                        "worlds": min(st["run"][p["id"]]["w"] + 1, int(st["rules"].get("worlds", 3))),
                        "record": bool(records.get(p["id"])), "complete": bool(st.get("complete")), "coins": coins.get(p["id"], 0)})
                except Exception:  # noqa: BLE001
                    pass

    def coins_for(self, st: dict) -> dict[str, int]:
        """Coins per player: places 1–3, only people of the family, only with at least two of them at a family table,
        only for a game played to the end."""
        people = [p for p in st["players"] if not p.get("bot") and not p.get("guest")]
        if st.get("solo") or len(people) < 2 or st.get("phase") != "done" or not st.get("complete"):
            return {}
        amounts = rewards_of(self.db)
        pl = st.get("places") or {}
        out = {}
        for p in people:
            n = pl.get(p["id"])
            if n and 1 <= n <= 3 and amounts[n - 1] > 0:
                out[p["id"]] = amounts[n - 1]
        return out

    def _bots(self, st: dict, need: int) -> list[dict]:
        if need > 0 and self.bots_off(KIND, st["players"]):          # parent area › Games: without bots
            st.pop("bot_pool", None)
            return []
        pool = st.pop("bot_pool", None) or []
        taken = {b["name"] for b in pool}
        for n, e in random.sample(BOTS, len(BOTS)):
            if len(pool) >= need:
                break
            if n not in taken:
                pool.append({"name": n, "emoji": e, "level": st["rules"]["level"]})
                taken.add(n)
        out = []
        for i, b in enumerate(pool[:need]):
            lvl = b.get("level") if b.get("level") in LEVELS else st["rules"]["level"]
            out.append({"id": f"bot{i + 1}", "name": b["name"], "emoji": b.get("emoji") or "🤖", "color": b.get("color"),
                        "owner": b.get("owner"), "bot": True, "level": lvl})
        return out

    def _deal(self, st: dict) -> None:
        humans = [p for p in st["players"] if not p.get("bot")]
        n = max(0, min(st["rules"]["bots"], MAX_PLAYERS - len(humans)))
        st["players"] = humans + self._bots(st, n)
        st.pop("bot_pool", None)
        self.table(st).setup()

    def start(self, kind: str, host: int, rules: dict | None = None, solo: bool = False, bots: list[dict] | None = None) -> int:
        if kind != KIND:
            raise CommunityError("Unknown game")
        with self.lock:
            if not solo and self._row(KIND):
                raise CommunityError("This game is already running")
            if solo:
                old = self._row(KIND, host)
                if old and old["solo"]:
                    self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", old["id"])
            r = self.clean_rules(KIND, {**self.default_rules(), **{k: v for k, v in (rules or {}).items() if v is not None}})
            self.db.set_setting(f"game_rules.{KIND}", r)
            st = {"kind": KIND, "rules": r, "players": [self._person(host)], "phase": "lobby", "solo": solo, "bot_pool": list(bots or [])}
            gid = self.db.x("INSERT INTO card_game(kind, host_id, solo, state) VALUES(?,?,?,?)", KIND, host, int(solo), json.dumps(st))
            if solo:                                      # alone: the countdown starts right away
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", gid)
                self._deal(st)
                self._save(row, st)
            return gid

    def join(self, kind: str, pid: int) -> None:
        with self.lock:
            row = self._row(KIND)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if any(p["id"] == str(pid) for p in st["players"]):
                return
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            if len(st["players"]) >= MAX_PLAYERS:
                raise CommunityError("The table is full")
            st["players"].append(self._person(pid))
            self._save(row, st)

    def begin(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                raise CommunityError("No game is running")
            st = json.loads(row["state"])
            if st["phase"] != "lobby":
                raise CommunityError("The game has already started")
            self._deal(st)
            self._save(row, st)

    def report(self, pid: int, t=None, events=()) -> dict | None:
        """The app of this player reports its light switches (only its own map) – answers with the state."""
        rej = []
        with self.lock:
            row = self._row(KIND, pid)
            if row:
                st = json.loads(row["state"])
                if st["phase"] == "lobby":
                    raise CommunityError("The game has not started yet")
                if st["phase"] == "play":
                    t_ = self.table(st)
                    if str(pid) in st["run"]:
                        st["run"][str(pid)]["seen"] = self.now()
                    t_.tick()
                    if st["phase"] == "play":
                        rej = t_.report(str(pid), t, events)
                    self._save(row, st)
                    row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        if not row:
            return self.state(KIND, pid)
        out = self._view(row, st, str(pid), mine=bool(rej))
        out["rej"] = rej
        return out

    def end(self, kind: str, viewer: int) -> None:
        with self.lock:
            row = self._row(KIND, viewer)
            if not row:
                return
            st = json.loads(row["state"])
            if st["phase"] == "play":
                self.table(st).end()
                self._save(row, st)
            else:
                self.db.x("UPDATE card_game SET status='done', finished_at=datetime('now','localtime') WHERE id=?", row["id"])

    def _current(self, viewer: int):
        row = self._row(KIND, viewer)
        if row:
            return row, json.loads(row["state"])
        row = self.db.q1("""SELECT * FROM card_game WHERE kind=? AND status='done' AND finished_at >= datetime('now','localtime','-10 minutes')
                            AND (solo=0 OR host_id=?) ORDER BY id DESC LIMIT 1""", KIND, viewer)
        if not row:
            return None, None
        st = json.loads(row["state"])
        if not any(p["id"] == str(viewer) for p in st["players"]):
            return None, None
        return row, st

    def state(self, kind: str, viewer: int, mine: bool = False) -> dict | None:
        with self.lock:
            row, st = self._current(viewer)
            if not row:
                return None
            if row["status"] != "done" and st["phase"] == "play" and self.table(st).tick():
                self._save(row, st)
                row = self.db.q1("SELECT * FROM card_game WHERE id=?", row["id"])
        return self._view(row, st, str(viewer), mine=mine)

    def worlds(self, viewer: int) -> dict | None:
        """The worlds of the viewer's game (layouts and cars) – the app simulates its map with them."""
        row, st = self._current(viewer)
        if not row or st.get("phase") == "lobby":
            return None
        t = self.table(st)
        return {"game": row["id"], "seed": st["seed"], "difficulty": t.diff(),
                "worlds": [world(n, st["seed"], t.diff()) for n in range(t.nworlds())]}

    def _view(self, row, st: dict, me: str, mine: bool = False) -> dict:
        joined = any(p["id"] == me for p in st["players"])
        people = sum(1 for p in st["players"] if not p.get("bot") and not p.get("guest"))
        ph = st["phase"]
        if row["status"] == "done" and ph != "lobby":
            ph = "done"
        rules = st["rules"]
        d = DIFF.get(rules.get("difficulty"), DIFF["normal"])
        base = {"game": row["id"], "kind": KIND, "title": TITLE, "status": row["status"], "phase": ph,
                "solo": bool(row["solo"]), "host": row["host_id"], "rules": rules, "joined": joined,
                "rewards": rewards_of(self.db), "coins_on": not st.get("solo") and people >= 2, "max_players": MAX_PLAYERS,
                "best": self.best(me) if joined else 0, "now": self.now(),
                "limits": {"acc": d["acc"], "ang": d["ang"], "annoy": d["annoy"], "angry": d["angry"]},
                "worlds_names": [n for n, _ in LAYOUTS[:int(rules.get("worlds", 3))]]}
        if st["phase"] == "lobby":
            players = [{"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                        "guest": bool(p.get("guest"))} for p in st["players"]]
            return {**base, "players": players, "bots": max(0, min(rules["bots"], MAX_PLAYERS - len(players)))}
        t = self.table(st)
        run, coins, pl = st["run"], st.get("coins") or {}, st.get("places") or {}
        scores = st.get("scores") or {}
        players = []
        for p in st["players"]:
            r = run[p["id"]]
            s = scores.get(p["id"]) or t.stats(p["id"])
            players.append({"id": p["id"], "name": p["name"], "avatar": p.get("avatar"), "emoji": p.get("emoji"), "bot": bool(p.get("bot")),
                            "guest": bool(p.get("guest")), "color": p.get("color"), "owner": p.get("owner"), "level": p.get("level"),
                            **{k: s[k] for k in ("acc", "ann", "ang", "pas", "score")}, "w": min(r["w"], t.nworlds() - 1),
                            "out": None if r["out"] is None else round(r["out"] / HZ, 1), "left": bool(r.get("left")),
                            "place": pl.get(p["id"]), "coins": coins.get(p["id"], 0), "record": bool((st.get("records") or {}).get(p["id"]))})
        out = {**base, "players": players, "me": me if joined else None, "seed": st["seed"], "t0": st["t0"],
               "end_t": st.get("end_t"), "ranking": st.get("ranking"), "complete": bool(st.get("complete")),
               "now_t": t.gt() if ph == "play" else st.get("end_t"), "wt": WT, "hz": HZ}
        if mine and joined and ph == "play":
            r = run[me]
            out["my"] = {"w": r["w"], "sim": r["sim"], "tot": r["tot"], "out": r["out"],
                         "evs": {k: v for k, v in r["evs"].items() if int(k) >= r["w"]}}
        return out

    def summary(self, kind: str, pid: int) -> dict | None:
        return super().summary(KIND, pid)
