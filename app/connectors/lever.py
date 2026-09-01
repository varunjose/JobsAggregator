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


class LeverConnector(BaseConnector):
    provider = "lever"

    @property
    def token(self) -> str:
        value = self.spec.token or self.spec.board
        if not value:
            raise ConnectorError("Lever source requires token")
        return value

    @property
    def source_key(self) -> str:
        return f"lever:{self.token.lower()}"

    def fetch(self) -> Iterator[NormalizedJob]:
        url = f"https://api.lever.co/v0/postings/{self.token}"
        limit = min(max(self.settings.page_size, 1), 100)
        for page in range(self.settings.max_pages_per_source):
            records = self.request_json(
                "GET",
                url,
                params={"mode": "json", "limit": limit, "skip": page * limit},
            )
            if not isinstance(records, list):
                raise ConnectorError("Lever response was not a list")
            for item in records:
                if isinstance(item, dict):
                    yield self._normalize(item)
            if len(records) < limit:
                break
        else:
            self.snapshot_complete = False

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        categories = item.get("categories") or {}
        title = str(item.get("text") or "Untitled role")
        company = self.spec.company or self.token.replace("-", " ").title()
        location = categories.get("location")
        workplace = item.get("workplaceType")
        description_parts = [item.get("descriptionPlain"), item.get("additionalPlain")]
        for section in item.get("lists") or []:
            if isinstance(section, dict):
                description_parts.extend([section.get("text"), clean_html(section.get("content"))])
        description = "\n\n".join(str(part).strip() for part in description_parts if part)
        description = description or None
        city, state, country = infer_location_parts(location, country_code=self.spec.country_code)
        salary_text = None
        salary_range = item.get("salaryRange") or {}
        salary_min = salary_range.get("min")
        salary_max = salary_range.get("max")
        currency = salary_range.get("currency")
        interval = salary_range.get("interval")
        if salary_min is None and salary_max is None:
            salary_min, salary_max, currency, interval = extract_salary(description)
        original_url = item.get("hostedUrl")
        apply_url = item.get("applyUrl") or original_url
        external_id = str(item.get("id") or stable_external_id(company, title, original_url))
        posted_at = parse_datetime(item.get("createdAt"))
        remote = is_remote_job(location, workplace, description)

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
            workplace_type=str(workplace).lower() if workplace else ("remote" if remote else None),
            employment_type=categories.get("commitment"),
            department=categories.get("department") or categories.get("team"),
            description=description,
            salary_min=float(salary_min) if salary_min is not None else None,
            salary_max=float(salary_max) if salary_max is not None else None,
            salary_currency=str(currency).upper() if currency else None,
            salary_period=str(interval).lower() if interval else None,
            salary_text=salary_text,
            posted_at=posted_at,
            posted_at_confidence="source_created_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            source_updated_at=parse_datetime(item.get("updatedAt")),
            apply_url=apply_url,
            original_url=original_url,
            ats="lever",
            requisition_id=external_id,
            raw_payload=item,
        )
