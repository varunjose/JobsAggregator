from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import Settings
from app.connectors.base import NormalizedJob
from app.database import SessionLocal
from app.main import app
from app.models import Job
from app.services.sync_service import _upsert_job


def sample_job(provider: str, source_key: str, external_id: str, url: str) -> NormalizedJob:
    return NormalizedJob(
        provider=provider,
        source_key=source_key,
        external_id=external_id,
        title="AI Engineer",
        company="Acme",
        location="New York, NY",
        country_code="US",
        description="Build Python LLM and RAG services on AWS. Requires 2 years of experience.",
        posted_at=datetime.now(UTC),
        posted_at_confidence="source_posted_at",
        discovered_at=datetime.now(UTC),
        apply_url=f"{url}/apply",
        original_url=url,
        ats="greenhouse",
        raw_payload={"id": external_id},
    )


def test_sync_merges_duplicate_sources_and_api_returns_provenance():
    settings = Settings(sync_scheduler_enabled=False)
    with SessionLocal() as session:
        first = sample_job("theirstack", "theirstack:us", "ts-1", "https://acme.com/jobs/1")
        second = sample_job("greenhouse", "greenhouse:acme", "gh-1", "https://acme.com/jobs/1")
        assert _upsert_job(session, first, settings) == "created"
        assert _upsert_job(session, second, settings) == "updated"
        session.commit()
        assert session.query(Job).count() == 1

    with TestClient(app) as client:
        response = client.get("/api/jobs?hours=24&freshness=posted")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert len(payload["items"][0]["sources"]) == 2
        assert payload["items"][0]["fit_score"] >= 70
        assert payload["items"][0]["posted_at"].endswith("Z")


def test_health_and_dashboard():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "JobSignal" in dashboard.text
