from __future__ import annotations

from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.http import get_json
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_ashby(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    try:
        data = await get_json(client, url, params={"includeCompensation": "true"})
    except Exception:
        return []
    if not data:
        return []
    jobs = []
    for raw in data.get("jobs") or []:
        if raw.get("isListed") is False:
            continue
        location = raw.get("location") or ""
        apply = raw.get("jobUrl") or raw.get("applyUrl") or ""
        comp = raw.get("compensation") or {}
        salary_min = salary_max = currency = None
        if isinstance(comp, dict):
            salary_min = _num(comp.get("minValue") or comp.get("min"))
            salary_max = _num(comp.get("maxValue") or comp.get("max"))
            currency = comp.get("currency")
        summary = raw.get("compensation") if isinstance(raw.get("compensation"), str) else None
        jobs.append(
            Job(
                job_id=f"ashby:{raw.get('id')}",
                title=(raw.get("title") or "").strip(),
                company=name,
                location=location,
                country=infer_country(location),
                remote=is_remote(location) or bool(raw.get("isRemote")),
                ats="ashby",
                source="company-career-page",
                posted_at=parse_dt(raw.get("publishedAt") or raw.get("publishedDate")),
                description=strip_html(raw.get("descriptionHtml") or raw.get("descriptionPlain") or ""),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                apply_url=apply,
                original_url=apply,
                department=raw.get("department") or raw.get("team"),
                extra={"board": board, "compensation_text": summary},
            )
        )
    return jobs


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
