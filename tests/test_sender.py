import datetime
import pytz
from fastapi.testclient import TestClient

from main import app
from services.time_filter import is_sender_operating_hours
from services.template_service import TemplateService
from services.smtp_service import SMTPService

client = TestClient(app)

def test_sender_operating_hours():
    rome_tz = pytz.timezone("Europe/Rome")

    # 10:30 AM should be in operating hours
    day_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 10, 30))
    assert is_sender_operating_hours(day_dt) is True

    # 07:00 AM should be in operating hours
    morning_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 7, 0))
    assert is_sender_operating_hours(morning_dt) is True

    # 23:00 PM should NOT be in operating hours
    night_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 23, 0))
    assert is_sender_operating_hours(night_dt) is False

    # 04:00 AM should NOT be in operating hours
    early_night_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 4, 0))
    assert is_sender_operating_hours(early_night_dt) is False

def test_template_rendering():
    template_service = TemplateService()
    lead_data = {
        "place_id": "Ristorante Da Mario",
        "city": "Milano",
        "sector": "Ristorazione",
        "website": "https://damario-milano.it",
        "email": "info@damario-milano.it"
    }

    subject, html_body, plain_text = template_service.render_email(lead_data)

    assert "Milano" in subject
    assert "Ristorante Da Mario" in html_body
    assert "https://damario-milano.it" in html_body
    assert "Ristorazione" in plain_text

def test_smtp_missing_credentials_fails_gracefully():
    # Calling send_email with empty credentials should fail safely without crashing
    smtp_service = SMTPService(sender_email="", app_password="")
    success = smtp_service.send_email("test@example.com", "Subject", "<h1>Test</h1>", "Test")
    assert success is False

def test_send_emails_endpoint():
    response = client.post("/send-emails")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["skipped", "processing"]
