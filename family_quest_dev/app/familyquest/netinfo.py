"""How devices in the home network reach the app directly (QR codes for tablets, kiosk dashboard, game guests)."""
from __future__ import annotations

import os

import httpx


async def home_access(s) -> dict:
    """Is direct access on, which host port is mapped to 8099 and which IP has Home Assistant (Supervisor API)."""
    port, ips = None, []
    if s.ha_token:
        base = os.environ.get("FQ_SUPERVISOR_URL", "http://supervisor")
        async with httpx.AsyncClient(base_url=base, timeout=3, headers={"Authorization": f"Bearer {s.ha_token}"}) as c:
            try:
                info = (await c.get("/addons/self/info")).json().get("data") or {}
                port = (info.get("network") or {}).get("8099/tcp")
            except (httpx.HTTPError, ValueError):
                pass
            try:
                net = (await c.get("/network/info")).json().get("data") or {}
                for itf in net.get("interfaces") or []:
                    for addr in ((itf.get("ipv4") or {}).get("address") or []):
                        ip = str(addr).split("/")[0]
                        (ips.insert(0, ip) if itf.get("primary") else ips.append(ip))
            except (httpx.HTTPError, ValueError):
                pass
    from .settings import default_port
    return {"enabled": s.direct_access, "port": port, "default_port": default_port(), "ips": ips}


_PANEL: dict = {}


async def ha_panel(s) -> dict:
    """Where the Family Quest panel is in Home Assistant: add-on slug plus HA port and https – the browser adds its own host
    (http://<host>:8123/app/<slug>, older HA /hassio/ingress/<slug> – works for every user and leads to the HA login first). Asked once from the Supervisor and kept."""
    if _PANEL or not s.ha_token:
        return dict(_PANEL)
    base = os.environ.get("FQ_SUPERVISOR_URL", "http://supervisor")
    async with httpx.AsyncClient(base_url=base, timeout=3, headers={"Authorization": f"Bearer {s.ha_token}"}) as c:
        try:
            info = (await c.get("/addons/self/info")).json().get("data") or {}
            core = (await c.get("/core/info")).json().get("data") or {}
        except (httpx.HTTPError, ValueError):
            return {}
    if info.get("slug"):
        _PANEL.update(slug=info["slug"], port=int(core.get("port") or 8123), ssl=bool(core.get("ssl")))
    return dict(_PANEL)


async def update_info(s) -> dict:
    """Installed and newest known version of this add-on (Supervisor store) – not cached, the store may have refreshed."""
    if not s.ha_token:
        return {}
    base = os.environ.get("FQ_SUPERVISOR_URL", "http://supervisor")
    async with httpx.AsyncClient(base_url=base, timeout=5, headers={"Authorization": f"Bearer {s.ha_token}"}) as c:
        try:
            info = (await c.get("/addons/self/info")).json().get("data") or {}
        except (httpx.HTTPError, ValueError):
            return {}
    return {"version": info.get("version"), "latest": info.get("version_latest"),
            "update": bool(info.get("update_available"))}
