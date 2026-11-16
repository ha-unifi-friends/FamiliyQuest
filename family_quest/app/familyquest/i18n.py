"""Server-side text is English source text; the web client translates it (see web/shared/i18n.js).

Wrap user-visible English strings in `_t()` so tools/i18n_extract.py finds them.
"""


def _t(s: str) -> str:
    return s
