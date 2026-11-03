import datetime
import pytz
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from services.time_filter import is_night_time
from services.email_extractor import EmailExtractor, is_support_email
from services.geo_matrix import generate_search_targets, ITALY_GEO_TREE, SECTORS
from services.web_scraper import WebScraper

client = TestClient(app)

def test_is_support_email():
    assert is_support_email("support@azienda.it") is True
    assert is_support_email("SUPPORT@AZIENDA.COM") is True
    assert is_support_email("tech-support@company.org") is True
    assert is_support_email("info@azienda.it") is False
    assert is_support_email("contatti@studiolegale.it") is False
    assert is_support_email("") is False
    assert is_support_email(None) is False

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
    Ignore bad emails like image.png@2x or fake@example.com or support@studiolegale-esempio.it.
    """
    extracted = extractor.extract_email_with_regex(sample_text)
    assert extracted == "info@studiolegale-esempio.it"

def test_email_extraction_regex_only_support_returns_none():
    extractor = EmailExtractor()
    sample_text = "Assistenza clienti: support@studiolegale-esempio.it oppure helpdesk-support@domain.com."
    extracted = extractor.extract_email_with_regex(sample_text)
    assert extracted is None

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

def test_geo_matrix_alternation():
    targets = list(generate_search_targets(offset=0))[:16]
    # First 8 should all be Milano, alternating all 8 sectors
    milano_sectors = [t[3] for t in targets[:8]]
    assert len(set(milano_sectors)) == 8
    for t in targets[:8]:
        assert t[2] == "Milano"
    
    # Next 8 should be the next city (Milano Navigli), alternating all 8 sectors
    navigli_sectors = [t[3] for t in targets[8:16]]
    assert len(set(navigli_sectors)) == 8
    for t in targets[8:16]:
        assert t[2] == "Milano Navigli"

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

    mailto_html = """
    <div>
        <a href="mailto:support@azienda.it">Supporto Clienti</a>
        <a href="mailto:info@azienda.it?subject=Info">Scrivici</a>
    </div>
    """
    mailto_emails = scraper.extract_mailto_emails(mailto_html)
    assert mailto_emails == ["info@azienda.it"]

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

    # Test review count sorting logic (ascending)
    test_places = [
        {"place_id": "1", "name": "Famous Place", "user_rating_count": 500},
        {"place_id": "2", "name": "Local Place", "user_rating_count": 45},
        {"place_id": "3", "name": "Medium Place", "user_rating_count": 120}
    ]
    test_places.sort(key=lambda p: (
        p.get("user_rating_count") if p.get("user_rating_count") is not None else 999999
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



@pytest.mark.parametrize("cycles", [1, 2, 3])
@pytest.mark.parametrize("offset", [0, 7, 8, 9, 15, 16, 31, 117])
def test_expanded_cursor_preserves_next_city_and_sector(monkeypatch, cycles, offset):
    from config import settings
    from services.geo_matrix import convert_matrix_offset
    monkeypatch.setattr(settings, "CYCLES_PER_CITY", cycles)
    before = next(generate_search_targets(offset, "legacy_v1"))
    after = next(generate_search_targets(convert_matrix_offset(offset, cycles), "expanded_v2"))
    assert before[:4] == after[:4]


def test_new_sectors_have_keywords_and_explicit_targeting():
    from services.campaign_catalog import SECTOR_RULES, DEFAULT_LIMITS
    from services.geo_matrix import sector_names_for_profile
    assert len(sector_names_for_profile("legacy_v1")) == 8
    assert len(sector_names_for_profile("expanded_v2")) == 11
    assert sum(DEFAULT_LIMITS.values()) == 150
    for sector in ("Agenzie Immobiliari", "Architettura e Interior Design", "Eventi e Wedding"):
        assert len(SECTORS[sector]) >= 5
        assert sector in SECTOR_RULES["social"]
        assert sector in SECTOR_RULES["media"]
        assert sector not in SECTOR_RULES["nfc"]
    with pytest.raises(ValueError):
        sector_names_for_profile("unknown")



@pytest.mark.parametrize("source", ["legacy_v1", "expanded_v2", "expanded_v3"])
@pytest.mark.parametrize("cycles", [1, 2])
@pytest.mark.parametrize("offset", [0, 7, 8, 10, 11, 12, 22, 135])
def test_v3_scraper_cursor_preserves_next_task(source, cycles, offset, monkeypatch):
    from services.geo_matrix import convert_matrix_offset, sector_names_for_profile
    from config import settings
    monkeypatch.setattr(settings, "CYCLES_PER_CITY", cycles)
    before = next(generate_search_targets(offset, source))
    converted = convert_matrix_offset(offset, cycles, source, "expanded_v3")
    after = next(generate_search_targets(converted, "expanded_v3"))
    assert before[:4] == after[:4]
    assert len(sector_names_for_profile("expanded_v3")) == 13
    assert converted == convert_matrix_offset(converted, cycles, "expanded_v3", "expanded_v3")


@pytest.mark.parametrize("source", ["legacy_v1", "expanded_v2", "expanded_v3", "expanded_v4"])
@pytest.mark.parametrize("cycles", [1, 2])
@pytest.mark.parametrize("offset", [0, 7, 12, 13, 20, 21, 135])
def test_v4_scraper_cursor_preserves_next_task(source, cycles, offset, monkeypatch):
    from services.geo_matrix import convert_matrix_offset
    from config import settings
    monkeypatch.setattr(settings, "CYCLES_PER_CITY", cycles)
    before = next(generate_search_targets(offset, source))
    converted = convert_matrix_offset(offset, cycles, source, "expanded_v4")
    assert next(generate_search_targets(converted, "expanded_v4"))[:4] == before[:4]
    assert converted == convert_matrix_offset(converted, cycles, "expanded_v4", "expanded_v4")


def test_nfc_media_segments_have_keywords_and_the_first_service_to_propose():
    from services.campaign_catalog import SECTOR_RULES, SEGMENT_RULES_V4
    from services.geo_matrix import sector_names_for_profile
    v3, v4 = sector_names_for_profile("expanded_v3"), sector_names_for_profile("expanded_v4")
    assert len(v3) == 13 and len(v4) == 21 and v4[:13] == v3
    assert set(v4[13:]) == set(SEGMENT_RULES_V4)
    for sector in v4[13:]:
        assert len(SECTORS[sector]) >= 4 and "," not in sector
        targeted = {c for c, sectors in SECTOR_RULES.items() if sector in sectors}
        assert targeted == set(SEGMENT_RULES_V4[sector])
    for sector in ("Tatuaggi e Piercing", "Cantine e Frantoi", "Autoscuole e Scuole di Lingue"):
        assert sector in SECTOR_RULES["nfc"]
    assert "Serramenti e Pergole" not in SECTOR_RULES["nfc"]
    assert SECTOR_RULES["consulenza"][-1] == "Amministratori di Condominio"
    assert all(len(set(sectors)) == len(sectors) for sectors in SECTOR_RULES.values())


def test_places_requests_free_pro_fields_and_parses_them(monkeypatch):
    from services import places_service
    payload = {"places": [{
        "id": "abc", "displayName": {"text": "Inchiostro"}, "websiteUri": "https://ink.it",
        "rating": 4.9, "userRatingCount": 31, "businessStatus": "OPERATIONAL",
        "primaryTypeDisplayName": {"text": "Studio di tatuaggi"},
        "googleMapsUri": "https://maps.google.com/?cid=1", "photos": [{"name": str(i)} for i in range(7)],
    }, {"id": "bare", "displayName": {"text": "Senza foto"}}]}
    sent = {}

    class Client:
        def __init__(self, timeout): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, json, headers):
            sent["mask"] = headers["X-Goog-FieldMask"]
            return MagicMock(status_code=200, json=lambda: payload)

    monkeypatch.setattr(places_service.httpx, "Client", Client)
    results = places_service.PlacesService(api_key="TEST_KEY").search_places("tatuatore Milano")
    for field in ("businessStatus", "primaryTypeDisplayName", "googleMapsUri", "photos", "websiteUri"):
        assert "places." + field in sent["mask"].split(",")
    assert results[0]["google_category"] == "Studio di tatuaggi" and results[0]["google_photos"] == 7
    assert results[0]["business_status"] == "OPERATIONAL"
    assert results[1]["google_photos"] == 0 and results[1]["google_category"] == ""


def test_presentation_signals_read_only_the_site_showcase():
    scraper = WebScraper()
    html = """
    <a href="https://www.instagram.com/inchiostro">I nostri lavori</a>
    <a href="https://facebook.com/inchiostro">Facebook</a>
    <a href="mailto:info@ink.it">Galleria</a>
    <img src="a.jpg"><img src="b.jpg">
    """
    signals = scraper.presentation_signals(html)
    assert signals == {"fetched": True, "social": ["instagram", "facebook"], "showcase": False,
                       "video": False, "images": 2}
    rich = scraper.presentation_signals('<a href="/portfolio">Tatuaggi</a><iframe src="https://www.youtube.com/embed/x"></iframe>')
    assert rich["showcase"] and rich["video"] and not rich["social"]
    assert scraper.presentation_signals("")["fetched"] is False


@pytest.mark.parametrize("website,signals,photos,site,hook", [
    ("", None, 10, "nessun sito", "foto da valorizzare · senza sito"),
    ("", None, 2, "nessun sito", "senza sito"),
    ("https://a.it", {"fetched": False}, 10, "sito non raggiungibile", ""),
    ("https://a.it", None, 10, "sito non analizzato", ""),
    ("https://a.it", {"fetched": True, "social": [], "showcase": True, "video": False, "images": 30},
     10, "galleria · senza video · 30 immagini", ""),
    ("https://a.it", {"fetched": True, "social": ["tiktok"], "showcase": False, "video": False, "images": 1},
     5, "social: tiktok · senza galleria · senza video · 1 immagine", "foto da valorizzare"),
])
def test_signals_are_readable_facts(website, signals, photos, site, hook):
    from services.lead_signals import describe_site, hooks
    assert describe_site(website, signals) == site
    assert hooks(website, signals, photos) == hook
