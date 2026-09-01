import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dedup_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    fuzzy_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(500), index=True)
    company: Mapped[str] = mapped_column(String(300), index=True)
    company_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(500), index=True)
    city: Mapped[str | None] = mapped_column(String(150), index=True)
    state: Mapped[str | None] = mapped_column(String(100), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)

    remote: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    workplace_type: Mapped[str | None] = mapped_column(String(30), index=True)
    employment_type: Mapped[str | None] = mapped_column(String(80), index=True)
    seniority: Mapped[str | None] = mapped_column(String(80), index=True)
    department: Mapped[str | None] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(80), default="Other", index=True)

    description: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_min: Mapped[float | None] = mapped_column(Float)
    experience_max: Mapped[float | None] = mapped_column(Float)
    visa_signal: Mapped[str] = mapped_column(String(30), default="unknown", index=True)

    salary_min: Mapped[float | None] = mapped_column(Float, index=True)
    salary_max: Mapped[float | None] = mapped_column(Float, index=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(30))
    salary_text: Mapped[str | None] = mapped_column(String(500))

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    posted_at_confidence: Mapped[str] = mapped_column(String(30), default="unknown")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    apply_url: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    ats: Mapped[str | None] = mapped_column(String(80), index=True)
    primary_provider: Mapped[str] = mapped_column(String(80), index=True)
    requisition_id: Mapped[str | None] = mapped_column(String(200), index=True)

    fit_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    fit_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_jobs_active_posted", "is_active", "posted_at"),
        Index("ix_jobs_country_category", "country_code", "category"),
    )


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80), index=True)
    source_key: Mapped[str] = mapped_column(String(255), index=True)
    external_id: Mapped[str] = mapped_column(String(500))
    ats: Mapped[str | None] = mapped_column(String(80), index=True)
    original_url: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[Job] = relationship(back_populates="sources")

    __table_args__ = (UniqueConstraint("source_key", "external_id", name="uq_source_external_job"),)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    source_key: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    deactivated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_sync_runs_source_started", "source_key", "started_at"),)
