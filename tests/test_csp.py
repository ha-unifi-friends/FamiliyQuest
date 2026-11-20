"""Content-Security-Policy and security headers (familyquest/csp.py, main.py) – review finding M2."""
import base64
import hashlib
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "family_quest" / "app" / "web"
EVIL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.cookie)</script><rect width="1" height="1"/></svg>'


def _directives(csp: str) -> dict:
    return {p.split()[0]: p.split()[1:] for p in (x.strip() for x in csp.split(";")) if p}


def _common(r):
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"


def test_pages_have_a_strict_policy(client):
    for path in ("/", "/app", "/parents", "/guest", "/planner", "/dashboard"):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), path
        _common(r)
        d = _directives(r.headers["content-security-policy"])
        assert d["script-src"] == ["'self'"], path                     # no 'unsafe-inline', no 'unsafe-eval'
        assert d["default-src"] == ["'self'"] and d["object-src"] == ["'none'"] and d["base-uri"] == ["'self'"], path
        assert "'self'" in d["connect-src"] and "wss:" in d["connect-src"], path       # the planer websocket
        assert "data:" in d["img-src"] and "blob:" in d["img-src"], path
        assert d["form-action"] == ["'self'"] and d["frame-src"] == ["'self'"], path
        assert d["frame-ancestors"] == (["*"] if path == "/dashboard" else ["'self'"]), path


def test_api_and_static_answers_have_headers(client):
    r = client.get("/api/info")
    _common(r)
    d = _directives(r.headers["content-security-policy"])
    assert d["default-src"] == ["'none'"] and "sandbox" in d
    r = client.get("/api/nothing-here")                     # errors too
    _common(r)
    assert "sandbox" in r.headers["content-security-policy"]
    r = client.get("/shared/base.css")
    _common(r)
    assert "content-security-policy" in r.headers


def test_refusals_have_headers(client, monkeypatch):
    """The early answers of the access middleware (firewall) get the headers too."""
    from familyquest import netfilter
    monkeypatch.setattr(netfilter, "check", lambda fq, ip, path: "app")
    monkeypatch.setattr(netfilter, "log_blocked", lambda *a: None)
    r = client.get("/app")
    assert r.status_code == 403
    _common(r)
    assert _directives(r.headers["content-security-policy"])["script-src"] == ["'self'"]


def test_media_svg_is_sandboxed(client):
    media = client.app.state.fq.settings.media_dir / "evilpack"
    media.mkdir(parents=True, exist_ok=True)
    (media / "x.svg").write_bytes(EVIL_SVG)
    (media / "x.html").write_bytes(b"<script>alert(1)</script>")
    (media / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    r = client.get("/media/evilpack/x.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    _common(r)
    d = _directives(r.headers["content-security-policy"])
    assert "sandbox" in d and d["default-src"] == ["'none'"] and "script-src" not in d
    assert "attachment" not in r.headers.get("content-disposition", "")       # still shows as a picture
    # an unknown type (e.g. HTML from a restored backup) is a download, never a page of the app
    r = client.get("/media/evilpack/x.html")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in r.headers["content-security-policy"]
    r = client.get("/media/evilpack/a.png")
    assert r.headers["content-type"] == "image/png" and "sandbox" in r.headers["content-security-policy"]


def test_planer_files_are_sandboxed(client):
    base = client.app.state.fq.settings.data_dir / "family_planer" / "avatars"
    base.mkdir(parents=True, exist_ok=True)
    (base / "p.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    r = client.get("/family_planer_files/avatars/p.png")
    assert r.status_code == 200
    _common(r)
    assert "sandbox" in r.headers["content-security-policy"]


def test_media_kwargs():
    from familyquest import csp
    assert csp.media_kwargs("a.SVG") == {"media_type": "image/svg+xml"}
    assert csp.media_kwargs("song.mp3") == {"media_type": "audio/mpeg"}
    k = csp.media_kwargs("evil.html")
    assert k["content_disposition_type"] == "attachment" and k["media_type"] == "application/octet-stream"
    assert csp.media_kwargs("noext")["content_disposition_type"] == "attachment"


INLINE_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
HANDLER = re.compile(r"<[a-z][^>]*\son[a-z]+\s*=", re.I)


def test_html_files_have_no_inline_script():
    """script-src 'self': every <script> of the pages is a file of the app (or carries a hash in the policy – none
    does today), and no element has an inline event handler or a javascript: link."""
    from familyquest import csp
    files = sorted(WEB.rglob("*.html"))
    assert {"index.html", "eltern.html", "gast.html", "planer.html", "dashboard.html"} <= {f.name for f in files}
    for f in files:
        t = f.read_text(encoding="utf-8")
        for attrs, body in INLINE_SCRIPT.findall(t):
            if "src=" in attrs:
                assert not body.strip(), f"{f.name}: <script src> with a body"
                continue
            digest = "'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
            assert digest in csp.PAGE_CSP, f"{f.name}: inline <script> without a hash in the policy: {body.strip()[:60]!r}"
        assert not HANDLER.search(t), f"{f.name}: inline event handler"
        assert "javascript:" not in t.lower(), f"{f.name}: javascript: link"
        for src in re.findall(r"<script[^>]*\ssrc=\"([^\"?]+)", t):
            assert not src.startswith(("http:", "https:", "//")), f"{f.name}: external script {src}"
            assert (WEB / src).is_file(), f"{f.name}: missing {src}"
