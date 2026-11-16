"""Build web/geo/arms.json – simplified symbols of the 26 canton coats of arms (pixel style, 13 × 13) for picture
questions («Which canton has this coat of arms?»).

Source: the npm package ch-canton-symbols (NZZ Storytelling), licence CC BY-SA 4.0 – the built file stays under
that licence (see THIRD_PARTY_NOTICES.md). Run:

    npm pack ch-canton-symbols@1.3.2 && tar xzf ch-canton-symbols-1.3.2.tgz
    python3 tools/build_ch_arms.py package/symbols/13x13
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "family_quest/app/web/geo/arms.json"
CANTONS = "ZH BE LU UR SZ OW NW GL ZG FR SO BS BL SH AR AI SG GR AG TG TI VD VS NE GE JU".split()


def main(src: str) -> None:
    arms = {}
    for k in CANTONS:
        svg = (pathlib.Path(src) / f"{k.lower()}.svg").read_text(encoding="utf-8")
        body = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg.strip(), flags=re.S)
        if "<script" in body or "on" in re.findall(r"\s(on)\w+=", body):
            raise SystemExit(f"{k}: unexpected content")
        arms[k] = body
    out = {"source": "ch-canton-symbols © NZZ Storytelling", "license": "CC BY-SA 4.0", "size": 13, "arms": arms}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: {OUT.stat().st_size} bytes, {len(arms)} coats of arms")


if __name__ == "__main__":
    main(sys.argv[1])
