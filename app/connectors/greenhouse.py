from collections.abc import Iterator
from typing import Any

from app.connectors.base import BaseConnector, ConnectorError, NormalizedJob, stable_external_id
from app.services.enrichment import (
    clean_html,
    extract_salary,
    infer_location_parts,
    is_remote_job,
    parse_datetime,
    utcnow,
)


class GreenhouseConnector(BaseConnector):
    provider = "greenhouse"

    @property
    def token(self) -> str:
        value = self.spec.token or self.spec.board
        if not value:
            raise ConnectorError("Greenhouse source requires token")
        return value

    @property
    def source_key(self) -> str:
        return f"greenhouse:{self.token.lower()}"

    def fetch(self) -> Iterator[NormalizedJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.token}/jobs"
        response = self.request_json("GET", url, params={"content": "true"})
        for item in response.get("jobs", []):
            if isinstance(item, dict):
                yield self._normalize(item)

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        title = str(item.get("title") or "Untitled role")
        company = self.spec.company or self.token.replace("-", " ").title()
        location = (item.get("location") or {}).get("name")
        description = clean_html(item.get("content"))
        city, state, country = infer_location_parts(
            location,
            country_code=self.spec.country_code,
        )
        departments = item.get("departments") or []
        department = (
            ", ".join(
                str(value.get("name"))
                for value in departments
                if isinstance(value, dict) and value.get("name")
            )
            or None
        )
        salary_min, salary_max, currency, period = extract_salary(description)
        original_url = item.get("absolute_url")
        external_id = str(item.get("id") or stable_external_id(company, title, original_url))
        remote = is_remote_job(location, None, description)

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
            remote=remote,
            workplace_type="remote" if remote else None,
            department=department,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            posted_at=None,
            posted_at_confidence="unknown",
            discovered_at=utcnow(),
            source_updated_at=parse_datetime(item.get("updated_at")),
            apply_url=original_url,
            original_url=original_url,
            ats="greenhouse",
            requisition_id=external_id,
            raw_payload=item,
        )
