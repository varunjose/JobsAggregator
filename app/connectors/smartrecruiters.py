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


class SmartRecruitersConnector(BaseConnector):
    provider = "smartrecruiters"

    @property
    def token(self) -> str:
        value = self.spec.token or self.spec.board
        if not value:
            raise ConnectorError("SmartRecruiters source requires company token")
        return value

    @property
    def source_key(self) -> str:
        return f"smartrecruiters:{self.token.lower()}"

    def fetch(self) -> Iterator[NormalizedJob]:
        base_url = f"https://api.smartrecruiters.com/v1/companies/{self.token}/postings"
        limit = min(max(self.settings.page_size, 1), 100)
        offset = 0
        for _ in range(self.settings.max_pages_per_source):
            response = self.request_json(
                "GET",
                base_url,
                params={
                    "limit": limit,
                    "offset": offset,
                    "destination": "PUBLIC",
                },
            )
            records = response.get("content", [])
            for summary in records:
                if not isinstance(summary, dict):
                    continue
                details = summary
                posting_id = summary.get("id") or summary.get("uuid")
                if self.spec.fetch_details and posting_id:
                    details = self.request_json("GET", f"{base_url}/{posting_id}")
                    details["_list_summary"] = summary
                yield self._normalize(details)
            offset += len(records)
            total = int(response.get("totalFound") or 0)
            if not records or len(records) < limit or (total and offset >= total):
                break
        else:
            self.snapshot_complete = False

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        summary = item.get("_list_summary") or item
        title = str(item.get("name") or summary.get("name") or "Untitled role")
        company_data = item.get("company") or summary.get("company") or {}
        company = self.spec.company or company_data.get("name") or self.token
        location_data = item.get("location") or summary.get("location") or {}
        location_parts = [
            location_data.get("city"),
            location_data.get("region"),
            location_data.get("country"),
        ]
        location = ", ".join(str(value) for value in location_parts if value) or None
        city, state, country = infer_location_parts(
            location,
            city=location_data.get("city"),
            state=location_data.get("region"),
            country_code=location_data.get("country") or self.spec.country_code,
        )
        job_ad = item.get("jobAd") or {}
        sections = job_ad.get("sections") or {}
        description_parts = []
        for value in sections.values() if isinstance(sections, dict) else []:
            if isinstance(value, dict):
                description_parts.append(value.get("text") or value.get("title"))
            elif value:
                description_parts.append(value)
        description = clean_html("\n\n".join(str(value) for value in description_parts if value))
        workplace = item.get("workplaceMode") or summary.get("workplaceMode")
        remote = is_remote_job(location, workplace, description)
        salary_text = item.get("salary") or summary.get("salary")
        if isinstance(salary_text, dict):
            salary_text = " ".join(str(value) for value in salary_text.values() if value)
        salary_min, salary_max, currency, period = extract_salary(
            f"{salary_text or ''}\n{description or ''}"
        )
        original_url = (
            item.get("jobAdUrl")
            or job_ad.get("publicAdUrl")
            or item.get("postingUrl")
            or summary.get("jobAdUrl")
            or f"https://jobs.smartrecruiters.com/{self.token}/{summary.get('id', '')}"
        )
        apply_url = item.get("applyUrl") or job_ad.get("applyUrl") or original_url
        external_id = str(
            item.get("id") or item.get("uuid") or stable_external_id(company, title, original_url)
        )
        posted_at = parse_datetime(item.get("releasedDate") or summary.get("releasedDate"))
        employment = item.get("typeOfEmployment") or summary.get("typeOfEmployment") or {}
        department = item.get("department") or summary.get("department") or {}

        return NormalizedJob(
            provider=self.provider,
            source_key=self.source_key,
            external_id=external_id,
            title=title,
            company=str(company),
            company_domain=company_data.get("website"),
            location=location,
            city=city,
            state=state,
            country_code=country,
            remote=remote,
            workplace_type=str(workplace).lower() if workplace else ("remote" if remote else None),
            employment_type=(
                employment.get("label") or employment.get("id")
                if isinstance(employment, dict)
                else str(employment)
                if employment
                else None
            ),
            department=(
                department.get("label") or department.get("name")
                if isinstance(department, dict)
                else str(department)
                if department
                else None
            ),
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            salary_text=str(salary_text) if salary_text else None,
            posted_at=posted_at,
            posted_at_confidence="source_released_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            source_updated_at=parse_datetime(item.get("updatedDate")),
            apply_url=apply_url,
            original_url=original_url,
            ats="smartrecruiters",
            requisition_id=str(item.get("refNumber") or external_id),
            raw_payload=item,
        )
