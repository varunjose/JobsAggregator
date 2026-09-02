import re
from collections.abc import Iterator
from typing import Any

from app.connectors.base import BaseConnector, ConnectorError, NormalizedJob, stable_external_id
from app.services.enrichment import clean_html, infer_location_parts, parse_datetime, utcnow

DEFAULT_TITLE_KEYWORDS = (
    "software",
    "engineer",
    "developer",
    "machine learning",
    "data",
    "artificial intelligence",
    "ai",
    "ml",
    "python",
    "backend",
    "frontend",
    "full stack",
    "platform",
    "cloud",
    "devops",
    "systems",
)


class RemoteOkConnector(BaseConnector):
    """Keyless Remote OK feed; canonical links preserve required attribution."""

    provider = "remoteok"
    complete_snapshot = False

    @property
    def source_key(self) -> str:
        return "remoteok:public"

    def fetch(self) -> Iterator[NormalizedJob]:
        response = self.request_json("GET", "https://remoteok.com/api")
        if not isinstance(response, list):
            raise ConnectorError("Remote OK response was not a list")
        for item in response:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            if self._matches_requested_roles(item):
                yield self._normalize(item)

    def _matches_requested_roles(self, item: dict[str, Any]) -> bool:
        if self.spec.options.get("targeted_only", True) is False:
            return True
        configured = self.spec.options.get("title_keywords")
        if isinstance(configured, str):
            keywords = [value.strip() for value in configured.split(",") if value.strip()]
        elif isinstance(configured, list):
            keywords = [str(value).strip() for value in configured if str(value).strip()]
        else:
            keywords = list(DEFAULT_TITLE_KEYWORDS)
        tags = " ".join(str(tag) for tag in item.get("tags") or [])
        haystack = f"{item.get('position', '')} {tags}".lower()
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])", haystack)
            for keyword in keywords
        )

    def _normalize(self, item: dict[str, Any]) -> NormalizedJob:
        title = str(item.get("position") or "Untitled role")
        company = str(item.get("company") or "Unknown company")
        raw_location = str(item.get("location") or "").strip()
        location = raw_location or "Remote / Worldwide"
        description = clean_html(item.get("description"))
        city, state, country = infer_location_parts(
            location,
            country_code=self.spec.country_code,
        )
        global_remote = any(
            value in location.lower()
            for value in ("remote", "worldwide", "anywhere", "global")
        )
        if country is None and global_remote:
            country = "US"
        original_url = str(item.get("url") or "").strip() or None
        external_id = str(
            item.get("id")
            or item.get("slug")
            or stable_external_id(company, title, original_url)
        )
        posted_at = parse_datetime(item.get("date") or item.get("epoch"))
        salary_min = _positive_number(item.get("salary_min"))
        salary_max = _positive_number(item.get("salary_max"))
        tags = [str(tag).strip() for tag in item.get("tags") or [] if str(tag).strip()]

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
            employment_type=_employment_type(tags),
            seniority=_seniority(tags),
            department=", ".join(tags[:8]) or None,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD" if salary_min is not None or salary_max is not None else None,
            salary_period="year" if salary_min is not None or salary_max is not None else None,
            posted_at=posted_at,
            posted_at_confidence="source_published_at" if posted_at else "unknown",
            discovered_at=utcnow(),
            # Remote OK's public API requires the displayed link to point back to Remote OK.
            apply_url=original_url,
            original_url=original_url,
            raw_payload=item,
        )


def _positive_number(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _employment_type(tags: list[str]) -> str | None:
    lowered = {tag.lower() for tag in tags}
    for candidate in ("full time", "part time", "contract", "freelance", "internship"):
        if candidate in lowered:
            return candidate.title()
    return None


def _seniority(tags: list[str]) -> str | None:
    lowered = {tag.lower() for tag in tags}
    for candidate in ("intern", "junior", "midlevel", "senior", "lead", "manager"):
        if candidate in lowered:
            return candidate
    return None
