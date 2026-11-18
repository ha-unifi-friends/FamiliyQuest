"""Small client for the Family Quest add-on API (/api/integration/…) – aiohttp only, no Home Assistant imports."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class FamilyQuestError(Exception):
    """The add-on cannot be reached or answered with an error."""


class FamilyQuestAuthError(FamilyQuestError):
    """The integration token is wrong, or the integration is switched off in Family Quest."""


class FamilyQuestApi:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token

    async def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        try:
            async with asyncio.timeout(15):
                async with self._session.request(
                    method, f"{self._url}/api/integration/{path}", json=json,
                    headers={"Authorization": f"Bearer {self._token}"},
                ) as resp:
                    if resp.status in (401, 403):
                        raise FamilyQuestAuthError(await _detail(resp))
                    if resp.status >= 400:
                        raise FamilyQuestError(await _detail(resp))
                    return await resp.json()
        except FamilyQuestError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise FamilyQuestError(str(err) or type(err).__name__) from err

    async def state(self) -> dict:
        return await self._request("GET", "state")

    async def action(self, action: str, **data: Any) -> dict:
        return await self._request("POST", "action", {"action": action, **data})


async def _detail(resp: aiohttp.ClientResponse) -> str:
    try:
        return str((await resp.json()).get("detail") or resp.status)
    except (aiohttp.ClientError, ValueError):
        return f"HTTP {resp.status}"
