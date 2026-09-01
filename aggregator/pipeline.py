from __future__ import annotations

import asyncio
import json
import logging
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from aggregator.config import Settings, load_settings
from aggregator.dedupe import dedupe, title_matches
from aggregator.geo import is_us_job
from aggregator.http import client as make_client
from aggregator.models import Job
from aggregator.notify import notify
from aggregator.score import load_resume_tokens, score_job
from aggregator.sources import ATS_FETCHERS, fetch_coresignal, fetch_jobspipe, fetch_theirstack
from aggregator.store import iso_now, load_seen, save_seen, write_outputs

log = logging.getLogger("aggregator")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


async def ingest(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    companies = json.loads(settings.companies_path.read_text())
    stats: dict[str, Any] = {
        "started_at": iso_now(),
        "companies": len(companies),
        "source_counts": {},
        "errors": [],
        "skipped_no_key": [],
    }
    buckets: dict[str, list[Job]] = defaultdict(list)

    timeout = float((settings.ats or {}).get("timeout_seconds") or 25)
    async with make_client(timeout=timeout, browser=True) as http:
        if settings.enable_theirstack:
            try:
                ts_jobs = await fetch_theirstack(http, settings.theirstack)
                buckets["theirstack"] = ts_jobs
                if not ts_jobs:
                    stats["skipped_no_key"].append("theirstack (no key or empty)")
            except Exception as exc:
                stats["errors"].append(f"theirstack: {exc}")
                log.exception("TheirStack failed")

        if settings.enable_coresignal:
            try:
                cs_jobs = await fetch_coresignal(http, settings.coresignal)
                buckets["coresignal"] = cs_jobs
                if not cs_jobs:
                    stats["skipped_no_key"].append("coresignal (no key or empty)")
            except Exception as exc:
                stats["errors"].append(f"coresignal: {exc}")
                log.exception("Coresignal failed")

        if settings.enable_jobspipe:
            try:
                jp_jobs = await fetch_jobspipe(http, settings.jobspipe)
                buckets["jobspipe"] = jp_jobs
                if not jp_jobs:
                    stats["skipped_no_key"].append("jobspipe (no key or empty)")
            except Exception as exc:
                stats["errors"].append(f"jobspipe: {exc}")
                log.exception("JobsPipe failed")

        if settings.enable_ats:
            ats_jobs, ats_errors = await _fetch_all_ats(http, companies, settings)
            buckets["ats"] = ats_jobs
            stats["errors"].extend(ats_errors)

    stats["source_counts"] = {k: len(v) for k, v in buckets.items()}
    combined = [job for group in buckets.values() for job in group]
    combined = [job for job in combined if job.title]
    combined = dedupe(combined)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.posted_within_hours)
    seen_path = settings.output_dir / "seen.json"
    seen = load_seen(seen_path)
    now_iso = iso_now()

    filtered: list[Job] = []
    for job in combined:
        if not is_us_job(job.location, job.country, settings.include_remote):
            continue
        if not title_matches(job.title, settings.title_keywords):
            continue
        first_seen = job.job_id not in seen
        if first_seen:
            seen[job.job_id] = now_iso
        if job.posted_at is None:
            if not settings.include_missing_posted_at:
                continue
            if not first_seen:
                continue
        elif job.posted_at < cutoff:
            continue
        filtered.append(job)

    resume_tokens = load_resume_tokens(settings.resume_file)
    for job in filtered:
        if not job.country:
            job.country = "US"
        score_job(job, resume_tokens)

    filtered.sort(key=lambda j: (j.posted_at is not None, j.posted_at or j.discovered_at, j.score), reverse=True)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    seen = {
        k: v
        for k, v in seen.items()
        if _parse_iso(v) and _parse_iso(v) > stale_cutoff
    }
    save_seen(seen_path, seen)

    meta = {
        **stats,
        "finished_at": iso_now(),
        "raw_jobs": len(combined),
        "kept_jobs": len(filtered),
        "posted_within_hours": settings.posted_within_hours,
        "ats_breakdown": dict(Counter(j.ats for j in filtered)),
        "layer_breakdown": dict(Counter(j.source for j in filtered)),
        "resume_file": str(settings.resume_file.name),
    }
    write_outputs(filtered, meta, settings.output_dir, settings.dashboard_dir, settings.description_chars)
    await notify(filtered, meta)
    log.info("Kept %s US jobs from %s raw postings", len(filtered), len(combined))
    return meta


async def _fetch_all_ats(http, companies: list[dict[str, Any]], settings: Settings) -> tuple[list[Job], list[str]]:
    concurrency = int((settings.ats or {}).get("concurrency") or 10)
    sem = asyncio.Semaphore(concurrency)
    errors: list[str] = []
    jobs: list[Job] = []

    async def one(company: dict[str, Any]) -> list[Job]:
        ats = company.get("ats")
        fetcher = ATS_FETCHERS.get(ats)
        if not fetcher:
            return []
        async with sem:
            try:
                return await fetcher(http, company)
            except Exception as exc:
                errors.append(f"{ats}:{company.get('name')}: {exc}")
                log.debug("%s", traceback.format_exc())
                return []

    results = await asyncio.gather(*(one(c) for c in companies))
    for batch in results:
        jobs.extend(batch)
    return jobs, errors[:50]


def _parse_iso(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_ingest() -> dict[str, Any]:
    setup_logging()
    return asyncio.run(ingest())
