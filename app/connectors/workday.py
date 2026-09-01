import re
from collections.abc import Iterator
from datetime import timedelta
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


class WorkdayConnector(BaseConnector):
    """Connector for Workday's public career-site JSON endpoint.

    This endpoint backs public career pages but is not a global Workday API. Each tenant and
    career site must be configured separately, and Workday may change the response over time.
    """

    provider = "workday"

    @property
    def host(self) -> str:
        value = (self.spec.host or "").strip().lower().removeprefix("https://").rstrip("/")
        if not value.endswith(".myworkdayjobs.com"):
            raise ConnectorError("Workday host must end with .myworkdayjobs.com")
        return value

    @property
    def tenant(self) -> str:
        if not self.spec.tenant:
            raise ConnectorError("Workday source requires tenant")
        return self.spec.tenant

    @property
    def site(self) -> str:
        if not self.spec.site:
            raise ConnectorError("Workday source requires site")
        return self.spec.site

    @property
    def source_key(self) -> str:
        return f"workday:{self.host}:{self.tenant}:{self.site}".lower()

    @property
    def api_base(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}"

    def fetch(self) -> Iterator[NormalizedJob]:
        limit = min(max(self.settings.page_size, 1), 100)
        offset = 0
        for _ in range(self.settings.max_pages_per_source):
            response = self.request_json(
                "POST",
                f"{self.api_base}/jobs",
                json={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""},
            )
            records = response.get("jobPostings", [])
            for summary in records:
                if not isinstance(summary, dict):
                    continue
                details: dict[str, Any] = {}
                path = summary.get("externalPath")
                if self.spec.fetch_details and path:
                    detail_response = self.request_json("GET", f"{self.api_base}{path}")
                    details = detail_response.get("jobPostingInfo") or detail_response
                yield self._normalize(summary, details)
            offset += len(records)
            total = int(response.get("total") or 0)
            if not records or len(records) < limit or (total and offset >= total):
                break
        else:
            self.snapshot_complete = False

    def _normalize(self, summary: dict[str, Any], details: dict[str, Any]) -> NormalizedJob:
        title = str(details.get("title") or summary.get("title") or "Untitled role")
        company = self.spec.company or self.tenant.replace("-", " ").title()
        location = details.get("location") or summary.get("locationsText")
        additional_locations = details.get("additionalLocations") or []
        if isinstance(additional_locations, list) and additional_locations:
            all_locations = (
                [str(location), *map(str, additional_locations)]
                if location
                else additional_locations
            )
            location = ", ".join(map(str, all_locations))
        city, state, country = infer_location_parts(
            str(location) if location else None,
            country_code=self.spec.country_code,
        )
        description = clean_html(details.get("jobDescription"))
        workplace = details.get("workplaceType")
        remote = is_remote_job(str(location) if location else None, workplace, description)
        salary_text = details.get("salary") or details.get("compensation")
        salary_min, salary_max, currency, period = extract_salary(
            f"{salary_text or ''}\n{description or ''}"
        )
        external_path = summary.get("externalPath") or details.get("externalPath")
        locale = str(self.spec.options.get("locale") or "en-US").strip("/")
        fallback_url = (
            f"https://{self.host}/{locale}/{self.site}{external_path}" if external_path else None
        )
        original_url = details.get("externalUrl") or fallback_url
        apply_url = details.get("applyUrl") or original_url
        requisition_id = details.get("jobReqId") or self._bullet_requisition(summary)
        external_id = str(
            requisition_id or stable_external_id(company, title, location, original_url)
        )
        posted_at = self._parse_posted(details.get("postedOn") or summary.get("postedOn"))

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
            employment_type=details.get("timeType") or details.get("workerSubType"),
            department=details.get("jobFamilyGroup"),
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            salary_text=str(salary_text) if salary_text else None,
            posted_at=posted_at,
            posted_at_confidence="source_relative_posted_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            source_updated_at=parse_datetime(details.get("updatedAt")),
            apply_url=apply_url,
            original_url=original_url,
            ats="workday",
            requisition_id=str(requisition_id) if requisition_id else None,
            raw_payload={"summary": summary, "details": details},
        )

    @staticmethod
    def _parse_posted(value: object) -> Any:
        if not value:
            return None
        text = str(value).strip()
        lowered = text.lower()
        now = utcnow()
        if "today" in lowered:
            return now
        if "yesterday" in lowered:
            return now - timedelta(days=1)
        match = re.search(r"(\d+)\s+days?\s+ago", lowered)
        if match:
            return now - timedelta(days=int(match.group(1)))
        return parse_datetime(text)

    @staticmethod
    def _bullet_requisition(summary: dict[str, Any]) -> str | None:
        for value in summary.get("bulletFields") or []:
            text = str(value)
            if re.search(r"\b(?:req|r)-?\d+\b", text, flags=re.IGNORECASE):
                return text
        return None
