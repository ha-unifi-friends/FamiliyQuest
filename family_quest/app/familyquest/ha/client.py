"""Small async Home Assistant client: REST for states/services/events, WebSocket for
registries, todo items and event subscriptions. Reconnects with backoff."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import httpx
import websockets

log = logging.getLogger("familyquest.ha")


class HAError(RuntimeError):
    pass


class HAClient:
    last_error: str = ""                    # why the last connection attempt failed (shown in the parent area)

    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/")
        self.token = token
        self.http = httpx.AsyncClient(base_url=self.base, timeout=15,
                                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.ws = None
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._subs: dict[int, Callable[[dict], Awaitable[None] | None]] = {}
        self._wanted_subs: list[tuple[str, Callable]] = []
        self.connected = asyncio.Event()
        self.on_connect: list[Callable[[], Awaitable[None]]] = []
        self._task: asyncio.Task | None = None

    # ---------------------------------------------------------------- REST
    async def get_state(self, entity_id: str) -> dict | None:
        r = await self.http.get(f"/api/states/{entity_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def states(self) -> list[dict]:
        r = await self.http.get("/api/states")
        r.raise_for_status()
        return r.json()

    async def set_state(self, entity_id: str, state: Any, attributes: dict) -> None:
        r = await self.http.post(f"/api/states/{entity_id}", json={"state": str(state), "attributes": attributes})
        r.raise_for_status()

    async def call(self, domain: str, service: str, data: dict) -> Any:
        r = await self.http.post(f"/api/services/{domain}/{service}", json=data)
        if r.status_code >= 400:
            raise HAError(f"{domain}.{service}: HTTP {r.status_code} {r.text[:200]}")
        return r.json() if r.content else None

    async def call_response(self, domain: str, service: str, data: dict) -> Any:
        """Service call that returns data (calendar.get_events, todo.get_items, ai_task.generate_data …)."""
        r = await self.http.post(f"/api/services/{domain}/{service}", params={"return_response": ""}, json=data, timeout=40)
        if r.status_code >= 400:
            raise HAError(f"{domain}.{service}: HTTP {r.status_code} {r.text[:200]}")
        body = r.json() if r.content else {}
        return body.get("service_response", body) if isinstance(body, dict) else body

    async def fire(self, event: str, data: dict) -> None:
        r = await self.http.post(f"/api/events/{event}", json=data)
        r.raise_for_status()

    async def config(self) -> dict:
        r = await self.http.get("/api/config")
        r.raise_for_status()
        return r.json()

    # ---------------------------------------------------------------- WebSocket
    def ws_url(self) -> str:
        u = self.base.replace("https://", "wss://").replace("http://", "ws://")
        return u + ("/websocket" if u.endswith("/core") else "/api/websocket")

    async def command(self, msg: dict, timeout: float = 15) -> Any:
        await asyncio.wait_for(self.connected.wait(), timeout)
        self._id += 1
        mid = self._id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self.ws.send(json.dumps({**msg, "id": mid}))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(mid, None)

    def subscribe(self, event_type: str, handler: Callable[[dict], Awaitable[None] | None]) -> None:
        """Registered once; (re)subscribed on every connect."""
        self._wanted_subs.append((event_type, handler))

    async def _subscribe_all(self) -> None:
        for et, handler in self._wanted_subs:
            self._id += 1
            mid = self._id
            self._subs[mid] = handler
            await self.ws.send(json.dumps({"id": mid, "type": "subscribe_events", "event_type": et}))

    async def _reader(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            mid = msg.get("id")
            if msg.get("type") == "result" and mid in self._pending:
                fut = self._pending[mid]
                if not fut.done():
                    if msg.get("success"):
                        fut.set_result(msg.get("result"))
                    else:
                        fut.set_exception(HAError(str(msg.get("error"))))
            elif msg.get("type") == "event" and mid in self._subs:
                try:
                    res = self._subs[mid](msg["event"])
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:  # noqa: BLE001
                    log.exception("event handler failed")

    async def run(self) -> None:
        delay = 2
        while True:
            try:
                async with websockets.connect(self.ws_url(), max_size=32 * 1024 * 1024) as ws:
                    self.ws = ws
                    hello = json.loads(await ws.recv())
                    if hello.get("type") == "auth_required":
                        await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
                        ok = json.loads(await ws.recv())
                        if ok.get("type") != "auth_ok":
                            raise HAError("authentication failed")
                    self._subs.clear()
                    self.connected.set()
                    self.last_error = ""
                    log.info("connected to Home Assistant")
                    delay = 2
                    reader = asyncio.create_task(self._reader())
                    await self._subscribe_all()
                    for cb in self.on_connect:
                        asyncio.create_task(cb())
                    await reader
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 – keep reconnecting
                self.last_error = f"{type(e).__name__}: {e}"[:300]
                log.warning("Home Assistant connection: %s – retry in %ss", e, delay)
            finally:
                self.connected.clear()
                for f in self._pending.values():
                    if not f.done():
                        f.set_exception(HAError("disconnected"))
            await asyncio.sleep(delay)
            delay = min(60, delay * 2)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self.http.aclose()
