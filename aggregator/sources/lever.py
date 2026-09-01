from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_lever(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    url = f"https://api.lever.co/v0/postings/{board}"
    try:
        data = await get_json(client, url, params={"mode": "json"})
    except Exception:
        return []
    if not data or not isinstance(data, list):
        return []
    jobs = []
    for raw in data:
        cats = raw.get("categories") or {}
        location = cats.get("location") or ""
        if cats.get("allLocations"):
            location = ", ".join(cats.get("allLocations") or [location])
        workplace = (raw.get("workplaceType") or "").lower()
        apply = raw.get("applyUrl") or raw.get("hostedUrl") or ""
        jobs.append(
            Job(
                job_id=f"lever:{raw.get('id')}",
                title=(raw.get("text") or "").strip(),
                company=name,
                location=location,
                country=infer_country(location),
                remote=is_remote(location) or workplace == "remote",
                ats="lever",
                source="company-career-page",
                posted_at=parse_dt(raw.get("createdAt")),
                description=strip_html(raw.get("descriptionPlain") or raw.get("description")),
                apply_url=apply,
                original_url=raw.get("hostedUrl") or apply,
                department=cats.get("department"),
                extra={"board": board, "commitment": cats.get("commitment")},
            )
        )
    return jobs
