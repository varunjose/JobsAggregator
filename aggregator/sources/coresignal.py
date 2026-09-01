from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json, post_json
from aggregator.models import Job
from aggregator.textutil import detect_ats_from_url, parse_dt, strip_html

SEARCH_URL = "https://api.coresignal.com/cdapi/v2/job_base/search/filter"
COLLECT_URL = "https://api.coresignal.com/cdapi/v2/job_base/collect/{job_id}"


async def fetch_coresignal(client: httpx.AsyncClient, settings: dict[str, Any]) -> list[Job]:
    key = os.getenv("CORESIGNAL_API_KEY", "").strip()
    if not key:
        return []
    headers = {"apikey": key, "Content-Type": "application/json", "accept": "application/json"}
    since = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    titles = settings.get("titles") or [
        "Software Engineer",
        "Machine Learning Engineer",
        "AI Engineer",
        "Data Engineer",
    ]
    ids: list[Any] = []
    for title in titles:
        payload = {
            "title": title,
            "country": "United States",
            "application_active": True,
            "created_at_gte": since,
        }
        try:
            data = await post_json(client, SEARCH_URL, payload, headers=headers)
        except Exception:
            continue
        batch = _extract_ids(data)
        ids.extend(batch)
        if len(ids) >= int(settings.get("max_ids") or 200):
            break
    unique_ids = list(dict.fromkeys(str(i) for i in ids))[: int(settings.get("max_ids") or 200)]
    collect_cap = int(settings.get("max_collect") or 80)
    jobs: list[Job] = []
    for job_id in unique_ids[:collect_cap]:
        try:
            raw = await get_json(client, COLLECT_URL.format(job_id=job_id), headers=headers)
        except Exception:
            continue
        if isinstance(raw, dict):
            jobs.append(_to_job(raw, job_id))
    return jobs


def _extract_ids(data: Any) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return [row.get("id") or row.get("job_id") for row in data if row.get("id") or row.get("job_id")]
        return data
    if isinstance(data, dict):
        for key in ("data", "results", "ids", "job_ids"):
            if key in data:
                return _extract_ids(data[key])
    return []


def _to_job(raw: dict[str, Any], fallback_id: str) -> Job:
    location = raw.get("location") or raw.get("city") or ""
    if isinstance(location, dict):
        location = ", ".join(
            str(p) for p in [location.get("city"), location.get("state"), location.get("country")] if p
        )
    url = raw.get("external_url") or raw.get("url") or raw.get("application_url") or ""
    return Job(
        job_id=f"coresignal:{raw.get('id') or fallback_id}",
        title=(raw.get("title") or "").strip(),
        company=raw.get("company_name") or raw.get("company") or "Unknown",
        location=str(location),
        country=infer_country(str(location), raw.get("country")),
        remote=is_remote(str(location)) or bool(raw.get("remote")),
        ats=detect_ats_from_url(url),
        source="coresignal",
        posted_at=parse_dt(raw.get("created") or raw.get("created_at") or raw.get("posted_at")),
        description=strip_html(raw.get("description") or raw.get("description_original")),
        salary_min=_num(raw.get("salary_min") or raw.get("min_salary")),
        salary_max=_num(raw.get("salary_max") or raw.get("max_salary")),
        apply_url=url,
        original_url=url,
        extra={"coresignal_id": raw.get("id") or fallback_id},
    )


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
