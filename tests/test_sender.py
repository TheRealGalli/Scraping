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

    # The new sender starts at 08:30, independently of the scraper window.
    morning_dt = rome_tz.localize(datetime.datetime(2026, 8, 17, 7, 0))
    assert is_sender_operating_hours(morning_dt) is False

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

    assert "TAP" in subject  # fixed campaign subject
    assert "Google Maps" in subject
    assert "csd-station.it" in html_body  # portal link is always present
    assert "Recensioni Google" in plain_text  # present in plain text body
    assert "whatsapp.com" in html_body  # WhatsApp CTA is always present

def test_smtp_missing_credentials_fails_gracefully():
    # Calling send_email with empty credentials should fail safely without crashing
    smtp_service = SMTPService(sender_email="", app_password="")
    success = smtp_service.send_email("test@example.com", "Subject", "<h1>Test</h1>", "Test")
    assert success is False

def test_send_emails_endpoint():
    response = client.post("/send-emails")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["skipped", "completed"]

def test_sender_skips_support_email(monkeypatch):
    from unittest.mock import MagicMock
    from services.sender_worker import run_email_sender_task

    mock_sheets = MagicMock()
    mock_sheets.get_pending_leads.return_value = [
        {"row_index": 5, "email": "support@example.it", "place_id": "p1", "city": "Roma", "sector": "Ristorazione"}
    ]
    mock_sheets.get_existing_sent_emails.return_value = set()
    
    mock_smtp = MagicMock()
    
    monkeypatch.setattr("services.sender_worker.SheetsService", lambda: mock_sheets)
    monkeypatch.setattr("services.sender_worker.SMTPService", lambda: mock_smtp)
    monkeypatch.setattr("services.sender_worker.is_sender_operating_hours", lambda dt=None: True)
    
    run_email_sender_task()
    
    mock_sheets.update_lead_status.assert_called_once_with(row_index=5, success=False, mark_as="Email Supporto")
    mock_smtp.send_email.assert_not_called()

def test_sender_skips_duplicate_email(monkeypatch):
    from unittest.mock import MagicMock
    from services.sender_worker import run_email_sender_task

    mock_sheets = MagicMock()
    mock_sheets.get_pending_leads.return_value = [
        {"row_index": 6, "email": "info@example.it", "place_id": "p2", "city": "Milano", "sector": "Ristorazione"}
    ]
    mock_sheets.get_existing_sent_emails.return_value = {"info@example.it"}
    
    mock_smtp = MagicMock()
    
    monkeypatch.setattr("services.sender_worker.SheetsService", lambda: mock_sheets)
    monkeypatch.setattr("services.sender_worker.SMTPService", lambda: mock_smtp)
    monkeypatch.setattr("services.sender_worker.is_sender_operating_hours", lambda dt=None: True)
    
    run_email_sender_task()
    
    mock_sheets.update_lead_status.assert_called_once_with(row_index=6, success=False, mark_as="Duplicato Email")
    mock_smtp.send_email.assert_not_called()

