from aggregator.dedupe import dedupe, title_matches
from aggregator.geo import is_us_job
from aggregator.models import Job
from aggregator.textutil import parse_dt, strip_html


def test_us_location():
    assert is_us_job("New York, NY", None, True)
    assert is_us_job("Remote", None, True)
    assert is_us_job("San Francisco", "US", True)
    assert not is_us_job("London, UK", None, True)
    assert not is_us_job("Bengaluru, India", None, True)


def test_title_filter():
    assert title_matches("Senior Machine Learning Engineer", ["Machine Learning", "LLM"])
    assert title_matches("Staff LLM Engineer", ["LLM"])
    assert not title_matches("Staff Accountant", ["Machine Learning", "LLM"])
    assert not title_matches("Dual Enrollment Support Specialist", ["LLM", "Python"])
    assert not title_matches("Fulfillment Operations Team Leader", ["LLM"])


def test_emea_not_us():
    assert not is_us_job("EMEA - Remote", None, True)


def test_workday_relative_dates():
    today = parse_dt("Posted Today")
    old = parse_dt("Posted 13 Days Ago")
    assert today is not None
    assert old is not None
    assert (today - old).days >= 12


def test_dedupe_by_url():
    a = Job(job_id="a", title="SWE", company="Acme", ats="greenhouse", source="x", apply_url="https://x.test/job/1", description="short")
    b = Job(job_id="b", title="SWE", company="Acme", ats="lever", source="y", apply_url="https://x.test/job/1", description="a much longer description")
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0].description.startswith("a much")


def test_strip_html_entities():
    text = strip_html("&lt;p&gt;Hello &amp; welcome&lt;/p&gt;")
    assert "Hello" in text
    assert "<" not in text
