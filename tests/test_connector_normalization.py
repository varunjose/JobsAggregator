import json
from datetime import UTC, datetime

import httpx

from app.config import Settings
from app.connectors.ashby import AshbyConnector
from app.connectors.base import SourceSpec
from app.connectors.lever import LeverConnector
from app.connectors.smartrecruiters import SmartRecruitersConnector
from app.connectors.theirstack import TheirStackConnector
from app.connectors.workday import WorkdayConnector

SETTINGS = Settings(sync_scheduler_enabled=False)


def test_theirstack_normalizes_provider_fields():
    connector = TheirStackConnector(SourceSpec(type="theirstack"), SETTINGS)
    job = connector._normalize(
        {
            "id": 42,
            "job_title": "Machine Learning Engineer",
            "company": "Acme AI",
            "job_location": "Remote - US",
            "job_country_code": "US",
            "description": "<p>Python, LLM and RAG.</p>",
            "date_posted": "2026-09-01T10:00:00Z",
            "discovered_at": "2026-09-01T10:05:00Z",
            "final_url": "https://jobs.ashbyhq.com/acme/42",
            "remote": "false",
        }
    )
    connector.close()
    assert job.ats == "ashby"
    assert job.remote is True  # Location is explicitly remote even when the provider flag is false.
    assert job.posted_at == datetime(2026, 9, 1, 10, tzinfo=UTC)


def test_theirstack_fetch_uses_incremental_open_job_filter():
    observed_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_payload.update(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, json={"data": []})

    settings = Settings(
        theirstack_api_key="secret",
        page_size=25,
        max_pages_per_source=1,
        sync_scheduler_enabled=False,
    )
    connector = TheirStackConnector(SourceSpec(type="theirstack"), settings)
    connector.client.close()
    connector.client = httpx.Client(transport=httpx.MockTransport(handler))
    connector.since = datetime(2026, 9, 1, 8, tzinfo=UTC)
    assert list(connector.fetch()) == []
    connector.close()

    assert observed_payload["is_closed"] is False
    assert observed_payload["include_total_results"] is False
    assert observed_payload["discovered_at_gte"] == "2026-09-01T08:00:00+00:00"


def test_lever_and_ashby_normalize_public_records():
    lever = LeverConnector(SourceSpec(type="lever", token="acme", company="Acme"), SETTINGS)
    lever_job = lever._normalize(
        {
            "id": "lever-1",
            "text": "Backend Engineer",
            "categories": {"location": "New York, NY", "commitment": "Full-time"},
            "descriptionPlain": "Build Python APIs.",
            "createdAt": 1788256800000,
            "hostedUrl": "https://jobs.lever.co/acme/lever-1",
            "applyUrl": "https://jobs.lever.co/acme/lever-1/apply",
        }
    )
    lever.close()

    ashby = AshbyConnector(SourceSpec(type="ashby", board="Acme", company="Acme"), SETTINGS)
    ashby_job = ashby._normalize(
        {
            "id": "ashby-1",
            "title": "AI Engineer",
            "location": "San Francisco, CA",
            "descriptionHtml": "<p>Build LLM systems.</p>",
            "publishedAt": "2026-09-01T10:00:00Z",
            "jobUrl": "https://jobs.ashbyhq.com/acme/ashby-1",
            "applyUrl": "https://jobs.ashbyhq.com/acme/ashby-1/application",
        }
    )
    ashby.close()
    assert lever_job.country_code == "US"
    assert lever_job.employment_type == "Full-time"
    assert ashby_job.state == "CA"
    assert ashby_job.posted_at_confidence == "source_published_at"


def test_smartrecruiters_and_workday_normalize_details():
    smart = SmartRecruitersConnector(
        SourceSpec(type="smartrecruiters", token="acme", company="Acme"),
        SETTINGS,
    )
    smart_job = smart._normalize(
        {
            "id": "smart-1",
            "name": "Data Engineer",
            "location": {"city": "Boston", "region": "MA", "country": "US"},
            "jobAd": {
                "publicAdUrl": "https://jobs.smartrecruiters.com/acme/smart-1",
                "sections": {"jobDescription": {"text": "Build data pipelines with Python."}},
            },
            "releasedDate": "2026-09-01T10:00:00Z",
        }
    )
    smart.close()

    workday = WorkdayConnector(
        SourceSpec(
            type="workday",
            company="Acme",
            host="acme.wd1.myworkdayjobs.com",
            tenant="acme",
            site="External_Careers",
        ),
        SETTINGS,
    )
    workday_job = workday._normalize(
        {
            "title": "Software Engineer",
            "locationsText": "Austin, TX",
            "postedOn": "Posted Today",
            "externalPath": "/job/Austin-TX/Software-Engineer_R123",
            "bulletFields": ["R123"],
        },
        {"jobReqId": "R123", "jobDescription": "<p>Build reliable services.</p>"},
    )
    workday.close()
    assert smart_job.state == "MA"
    assert smart_job.original_url == "https://jobs.smartrecruiters.com/acme/smart-1"
    assert workday_job.original_url == (
        "https://acme.wd1.myworkdayjobs.com/en-US/External_Careers/job/"
        "Austin-TX/Software-Engineer_R123"
    )
    assert workday_job.requisition_id == "R123"
