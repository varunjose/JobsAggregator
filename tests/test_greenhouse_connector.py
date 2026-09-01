import httpx

from app.config import Settings
from app.connectors.base import SourceSpec
from app.connectors.greenhouse import GreenhouseConnector


def test_greenhouse_connector_does_not_invent_posted_at():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["content"] == "true"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 123,
                        "title": "Python Engineer",
                        "location": {"name": "New York, NY"},
                        "content": "<p>Build APIs with Python and FastAPI.</p>",
                        "updated_at": "2026-09-01T12:00:00Z",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                        "departments": [{"name": "Engineering"}],
                    }
                ]
            },
        )

    connector = GreenhouseConnector(
        SourceSpec(type="greenhouse", token="acme", company="Acme"),
        Settings(sync_scheduler_enabled=False),
    )
    connector.client.close()
    connector.client = httpx.Client(transport=httpx.MockTransport(handler))
    jobs = list(connector.fetch())
    connector.close()

    assert len(jobs) == 1
    assert jobs[0].posted_at is None
    assert jobs[0].source_updated_at is not None
    assert jobs[0].country_code == "US"
    assert jobs[0].description == "Build APIs with Python and FastAPI."
