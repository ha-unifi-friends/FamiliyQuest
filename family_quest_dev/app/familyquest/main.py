"""FastAPI application: API, web app (kids + parents), media and translations."""
from __future__ import annotations

import asyncio
import logging
import math
import re
from html import escape as html_escape
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from .i18n import _t
from .api import community, decks, integration as integration_api, kid, parent, planer
from .api import stories as stories_api
from .api import codelab as codelab_api
from . import loginlog, memo, netfilter
from .packs import i18n as pack_i18n
from .channel import feature_visible, hidden_games
from .api import deals as deals_api
from .api import haauth as haauth_api
from .api import analytics as analytics_api
from .api import privacy as privacy_api
from .api.auth import INGRESS_IP
from .services import FamilyQuest
from .settings import WEB_DIR, Settings, load_settings

log = logging.getLogger("familyquest")


def create_app(settings: Settings | None = None, fq: FamilyQuest | None = None) -> FastAPI:
    settings = settings or (fq.settings if fq else load_settings())
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        core = app.state.fq
        core.packs.sync_folders(settings.packs_dirs)
        core.db.start_backup_watch(settings.data_dir)     # hot backups by Home Assistant pause the writes (hotbackup.py)
        from . import integration
        asyncio.get_running_loop().run_in_executor(None, integration.install_on_start, core)   # HA integration: update /config copy
        async def relink():
            """Old copies of Home Assistant Media photos become references (smaller backup) – in the background."""
            from . import memorygame
            try:
                n = await asyncio.to_thread(memorygame.relink_ha_copies, core)
                if n:
                    log.info("%d photos now refer to Home Assistant Media instead of a copy", n)
            except Exception:  # noqa: BLE001
                log.exception("Linking photos to Home Assistant Media failed")
        asyncio.create_task(relink())
        from .planer.host import PlanerHost
        core.planer_host = PlanerHost(core)
        await core.planer_host.start(ha_expected=bool(settings.ha_enabled and settings.ha_token))
        client = None
        if settings.ha_enabled and settings.ha_token:
            from .ha.client import HAClient
            from .ha.service import HAService
            client = HAClient(settings.ha_url, settings.ha_token)
            core.ha = HAService(core, client, asyncio.get_running_loop())
            client.start()
            async def lan_base():
                """Where speakers in the home network fetch the game sounds: the direct access of the app."""
                from .netinfo import home_access
                try:
                    acc = await home_access(settings)
                except Exception:  # noqa: BLE001
                    return
                if acc.get("enabled") and acc.get("port") and acc.get("ips"):
                    core.lan_base = f"http://{acc['ips'][0]}:{acc['port']}"
            asyncio.create_task(lan_base())
        else:
            log.info("Home Assistant connection disabled")
        from . import privacy
        nightly = asyncio.create_task(privacy.auto_loop(core))     # the automatic clean-up at night (off by default)
        yield
        core.db.stop_backup_watch()
        nightly.cancel()
        await core.planer_host.stop()
        if client:
            await client.close()

    app = FastAPI(title="Family Quest", version=settings.version, lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request: Request, exc: RequestValidationError) -> JSONResponse:
        """422 like FastAPI's own – but a refused Infinity / NaN in the body must not break the answer itself."""
        def finite(v):
            if isinstance(v, float) and not math.isfinite(v):
                return str(v)
            if isinstance(v, dict):
                return {k: finite(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [finite(x) for x in v]
            return v
        return JSONResponse(status_code=422, content={"detail": finite(jsonable_encoder(exc.errors()))})
    app.state.fq = fq or FamilyQuest(settings)

    @app.middleware("http")
    async def access(request: Request, call_next):
        # games still in development (channel.py): outside the dev channel their API does not exist
        if request.url.path.startswith("/api/codelab") and not feature_visible("codelab"):    # 💡 Code Workshop: dev channel only
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.url.path.startswith("/api/community/") and community.game_of(request.url.path) in hidden_games():
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # Family Quest HA integration (custom component): inside the add-on only Home Assistant Core on the Supervisor
        # network may call it – the integration token is checked by the API itself (api/integration.py)
        if request.url.path.startswith("/api/integration/") and settings.ha_enabled:
            host = request.client.host if request.client else ""
            if not netfilter.allowed(host, [netfilter.SUPERVISOR_NET]) or host == INGRESS_IP:
                return JSONResponse({"detail": _t("Only Home Assistant may use the integration API")}, status_code=403)
            resp = await call_next(request)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        # Inside the add-on: without the direct-access option only Home Assistant ingress may talk to us.
        if settings.ha_enabled and not settings.direct_access:
            host = request.client.host if request.client else ""
            if host != INGRESS_IP:
                return JSONResponse({"detail": _t("Direct access is switched off – open Family Quest from Home Assistant")},
                                    status_code=403)
        # mini firewall: networks allowed for the app / the parent area (parent area → Settings)
        ip = loginlog.client_ip(request)
        reason = netfilter.check(app.state.fq, ip, request.url.path)
        if reason:
            netfilter.log_blocked(app.state.fq, ip, loginlog.device(app.state.fq, ip))
            msg = {"app": _t("Access from this network is not allowed"), "parent": _t("The parent area cannot be opened from this network"),
                   "guest": "Guest network: only games with an invitation (QR code) are open"}[reason]
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": msg}, status_code=403)
            return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                                f"<title>Family Quest</title><body style='font-family:system-ui;text-align:center;padding:40px'>"
                                f"<h1>🔒</h1><p>{msg}.</p><p style='color:#888'>{html_escape(ip)}</p>", status_code=403)
        resp = await call_next(request)
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        return resp

    @app.middleware("http")
    async def request_memo(request: Request, call_next):
        """Around everything (added last = outermost): one memo per request (memo.py) – settings, the games access,
        the running tables … are read once per request instead of dozens of times."""
        token = memo.begin()
        lang = pack_i18n.set_viewer(request.headers.get("x-fq-lang"))     # packs in the viewer's language (packs/i18n.py)
        try:
            return await call_next(request)
        finally:
            pack_i18n.reset_viewer(lang)
            memo.end(token)

    app.include_router(kid.router)
    app.include_router(parent.router)
    app.include_router(planer.router)
    app.include_router(community.router)
    app.include_router(decks.router)
    app.include_router(stories_api.router)
    app.include_router(codelab_api.router)              # 💡 Code Workshop (codelab.py)
    app.include_router(integration_api.router)
    app.include_router(integration_api.parent_router)
    app.include_router(deals_api.router)               # deals (deals.py)
    app.include_router(haauth_api.router)              # «Sign in with Home Assistant» on the direct port (haauth.py)
    app.include_router(deals_api.parent_router)
    app.include_router(analytics_api.router)           # 📈 Analytics in the parent area (analytics.py)
    app.include_router(privacy_api.router)             # privacy: retention periods and clean-up runs (privacy.py)

    def page(name: str) -> HTMLResponse:
        html = (WEB_DIR / name).read_text(encoding="utf-8").replace("__VERSION__", settings.version)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        # through Home Assistant («Open Web UI», sidebar) the address opens the parent area; on the direct port
        # (tablets, phones of the children) it stays the app
        return page("eltern.html" if _ingress_parent_area(request) else "index.html")

    def _ingress_parent_area(request: Request) -> bool:
        """Through Home Assistant the panel is open to every Home Assistant user (panel_admin: false): the parent area
        for linked parents and Home Assistant administrators, the children's app for everybody else (a child linked
        with its Home Assistant user logs in there without PIN). The parent area itself still needs its login."""
        from .api.auth import ha_kid, ha_user, profile_of_ha_user, via_ingress
        if not via_ingress(request):
            return False
        u = ha_user(request)
        if not u:
            return True                           # no user known (older Home Assistant): as before
        fq = app.state.fq
        if profile_of_ha_user(fq, u["id"], "parent"):
            return True
        if ha_kid(fq, request):
            return False
        return bool(fq.ha and fq.ha.connected and fq.ha.user_is_admin(u["id"]))

    @app.get("/app", include_in_schema=False)
    def kid_app():
        return page("index.html")

    @app.get("/app/", include_in_schema=False)
    def kid_app_slash():
        return Response(status_code=307, headers={"Location": "../app"})        # relative links need /app without slash

    @app.get("/parents", include_in_schema=False)
    def parents():
        return page("eltern.html")

    @app.get("/guest", include_in_schema=False)
    def guest_page():
        return page("gast.html")

    # the former German addresses (printed guest QR codes, bookmarks, home screen icons): a relative redirect – it
    # stays below the Home Assistant ingress prefix; the query is kept, the #hash the browser keeps by itself
    def _moved(to: str):
        def redirect(request: Request):
            q = request.url.query
            return Response(status_code=307, headers={"Location": to + ("?" + q if q else ""), "Cache-Control": "no-cache"})
        return redirect

    for _old, _new in netfilter.OLD_PAGES.items():
        app.add_api_route(_old, _moved(_new.lstrip("/")), methods=["GET", "HEAD"], include_in_schema=False)

    @app.get("/dashboard", include_in_schema=False)
    def dashboard_page():
        return page("dashboard.html")

    @app.get("/planner", include_in_schema=False)
    def planer_page():
        return page("planer.html")

    I18N_CACHE = {"Cache-Control": "private, max-age=604800"}   # the page asks with ?v=<app version>

    def _lang_ok(lang: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]{2}(-[A-Za-z]{2})?|x-[a-z0-9]{1,24}", lang))

    @app.get("/i18n/languages.json", include_in_schema=False)
    def i18n_languages():
        """Languages the parents created (shown in the language picker after the built-in ones)."""
        return JSONResponse(app.state.fq.translations.languages(), headers={"Cache-Control": "no-cache"})

    @app.get("/i18n/custom/{lang}.json", include_in_schema=False)
    def i18n_custom(lang: str):
        """The parents' own texts for a language – loaded last, so they win."""
        if not _lang_ok(lang):
            raise HTTPException(404)
        return JSONResponse(app.state.fq.translations.overrides(lang), headers={"Cache-Control": "no-cache"})

    def _i18n_file(lang: str, sub: str = ""):
        if not _lang_ok(lang):
            raise HTTPException(404)
        base = app.state.fq.translations.base_of(lang) if lang.startswith("x-") else lang
        f = WEB_DIR / "i18n" / sub / f"{base}.json"
        if not base or not f.is_file():
            return JSONResponse({}, status_code=404)
        return FileResponse(f, media_type="application/json; charset=utf-8",
                            headers=I18N_CACHE if base == lang else {"Cache-Control": "no-cache"})

    @app.get("/i18n/planer/{lang}.json", include_in_schema=False)
    def i18n_planer(lang: str):
        return _i18n_file(lang, "planer")

    @app.get("/i18n/{lang}.json", include_in_schema=False)
    def i18n(lang: str):
        return _i18n_file(lang)

    @app.get("/media/{pack_id}/{name}", include_in_schema=False)
    def media(pack_id: str, name: str):
        if not re.fullmatch(r"[a-z0-9_.-]+", pack_id) or "/" in name or name.startswith("."):
            raise HTTPException(404)
        f = (settings.media_dir / pack_id / name).resolve()
        if settings.media_dir.resolve() not in f.parents or not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/hamedia/{path:path}", include_in_schema=False)
    def ha_media_photo(path: str):
        """A photo of a set / the crest that stays in Home Assistant Media – only pictures a set or the crest uses."""
        from . import memorygame
        name = memorygame.HA + path
        if not memorygame.referenced(app.state.fq, name) or not memorygame.ha_ref_ok(app.state.fq, name):
            raise HTTPException(404)
        f = memorygame.ha_media_path(settings.ha_media_dir, path)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/family_planer_files/{path:path}", include_in_schema=False)
    def planer_files(path: str):
        """Photos of the Planer persons (img:/family_planer_files/avatars/…)."""
        base = (settings.data_dir / "family_planer").resolve()
        f = (base / path).resolve()
        if base not in f.parents or not f.is_file() or f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            raise HTTPException(404)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=86400"})

    static_types = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png",
                    ".webmanifest": "application/manifest+json", ".json": "application/json", ".ico": "image/x-icon",
                    ".wav": "audio/wav", ".mp3": "audio/mpeg"}

    @app.get("/{path:path}", include_in_schema=False)
    def static(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = (WEB_DIR / path).resolve()
        if WEB_DIR.resolve() not in f.parents or not f.is_file() or f.suffix not in static_types:
            raise HTTPException(404)
        headers = {"Cache-Control": "no-cache"}
        if path == "sw.js":
            body = f.read_text(encoding="utf-8").replace("__VERSION__", settings.version)
            return Response(body, media_type="text/javascript", headers=headers)
        return FileResponse(f, media_type=static_types[f.suffix], headers=headers)

    return app


def app_factory() -> FastAPI:
    return create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run("familyquest.main:app_factory", factory=True, host="0.0.0.0", port=8099, proxy_headers=False)


__all__ = ["create_app", "app_factory", "Path"]
