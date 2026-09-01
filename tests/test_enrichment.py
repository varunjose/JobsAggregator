from app.services.enrichment import (
    calculate_fit_score,
    classify_category,
    detect_visa_signal,
    extract_experience,
    extract_salary,
    extract_skills,
    infer_location_parts,
)


def test_enrichment_extracts_clear_job_signals():
    description = (
        "Build LLM and RAG services with Python, FastAPI, AWS, Docker and Kubernetes. "
        "Requires 2-4 years of experience. Salary: $130,000 - $170,000 per year. "
        "We are unable to sponsor employment visas."
    )
    assert classify_category("AI Engineer", description) == "AI / ML"
    assert {"Python", "FastAPI", "AWS", "Docker", "Kubernetes", "LLM", "RAG"}.issubset(
        extract_skills("AI Engineer", description)
    )
    assert extract_experience(description) == (2.0, 4.0)
    assert extract_salary(description) == (130000.0, 170000.0, "USD", "year")
    assert detect_visa_signal(description) == "not_available"


def test_location_and_fit_scoring():
    city, state, country = infer_location_parts("New York, NY")
    assert (city, state, country) == ("New York", "NY", "US")
    score, reasons = calculate_fit_score(
        title="AI Engineer",
        location="New York, NY",
        remote=False,
        skills=["Python", "LLM", "AWS"],
        experience_min=2,
        target_titles=["AI Engineer"],
        target_skills=["Python", "LLM", "AWS"],
        preferred_locations=["New York"],
    )
    assert score == 80
    assert len(reasons) >= 3


def test_location_infers_us_variants_and_mixed_case_state():
    assert infer_location_parts("Remote - US")[2] == "US"
    assert infer_location_parts("Austin, Tx")[1:] == ("TX", "US")
