import pytest


@pytest.fixture(autouse=True)
def no_real_scraping_from_endpoint_tests(monkeypatch):
    # Endpoint contract tests must not query Places, Sheets, or Vertex AI.
    monkeypatch.setattr("main.run_lead_generation_task", lambda: None)
