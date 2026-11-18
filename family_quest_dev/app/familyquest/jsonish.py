"""JSON as AIs tend to write it: wrapped in a ``` code fence, with a sentence around it, // or /* */ comments,
trailing commas. `loads` reads all of that; plain JSON is read as it is."""
from __future__ import annotations

import json
import re


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments outside of strings and commas before } or ]."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True; out.append(ch)
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j; continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def loads(text: str):
    text = (text or "").strip().lstrip("﻿")
    try:
        return json.loads(text)
    except ValueError:
        pass
    fence = re.search(r"```(?:json[c5]?|javascript)?\s*\n(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if starts:                                   # a sentence before the JSON
        a = min(starts)
        b = max(text.rfind("}"), text.rfind("]"))
        if b > a:
            text = text[a:b + 1]
    return json.loads(_strip_comments(text))
