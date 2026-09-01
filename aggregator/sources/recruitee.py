from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_recruitee(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    url = f"https://{board}.recruitee.com/api/offers/"
    try:
        data = await get_json(client, url)
    except Exception:
        return []
    jobs = []
    for raw in (data or {}).get("offers") or []:
        loc_parts = []
        loc = raw.get("location") or {}
        if isinstance(loc, dict):
            loc_parts = [loc.get("city"), loc.get("country_code") or loc.get("country")]
        location = raw.get("location_str") or ", ".join(p for p in loc_parts if p)
        apply = raw.get("careers_url") or raw.get("url") or ""
        jobs.append(
            Job(
                job_id=f"recruitee:{raw.get('id')}",
                title=(raw.get("title") or "").strip(),
                company=name,
                location=location,
                country=infer_country(location, loc.get("country_code") if isinstance(loc, dict) else None),
                remote=is_remote(location) or bool(raw.get("remote")),
                ats="recruitee",
                source="company-career-page",
                posted_at=parse_dt(raw.get("published_at") or raw.get("created_at")),
                description=strip_html(raw.get("description") or raw.get("requirements")),
                apply_url=apply,
                original_url=apply,
                extra={"board": board},
            )
        )
    return jobs
