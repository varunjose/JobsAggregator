import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.database import get_db, init_db
from app.models import Job
from app.scheduler import build_scheduler
from app.schemas import JobListOut, JobOut, SyncRunOut
from app.services.job_service import (
    category_counts,
    job_stats,
    list_jobs,
    recent_sync_runs,
)
from app.services.sync_service import (
    SyncAlreadyRunning,
    configured_sources,
    sync_all,
)

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    scheduler = None
    if settings.sync_scheduler_enabled:
        scheduler = build_scheduler(settings)
        scheduler.start()
        logger.info(
            "In-process sync scheduler started with a %d-minute interval",
            settings.sync_interval_minutes,
        )
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Jobs Aggregator API",
    version=__version__,
    description="Normalized and deduplicated job data from broad-market and direct ATS feeds.",
    lifespan=lifespan,
)

static_directory = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=static_directory), name="assets")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(static_directory / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "name": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "default_freshness_hours": settings.posted_within_hours,
        "sync_interval_minutes": settings.sync_interval_minutes,
        "us_only": settings.us_only,
        "target_titles": settings.target_title_list,
        "configured_source_count": len(configured_sources(settings)),
    }


@app.get("/api/jobs", response_model=JobListOut)
def jobs(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=80),
    state: str | None = Query(default=None, min_length=2, max_length=2),
    remote: bool | None = None,
    ats: str | None = Query(default=None, max_length=80),
    visa_signal: Literal["available", "not_available", "unknown"] | None = None,
    min_fit: int | None = Query(default=None, ge=0, le=100),
    min_salary: float | None = Query(default=None, ge=0),
    hours: int | None = Query(default=24, ge=1, le=24 * 365),
    freshness: Literal["posted", "discovered", "either"] = "posted",
    sort: Literal["newest", "fit", "salary"] = "newest",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobListOut:
    return list_jobs(
        db,
        q=q,
        category=category,
        state=state,
        remote=remote,
        ats=ats,
        visa_signal=visa_signal,
        min_fit=min_fit,
        min_salary=min_salary,
        hours=hours,
        freshness=freshness,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def job_detail(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)


@app.get("/api/stats")
def stats(
    hours: int = Query(default=24, ge=1, le=24 * 365),
    db: Session = Depends(get_db),
) -> dict:
    result = job_stats(db, hours=hours)
    result["categories"] = category_counts(db, hours=hours)
    return result


@app.get("/api/sources")
def sources(db: Session = Depends(get_db)) -> dict:
    configured = configured_sources(settings)
    latest_by_source = {}
    for run in recent_sync_runs(db, limit=100):
        latest_by_source.setdefault(run.source_key, SyncRunOut.model_validate(run).model_dump())
    for source in configured:
        source["last_run"] = latest_by_source.get(source["source_key"])
    return {"items": configured, "sync_interval_minutes": settings.sync_interval_minutes}


@app.get("/api/sync/runs", response_model=list[SyncRunOut])
def sync_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SyncRunOut]:
    return [SyncRunOut.model_validate(run) for run in recent_sync_runs(db, limit=limit)]


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if settings.admin_api_key:
        if not x_admin_key or not hmac.compare_digest(x_admin_key, settings.admin_api_key):
            raise HTTPException(status_code=401, detail="A valid X-Admin-Key header is required")
    elif settings.is_production:
        raise HTTPException(
            status_code=503,
            detail="Manual sync is disabled until ADMIN_API_KEY is configured",
        )


def _background_sync(source: str | None) -> None:
    try:
        sync_all(settings=settings, source_filter=source)
    except SyncAlreadyRunning:
        logger.info("Manual sync request skipped because a sync is already active")
    except Exception:
        logger.exception("Manual background sync failed")


@app.post("/api/sync", status_code=202, dependencies=[Depends(require_admin)])
def trigger_sync(
    background_tasks: BackgroundTasks,
    source: str | None = Query(default=None, max_length=200),
) -> dict:
    if not any(item.get("configured") for item in configured_sources(settings)):
        raise HTTPException(
            status_code=409,
            detail=(
                "No sources are configured. Set THEIRSTACK_API_KEY or enable a direct ATS "
                "source in config/sources.yaml."
            ),
        )
    background_tasks.add_task(_background_sync, source)
    return {"status": "accepted", "source": source or "all"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
