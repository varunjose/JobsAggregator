from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_smartrecruiters(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    jobs: list[Job] = []
    offset = 0
    limit = 100
    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{board}/postings"
        try:
            data = await get_json(client, url, params={"limit": limit, "offset": offset})
        except Exception:
            break
        if not data:
            break
        content = data.get("content") or data.get("postings") or []
        if not content:
            break
        for raw in content:
            loc = raw.get("location") or {}
            city = loc.get("city") or ""
            region = loc.get("region") or loc.get("regionCode") or ""
            country = loc.get("countryCode") or loc.get("country") or ""
            location = ", ".join(p for p in [city, region, country] if p)
            apply = raw.get("applyUrl") or raw.get("ref") or ""
            if not apply and raw.get("id"):
                apply = f"https://jobs.smartrecruiters.com/{board}/{raw.get('id')}"
            jobs.append(
                Job(
                    job_id=f"smartrecruiters:{raw.get('id') or raw.get('uuid')}",
                    title=(raw.get("name") or raw.get("title") or "").strip(),
                    company=name,
                    location=location,
                    country=infer_country(location, country),
                    remote=is_remote(location) or (raw.get("locationType") or "").lower() == "remote",
                    ats="smartrecruiters",
                    source="company-career-page",
                    posted_at=parse_dt(raw.get("releasedDate") or raw.get("createdOn")),
                    description=strip_html(raw.get("jobAd") or ""),
                    apply_url=apply,
                    original_url=apply,
                    department=(raw.get("department") or {}).get("label") if isinstance(raw.get("department"), dict) else raw.get("department"),
                    extra={"board": board},
                )
            )
        if len(content) < limit:
            break
        offset += limit
        if offset > 2000:
            break
    return jobs
