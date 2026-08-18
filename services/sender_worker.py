import logging
import random
import time
from typing import List, Dict, Any

from config import settings
from services.time_filter import is_sender_operating_hours, get_rome_time
from services.sheets_service import SheetsService
from services.template_service import TemplateService
from services.smtp_service import SMTPService

logger = logging.getLogger(__name__)

def run_email_sender_task():
    """
    Background worker process executed asynchronously on Cloud Run /send-emails endpoint call.
    Reads pending leads ('Da inviare'), sends emails via Google Workspace SMTP (max 50/day),
    applies dynamic 15-20 min delays between sends, and updates Google Sheet status.
    """
    logger.info("Starting background Email Sender worker process...")

    # 1. Daytime operating window check (06:00 to 22:00 Europe/Rome)
    if not is_sender_operating_hours():
        logger.info("Outside sender operating hours (06:00-22:00 Europe/Rome). Terminating email sender task.")
        return

    # Initialize services
    sheets_service = SheetsService()
    template_service = TemplateService()
    smtp_service = SMTPService()

    # 2. Fetch pending leads (default 1 lead per run for anti-spam rate limiting via Cloud Scheduler)
    max_emails_this_run = getattr(settings, "EMAILS_PER_BATCH", 1)
    pending_leads: List[Dict[str, Any]] = sheets_service.get_pending_leads(limit=max_emails_this_run)

    if not pending_leads:
        logger.info("No pending leads ('Da inviare') found in Google Sheet. Execution completed.")
        return

    logger.info(f"Loaded {len(pending_leads)} pending lead(s) for email dispatch (Batch size: {max_emails_this_run}).")

    sent_count = 0

    for idx, lead in enumerate(pending_leads):
        # Double check operating hours before each send
        if not is_sender_operating_hours():
            logger.info("Reached end of sender operating hours window (22:00 Europe/Rome). Stopping batch.")
            break

        if sent_count >= settings.MAX_DAILY_EMAILS:
            logger.info(f"Reached maximum daily quota ({settings.MAX_DAILY_EMAILS} emails). Stopping batch.")
            break

        row_index = lead.get("row_index")
        to_email = lead.get("email")

        logger.info(f"Processing lead #{idx+1}/{len(pending_leads)}: '{to_email}' (Sheet row {row_index})...")

        # Render email content
        subject, html_body, plain_text_body = template_service.render_email(lead)

        # Apply random pre-send jitter delay to randomize exact send timestamp
        if settings.PRE_SEND_JITTER_MAX_SEC > 0:
            jitter_sec = random.uniform(settings.PRE_SEND_JITTER_MIN_SEC, settings.PRE_SEND_JITTER_MAX_SEC)
            logger.info(f"Random pre-send jitter: pausing for {jitter_sec:.1f}s before sending email...")
            time.sleep(jitter_sec)

        # Send via SMTP
        success = smtp_service.send_email(to_email, subject, html_body, plain_text_body)

        # Record timestamp in Europe/Rome format YYYY-MM-DD HH:MM
        current_time_str = get_rome_time().strftime("%Y-%m-%d %H:%M")

        # Update status in Google Sheets
        sheets_service.update_lead_status(row_index=row_index, success=success, timestamp_str=current_time_str)

        if success:
            sent_count += 1

        # Apply dynamic anti-spam delay between sends (15-20 minutes, unless last lead in batch)
        if idx < len(pending_leads) - 1 and sent_count < settings.MAX_DAILY_EMAILS:
            delay_sec = random.uniform(settings.SEND_DELAY_MIN_SEC, settings.SEND_DELAY_MAX_SEC)
            delay_min = delay_sec / 60.0
            logger.info(f"Anti-spam delay: pausing for {delay_min:.1f} minutes ({delay_sec:.0f}s) before next send...")
            time.sleep(delay_sec)

    logger.info(f"Email Sender worker completed. Sent {sent_count} emails in this batch.")
