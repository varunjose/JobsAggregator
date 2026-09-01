from __future__ import annotations

from aggregator.models import Job
import re


def _phrase_in(text: str, phrase: str) -> bool:
    needle = phrase.lower().strip()
    hay = text.lower()
    if len(needle) <= 4 or " " not in needle:
        return bool(re.search(rf"\b{re.escape(needle)}\b", hay))
    return needle in hay


def title_matches(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    return any(_phrase_in(title, k) for k in keywords)


def merge_jobs(groups: list[list[Job]]) -> list[Job]:
    merged: list[Job] = []
    for group in groups:
        merged.extend(group)
    return merged


def dedupe(jobs: list[Job]) -> list[Job]:
    by_url: dict[str, Job] = {}
    by_fp: dict[str, Job] = {}
    out: list[Job] = []

    def better(a: Job, b: Job) -> Job:
        a_desc = len(a.description or "")
        b_desc = len(b.description or "")
        if a_desc != b_desc:
            return a if a_desc > b_desc else b
        a_posted = a.posted_at is not None
        b_posted = b.posted_at is not None
        if a_posted != b_posted:
            return a if a_posted else b
        return a

    for job in jobs:
        url = (job.apply_url or job.original_url or "").split("?")[0].rstrip("/").lower()
        fp = job.fingerprint()
        existing = None
        key = None
        if url:
            existing = by_url.get(url)
            key = ("url", url)
        if existing is None:
            existing = by_fp.get(fp)
            key = ("fp", fp)
        if existing is None:
            out.append(job)
            if url:
                by_url[url] = job
            by_fp[fp] = job
            continue
        winner = better(existing, job)
        if winner is not existing:
            try:
                out.remove(existing)
            except ValueError:
                pass
            out.append(winner)
            if url:
                by_url[url] = winner
            by_fp[fp] = winner
        elif key and key[0] == "url":
            by_fp[fp] = existing
    return out
