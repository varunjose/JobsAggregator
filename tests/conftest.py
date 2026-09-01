import os
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_jobs.db"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
os.environ["SOURCE_CONFIG_PATH"] = "config/nonexistent-test-sources.yaml"

from app.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    Path("test_jobs.db").unlink(missing_ok=True)
