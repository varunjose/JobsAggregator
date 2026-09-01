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


class AshbyConnector(BaseConnector):
    provider = "ashby"

    @property
    def token(self) -> str:
        value = self.spec.token or self.spec.board
        if not value:
            raise ConnectorError("Ashby source requires board or token")
        return value

    @property
    def source_key(self) -> str:
        return f"ashby:{self.token.lower()}"

    def fetch(self) -> Iterator[NormalizedJob]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.token}"
        response = self.request_json("GET", url, params={"includeCompensation": "true"})
        for item in response.get("jobs", []):
            if isinstance(item, dict) and item.get("isListed", True):
                yield self._normalize(item)

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        title = str(item.get("title") or "Untitled role")
        company = self.spec.company or self.token.replace("-", " ").title()
        location = item.get("location")
        secondary = item.get("secondaryLocations") or []
        secondary_names = [
            str(value.get("location"))
            for value in secondary
            if isinstance(value, dict) and value.get("location")
        ]
        if secondary_names:
            location = ", ".join([str(location), *secondary_names] if location else secondary_names)
        description = clean_html(item.get("descriptionHtml")) or item.get("descriptionPlain")
        address = item.get("address") or {}
        city, state, country = infer_location_parts(
            str(location) if location else None,
            city=address.get("addressLocality"),
            state=address.get("addressRegion"),
            country_code=address.get("addressCountry") or self.spec.country_code,
        )
        workplace = item.get("workplaceType")
        remote = is_remote_job(str(location) if location else None, workplace, description)
        salary_text = item.get("compensationTierSummary")
        salary_min, salary_max, currency, period = extract_salary(
            f"{salary_text or ''}\n{description or ''}"
        )
        original_url = item.get("jobUrl")
        apply_url = item.get("applyUrl") or original_url
        external_id = str(
            item.get("id")
            or item.get("jobPostingId")
            or stable_external_id(company, title, original_url)
        )
        posted_at = parse_datetime(item.get("publishedAt"))

        return NormalizedJob(
            provider=self.provider,
            source_key=self.source_key,
            external_id=external_id,
            title=title,
            company=company,
            location=str(location) if location else None,
            city=city,
            state=state,
            country_code=country,
            remote=remote,
            workplace_type=str(workplace).lower() if workplace else ("remote" if remote else None),
            employment_type=item.get("employmentType"),
            department=item.get("department") or item.get("team"),
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            salary_text=str(salary_text) if salary_text else None,
            posted_at=posted_at,
            posted_at_confidence="source_published_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            source_updated_at=parse_datetime(item.get("updatedAt")),
            apply_url=apply_url,
            original_url=original_url,
            ats="ashby",
            requisition_id=str(item.get("jobReqId") or external_id),
            raw_payload=item,
        )
