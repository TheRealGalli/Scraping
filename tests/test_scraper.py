import datetime
import pytz
import pytest
from fastapi.testclient import TestClient

from main import app
from services.time_filter import is_night_time
from services.email_extractor import EmailExtractor
from services.geo_matrix import generate_search_targets, ITALY_GEO_TREE, SECTORS
from services.web_scraper import WebScraper

client = TestClient(app)

def test_time_filter_anti_night():
    rome_tz = pytz.timezone("Europe/Rome")
    
    # 23:30 should be night
    night_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 23, 30))
    assert is_night_time(night_dt) is True
    
    # 03:15 should be night
    late_night_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 3, 15))
    assert is_night_time(late_night_dt) is True
    
    # 10:00 should NOT be night
    day_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 10, 0))
    assert is_night_time(day_dt) is False
    
    # 21:59 should NOT be night
    evening_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 21, 59))
    assert is_night_time(evening_dt) is False

def test_email_extraction_regex():
    extractor = EmailExtractor()
    sample_text = """
    Benvenuti nel nostro studio legale. Per informazioni e prenotazioni potete contattarci
    all'indirizzo info@studiolegale-esempio.it oppure via telefono al 02 1234567.
    Per contatti amministrativi: amministrazione@studiolegale-esempio.it.
    Ignore bad emails like image.png@2x or fake@example.com.
    """
    extracted = extractor.extract_email_with_regex(sample_text)
    assert extracted == "info@studiolegale-esempio.it"

def test_gemini_grounding_search_disabled():
    # Test when GROUNDING is disabled
    from config import settings
    original_setting = settings.ENABLE_GEMINI_GROUNDING
    settings.ENABLE_GEMINI_GROUNDING = False
    extractor = EmailExtractor()
    res = extractor.find_email_via_gemini_search("Test Business", "Milano", "https://example.it")
    assert res is None
    settings.ENABLE_GEMINI_GROUNDING = original_setting

def test_geo_matrix_generation():
    targets = list(generate_search_targets())
    assert len(targets) > 0
    first_target = targets[0]
    # (Region, Province, City, Sector, Keyword)
    assert first_target[0] == "Lombardia"
    assert first_target[1] == "Milano"
    assert first_target[2] == "Milano"
    assert first_target[3] in SECTORS

def test_web_scraper_html_cleaning():
    scraper = WebScraper()
    raw_html = """
    <html>
        <head><title>Test Page</title><script>var x = 10;</script></head>
        <body>
            <h1>Ristorante Da Mario</h1>
            <p>Contattaci a <a href="/contatti">Pagina Contatti</a></p>
        </body>
    </html>
    """
    cleaned = scraper.clean_html_to_text(raw_html)
    assert "var x = 10" not in cleaned
    assert "Ristorante Da Mario" in cleaned
    
    contact_links = scraper.find_contact_links("https://example.it", raw_html)
    assert len(contact_links) == 1
    assert contact_links[0] == "https://example.it/contatti"

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "is_night_time" in data

def test_worker_endpoint_invocation():
    response = client.post("/worker")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["skipped", "processing"]
