from aggregator.sources.ashby import fetch_ashby
from aggregator.sources.bamboohr import fetch_bamboohr
from aggregator.sources.coresignal import fetch_coresignal
from aggregator.sources.greenhouse import fetch_greenhouse
from aggregator.sources.jobspipe import fetch_jobspipe
from aggregator.sources.lever import fetch_lever
from aggregator.sources.personio import fetch_personio
from aggregator.sources.recruitee import fetch_recruitee
from aggregator.sources.smartrecruiters import fetch_smartrecruiters
from aggregator.sources.theirstack import fetch_theirstack
from aggregator.sources.workable import fetch_workable
from aggregator.sources.workday import fetch_workday

ATS_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workable": fetch_workable,
    "workday": fetch_workday,
    "recruitee": fetch_recruitee,
    "bamboohr": fetch_bamboohr,
    "personio": fetch_personio,
}

__all__ = [
    "ATS_FETCHERS",
    "fetch_theirstack",
    "fetch_coresignal",
    "fetch_jobspipe",
]
