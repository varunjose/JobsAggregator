from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_bamboohr(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    url = f"https://{board}.bamboohr.com/careers/list"
    try:
        data = await get_json(client, url)
    except Exception:
        return []
    listings = []
    if isinstance(data, dict):
        listings = data.get("result") or data.get("meta") or data.get("listings") or []
        if isinstance(data.get("result"), dict):
            listings = data["result"].get("listings") or data["result"].get("jobs") or []
    if isinstance(data, list):
        listings = data
    jobs = []
    for raw in listings or []:
        if not isinstance(raw, dict):
            continue
        location = raw.get("location") or raw.get("atsLocation") or ""
        if isinstance(location, dict):
            location = ", ".join(
                str(p) for p in [location.get("city"), location.get("state"), location.get("country")] if p
            )
        job_id = raw.get("id") or raw.get("jobOpeningId") or raw.get("jobId")
        apply = raw.get("jobOpeningShareUrl") or f"https://{board}.bamboohr.com/careers/{job_id}"
        jobs.append(
            Job(
                job_id=f"bamboohr:{job_id}",
                title=(raw.get("jobOpeningName") or raw.get("name") or raw.get("title") or "").strip(),
                company=name,
                location=str(location),
                country=infer_country(str(location)),
                remote=is_remote(str(location)),
                ats="bamboohr",
                source="company-career-page",
                posted_at=parse_dt(raw.get("datePosted") or raw.get("postedDate")),
                description=strip_html(raw.get("description") or ""),
                apply_url=apply,
                original_url=apply,
                extra={"board": board},
            )
        )
    return jobs
