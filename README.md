# JobsAggregator

Pull newly posted **US jobs from the underlying hiring stack**, not from LinkedIn search.

Every two hours, GitHub Actions hits public ATS job-board APIs (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, Recruitee, BambooHR, Personio) and, if you add keys, the broad market feeds from [TheirStack](https://theirstack.com/en/docs/api-reference/jobs/search_jobs_v1), [Coresignal](https://coresignal.com/solutions/jobs-data-api/), and [JobsPipe](https://jobspipe.dev/jobs-api). Results are normalized, US-filtered, de-duplicated, scored against `resume.example.md`, and published to the dashboard.

```text
TheirStack + Coresignal + JobsPipe     (layer 1, optional keys)
Greenhouse / Lever / Ashby / Workday   (layer 2, no key)
SmartRecruiters / Workable / others
                 │
                 ▼
        unified Job record
                 │
     US + posted < 24h + title filter
                 │
        resume fit score + dedupe
                 │
     docs/ dashboard  (GitHub Pages)
```

Live repo: [github.com/varunjose/JobsAggregator](https://github.com/varunjose/JobsAggregator)

## Unified job record

Every posting is stored as:

```json
{
  "job_id": "greenhouse:8023928",
  "title": "AI Engineer",
  "company": "Example Inc",
  "location": "New York, NY",
  "country": "US",
  "remote": false,
  "ats": "greenhouse",
  "source": "company-career-page",
  "posted_at": "2026-09-01T15:21:00+00:00",
  "discovered_at": "2026-09-01T15:27:14+00:00",
  "description": "...",
  "salary_min": 130000,
  "salary_max": 170000,
  "apply_url": "https://...",
  "original_url": "https://...",
  "is_active": true,
  "score": 12.4
}
```

## Cloud schedule (every 2 hours)

[`.github/workflows/ingest.yml`](.github/workflows/ingest.yml) runs on:

```yaml
on:
  schedule:
    - cron: "0 */2 * * *"
  workflow_dispatch:
```

That job:

1. Installs Python 3.12 and pulls boards listed in `companies.json`
2. Queries TheirStack / Coresignal / JobsPipe when the matching secret is set
3. Writes `data/jobs.json` and `docs/jobs.json`
4. Commits the snapshot back to the repo
5. Deploys `docs/` to GitHub Pages

Enable Pages once: **Settings → Pages → Source: GitHub Actions**.

Scheduled workflows on GitHub can lag by several minutes. Trigger **Actions → Ingest US jobs → Run workflow** to run immediately.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m aggregator ingest
python -m aggregator serve
```

Dashboard: [http://127.0.0.1:8000](http://127.0.0.1:8000)

Copy `.env.example` to `.env` for paid feeds. Copy `resume.example.md` to `resume.md` (gitignored) to score against your own resume.

## GitHub secrets

| Secret | Role |
| --- | --- |
| `THEIRSTACK_API_KEY` | Primary broad feed (~356k sites, including Workday / iCIMS / Oracle / ADP career domains) |
| `CORESIGNAL_API_KEY` | Backup / verification feed |
| `JOBSPIPE_API_KEY` | Optional third feed + webhooks-oriented API |
| `SLACK_WEBHOOK_URL` | Optional run summary |
| `DISCORD_WEBHOOK_URL` | Optional run summary |

Without keys the pipeline still runs: it only uses public ATS JSON endpoints and the ~400 company boards in `companies.json`. Add TheirStack when you want Workday/iCIMS/Taleo-heavy coverage beyond those boards.

## Why two layers

Public Greenhouse / Lever / Ashby / SmartRecruiters endpoints are anonymous and fast, but they only work if you already know the company's board slug. Workday, iCIMS, Oracle Taleo, ADP, and Jobvite are tenant-specific and are not a single global “all US jobs” API. TheirStack (and Coresignal) is the layer that searches across those career sites by `posted_at` and country. No dataset is a complete census of the labor market; TheirStack says this explicitly in its [sources docs](https://theirstack.com/en/docs/data/job/sources).

Direct ATS connectors are still worth keeping: they are free, first-party, and often fresher for companies already in `companies.json`.

## Config

Edit `config.yaml` for title keywords, the 24-hour window, and source toggles. Add boards to `companies.json`:

```json
{ "name": "Stripe", "ats": "greenhouse", "board": "stripe" }
{ "name": "OpenAI", "ats": "ashby", "board": "openai" }
{ "name": "Nvidia", "ats": "workday", "tenant": "nvidia", "site": "NVIDIAExternalCareerSite", "shard": "wd5" }
```

## Tests

```bash
pip install pytest
PYTHONPATH=. pytest -q
```
