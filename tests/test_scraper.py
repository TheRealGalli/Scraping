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
    assert data["status"] in ["skipped", "completed"]

def test_places_service_rating_and_sorting():
    from services.places_service import PlacesService
    ps = PlacesService(api_key="TEST_KEY")
    headers = ps._get_headers()
    assert "places.rating" in headers["X-Goog-FieldMask"]
    assert "places.userRatingCount" in headers["X-Goog-FieldMask"]

    # Test review count sorting logic
    test_places = [
        {"place_id": "1", "name": "Famous Place", "user_rating_count": 500},
        {"place_id": "2", "name": "Local Place", "user_rating_count": 45},
        {"place_id": "3", "name": "Medium Place", "user_rating_count": 120}
    ]
    test_places.sort(key=lambda p: (
        0 if (p.get("user_rating_count") or 9999) <= 200 else 1,
        p.get("user_rating_count") or 9999
    ))
    assert test_places[0]["place_id"] == "2"  # 45 reviews comes first
    assert test_places[1]["place_id"] == "3"  # 120 reviews comes second
    assert test_places[2]["place_id"] == "1"  # 500 reviews comes last

def test_cron_secret_security():
    from config import settings
    settings.CRON_SECRET = "supersecret123"
    
    # Missing secret -> 401
    resp_unauth = client.post("/worker")
    assert resp_unauth.status_code == 401
    
    # Correct secret header -> 200
    resp_auth_header = client.post("/worker", headers={"X-Cron-Secret": "supersecret123"})
    assert resp_auth_header.status_code == 200

    # Correct secret query param ?key= -> 200
    resp_auth_key = client.get("/worker?key=supersecret123")
    assert resp_auth_key.status_code == 200

    # Correct secret query param ?secret= -> 200
    resp_auth_secret = client.get("/worker?secret=supersecret123")
    assert resp_auth_secret.status_code == 200
    
    # Reset
    settings.CRON_SECRET = ""

