from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dateutil import parser as dateparser

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_html(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = TAG_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    else:
        relative = _parse_relative(str(value))
        if relative is not None:
            return relative
        try:
            dt = dateparser.parse(str(value))
        except (ValueError, OverflowError, TypeError):
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_relative(text: str) -> Optional[datetime]:
    t = text.strip().lower()
    now = datetime.now(timezone.utc)
    if re.search(r"\btoday\b", t) and "ago" not in t:
        return now
    if re.search(r"\byesterday\b", t):
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\s+days?\s+ago", t)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"(\d+)\s+hours?\s+ago", t)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    return None


def detect_ats_from_url(url: str) -> str:
    u = (url or "").lower()
    mapping = [
        ("greenhouse.io", "greenhouse"),
        ("lever.co", "lever"),
        ("ashbyhq.com", "ashby"),
        ("myworkdayjobs.com", "workday"),
        ("workday.com", "workday"),
        ("icims.com", "icims"),
        ("smartrecruiters.com", "smartrecruiters"),
        ("workable.com", "workable"),
        ("jobvite.com", "jobvite"),
        ("taleo.net", "taleo"),
        ("oraclecloud.com", "oracle"),
        ("adp.com", "adp"),
        ("bamboohr.com", "bamboohr"),
        ("paylocity.com", "paylocity"),
        ("personio", "personio"),
        ("recruitee.com", "recruitee"),
        ("breezy.hr", "breezy"),
        ("teamtailor.com", "teamtailor"),
        ("linkedin.com", "linkedin"),
        ("indeed.com", "indeed"),
        ("glassdoor.com", "glassdoor"),
        ("ziprecruiter.com", "ziprecruiter"),
    ]
    for needle, name in mapping:
        if needle in u:
            return name
    return "unknown"
