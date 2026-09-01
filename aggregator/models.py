from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str = ""
    country: Optional[str] = None
    remote: bool = False
    ats: str
    source: str
    posted_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=utcnow)
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    apply_url: str = ""
    original_url: str = ""
    is_active: bool = True
    department: Optional[str] = None
    score: float = 0.0
    score_reasons: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        title = " ".join(self.title.lower().split())
        company = " ".join(self.company.lower().split())
        loc = " ".join(self.location.lower().split())
        return f"{company}|{title}|{loc}"

    def dashboard_dict(self, description_chars: int = 1800) -> dict[str, Any]:
        posted = self.posted_at.isoformat() if self.posted_at else None
        desc = self.description.strip()
        if len(desc) > description_chars:
            desc = desc[: description_chars - 1].rstrip() + "…"
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "country": self.country,
            "remote": self.remote,
            "ats": self.ats,
            "source": self.source,
            "posted_at": posted,
            "discovered_at": self.discovered_at.isoformat(),
            "description": desc,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "apply_url": self.apply_url or self.original_url,
            "original_url": self.original_url or self.apply_url,
            "is_active": self.is_active,
            "department": self.department,
            "score": round(self.score, 3),
            "score_reasons": self.score_reasons,
        }
