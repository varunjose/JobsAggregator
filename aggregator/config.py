from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class Settings:
    posted_within_hours: int = 24
    country_codes: list[str] = field(default_factory=lambda: ["US"])
    include_remote: bool = True
    include_missing_posted_at: bool = True
    title_keywords: list[str] = field(default_factory=list)
    resume_path: str = "resume.example.md"
    enable_theirstack: bool = True
    enable_coresignal: bool = True
    enable_jobspipe: bool = True
    enable_ats: bool = True
    theirstack: dict[str, Any] = field(default_factory=dict)
    coresignal: dict[str, Any] = field(default_factory=dict)
    jobspipe: dict[str, Any] = field(default_factory=dict)
    ats: dict[str, Any] = field(default_factory=dict)
    output_dir: Path = ROOT / "data"
    dashboard_dir: Path = ROOT / "web"
    companies_path: Path = ROOT / "companies.json"
    description_chars: int = 1800

    @property
    def resume_file(self) -> Path:
        path = ROOT / self.resume_path
        if path.exists():
            return path
        return ROOT / "resume.example.md"


def load_settings(path: Path | None = None) -> Settings:
    load_dotenv()
    cfg_path = path or ROOT / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text()) or {}

    sources = raw.get("sources") or {}
    return Settings(
        posted_within_hours=int(raw.get("posted_within_hours", 24)),
        country_codes=list(raw.get("country_codes") or ["US"]),
        include_remote=bool(raw.get("include_remote", True)),
        include_missing_posted_at=bool(raw.get("include_missing_posted_at", True)),
        title_keywords=list(raw.get("title_keywords") or []),
        resume_path=str(raw.get("resume_path") or "resume.example.md"),
        enable_theirstack=bool(sources.get("theirstack", True)),
        enable_coresignal=bool(sources.get("coresignal", True)),
        enable_jobspipe=bool(sources.get("jobspipe", True)),
        enable_ats=bool(sources.get("ats", True)),
        theirstack=dict(raw.get("theirstack") or {}),
        coresignal=dict(raw.get("coresignal") or {}),
        jobspipe=dict(raw.get("jobspipe") or {}),
        ats=dict(raw.get("ats") or {}),
        output_dir=ROOT / str(raw.get("output_dir") or "data"),
        dashboard_dir=ROOT / str(raw.get("dashboard_dir") or "web"),
        description_chars=int(raw.get("description_chars") or 1800),
    )
