from __future__ import annotations

import os
from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json, post_json
from aggregator.models import Job
from aggregator.textutil import detect_ats_from_url, parse_dt, strip_html

SEARCH_URLS = [
    "https://api.jobspipe.dev/v1/jobs/search",
    "https://api.jobspipe.com/v1/jobs/search",
]


async def fetch_jobspipe(client: httpx.AsyncClient, settings: dict[str, Any]) -> list[Job]:
    key = os.getenv("JOBSPIPE_API_KEY", "").strip()
    if not key:
        return []
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-API-Key": key,
    }
    payload = {
        "country": "US",
        "posted_within_hours": 24,
        "keywords": settings.get("keywords")
        or ["software engineer", "machine learning", "ai engineer", "data engineer"],
        "limit": int(settings.get("max_jobs") or 400),
    }
    data = None
    for url in SEARCH_URLS:
        try:
            data = await post_json(client, url, payload, headers=headers)
            if data:
                break
        except Exception:
            try:
                data = await get_json(client, url, params={"country": "US", "limit": payload["limit"]}, headers=headers)
                if data:
                    break
            except Exception:
                continue
    if not data:
        return []
    rows = data.get("jobs") or data.get("data") or data.get("results") or []
    if isinstance(data, list):
        rows = data
    jobs = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        location = raw.get("location") or ""
        url = raw.get("apply_url") or raw.get("url") or ""
        jobs.append(
            Job(
                job_id=f"jobspipe:{raw.get('id') or raw.get('job_id')}",
                title=(raw.get("title") or "").strip(),
                company=raw.get("company") or raw.get("company_name") or "Unknown",
                location=str(location),
                country=infer_country(str(location), raw.get("country") or "US"),
                remote=is_remote(str(location)) or bool(raw.get("remote")),
                ats=raw.get("ats") or detect_ats_from_url(url),
                source="jobspipe",
                posted_at=parse_dt(raw.get("posted_at") or raw.get("published_at")),
                description=strip_html(raw.get("description")),
                salary_min=_num(raw.get("salary_min")),
                salary_max=_num(raw.get("salary_max")),
                apply_url=url,
                original_url=url,
            )
        )
    return jobs[: int(settings.get("max_jobs") or 400)]


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
