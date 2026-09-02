"""Source connectors that normalize external job feeds."""

from app.connectors.ashby import AshbyConnector
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.jobicy import JobicyConnector
from app.connectors.lever import LeverConnector
from app.connectors.remoteok import RemoteOkConnector
from app.connectors.smartrecruiters import SmartRecruitersConnector
from app.connectors.theirstack import TheirStackConnector
from app.connectors.workday import WorkdayConnector

CONNECTOR_TYPES = {
    "ashby": AshbyConnector,
    "greenhouse": GreenhouseConnector,
    "jobicy": JobicyConnector,
    "lever": LeverConnector,
    "remoteok": RemoteOkConnector,
    "smartrecruiters": SmartRecruitersConnector,
    "theirstack": TheirStackConnector,
    "workday": WorkdayConnector,
}

__all__ = ["CONNECTOR_TYPES"]
