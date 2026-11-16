"""Build web/geo/europe.json – country outlines of Europe as SVG paths – for map questions («Where is Berlin?»).

Source: Natural Earth (public domain) via the npm package world-atlas (ISC). Run:

    npm pack world-atlas@2.0.2 && tar xzf world-atlas-2.0.2.tgz
    python3 tools/build_europe_geo.py package/countries-50m.json

Projection: equirectangular around 52° N; the frame shows 25° W … 45° E, 34° … 71.5° N (1000 units wide).
Polygons are clipped to a margin around the frame (Sutherland–Hodgman).
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_ch_geo import decode, polygons, simplify  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "family_quest/app/web/geo/europe.json"
LON0, LON1, LAT0, LAT1 = -25.0, 45.0, 34.0, 71.5
K = math.cos(math.radians(52))
WIDTH = 1000.0
TOL = 1.0


def main(src: str) -> None:
    topo = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    arcs = decode(topo)
    scale = WIDTH / ((LON1 - LON0) * K)
    height = round((LAT1 - LAT0) * scale, 1)
    m = 40

    def proj(p):
        return ((p[0] - LON0) * K * scale, (LAT1 - p[1]) * scale)

    def clip(pts):
        """Sutherland–Hodgman against the frame plus a margin."""
        edges = [(lambda q: q[0] >= -m, lambda a, b: (-m, a[1] + (b[1] - a[1]) * (-m - a[0]) / (b[0] - a[0]))),
                 (lambda q: q[0] <= WIDTH + m, lambda a, b: (WIDTH + m, a[1] + (b[1] - a[1]) * (WIDTH + m - a[0]) / (b[0] - a[0]))),
                 (lambda q: q[1] >= -m, lambda a, b: (a[0] + (b[0] - a[0]) * (-m - a[1]) / (b[1] - a[1]), -m)),
                 (lambda q: q[1] <= height + m, lambda a, b: (a[0] + (b[0] - a[0]) * (height + m - a[1]) / (b[1] - a[1]), height + m))]
        for inside, cut in edges:
            if not pts:
                break
            out, prev = [], pts[-1]
            for cur in pts:
                if inside(cur):
                    if not inside(prev):
                        out.append(cut(prev, cur))
                    out.append(cur)
                elif inside(prev):
                    out.append(cut(prev, cur))
                prev = cur
            pts = out
        return [(round(x, 1), round(y, 1)) for x, y in pts]

    countries = []
    for g in topo["objects"]["countries"]["geometries"]:
        d = []
        for poly in polygons(arcs, g):
            for r in poly:
                if not any(LON0 - 5 < lon < LON1 + 5 and LAT0 - 5 < lat < LAT1 + 5 for lon, lat in r):
                    continue
                if max(lon for lon, _ in r) - min(lon for lon, _ in r) > 180:      # crosses the date line (Russia)
                    r = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in r]
                pts = clip([proj(p) for p in r])
                if len(pts) < 3:
                    continue
                pts = simplify(pts + [pts[0]], TOL)[:-1]
                pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
                if len(pts) >= 3:
                    d.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        if d:
            countries.append({"name": (g.get("properties") or {}).get("name", ""), "d": "".join(d)})
    out = {"source": "Natural Earth (public domain), via world-atlas (ISC)", "width": WIDTH, "height": height,
           "countries": countries, "proj": {"lon0": LON0, "lat1": LAT1, "k": K, "scale": scale}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: {OUT.stat().st_size // 1024} KB, {len(countries)} countries")


if __name__ == "__main__":
    main(sys.argv[1])
