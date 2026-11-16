"""Build web/geo/ch.json – the outlines of the 26 cantons and the big lakes as SVG paths – for picture questions.

Source: the npm package swiss-maps (BSD-3-Clause, Interactive Things) with the generalised boundaries of the Federal
Statistical Office (FSO / swisstopo, free to use with the source given). Run:

    npm pack swiss-maps@4.7.0 && tar xzf swiss-maps-4.7.0.tgz
    python3 tools/build_ch_geo.py package/2026/ch-combined.json

The coordinates (WGS84) are projected with a simple equirectangular projection around 46.8° N, simplified
(Douglas-Peucker) and written in a 1000-unit wide frame.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "family_quest/app/web/geo/ch.json"
# FSO canton numbers → abbreviation, German name
CANTONS = {1: ("ZH", "Zürich"), 2: ("BE", "Bern"), 3: ("LU", "Luzern"), 4: ("UR", "Uri"), 5: ("SZ", "Schwyz"),
           6: ("OW", "Obwalden"), 7: ("NW", "Nidwalden"), 8: ("GL", "Glarus"), 9: ("ZG", "Zug"), 10: ("FR", "Freiburg"),
           11: ("SO", "Solothurn"), 12: ("BS", "Basel-Stadt"), 13: ("BL", "Basel-Landschaft"), 14: ("SH", "Schaffhausen"),
           15: ("AR", "Appenzell Ausserrhoden"), 16: ("AI", "Appenzell Innerrhoden"), 17: ("SG", "St. Gallen"),
           18: ("GR", "Graubünden"), 19: ("AG", "Aargau"), 20: ("TG", "Thurgau"), 21: ("TI", "Tessin"), 22: ("VD", "Waadt"),
           23: ("VS", "Wallis"), 24: ("NE", "Neuenburg"), 25: ("GE", "Genf"), 26: ("JU", "Jura")}
LAT0 = math.radians(46.8)
WIDTH = 1000.0
TOL = 0.9                      # simplification in output units


def decode(topo: dict) -> list[list[tuple[float, float]]]:
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring(arcs, idx: list[int]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i in idx:
        pts = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        out += pts if not out else pts[1:]
    return out


def polygons(arcs, geom) -> list[list[list[tuple[float, float]]]]:
    if geom["type"] == "Polygon":
        return [[ring(arcs, r) for r in geom["arcs"]]]
    if geom["type"] == "MultiPolygon":
        return [[ring(arcs, r) for r in p] for p in geom["arcs"]]
    return []


def simplify(pts, tol):
    if len(pts) < 4:
        return pts
    def dist(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return math.hypot(x - x1, y - y1)
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        best, idx = 0.0, None
        for i in range(a + 1, b):
            d = dist(pts[i], pts[a], pts[b])
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def main(src: str) -> None:
    topo = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    arcs = decode(topo)
    allpts = [p for a in arcs for p in a]
    lon0 = min(p[0] for p in allpts)
    lat1 = max(p[1] for p in allpts)
    k = math.cos(LAT0)
    xs = [(p[0] - lon0) * k for p in allpts]
    scale = WIDTH / max(xs)
    proj = lambda p: (round((p[0] - lon0) * k * scale, 1), round((lat1 - p[1]) * scale, 1))   # noqa: E731
    height = round(max(proj(p)[1] for p in allpts), 1)

    def path(polys) -> tuple[str, list[float]]:
        d, bb = [], [1e9, 1e9, -1e9, -1e9]
        for poly in polys:
            for r in poly:
                pts = simplify([proj(p) for p in r], TOL)
                if len(pts) < 3:
                    continue
                for x, y in pts:
                    bb = [min(bb[0], x), min(bb[1], y), max(bb[2], x), max(bb[3], y)]
                d.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        return "".join(d), [round(v, 1) for v in bb]

    cantons = {}
    for g in topo["objects"]["cantons"]["geometries"]:
        abbr, name = CANTONS[int(g["id"])]
        d, bb = path(polygons(arcs, g))
        cantons[abbr] = {"name": name, "d": d, "bbox": bb}
    lakes = []
    for g in topo["objects"]["lakes"]["geometries"]:
        d, bb = path(polygons(arcs, g))
        if (bb[2] - bb[0]) * (bb[3] - bb[1]) > 60:       # only lakes you can see on the whole map
            lakes.append(d)
    out = {"source": "FSO/swisstopo generalised boundaries, via swiss-maps (BSD-3-Clause, Interactive Things)",
           "width": WIDTH, "height": height, "cantons": cantons, "lakes": lakes,
           # x = (lon - lon0) * k * scale, y = (lat1 - lat) * scale – to turn a pin back into coordinates
           "proj": {"lon0": lon0, "lat1": lat1, "k": k, "scale": scale}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: {OUT.stat().st_size // 1024} KB, {len(cantons)} cantons, {len(lakes)} lakes")


if __name__ == "__main__":
    main(sys.argv[1])
