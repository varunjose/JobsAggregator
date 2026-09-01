import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from app.services.sync_service import SyncAlreadyRunning, sync_all

logger = logging.getLogger(__name__)


def _scheduled_sync(settings: Settings) -> None:
    try:
        summaries = sync_all(settings=settings)
        failed = [summary for summary in summaries if summary.status == "failed"]
        if failed:
            logger.error("Scheduled sync completed with %d failed sources", len(failed))
        else:
            logger.info("Scheduled sync completed for %d sources", len(summaries))
    except SyncAlreadyRunning:
        logger.info("Skipped scheduled sync because another sync is active")
    except Exception:
        logger.exception("Scheduled sync failed")


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    next_run_time = None
    if settings.sync_on_startup:
        next_run_time = datetime.now(UTC) + timedelta(seconds=10)
    job_options = {
        "trigger": "interval",
        "minutes": settings.sync_interval_minutes,
        "kwargs": {"settings": settings},
        "id": "job-market-sync",
        "name": "Sync job sources",
        "replace_existing": True,
        "coalesce": True,
        "max_instances": 1,
    }
    if next_run_time:
        job_options["next_run_time"] = next_run_time
    scheduler.add_job(
        _scheduled_sync,
        **job_options,
    )
    return scheduler
