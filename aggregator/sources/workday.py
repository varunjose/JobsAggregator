from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import post_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_workday(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    tenant = company.get("tenant")
    site = company.get("site")
    shard = company.get("shard")
    name = company["name"]
    if not (tenant and site and shard):
        return []
    endpoint = (
        f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    )
    jobs: list[Job] = []
    offset = 0
    limit = 20
    while True:
        payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
        try:
            data = await post_json(client, endpoint, payload)
        except Exception:
            break
        if not data:
            break
        postings = data.get("jobPostings") or []
        if not postings:
            break
        for raw in postings:
            location = raw.get("locationsText") or raw.get("bulletFields") or ""
            if isinstance(location, list):
                location = ", ".join(str(x) for x in location)
            path = raw.get("externalPath") or ""
            apply = ""
            if path:
                apply = f"https://{tenant}.{shard}.myworkdayjobs.com/{site}{path}"
            jobs.append(
                Job(
                    job_id=f"workday:{tenant}:{raw.get('bulletFields') or raw.get('title')}:{raw.get('postedOn')}",
                    title=(raw.get("title") or "").strip(),
                    company=name,
                    location=str(location),
                    country=infer_country(str(location)),
                    remote=is_remote(str(location)),
                    ats="workday",
                    source="company-career-page",
                    posted_at=parse_dt(raw.get("postedOn") or raw.get("firstPosted")),
                    description=strip_html(raw.get("jobDescription") or ""),
                    apply_url=apply,
                    original_url=apply,
                    extra={"tenant": tenant, "site": site},
                )
            )
        total = (data.get("total") or 0)
        offset += limit
        if offset >= min(total or 0, 400) or len(postings) < limit:
            break
    return jobs
