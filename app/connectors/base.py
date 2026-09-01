import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings


class SourceSpec(BaseModel):
    type: str
    enabled: bool = True
    company: str | None = None
    token: str | None = None
    board: str | None = None
    tenant: str | None = None
    site: str | None = None
    host: str | None = None
    country_code: str | None = None
    fetch_details: bool = True
    options: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class NormalizedJob(BaseModel):
    provider: str
    source_key: str
    external_id: str
    title: str
    company: str
    company_domain: str | None = None
    location: str | None = None
    city: str | None = None
    state: str | None = None
    country_code: str | None = None
    remote: bool = False
    workplace_type: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    department: str | None = None
    description: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_text: str | None = None
    posted_at: datetime | None = None
    posted_at_confidence: str = "unknown"
    discovered_at: datetime
    source_updated_at: datetime | None = None
    expires_at: datetime | None = None
    apply_url: str | None = None
    original_url: str | None = None
    ats: str | None = None
    requisition_id: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ConnectorError(RuntimeError):
    pass


class BaseConnector(ABC):
    provider: ClassVar[str]
    complete_snapshot: ClassVar[bool] = True

    def __init__(self, spec: SourceSpec, settings: Settings):
        self.spec = spec
        self.settings = settings
        self.snapshot_complete = self.complete_snapshot
        self.since: datetime | None = None
        self.client = httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "JobsAggregator/1.0 (+https://github.com/varunjose/JobsAggregator)",
            },
        )

    @property
    @abstractmethod
    def source_key(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch(self) -> Iterator[NormalizedJob]:
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, ConnectorError)),
        reraise=True,
    )
    def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        response = self.client.request(method, url, **kwargs)
        if response.status_code == 429 or response.status_code >= 500:
            raise ConnectorError(
                f"Temporary upstream error {response.status_code} from {self.provider}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:300].replace("\n", " ")
            raise ConnectorError(
                f"{self.provider} returned {response.status_code}: {detail}"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError(f"{self.provider} returned invalid JSON") from exc

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "BaseConnector":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def first_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return default


def stable_external_id(*values: object) -> str:
    combined = "|".join(str(value) for value in values if value is not None and value != "")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]
