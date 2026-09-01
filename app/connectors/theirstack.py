import math
import re
from collections.abc import Iterator
from typing import Any

from app.connectors.base import (
    BaseConnector,
    ConnectorError,
    NormalizedJob,
    first_value,
    stable_external_id,
)
from app.services.enrichment import (
    clean_html,
    detect_ats,
    extract_salary,
    infer_location_parts,
    is_remote_job,
    parse_datetime,
    utcnow,
)


class TheirStackConnector(BaseConnector):
    provider = "theirstack"
    complete_snapshot = False

    @property
    def source_key(self) -> str:
        return "theirstack:us-market"

    def fetch(self) -> Iterator[NormalizedJob]:
        if not self.settings.theirstack_api_key:
            raise ConnectorError("THEIRSTACK_API_KEY is not configured")

        url = f"{self.settings.theirstack_base_url.rstrip('/')}/v1/jobs/search"
        headers = {"Authorization": f"Bearer {self.settings.theirstack_api_key}"}
        limit = min(max(self.settings.page_size, 1), 100)
        max_age_days = max(1, math.ceil(self.settings.posted_within_hours / 24))

        for page in range(self.settings.max_pages_per_source):
            payload: dict[str, Any] = {
                "posted_at_max_age_days": max_age_days,
                "job_country_code_or": ["US"],
                "job_title_pattern_or": self._title_patterns(),
                "include_total_results": page == 0,
                "limit": limit,
                "page": page,
            }
            response = self.request_json("POST", url, headers=headers, json=payload)
            records = response.get("data", []) if isinstance(response, dict) else []
            if not isinstance(records, list):
                raise ConnectorError("TheirStack response did not contain a data list")
            for item in records:
                if isinstance(item, dict):
                    yield self._normalize(item)
            if len(records) < limit:
                break

    def _title_patterns(self) -> list[str]:
        # A broad regex keeps useful title variants while avoiding an unbounded market query.
        patterns = []
        for title in self.settings.target_title_list:
            words = [word for word in title.replace("/", " ").split() if word]
            if words:
                patterns.append(r"\b" + r"\s+".join(map(re.escape, words)) + r"s?\b")
        return patterns

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        company_object = item.get("company_object") or {}
        company = str(
            first_value(item, "company", "company_name", default=company_object.get("name"))
            or "Unknown company"
        )
        title = str(first_value(item, "job_title", "title", default="Untitled role"))
        location = first_value(item, "job_location", "location")
        if isinstance(location, list):
            location = ", ".join(str(value) for value in location if value)
        cities = item.get("cities") or []
        states = item.get("states") or []
        city = first_value(item, "job_city", "city", default=cities[0] if cities else None)
        state = first_value(item, "job_state", "state", default=states[0] if states else None)
        country = first_value(item, "job_country_code", "country_code")
        city, state, country = infer_location_parts(
            str(location) if location else None,
            city=str(city) if city else None,
            state=str(state) if state else None,
            country_code=str(country) if country else None,
        )
        description = clean_html(first_value(item, "description", "job_description"))
        original_url = first_value(item, "final_url", "url", "job_url", "source_url")
        apply_url = first_value(item, "apply_url", "application_url", default=original_url)
        salary_text = first_value(item, "salary_string", "salary_text")
        salary_min = first_value(
            item,
            "min_annual_salary_usd",
            "min_salary_usd",
            "salary_min",
        )
        salary_max = first_value(
            item,
            "max_annual_salary_usd",
            "max_salary_usd",
            "salary_max",
        )
        if salary_min is None and salary_max is None:
            salary_min, salary_max, currency, period = extract_salary(
                str(salary_text or description or "")
            )
        else:
            currency, period = "USD", "year"

        external_id = str(
            first_value(item, "id", "job_id")
            or stable_external_id(company, title, location, original_url)
        )
        workplace = first_value(item, "workplace_type", "remote_type")
        remote_value = first_value(item, "remote", "is_remote", "remote_derived")
        explicitly_remote = remote_value is True or str(remote_value).lower() in {
            "1",
            "true",
            "yes",
        }
        remote = explicitly_remote or is_remote_job(
            str(location) if location else None,
            str(workplace) if workplace else None,
            description,
        )
        posted_at = parse_datetime(first_value(item, "date_posted", "posted_at"))

        return NormalizedJob(
            provider=self.provider,
            source_key=self.source_key,
            external_id=external_id,
            title=title,
            company=company,
            company_domain=first_value(
                item,
                "company_domain",
                default=company_object.get("domain"),
            ),
            location=str(location) if location else None,
            city=city,
            state=state,
            country_code=country or "US",
            remote=remote,
            workplace_type=str(workplace).lower() if workplace else ("remote" if remote else None),
            employment_type=self._join_value(
                first_value(item, "employment_statuses", "employment_type")
            ),
            seniority=self._join_value(first_value(item, "job_seniority", "seniority")),
            department=self._join_value(first_value(item, "departments", "department")),
            description=description,
            salary_min=float(salary_min) if salary_min is not None else None,
            salary_max=float(salary_max) if salary_max is not None else None,
            salary_currency=currency,
            salary_period=period,
            salary_text=str(salary_text) if salary_text else None,
            posted_at=posted_at,
            posted_at_confidence="source_posted_at" if posted_at else "unknown",
            discovered_at=parse_datetime(item.get("discovered_at")) or utcnow(),
            source_updated_at=parse_datetime(first_value(item, "updated_at", "last_updated_at")),
            expires_at=parse_datetime(first_value(item, "expires_at", "closed_at")),
            apply_url=str(apply_url) if apply_url else None,
            original_url=str(original_url) if original_url else None,
            ats=first_value(item, "ats", "scraper_name")
            or detect_ats(str(original_url) if original_url else None),
            requisition_id=str(first_value(item, "requisition_id", "job_number") or "") or None,
            raw_payload=item,
        )

    @staticmethod
    def _join_value(value: object) -> str | None:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item) or None
        return str(value) if value else None
