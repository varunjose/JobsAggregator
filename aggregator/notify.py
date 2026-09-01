from __future__ import annotations

import os
from typing import Any

import httpx

from aggregator.models import Job


async def notify(jobs: list[Job], meta: dict[str, Any]) -> None:
    text = (
        f"JobsAggregator: {meta.get('kept_jobs', 0)} US jobs "
        f"(last {meta.get('posted_within_hours', 24)}h)\n"
        f"Sources raw: {meta.get('source_counts')}\n"
        f"ATS mix: {meta.get('ats_breakdown')}"
    )
    slack = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    discord = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not slack and not discord:
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        if slack:
            try:
                await client.post(slack, json={"text": text})
            except Exception:
                pass
        if discord:
            try:
                await client.post(discord, json={"content": text[:1800]})
            except Exception:
                pass
