import logging
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.connectors import CONNECTOR_TYPES
from app.connectors.base import BaseConnector, NormalizedJob, SourceSpec
from app.database import SessionLocal, init_db
from app.models import Job, JobSource, SyncRun
from app.services.dedup import build_dedup_key, dates_compatible
from app.services.enrichment import (
    calculate_fit_score,
    classify_category,
    detect_visa_signal,
    extract_experience,
    extract_skills,
    is_us_job,
    utcnow,
)

logger = logging.getLogger(__name__)
_sync_lock = threading.Lock()


@dataclass
class SyncSummary:
    provider: str
    source_key: str
    status: str
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    deactivated: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class SyncAlreadyRunning(RuntimeError):
    pass


def load_source_specs(settings: Settings) -> list[SourceSpec]:
    specs: list[SourceSpec] = []
    if settings.theirstack_api_key:
        specs.append(SourceSpec(type="theirstack", enabled=True))

    path = Path(settings.source_config_path)
    if path.exists():
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        records = payload.get("sources", []) if isinstance(payload, dict) else []
        for record in records:
            if isinstance(record, dict):
                spec = SourceSpec.model_validate(record)
                if spec.enabled:
                    specs.append(spec)
    return specs


def configured_sources(settings: Settings | None = None) -> list[dict]:
    active_settings = settings or get_settings()
    output = []
    for spec in load_source_specs(active_settings):
        connector_type = CONNECTOR_TYPES.get(spec.type.lower())
        if not connector_type:
            output.append(
                {
                    "provider": spec.type,
                    "source_key": spec.type,
                    "configured": False,
                    "error": "Unsupported connector type",
                }
            )
            continue
        try:
            connector = connector_type(spec, active_settings)
            output.append(
                {
                    "provider": connector.provider,
                    "source_key": connector.source_key,
                    "configured": True,
                    "complete_snapshot": connector.complete_snapshot,
                }
            )
            connector.close()
        except Exception as exc:  # Configuration validation should be visible in the UI.
            output.append(
                {
                    "provider": spec.type,
                    "source_key": spec.type,
                    "configured": False,
                    "error": str(exc),
                }
            )
    return output


def sync_all(
    *,
    settings: Settings | None = None,
    source_filter: str | None = None,
) -> list[SyncSummary]:
    active_settings = settings or get_settings()
    init_db()
    if not _sync_lock.acquire(blocking=False):
        raise SyncAlreadyRunning("A sync is already running")
    try:
        specs = load_source_specs(active_settings)
        summaries = []
        for spec in specs:
            if source_filter and source_filter.lower() not in {
                spec.type.lower(),
                (spec.token or "").lower(),
                (spec.company or "").lower(),
            }:
                continue
            connector_type = CONNECTOR_TYPES.get(spec.type.lower())
            if not connector_type:
                summaries.append(
                    SyncSummary(
                        provider=spec.type,
                        source_key=spec.type,
                        status="failed",
                        error=f"Unsupported connector type: {spec.type}",
                    )
                )
                continue
            connector = connector_type(spec, active_settings)
            try:
                summaries.append(_sync_connector(connector, active_settings))
            finally:
                connector.close()
        if not summaries and source_filter:
            raise ValueError(f"No enabled source matched {source_filter!r}")
        return summaries
    finally:
        _sync_lock.release()


def _sync_connector(connector: BaseConnector, settings: Settings) -> SyncSummary:
    summary = SyncSummary(
        provider=connector.provider,
        source_key=connector.source_key,
        status="running",
    )
    session = SessionLocal()
    run = SyncRun(
        provider=connector.provider,
        source_key=connector.source_key,
        status="running",
    )
    session.add(run)
    session.commit()
    run_id = run.id
    seen_external_ids: set[str] = set()

    try:
        for normalized in connector.fetch():
            summary.fetched += 1
            if settings.us_only and not is_us_job(
                normalized.country_code,
                normalized.location,
            ):
                summary.skipped += 1
                continue
            seen_external_ids.add(normalized.external_id)
            action = _upsert_job(session, normalized, settings)
            if action == "created":
                summary.created += 1
            else:
                summary.updated += 1

        if connector.complete_snapshot and connector.snapshot_complete:
            summary.deactivated = _deactivate_missing(
                session,
                connector.source_key,
                seen_external_ids,
            )
        session.commit()
        summary.status = "completed"
    except Exception as exc:
        session.rollback()
        summary.status = "failed"
        summary.error = str(exc)[:2000]
        logger.exception("Sync failed for %s", connector.source_key)
    finally:
        persisted_run = session.get(SyncRun, run_id)
        if persisted_run:
            persisted_run.status = summary.status
            persisted_run.finished_at = utcnow()
            persisted_run.fetched = summary.fetched
            persisted_run.created = summary.created
            persisted_run.updated = summary.updated
            persisted_run.skipped = summary.skipped
            persisted_run.deactivated = summary.deactivated
            persisted_run.error_message = summary.error
            session.commit()
        session.close()
    return summary


def _upsert_job(session: Session, normalized: NormalizedJob, settings: Settings) -> str:
    now = utcnow()
    dedup_key, fuzzy_key, canonical_url = build_dedup_key(
        company=normalized.company,
        title=normalized.title,
        location=normalized.location,
        original_url=normalized.original_url,
        apply_url=normalized.apply_url,
        external_id=normalized.external_id,
        source_key=normalized.source_key,
    )

    source = session.scalar(
        select(JobSource).where(
            JobSource.source_key == normalized.source_key,
            JobSource.external_id == normalized.external_id,
        )
    )
    if source:
        job = source.job
        action = "updated"
    else:
        job = session.scalar(select(Job).where(Job.dedup_key == dedup_key))
        if not job:
            job = _find_fuzzy_match(session, normalized, fuzzy_key)
        if job:
            action = "updated"
        else:
            job = Job(
                dedup_key=dedup_key,
                fuzzy_key=fuzzy_key,
                title=normalized.title,
                company=normalized.company,
                location=normalized.location,
                country_code=normalized.country_code,
                primary_provider=normalized.provider,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(job)
            session.flush()
            action = "created"

        source = JobSource(
            job_id=job.id,
            provider=normalized.provider,
            source_key=normalized.source_key,
            external_id=normalized.external_id,
            discovered_at=normalized.discovered_at,
        )
        session.add(source)

    _merge_job(job, normalized, settings, canonical_url, now)
    source.provider = normalized.provider
    source.ats = normalized.ats
    source.original_url = normalized.original_url
    source.apply_url = normalized.apply_url
    source.posted_at = normalized.posted_at
    source.last_seen_at = now
    source.is_active = True
    source.raw_payload = normalized.raw_payload
    session.flush()
    return action


def _find_fuzzy_match(
    session: Session,
    normalized: NormalizedJob,
    fuzzy_key: str,
) -> Job | None:
    candidates = session.scalars(select(Job).where(Job.fuzzy_key == fuzzy_key)).all()
    for candidate in candidates:
        if (
            candidate.requisition_id
            and normalized.requisition_id
            and candidate.requisition_id != normalized.requisition_id
        ):
            continue
        if not dates_compatible(candidate.posted_at, normalized.posted_at):
            continue
        # Two same-title openings from one board are not assumed to be duplicates.
        if any(source.source_key == normalized.source_key for source in candidate.sources):
            continue
        return candidate
    return None


def _merge_job(
    job: Job,
    normalized: NormalizedJob,
    settings: Settings,
    canonical_url: str | None,
    now: datetime,
) -> None:
    current_is_broad = job.primary_provider == "theirstack"
    incoming_is_direct = normalized.provider != "theirstack"
    prefer_incoming = current_is_broad and incoming_is_direct

    core_fields = (
        "title",
        "company",
        "company_domain",
        "location",
        "city",
        "state",
        "country_code",
        "workplace_type",
        "employment_type",
        "seniority",
        "department",
        "salary_text",
        "source_updated_at",
        "expires_at",
        "apply_url",
        "original_url",
        "ats",
        "requisition_id",
    )
    for field in core_fields:
        incoming = getattr(normalized, field)
        if incoming is not None and (prefer_incoming or getattr(job, field) in {None, ""}):
            setattr(job, field, incoming)

    if normalized.description and (
        not job.description or len(normalized.description) > len(job.description)
    ):
        job.description = normalized.description
    if normalized.salary_min is not None and (job.salary_min is None or prefer_incoming):
        job.salary_min = normalized.salary_min
        job.salary_currency = normalized.salary_currency
        job.salary_period = normalized.salary_period
    if normalized.salary_max is not None and (job.salary_max is None or prefer_incoming):
        job.salary_max = normalized.salary_max
        job.salary_currency = normalized.salary_currency
        job.salary_period = normalized.salary_period

    if normalized.posted_at and (
        job.posted_at is None or normalized.posted_at < _aware(job.posted_at)
    ):
        job.posted_at = normalized.posted_at
        job.posted_at_confidence = normalized.posted_at_confidence

    job.remote = job.remote or normalized.remote
    job.canonical_url = job.canonical_url or canonical_url
    job.last_seen_at = now
    job.is_active = True
    if prefer_incoming:
        job.primary_provider = normalized.provider

    job.category = classify_category(job.title, job.description)
    job.skills = extract_skills(job.title, job.description)
    job.experience_min, job.experience_max = extract_experience(job.description)
    job.visa_signal = detect_visa_signal(job.description)
    job.fit_score, job.fit_reasons = calculate_fit_score(
        title=job.title,
        location=job.location,
        remote=job.remote,
        skills=job.skills,
        experience_min=job.experience_min,
        target_titles=settings.target_title_list,
        target_skills=settings.target_skill_list,
        preferred_locations=settings.preferred_location_list,
    )


def _deactivate_missing(
    session: Session,
    source_key: str,
    seen_external_ids: set[str],
) -> int:
    records = session.scalars(
        select(JobSource).where(
            JobSource.source_key == source_key,
            JobSource.is_active.is_(True),
        )
    ).all()
    affected_job_ids: set[str] = set()
    count = 0
    for record in records:
        if record.external_id not in seen_external_ids:
            record.is_active = False
            affected_job_ids.add(record.job_id)
            count += 1
    session.flush()
    for job_id in affected_job_ids:
        job = session.get(Job, job_id)
        if job:
            job.is_active = any(source.is_active for source in job.sources)
    return count


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
