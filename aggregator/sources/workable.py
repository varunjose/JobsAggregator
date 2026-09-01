from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json, post_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_workable(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    jobs: list[Job] = []
    url = f"https://apply.workable.com/api/v1/widget/accounts/{board}"
    try:
        data = await get_json(client, url)
    except Exception:
        data = None
    listings = []
    if isinstance(data, dict):
        listings = data.get("jobs") or data.get("results") or []
    if not listings:
        jobs.extend(await _workable_search(client, board, name))
        return jobs
    for raw in listings:
        location = raw.get("location") or ""
        if isinstance(location, dict):
            location = ", ".join(
                p for p in [location.get("city"), location.get("region"), location.get("country")] if p
            )
        apply = raw.get("url") or raw.get("application_url") or ""
        jobs.append(
            Job(
                job_id=f"workable:{raw.get('id') or raw.get('shortcode')}",
                title=(raw.get("title") or "").strip(),
                company=data.get("name") if isinstance(data, dict) and data.get("name") else name,
                location=str(location),
                country=infer_country(str(location), (raw.get("country") if isinstance(raw.get("country"), str) else None)),
                remote=is_remote(str(location)) or bool(raw.get("telecommuting")),
                ats="workable",
                source="company-career-page",
                posted_at=parse_dt(raw.get("published_on") or raw.get("created_at")),
                description=strip_html(raw.get("description")),
                apply_url=apply,
                original_url=apply,
                extra={"board": board},
            )
        )
    return jobs


async def _workable_search(client: httpx.AsyncClient, board: str, name: str) -> list[Job]:
    url = f"https://apply.workable.com/api/v2/accounts/{board}/jobs"
    try:
        data = await post_json(client, url, {"query": "", "location": [], "department": [], "workType": []})
    except Exception:
        return []
    jobs = []
    for raw in (data or {}).get("results") or []:
        loc = raw.get("location") or {}
        location = loc.get("locationStr") or ", ".join(
            p for p in [loc.get("city"), loc.get("regionCode") or loc.get("countryName")] if p
        )
        apply = raw.get("applicationUrl") or f"https://apply.workable.com/{board}/j/{raw.get('shortcode')}/"
        jobs.append(
            Job(
                job_id=f"workable:{raw.get('id') or raw.get('shortcode')}",
                title=(raw.get("title") or "").strip(),
                company=name,
                location=location,
                country=infer_country(location, loc.get("countryCode")),
                remote=is_remote(location) or (raw.get("workplace") or "").lower() == "remote",
                ats="workable",
                source="company-career-page",
                posted_at=parse_dt(raw.get("published")),
                description="",
                apply_url=apply,
                original_url=apply,
                extra={"board": board},
            )
        )
    return jobs
