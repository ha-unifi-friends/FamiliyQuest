"""Content-Security-Policy and the other security headers of every response (main.py).

Why: pack media, photos and files of a restored backup are served from the app's own origin – through Home Assistant
ingress that is Home Assistant's origin, where a script could read the `hassTokens`. So:
- the pages (index, eltern, gast, planer, dashboard) only run scripts from the app itself: no inline scripts, no
  inline event handlers, no eval (tests/test_csp.py checks the HTML files);
- user and media content (`/media`, `/hamedia`, `/family_planer_files`, HA media previews, song covers) and every
  other non-page response gets a sandbox policy: an SVG or HTML file opened directly never runs a script;
- media files of an unknown type are downloads (`Content-Disposition: attachment`), never shown inline.
"""
from __future__ import annotations

# pages: scripts only from the app; inline styles stay allowed (the app sets many style attributes, low risk).
# connect-src ws: wss: – the planer websocket (api/planer/ws); 'self' alone does not cover ws: in older Safari.
_PAGE = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self' 'unsafe-inline'",
    "img-src": "'self' data: blob:",
    "media-src": "'self' data: blob:",
    "font-src": "'self' data:",
    "connect-src": "'self' ws: wss:",
    "worker-src": "'self'",
    "manifest-src": "'self'",
    "frame-src": "'self'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
    # through ingress Home Assistant frames us from its own origin = our origin there
    "frame-ancestors": "'self'",
}


def _join(d: dict[str, str]) -> str:
    return "; ".join(f"{k} {v}" for k, v in d.items())


PAGE_CSP = _join(_PAGE)
# parent area: the HA app sign-in test asks <Home Assistant>/auth/providers from this device (no-cors fetch,
# parent.js haAppLoginBox) – any address the parents type, so http: https: for connections on this page only
PARENT_CSP = _join({**_PAGE, "connect-src": "'self' ws: wss: http: https:"})
# kiosk dashboard: read-only, no login – a wall tablet may show it inside another page (e.g. a Home Assistant
# webpage card on the direct port), so any page may frame it
DASHBOARD_CSP = _join({**_PAGE, "frame-ancestors": "*"})
PAGE_CSP_OF = {"eltern.html": PARENT_CSP, "dashboard.html": DASHBOARD_CSP}

# media, uploads, exports, API answers: nothing runs, nothing loads except pictures; sandbox = an opaque origin
FILE_CSP = "default-src 'none'; img-src 'self' data:; media-src 'self' data:; style-src 'unsafe-inline'; sandbox"

WORKER_CSP = "script-src 'self'; object-src 'none'; base-uri 'self'"

# user and media content (main.py): always FILE_CSP, whatever type the file has
USER_CONTENT = ("/media/", "/hamedia/", "/family_planer_files/", "/api/parent/ha-media/file", "/api/community/song/cover")

# media types shown inline (pictures, sound, PDF); anything else under /media is a download
INLINE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".bmp": "image/bmp", ".ico": "image/x-icon", ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".aac": "audio/aac", ".opus": "audio/ogg", ".flac": "audio/flac", ".webm": "audio/webm",
    ".mp4": "video/mp4", ".pdf": "application/pdf",
}


def media_kwargs(name: str) -> dict:
    """FileResponse arguments for a user file: a known picture / sound inline with its type, the rest as download."""
    t = INLINE_TYPES.get(("." + name.rsplit(".", 1)[-1]).lower() if "." in name else "")
    if t:
        return {"media_type": t}
    return {"media_type": "application/octet-stream", "filename": name, "content_disposition_type": "attachment"}


def apply(path: str, headers) -> None:
    """Security headers of one response (headers = the response's MutableHeaders)."""
    headers["X-Content-Type-Options"] = "nosniff"
    headers.setdefault("Referrer-Policy", "same-origin")
    if path.startswith(USER_CONTENT):
        headers["Content-Security-Policy"] = FILE_CSP
        return
    if "Content-Security-Policy" in headers:          # a page set its own (main.py page())
        return
    ctype = headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype == "text/html":
        headers["Content-Security-Policy"] = PAGE_CSP
    elif ctype in ("text/javascript", "application/javascript"):
        # workers (sw.js, cubesolver.js) run under the policy of their own script response: only scripts of the app;
        # connections stay open – the service worker passes the pages' own requests on (e.g. the HA test of the
        # parent area), the page's policy already limits those
        headers["Content-Security-Policy"] = WORKER_CSP
    else:
        headers["Content-Security-Policy"] = FILE_CSP
