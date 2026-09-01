import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = {
    "gh_src",
    "lever-source",
    "ref",
    "referrer",
    "source",
    "sourceid",
    "trk",
}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", normalized.lower()).strip()


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    try:
        split = urlsplit(value)
    except ValueError:
        return value
    if not split.netloc:
        return value

    filtered_query = []
    for key, item_value in parse_qsl(split.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_PARAMETERS:
            continue
        filtered_query.append((key, item_value))

    path = re.sub(r"/{2,}", "/", split.path).rstrip("/") or "/"
    return urlunsplit(
        (
            (split.scheme or "https").lower(),
            split.netloc.lower(),
            path,
            urlencode(sorted(filtered_query)),
            "",
        )
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_fuzzy_key(company: str, title: str, location: str | None) -> str:
    parts = [normalize_text(company), normalize_text(title), normalize_text(location)]
    return _hash("|".join(parts))


def build_dedup_key(
    *,
    company: str,
    title: str,
    location: str | None,
    original_url: str | None,
    apply_url: str | None,
    external_id: str,
    source_key: str,
) -> tuple[str, str, str | None]:
    canonical_url = canonicalize_url(original_url or apply_url)
    fuzzy_key = build_fuzzy_key(company, title, location)
    if canonical_url:
        return _hash(f"url|{canonical_url}"), fuzzy_key, canonical_url
    fallback = f"fallback|{fuzzy_key}|{normalize_text(source_key)}|{normalize_text(external_id)}"
    return _hash(fallback), fuzzy_key, None


def dates_compatible(first: datetime | None, second: datetime | None, max_days: int = 7) -> bool:
    if first is None or second is None:
        return True
    if first.tzinfo is None:
        first = first.replace(tzinfo=UTC)
    if second.tzinfo is None:
        second = second.replace(tzinfo=UTC)
    return (
        abs((first.astimezone(UTC) - second.astimezone(UTC)).total_seconds()) <= max_days * 86_400
    )
