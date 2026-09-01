from __future__ import annotations

import re
from typing import Optional

US_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN",
    "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
    "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT",
    "WA", "WI", "WV", "WY",
}

US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming", "district of columbia",
}

US_CITIES = {
    "seattle", "san francisco", "new york", "austin", "boston", "chicago",
    "los angeles", "denver", "atlanta", "dallas", "miami", "portland",
    "san diego", "san jose", "palo alto", "mountain view", "sunnyvale",
    "redmond", "bellevue", "arlington", "washington dc", "nyc", "sf",
    "bay area", "silicon valley", "brooklyn", "manhattan",
}

NON_US_MARKERS = [
    "united kingdom", "england", "scotland", "ireland", "germany", "france",
    "spain", "italy", "netherlands", "belgium", "sweden", "norway", "denmark",
    "finland", "poland", "india", "singapore", "australia", "canada",
    "mexico", "brazil", "japan", "china", "korea", "israel", "uae",
    "united arab", "switzerland", "austria", "portugal", "romania",
    "philippines", "indonesia", "malaysia", "thailand", "vietnam",
    "south africa", "argentina", "chile", "colombia", "pakistan",
    "bangladesh", "nigeria", "egypt", "turkey", "czechia", "czech",
    "hungary", "greece", "new zealand", "hong kong", "taiwan",
    "london", "berlin", "paris", "amsterdam", "dublin", "toronto",
    "vancouver", "bangalore", "bengaluru", "hyderabad", "mumbai",
    "pune", "chennai", "gurgaon", "gurugram", "noida", "tel aviv",
    "sydney", "melbourne", "zurich", "munich", "warsaw", "emea",
    "apac", "latam",
]

STATE_COMMA_RE = re.compile(r",\s*([A-Z]{2})(?:\s|$|,)")
REMOTE_RE = re.compile(r"\bremote\b", re.I)


def is_remote(location: str) -> bool:
    return bool(REMOTE_RE.search(location or ""))


def looks_non_us(location: str) -> bool:
    loc = (location or "").lower()
    return any(marker in loc for marker in NON_US_MARKERS)


def looks_us(location: str) -> bool:
    loc = location or ""
    low = loc.lower()
    if "united states" in low or "usa" in low or re.search(r"\bus\b", low):
        return True
    if any(name in low for name in US_STATE_NAMES):
        return True
    if any(city in low for city in US_CITIES):
        return True
    m = STATE_COMMA_RE.search(loc)
    if m and m.group(1) in US_STATE_ABBR:
        return True
    return False


def infer_country(location: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        code = explicit.strip().upper()
        if len(code) == 2:
            return code
        low = explicit.lower()
        if "united states" in low or low in {"usa", "us", "america"}:
            return "US"
    if looks_us(location) and not looks_non_us(location):
        return "US"
    if looks_non_us(location) and not looks_us(location):
        return None
    if is_remote(location) and not looks_non_us(location):
        return "US"
    return None


def is_us_job(location: str, country: Optional[str], include_remote: bool) -> bool:
    if country and country.upper() == "US":
        if looks_non_us(location) and not looks_us(location) and not is_remote(location):
            return False
        return True
    if country and country.upper() != "US":
        return False
    if include_remote and is_remote(location) and not looks_non_us(location):
        return True
    return looks_us(location)
