from datetime import UTC, datetime

from app.services.dedup import build_dedup_key, canonicalize_url, dates_compatible


def test_canonicalize_url_removes_tracking_but_keeps_job_identity():
    result = canonicalize_url(
        "https://boards.greenhouse.io/acme/jobs/123/?gh_jid=123&utm_source=linkedin&ref=feed"
    )
    assert result == "https://boards.greenhouse.io/acme/jobs/123?gh_jid=123"


def test_same_job_urls_build_same_key():
    common = {
        "company": "Acme, Inc.",
        "title": "AI Engineer",
        "location": "New York, NY",
        "apply_url": None,
        "external_id": "one",
        "source_key": "greenhouse:acme",
    }
    first = build_dedup_key(
        **common,
        original_url="https://example.com/jobs/123?utm_source=a",
    )
    second = build_dedup_key(
        **{**common, "external_id": "two", "source_key": "theirstack:us"},
        original_url="https://example.com/jobs/123?utm_source=b",
    )
    assert first[0] == second[0]
    assert first[1] == second[1]


def test_dates_compatible_handles_sqlite_naive_datetime():
    naive = datetime(2026, 9, 1, 12)
    aware = datetime(2026, 9, 2, 12, tzinfo=UTC)
    assert dates_compatible(naive, aware)
