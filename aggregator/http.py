from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

DEFAULT_UA = (
    "JobsAggregator/1.0 (+https://github.com/varunjose/JobsAggregator)"
)
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def client(timeout: float = 25.0, browser: bool = False) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": BROWSER_UA if browser else DEFAULT_UA, "Accept": "application/json"},
        follow_redirects=True,
        http2=False,
    )


async def get_json(
    c: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    retries: int = 3,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = await c.get(url, params=params, headers=headers)
            if resp.status_code in {429, 502, 503, 504}:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            if not resp.content:
                return None
            return resp.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            await asyncio.sleep(0.8 * (attempt + 1))
    if last_exc:
        raise last_exc
    return None


async def post_json(
    c: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    *,
    headers: Optional[dict[str, str]] = None,
    retries: int = 3,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = await c.post(url, json=payload, headers=headers)
            if resp.status_code in {429, 502, 503, 504}:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            if not resp.content:
                return None
            return resp.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            await asyncio.sleep(0.8 * (attempt + 1))
    if last_exc:
        raise last_exc
    return None
