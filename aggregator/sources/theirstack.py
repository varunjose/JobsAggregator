from __future__ import annotations

import os
from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import post_json
from aggregator.models import Job, utcnow
from aggregator.textutil import detect_ats_from_url, parse_dt, strip_html

API_URL = "https://api.theirstack.com/v1/jobs/search"

DEFAULT_TITLES = [
    "Software Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "LLM Engineer",
    "Data Engineer",
    "Python Developer",
    "Data Scientist",
    "Research Engineer",
    "Applied Scientist",
]


async def fetch_theirstack(client: httpx.AsyncClient, settings: dict[str, Any]) -> list[Job]:
    token = os.getenv("THEIRSTACK_API_KEY", "").strip()
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    limit = int(settings.get("limit") or 50)
    max_pages = int(settings.get("max_pages") or 20)
    max_jobs = int(settings.get("max_jobs") or 800)
    titles = settings.get("job_title_or") or DEFAULT_TITLES
    jobs: list[Job] = []
    for page in range(max_pages):
        payload = {
            "posted_at_max_age_days": int(settings.get("posted_at_max_age_days") or 1),
            "job_country_code_or": ["US"],
            "job_title_or": titles,
            "limit": limit,
            "page": page,
        }
        try:
            data = await post_json(client, API_URL, payload, headers=headers)
        except Exception:
            break
        if not data:
            break
        rows = data.get("data") or data.get("jobs") or []
        if not rows:
            break
        for raw in rows:
            jobs.append(_to_job(raw))
            if len(jobs) >= max_jobs:
                return jobs
        if len(rows) < limit:
            break
    return jobs


def _to_job(raw: dict[str, Any]) -> Job:
    company_obj = raw.get("company_object") or {}
    company = company_obj.get("name") or raw.get("company") or "Unknown"
    location = (
        raw.get("long_location")
        or raw.get("short_location")
        or raw.get("location")
        or ""
    )
    url = raw.get("final_url") or raw.get("url") or raw.get("source_url") or ""
    source_url = raw.get("source_url") or url
    ats = detect_ats_from_url(url) or detect_ats_from_url(source_url)
    country = raw.get("country_code") or infer_country(location, raw.get("country"))
    return Job(
        job_id=f"theirstack:{raw.get('id')}",
        title=(raw.get("job_title") or raw.get("normalized_title") or "").strip(),
        company=company,
        location=location,
        country=country if isinstance(country, str) else infer_country(location),
        remote=bool(raw.get("remote")) or is_remote(location),
        ats=ats if ats != "unknown" else "theirstack",
        source="theirstack",
        posted_at=parse_dt(raw.get("date_posted") or raw.get("date_reposted")),
        discovered_at=parse_dt(raw.get("discovered_at")) or utcnow(),
        description=strip_html(raw.get("description")),
        salary_min=_num(raw.get("min_annual_salary_usd") or raw.get("min_annual_salary")),
        salary_max=_num(raw.get("max_annual_salary_usd") or raw.get("max_annual_salary")),
        salary_currency=raw.get("salary_currency") or "USD",
        apply_url=url,
        original_url=source_url,
        extra={"source_url": source_url, "final_url": raw.get("final_url")},
    )


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
