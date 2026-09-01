from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aggregator.models import Job


def load_seen(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_seen(path: Path, seen: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, indent=2))


def write_outputs(
    jobs: list[Job],
    meta: dict[str, Any],
    output_dir: Path,
    dashboard_dir: Path,
    description_chars: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [job.dashboard_dict(description_chars) for job in jobs]
    jobs_path = output_dir / "jobs.json"
    meta_path = output_dir / "meta.json"
    jobs_path.write_text(json.dumps(payload, indent=2))
    meta_path.write_text(json.dumps(meta, indent=2, default=str))

    dashboard_dir.mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "jobs.json").write_text(json.dumps(payload))
    (dashboard_dir / "meta.json").write_text(json.dumps(meta, default=str))


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
