from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def serialize_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class UTCModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetimes(self, value):
        return serialize_utc(value) if isinstance(value, datetime) else value


class JobSourceOut(UTCModel):
    provider: str
    source_key: str
    external_id: str
    ats: str | None
    original_url: str | None
    apply_url: str | None
    posted_at: datetime | None
    discovered_at: datetime
    last_seen_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class JobOut(UTCModel):
    id: str
    title: str
    company: str
    company_domain: str | None
    location: str | None
    city: str | None
    state: str | None
    country_code: str | None
    remote: bool
    workplace_type: str | None
    employment_type: str | None
    seniority: str | None
    department: str | None
    category: str
    description: str | None
    skills: list[str] = Field(default_factory=list)
    experience_min: float | None
    experience_max: float | None
    visa_signal: str
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    salary_period: str | None
    salary_text: str | None
    posted_at: datetime | None
    posted_at_confidence: str
    first_seen_at: datetime
    last_seen_at: datetime
    expires_at: datetime | None
    apply_url: str | None
    original_url: str | None
    canonical_url: str | None
    ats: str | None
    primary_provider: str
    requisition_id: str | None
    fit_score: int
    fit_reasons: list[str] = Field(default_factory=list)
    is_active: bool
    sources: list[JobSourceOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class JobListOut(UTCModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int
    generated_at: datetime


class SyncRunOut(UTCModel):
    id: str
    provider: str
    source_key: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched: int
    created: int
    updated: int
    skipped: int
    deactivated: int
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)
