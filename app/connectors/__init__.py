"""Source connectors that normalize external job feeds."""

from app.connectors.ashby import AshbyConnector
from app.connectors.greenhouse import GreenhouseConnector
from app.connectors.lever import LeverConnector
from app.connectors.smartrecruiters import SmartRecruitersConnector
from app.connectors.theirstack import TheirStackConnector
from app.connectors.workday import WorkdayConnector

CONNECTOR_TYPES = {
    "ashby": AshbyConnector,
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "smartrecruiters": SmartRecruitersConnector,
    "theirstack": TheirStackConnector,
    "workday": WorkdayConnector,
}

__all__ = ["CONNECTOR_TYPES"]
