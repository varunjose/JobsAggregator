from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_greenhouse(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    data = await _get(client, url)
    if not data:
        return []
    jobs = []
    for raw in data.get("jobs") or []:
        location = ((raw.get("location") or {}).get("name")) or ""
        apply = raw.get("absolute_url") or ""
        jobs.append(
            Job(
                job_id=f"greenhouse:{raw.get('id')}",
                title=(raw.get("title") or "").strip(),
                company=raw.get("company_name") or name,
                location=location,
                country=infer_country(location),
                remote=is_remote(location),
                ats="greenhouse",
                source="company-career-page",
                posted_at=parse_dt(raw.get("first_published")),
                description=strip_html(raw.get("content")),
                apply_url=apply,
                original_url=apply,
                department=_dept(raw),
                extra={"updated_at": raw.get("updated_at"), "board": board},
            )
        )
    return jobs


def _dept(raw: dict[str, Any]) -> str | None:
    depts = raw.get("departments") or []
    if depts and isinstance(depts, list):
        return depts[0].get("name")
    return None


async def _get(client: httpx.AsyncClient, url: str, params=None):
    from aggregator.http import get_json

    try:
        return await get_json(client, url, params=params)
    except Exception:
        return None
