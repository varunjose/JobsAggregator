from __future__ import annotations

import re
from pathlib import Path

from aggregator.models import Job

TOKEN_RE = re.compile(r"[a-z0-9+#./-]+", re.I)

TITLE_WEIGHTS = [
    ("llm", 8),
    ("genai", 8),
    ("generative ai", 8),
    ("machine learning", 7),
    ("ml engineer", 7),
    ("ai engineer", 7),
    ("research scientist", 6),
    ("applied scientist", 6),
    ("data scientist", 5),
    ("data engineer", 5),
    ("software engineer", 4),
    ("backend", 3),
    ("full stack", 3),
    ("python", 3),
]


def load_resume_tokens(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return {t for t in TOKEN_RE.findall(text) if len(t) > 2}


def score_job(job: Job, resume_tokens: set[str]) -> Job:
    title = job.title.lower()
    desc = (job.description or "").lower()
    blob = f"{title} {desc}"
    score = 0.0
    reasons: list[str] = []

    for phrase, weight in TITLE_WEIGHTS:
        if re.search(rf"\b{re.escape(phrase)}\b", title):
            score += weight
            reasons.append(f"title:{phrase}")

    hits = []
    for token in sorted(resume_tokens):
        if len(token) < 4:
            continue
        if re.search(rf"\b{re.escape(token)}\b", blob):
            hits.append(token)
    unique_hits = list(dict.fromkeys(hits))[:12]
    score += min(len(unique_hits), 10) * 1.2
    if unique_hits:
        reasons.append("skills:" + ",".join(unique_hits[:6]))

    if job.salary_min and job.salary_min >= 130000:
        score += 1.5
        reasons.append("salary")
    if job.remote:
        score += 0.5

    job.score = round(score, 3)
    job.score_reasons = reasons
    return job
