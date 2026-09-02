import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import Settings
from app.connectors.base import SourceSpec
from app.connectors.jobicy import JobicyConnector
from app.connectors.remoteok import RemoteOkConnector
from app.services.sync_service import load_source_specs

SETTINGS = Settings(sync_scheduler_enabled=False)


def test_jobicy_fetch_is_keyless_and_uses_configured_filters():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(dict(request.url.params))
        return httpx.Response(200, json={"jobs": []})

    connector = JobicyConnector(
        SourceSpec(
            type="jobicy",
            options={"geo": "usa", "industry": "engineering", "count": 200},
        ),
        SETTINGS,
    )
    connector.client.close()
    connector.client = httpx.Client(transport=httpx.MockTransport(handler))
    assert list(connector.fetch()) == []
    connector.close()

    assert observed == {"count": "200", "geo": "usa", "industry": "engineering"}


def test_jobicy_normalizes_us_remote_job():
    connector = JobicyConnector(
        SourceSpec(type="jobicy", options={"geo": "usa", "industry": "engineering"}),
        SETTINGS,
    )
    job = connector._normalize(
        {
            "id": 123,
            "url": "https://jobicy.com/jobs/backend-engineer",
            "jobTitle": "Backend Engineer",
            "companyName": "Acme",
            "jobIndustry": ["Engineering"],
            "jobType": ["full-time"],
            "jobGeo": "USA",
            "jobLevel": "Entry",
            "jobDescription": "<p>Build Python APIs.</p>",
            "pubDate": "2026-09-01T10:00:00+00:00",
            "salaryMin": 90000,
            "salaryMax": 120000,
            "salaryCurrency": "usd",
            "salaryPeriod": "yearly",
        }
    )
    connector.close()

    assert job.country_code == "US"
    assert job.remote is True
    assert job.description == "Build Python APIs."
    assert job.posted_at == datetime(2026, 9, 1, 10, tzinfo=UTC)
    assert job.salary_period == "year"
    assert job.original_url == "https://jobicy.com/jobs/backend-engineer"


def test_remoteok_skips_legal_row_and_unrelated_roles():
    payload = [
        {"legal": "Link back to Remote OK"},
        {"id": 1, "position": "Restaurant Manager", "tags": ["hospitality"]},
        {
            "id": 2,
            "position": "Python Backend Engineer",
            "company": "Acme",
            "location": "Remote / Worldwide",
            "date": "2026-09-01T12:00:00Z",
            "description": "<p>Build distributed APIs.</p>",
            "url": "https://remoteok.com/remote-jobs/2",
            "apply_url": "https://remoteok.com/remote-jobs/2",
            "salary_min": 100000,
            "salary_max": 140000,
            "tags": ["python", "engineer", "full time"],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(payload))

    connector = RemoteOkConnector(SourceSpec(type="remoteok"), SETTINGS)
    connector.client.close()
    connector.client = httpx.Client(transport=httpx.MockTransport(handler))
    jobs = list(connector.fetch())
    connector.close()

    assert len(jobs) == 1
    assert jobs[0].external_id == "2"
    assert jobs[0].country_code == "US"
    assert jobs[0].provider == "remoteok"
    assert jobs[0].employment_type == "Full Time"


def test_default_source_file_runs_without_paid_api_key():
    settings = Settings(
        theirstack_api_key=None,
        source_config_path=Path("config/sources.yaml"),
        sync_scheduler_enabled=False,
    )
    specs = load_source_specs(settings)

    assert [spec.type for spec in specs[:3]] == ["jobicy", "jobicy", "remoteok"]
