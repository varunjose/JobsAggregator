import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

US_STATES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}
STATE_CODES = set(US_STATES.values())

SKILL_ALIASES = {
    "Python": ("python",),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "Java": ("java",),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "React": ("react", "react.js", "reactjs"),
    "Node.js": ("node.js", "nodejs"),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Machine Learning": ("machine learning",),
    "LLM": ("large language model", "llm"),
    "RAG": ("retrieval augmented generation", "retrieval-augmented generation", "rag"),
    "AI Agents": ("ai agent", "agentic", "multi-agent"),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Kafka": ("kafka",),
    "Spark": ("apache spark", "pyspark"),
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        parsed = datetime.fromtimestamp(timestamp, tz=UTC)
    else:
        try:
            parsed = date_parser.parse(str(value))
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def clean_html(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(unescape(value), "html.parser")
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def normalize_country_code(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered in {"us", "usa", "united states", "united states of america"}:
        return "US"
    if len(lowered) == 2:
        return lowered.upper()
    return None


def infer_location_parts(
    location: str | None,
    *,
    city: str | None = None,
    state: str | None = None,
    country_code: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    location_value = (location or "").strip()
    city_value = city.strip() if city else None
    state_value = state.strip() if state else None
    country_value = normalize_country_code(country_code)

    if state_value:
        state_value = US_STATES.get(state_value.lower(), state_value.upper())

    lowered = location_value.lower()
    if not country_value and re.search(
        r"\b(united states(?: of america)?|u\.?s\.?a?\.?)\b",
        lowered,
    ):
        country_value = "US"

    if not state_value:
        for state_name, state_code in US_STATES.items():
            if re.search(rf"\b{re.escape(state_name)}\b", lowered):
                state_value = state_code
                break
        if not state_value:
            state_match = re.search(
                r"(?:,|\s)\s*([a-z]{2})(?:\s|,|$)",
                location_value,
                flags=re.IGNORECASE,
            )
            if state_match and state_match.group(1).upper() in STATE_CODES:
                state_value = state_match.group(1).upper()

    if state_value in STATE_CODES and not country_value:
        country_value = "US"

    if not city_value and location_value and "," in location_value:
        first = location_value.split(",", 1)[0].strip()
        if first and first.lower() not in {"remote", "united states", "usa"}:
            city_value = first

    return city_value, state_value, country_value


def is_remote_job(
    location: str | None,
    workplace_type: str | None,
    description: str | None,
) -> bool:
    explicit = (workplace_type or "").lower()
    if explicit == "remote" or "remote" in explicit:
        return True
    location_text = (location or "").lower()
    if re.search(r"\b(remote|work from home|anywhere in the u\.?s\.?)\b", location_text):
        return True
    # Avoid marking a role remote from a generic benefits sentence deep in the description.
    lead = (description or "")[:600].lower()
    return bool(re.search(r"\b(fully remote|remote position|remote role)\b", lead))


def is_us_job(country_code: str | None, location: str | None) -> bool:
    normalized = normalize_country_code(country_code)
    if normalized:
        return normalized == "US"
    _, state, inferred = infer_location_parts(location)
    return inferred == "US" or state in STATE_CODES


def detect_ats(*urls: str | None) -> str | None:
    domains = {
        "greenhouse.io": "greenhouse",
        "lever.co": "lever",
        "ashbyhq.com": "ashby",
        "smartrecruiters.com": "smartrecruiters",
        "myworkdayjobs.com": "workday",
        "icims.com": "icims",
        "oraclecloud.com": "oracle",
        "workable.com": "workable",
        "jobvite.com": "jobvite",
        "bamboohr.com": "bamboohr",
        "recruitee.com": "recruitee",
        "teamtailor.com": "teamtailor",
    }
    for url in urls:
        if not url:
            continue
        try:
            host = urlsplit(url).netloc.lower()
        except ValueError:
            continue
        for suffix, ats in domains.items():
            if host == suffix or host.endswith(f".{suffix}"):
                return ats
    return None


def classify_category(title: str, description: str | None) -> str:
    text = f"{title} {(description or '')[:1000]}".lower()
    title_lower = title.lower()
    ai_pattern = r"\b(llm|gen(?:erative)? ai|ai engineer|machine learning|ml engineer|nlp)\b"
    if re.search(ai_pattern, text):
        return "AI / ML"
    if re.search(r"\b(data engineer|analytics engineer|etl|data platform)\b", title_lower):
        return "Data Engineering"
    if re.search(r"\b(data scientist|data analyst|machine learning scientist)\b", title_lower):
        return "Data Science"
    if re.search(r"\b(full[ -]?stack|frontend|front-end|react developer)\b", title_lower):
        return "Full Stack / Frontend"
    if re.search(r"\b(backend|back-end|python developer|api engineer)\b", title_lower):
        return "Backend / Python"
    if re.search(r"\b(software|developer|sde|platform engineer|systems engineer)\b", title_lower):
        return "Software Engineering"
    return "Other"


def extract_skills(title: str, description: str | None) -> list[str]:
    text = f"{title}\n{description or ''}".lower()
    found = []
    for canonical, aliases in SKILL_ALIASES.items():
        matches = (
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) for alias in aliases
        )
        if any(matches):
            found.append(canonical)
    return found


def extract_experience(description: str | None) -> tuple[float | None, float | None]:
    if not description:
        return None, None
    values: list[tuple[float, float]] = []
    patterns = (
        r"(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
        r"experience\s+(?:of\s+)?(\d{1,2})(?:\s*[-–—]\s*(\d{1,2}))?\+?\s*(?:years?|yrs?)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, description, flags=re.IGNORECASE):
            minimum = float(match.group(1))
            maximum = float(match.group(2) or minimum)
            if minimum <= 25 and maximum <= 30:
                values.append((minimum, maximum))
    if not values:
        return None, None
    return min(value[0] for value in values), max(value[1] for value in values)


def detect_visa_signal(description: str | None) -> str:
    text = (description or "").lower()
    negative_patterns = (
        "unable to sponsor",
        "will not sponsor",
        "no visa sponsorship",
        "not provide sponsorship",
        "without sponsorship",
        "do not sponsor",
    )
    positive_patterns = (
        "visa sponsorship available",
        "sponsorship is available",
        "we sponsor",
        "immigration sponsorship",
    )
    if any(pattern in text for pattern in negative_patterns):
        return "not_available"
    if any(pattern in text for pattern in positive_patterns):
        return "available"
    return "unknown"


def _salary_number(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip().lower()
    multiplier = 1000 if cleaned.endswith("k") else 1
    cleaned = cleaned.removesuffix("k").strip()
    return float(cleaned) * multiplier


def extract_salary(text: str | None) -> tuple[float | None, float | None, str | None, str | None]:
    if not text:
        return None, None, None, None
    pattern = re.compile(
        r"(?P<currency>\$|USD\s*)"
        r"(?P<low>\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s*[kK])"
        r"(?:\s*(?:-|–|—|to)\s*(?:\$|USD\s*)?"
        r"(?P<high>\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s*[kK]))?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text[:20_000]):
        low = _salary_number(match.group("low"))
        high = _salary_number(match.group("high")) if match.group("high") else low
        nearby = text[match.start() : match.end() + 40].lower()
        period = "hour" if re.search(r"(?:/|per\s+)hour|hourly", nearby) else "year"
        if period == "year" and low < 20_000:
            continue
        if period == "hour" and high > 1000:
            continue
        return low, high, "USD", period
    return None, None, None, None


def calculate_fit_score(
    *,
    title: str,
    location: str | None,
    remote: bool,
    skills: list[str],
    experience_min: float | None,
    target_titles: list[str],
    target_skills: list[str],
    preferred_locations: list[str],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    title_lower = title.lower()
    title_matches = [target for target in target_titles if target.lower() in title_lower]
    if title_matches:
        score += 45
        reasons.append(f"Title matches {title_matches[0]}")
    elif any(token in title_lower for token in ("engineer", "developer", "data", "software")):
        score += 20
        reasons.append("Related technical role")

    target_skill_lookup = {skill.lower() for skill in target_skills}
    matched_skills = [skill for skill in skills if skill.lower() in target_skill_lookup]
    skill_score = min(35, len(matched_skills) * 5)
    score += skill_score
    if matched_skills:
        reasons.append(f"{len(matched_skills)} matching skills")

    location_lower = (location or "").lower()
    preferred = any(item.lower() in location_lower for item in preferred_locations)
    if remote or preferred:
        score += 15
        reasons.append("Preferred location or remote")

    if experience_min is None or experience_min <= 3:
        score += 5
        reasons.append("Accessible experience range")

    return min(100, score), reasons[:4]
