from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from aggregator.geo import infer_country, is_remote
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


async def fetch_personio(client: httpx.AsyncClient, company: dict[str, Any]) -> list[Job]:
    board = company["board"]
    name = company["name"]
    urls = [
        f"https://{board}.jobs.personio.com/xml",
        f"https://{board}.jobs.personio.de/xml",
    ]
    xml_text = None
    for url in urls:
        try:
            resp = await client.get(url, headers={"Accept": "application/xml, text/xml"})
            body = (resp.text or "").lower()
            if resp.status_code == 200 and ("<position" in body or "<workzag" in body):
                xml_text = resp.text
                break
        except Exception:
            continue
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    jobs = []
    for pos in root.findall(".//position"):
        title = (pos.findtext("name") or "").strip()
        office = pos.findtext("office") or ""
        city = pos.findtext(".//city") or office
        country = pos.findtext(".//country") or ""
        location = ", ".join(p for p in [city, country] if p)
        job_id = pos.findtext("id") or title
        apply = pos.findtext("recruitingUrl") or pos.findtext("url") or ""
        desc = " ".join(
            filter(None, [pos.findtext("jobDescription"), pos.findtext("employmentType")])
        )
        jobs.append(
            Job(
                job_id=f"personio:{job_id}",
                title=title,
                company=name,
                location=location,
                country=infer_country(location, country),
                remote=is_remote(location),
                ats="personio",
                source="company-career-page",
                posted_at=parse_dt(pos.findtext("createdAt")),
                description=strip_html(desc),
                apply_url=apply,
                original_url=apply,
                extra={"board": board},
            )
        )
    return jobs
