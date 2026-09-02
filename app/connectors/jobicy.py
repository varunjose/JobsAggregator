from collections.abc import Iterator
from typing import Any

from app.connectors.base import BaseConnector, ConnectorError, NormalizedJob, stable_external_id
from app.services.enrichment import clean_html, infer_location_parts, parse_datetime, utcnow


class JobicyConnector(BaseConnector):
    """Keyless remote-job feed with explicit U.S. eligibility filtering."""

    provider = "jobicy"
    complete_snapshot = False

    @property
    def source_key(self) -> str:
        geo = str(self.spec.options.get("geo") or "all").lower()
        industry = str(self.spec.options.get("industry") or "all").lower()
        tag = str(self.spec.options.get("tag") or "all").lower()
        return f"jobicy:{geo}:{industry}:{tag}"

    def fetch(self) -> Iterator[NormalizedJob]:
        try:
            count = int(self.spec.options.get("count", 200))
        except (TypeError, ValueError):
            count = 200
        params: dict[str, str | int] = {"count": min(max(count, 1), 200)}
        for name in ("geo", "industry", "tag"):
            value = self.spec.options.get(name)
            if value:
                params[name] = str(value)

        response = self.request_json(
            "GET",
            "https://jobicy.com/api/v2/remote-jobs",
            params=params,
        )
        records = response.get("jobs") if isinstance(response, dict) else None
        if not isinstance(records, list):
            raise ConnectorError("Jobicy response did not contain a jobs list")
        for item in records:
            if isinstance(item, dict):
                yield self._normalize(item)

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        title = str(item.get("jobTitle") or "Untitled role")
        company = str(item.get("companyName") or "Unknown company")
        location = str(item.get("jobGeo") or "Remote")
        description = clean_html(item.get("jobDescription")) or item.get("jobExcerpt")
        configured_geo = str(self.spec.options.get("geo") or "").lower()
        configured_country = "US" if configured_geo in {"us", "usa"} else self.spec.country_code
        city, state, country = infer_location_parts(
            location,
            country_code=configured_country,
        )
        industries = _string_list(item.get("jobIndustry"))
        job_types = _string_list(item.get("jobType"))
        seniority = str(item.get("jobLevel") or "").strip() or None
        if seniority and seniority.lower() == "any":
            seniority = None
        salary_min = _number(item.get("salaryMin"))
        salary_max = _number(item.get("salaryMax"))
        currency = str(item.get("salaryCurrency") or "").strip().upper() or None
        period = _salary_period(item.get("salaryPeriod"))
        original_url = str(item.get("url") or "").strip() or None
        external_id = str(
            item.get("id")
            or item.get("jobSlug")
            or stable_external_id(company, title, original_url)
        )
        posted_at = parse_datetime(item.get("pubDate"))

        return NormalizedJob(
            provider=self.provider,
            source_key=self.source_key,
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            city=city,
            state=state,
            country_code=country,
            remote=True,
            workplace_type="remote",
            employment_type=", ".join(job_types) or None,
            seniority=seniority,
            department=", ".join(industries) or None,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            posted_at=posted_at,
            posted_at_confidence="source_published_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            apply_url=original_url,
            original_url=original_url,
            raw_payload=item,
        )


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _salary_period(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    return {
        "yearly": "year",
        "annually": "year",
        "hourly": "hour",
        "monthly": "month",
        "weekly": "week",
        "daily": "day",
    }.get(raw, raw or None)
