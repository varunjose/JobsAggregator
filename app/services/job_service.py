from datetime import timedelta

from sqlalchemy import String, and_, cast, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Job, SyncRun
from app.schemas import JobListOut, JobOut
from app.services.enrichment import utcnow


def list_jobs(
    session: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    state: str | None = None,
    remote: bool | None = None,
    ats: str | None = None,
    visa_signal: str | None = None,
    min_fit: int | None = None,
    min_salary: float | None = None,
    hours: int | None = 24,
    freshness: str = "posted",
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> JobListOut:
    conditions = [Job.is_active.is_(True)]
    if q:
        pattern = f"%{q.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Job.title).like(pattern),
                func.lower(Job.company).like(pattern),
                func.lower(func.coalesce(Job.location, "")).like(pattern),
                func.lower(func.coalesce(Job.description, "")).like(pattern),
                func.lower(cast(Job.skills, String)).like(pattern),
            )
        )
    if category:
        conditions.append(Job.category == category)
    if state:
        conditions.append(func.upper(Job.state) == state.upper())
    if remote is not None:
        conditions.append(Job.remote.is_(remote))
    if ats:
        conditions.append(func.lower(Job.ats) == ats.lower())
    if visa_signal:
        conditions.append(Job.visa_signal == visa_signal)
    if min_fit is not None:
        conditions.append(Job.fit_score >= min_fit)
    if min_salary is not None:
        conditions.append(func.coalesce(Job.salary_max, Job.salary_min) >= min_salary)

    if hours is not None:
        cutoff = utcnow() - timedelta(hours=hours)
        if freshness == "posted":
            conditions.append(and_(Job.posted_at.is_not(None), Job.posted_at >= cutoff))
        elif freshness == "discovered":
            conditions.append(Job.first_seen_at >= cutoff)
        elif freshness == "either":
            conditions.append(
                or_(
                    and_(Job.posted_at.is_not(None), Job.posted_at >= cutoff),
                    Job.first_seen_at >= cutoff,
                )
            )
        else:
            raise ValueError("freshness must be posted, discovered, or either")

    if sort == "fit":
        order_by = (desc(Job.fit_score), desc(func.coalesce(Job.posted_at, Job.first_seen_at)))
    elif sort == "salary":
        order_by = (
            desc(func.coalesce(Job.salary_max, Job.salary_min, 0)),
            desc(func.coalesce(Job.posted_at, Job.first_seen_at)),
        )
    else:
        order_by = (desc(func.coalesce(Job.posted_at, Job.first_seen_at)), desc(Job.fit_score))

    total = session.scalar(select(func.count(Job.id)).where(*conditions)) or 0
    jobs = session.scalars(
        select(Job)
        .options(selectinload(Job.sources))
        .where(*conditions)
        .order_by(*order_by)
        .offset(offset)
        .limit(limit)
    ).all()
    return JobListOut(
        items=[JobOut.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
        generated_at=utcnow(),
    )


def job_stats(session: Session, hours: int = 24) -> dict:
    cutoff = utcnow() - timedelta(hours=hours)
    active = Job.is_active.is_(True)
    fresh = and_(active, Job.posted_at.is_not(None), Job.posted_at >= cutoff)
    return {
        "active_jobs": session.scalar(select(func.count(Job.id)).where(active)) or 0,
        "fresh_jobs": session.scalar(select(func.count(Job.id)).where(fresh)) or 0,
        "companies": session.scalar(select(func.count(func.distinct(Job.company))).where(fresh))
        or 0,
        "remote_jobs": session.scalar(select(func.count(Job.id)).where(fresh, Job.remote.is_(True)))
        or 0,
        "high_fit_jobs": session.scalar(
            select(func.count(Job.id)).where(fresh, Job.fit_score >= 70)
        )
        or 0,
        "hours": hours,
        "generated_at": utcnow(),
    }


def category_counts(session: Session, hours: int = 24) -> list[dict]:
    cutoff = utcnow() - timedelta(hours=hours)
    rows = session.execute(
        select(Job.category, func.count(Job.id))
        .where(Job.is_active.is_(True), Job.posted_at >= cutoff)
        .group_by(Job.category)
        .order_by(desc(func.count(Job.id)))
    ).all()
    return [{"category": category, "count": count} for category, count in rows]


def recent_sync_runs(session: Session, limit: int = 20) -> list[SyncRun]:
    return list(
        session.scalars(select(SyncRun).order_by(desc(SyncRun.started_at)).limit(limit)).all()
    )
